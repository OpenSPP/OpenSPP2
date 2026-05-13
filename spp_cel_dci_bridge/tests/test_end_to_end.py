"""End-to-end test of the demo flow.

Wires the full chain:
  precompute_cached_variables() -> _compute_variable_values() ->
  _handler_dr() -> mocked DCIClient -> spp.data.value rows ->
  CEL compile_expression() resolves `has_disability_test == true` to a
  SQL filter over spp_data_value -> domain returns the right partners.

If this test passes, the demo flow works.
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import tagged

from .common import BridgeTestBase, make_dr_search_response


@tagged("post_install", "-at_install")
class TestEndToEndEligibility(BridgeTestBase):
    """The demo flow under test: DCI fetch -> cache -> CEL filter."""

    def _patch_dr_responses(self, mock_client_class, responses_by_uin):
        """Configure the mocked DCIClient to vary response by identifier value."""
        mock_client = MagicMock()

        def search_by_id(identifier_type, identifier_value, **_kwargs):
            return responses_by_uin.get(
                identifier_value,
                {"message": {"search_response": []}},
            )

        mock_client.search_by_id.side_effect = search_by_id
        mock_client_class.return_value = mock_client
        return mock_client

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_demo_flow_precompute_then_cel_filter(self, mock_client_class):
        """Pre-fetch via DCI, then verify CEL filter selects the right subjects."""
        # Mock OpenG2P-shaped DR responses
        self._patch_dr_responses(
            mock_client_class,
            {
                "UIN-BRIDGE-A": make_dr_search_response(has_disability=True),
                "UIN-BRIDGE-B": make_dr_search_response(has_disability=False),
            },
        )

        # Phase 1: pre-compute. This is what cycle_manager_base does before
        # eligibility checks, via _precompute_cycle_cached_variables().
        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr.precompute_cached_variables(
            [self.partner_a.id, self.partner_b.id],
            period_key="current",
            variable_names=[self.variable.name],
        )

        self.assertTrue(result["success"], result.get("error_message"))
        self.assertEqual(result["total_computed"], 2)

        # Phase 2: verify cache rows exist
        DataValue = self.env["spp.data.value"]
        rows = DataValue.search(
            [
                ("variable_name", "=", self.variable.name),
                ("subject_id", "in", [self.partner_a.id, self.partner_b.id]),
            ]
        )
        self.assertEqual(len(rows), 2)
        by_subject = {r.subject_id: r.value_json["value"] for r in rows}
        self.assertEqual(by_subject[self.partner_a.id], True)
        self.assertEqual(by_subject[self.partner_b.id], False)

        # Phase 3: compile the CEL eligibility rule. The variable resolver
        # expands `has_disability_test == true` to `metric('has_disability_test', me) == true`,
        # the translator emits a MetricCompare plan, and the executor uses the
        # SQL fast path against spp_data_value.
        service = self.env["spp.cel.service"]
        compiled = service.compile_expression(
            f"{self.variable.cel_accessor} == true",
            profile="registry_individuals",
            base_domain=[
                ("id", "in", [self.partner_a.id, self.partner_b.id]),
            ],
            limit=0,
        )

        self.assertTrue(compiled["valid"], compiled.get("error"))
        # Exactly one matching partner (partner_a)
        self.assertEqual(compiled["count"], 1)

        # Phase 4: verify audit rows reflect the two fetches
        Audit = self.env["spp.dci.fetch.audit"]
        audits = Audit.search([("variable_name", "=", self.variable.name)])
        self.assertEqual(len(audits), 2)
        self.assertEqual({a.result for a in audits}, {"ok"})
        self.assertEqual(
            {a.subject_id for a in audits},
            {self.partner_a.id, self.partner_b.id},
        )

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_demo_flow_with_partial_dci_results(self, mock_client_class):
        """Partner A has a DR record, B doesn't. CEL must still filter correctly."""
        self._patch_dr_responses(
            mock_client_class,
            {
                "UIN-BRIDGE-A": make_dr_search_response(has_disability=True),
                # B is omitted → empty response → not_found
            },
        )

        cache_mgr = self.env["spp.data.cache.manager"]
        cache_mgr.precompute_cached_variables(
            [self.partner_a.id, self.partner_b.id],
            period_key="current",
            variable_names=[self.variable.name],
        )

        # Both subjects have a cache row — A holds the live True, B holds the
        # explicit None recorded when the DR returned no data. Keeping the
        # cache complete across the cohort is what lets the CEL executor use
        # the SQL fast path instead of falling back to Python evaluation.
        DataValue = self.env["spp.data.value"]
        rows = DataValue.search(
            [("variable_name", "=", self.variable.name)],
            order="subject_id",
        )
        self.assertEqual(len(rows), 2)
        by_subject = {r.subject_id: r.value_json["value"] for r in rows}
        self.assertEqual(by_subject[self.partner_a.id], True)
        self.assertIsNone(by_subject[self.partner_b.id])

        # CEL filter: A is included, B has no cache row and is excluded
        service = self.env["spp.cel.service"]
        compiled = service.compile_expression(
            f"{self.variable.cel_accessor} == true",
            profile="registry_individuals",
            base_domain=[
                ("id", "in", [self.partner_a.id, self.partner_b.id]),
            ],
            limit=0,
        )

        self.assertTrue(compiled["valid"], compiled.get("error"))
        self.assertEqual(compiled["count"], 1)

        # Audit: A=ok, B=not_found
        Audit = self.env["spp.dci.fetch.audit"]
        audits = Audit.search([("variable_name", "=", self.variable.name)])
        by_subject = {a.subject_id: a.result for a in audits}
        self.assertEqual(by_subject[self.partner_a.id], "ok")
        self.assertEqual(by_subject[self.partner_b.id], "not_found")
