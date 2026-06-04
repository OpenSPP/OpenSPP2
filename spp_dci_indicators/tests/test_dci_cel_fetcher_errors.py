# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Error-branch and edge-case tests for dci_cel_fetcher.py.

Covers lines not exercised by test_dci_cel_fetcher.py:
- fetch_values: handler returns None (value skipped from results)
- fetch_values: no data source on provider -> early return {}
- _get_partner_identifier: non-priority ID type falls back to first reg_id;
  fallback returns None when the first reg_id has no value
- _materialize_method_variable: (params, None) pair is skipped;
  no data source -> return 0
- _compute_method_values: unknown event arg hits else-continue
- cron_sync_all_registrants: early-return when no variables; loop body with registrants
- sync_for_partners: non-method-accessor variable (precompute_variable path)

Note: _compute_method_values line 177 ("return []") and the else-continue at line 174
are dead code: the former is guarded by a DCI_METHOD_ACCESSORS KeyError before it can
be reached; the latter requires an arg not in the ["birth","death"] list that is part of
the module constant. They are documented here but cannot be exercised without patching
module state (see test_unknown_event_arg_is_skipped which patches DCI_METHOD_ACCESSORS).
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

CHECK_DEATH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.check_death"
VERIFY_BIRTH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.verify_birth"
GET_STATUS = "odoo.addons.spp_dci_client_dr.services.dr_service.DRService.get_disability_status"


@tagged("post_install", "-at_install")
class TestDCICelFetcherErrors(TransactionCase):
    """Edge cases and error branches for DCICelFetcher.fetch_values."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]

        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "CRVS Edge Cases",
                "code": "crvs_edge_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {
                "name": "CRVS Edge Provider",
                "code": "crvs_edge_prov",
                "dci_data_source_id": cls.dci_source.id,
            }
        )

        # Standard priority-match ID type (NATIONAL_ID).
        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")

        cls.partner = cls.env["res.partner"].create(
            {"name": "zz_test_edge CRVS Person", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-EDGE-1"}
        )

    def test_fetch_values_handler_returns_none_skips_subject(self):
        """When a handler returns None, the subject must not appear in results."""
        var = self.env["spp.cel.variable"].create(
            {
                "name": "zz_test_edge.handler_none",
                "label": "Handler None Test",
                "cel_accessor": "dr.dci.has_disability",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": self.provider.id,
                "cache_strategy": "ttl",
            }
        )
        # Patch the handler so it returns None for this subject.
        with patch.object(
            type(self.Fetcher),
            "_dr_has_disability",
            return_value=None,
        ):
            result = self.Fetcher.fetch_values(var, [self.partner.id])
        # None value must not appear in the result dict.
        self.assertNotIn(self.partner.id, result)

    def test_fetch_values_no_data_source_returns_empty(self):
        """fetch_values short-circuits when provider has no linked data source."""
        provider_no_ds = self.env["spp.data.provider"].create(
            {"name": "No DS Provider Edge", "code": "no_ds_edge_prov"}
        )
        var_no_ds = self.env["spp.cel.variable"].create(
            {
                "name": "zz_test_edge.no_ds_var",
                "label": "No DS var",
                "cel_accessor": "dr.dci.assessed",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": provider_no_ds.id,
                "cache_strategy": "ttl",
            }
        )
        result = self.Fetcher.fetch_values(var_no_ds, [self.partner.id])
        self.assertEqual(result, {})


@tagged("post_install", "-at_install")
class TestGetPartnerIdentifierFallback(TransactionCase):
    """Cover the 'fallback to first reg_id' and 'None when empty' branches."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]
        # Use a non-priority code type for the fallback test.
        # "passport" has code='passport', which is NOT in _IDENTIFIER_PRIORITY.
        cls.passport_type = cls.env.ref("spp_vocabulary.code_id_type_passport")

    def test_fallback_to_first_reg_id_when_no_priority_match(self):
        """A partner with only a non-priority ID type uses the first reg_id."""
        partner = self.env["res.partner"].create(
            {"name": "zz_edge_fallback_partner", "is_registrant": True, "is_group": False}
        )
        self.env["spp.registry.id"].create(
            {"partner_id": partner.id, "id_type_id": self.passport_type.id, "value": "PASS-001"}
        )

        ident = self.Fetcher._get_partner_identifier(partner)
        self.assertIsNotNone(ident)
        # Falls back to the first (and only) reg_id.
        self.assertEqual(ident, (self.passport_type.code, "PASS-001"))

    def test_fallback_returns_none_when_first_reg_id_has_no_value(self):
        """When the only reg_id has an empty value, the fallback returns None."""
        partner = self.env["res.partner"].create(
            {"name": "zz_edge_empty_partner", "is_registrant": True, "is_group": False}
        )
        # Create a reg_id with empty value.
        self.env["spp.registry.id"].create(
            {"partner_id": partner.id, "id_type_id": self.passport_type.id, "value": False}
        )

        ident = self.Fetcher._get_partner_identifier(partner)
        self.assertIsNone(ident)


@tagged("post_install", "-at_install")
class TestMaterializeMethodVariable(TransactionCase):
    """Cover branches in _materialize_method_variable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]

        cls.dr_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "DR Mat Edge",
                "code": "dr_mat_edge_t",
                "base_url": "https://dr.example.org/api",
                "registry_type": RegistryType.DISABILITY_REGISTRY.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.dr_provider = cls.env["spp.data.provider"].create(
            {
                "name": "DR Mat Edge Prov",
                "code": "dr_mat_edge_prov",
                "dci_data_source_id": cls.dr_source.id,
            }
        )
        cls.sev_var = cls.env.ref("spp_dci_indicators.var_dci_dr_severity")
        cls.sev_var.external_provider_id = cls.dr_provider

        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create(
            {"name": "zz_test_mat_edge Person", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-MAT-EDGE-1"}
        )

    def test_none_value_pairs_are_skipped(self):
        """(params, None) pairs returned by _compute_method_values are not stored."""
        with patch.object(
            type(self.Fetcher),
            "_compute_method_values",
            return_value=[({"arg": "Vision"}, None), ({"arg": "Hearing"}, 2)],
        ):
            count = self.Fetcher._materialize_method_variable(self.sev_var, [self.partner.id])
        # Only the non-None pair (Hearing) should be stored.
        self.assertEqual(count, 1)

    def test_no_data_source_returns_zero(self):
        """_materialize_method_variable returns 0 immediately when no data source is set."""
        provider_no_ds = self.env["spp.data.provider"].create({"name": "No DS Mat Prov", "code": "no_ds_mat_prov"})
        # Temporarily point the variable at a provider without a data source.
        original_provider = self.sev_var.external_provider_id
        self.sev_var.external_provider_id = provider_no_ds
        try:
            count = self.Fetcher._materialize_method_variable(self.sev_var, [self.partner.id])
        finally:
            self.sev_var.external_provider_id = original_provider
        self.assertEqual(count, 0)


@tagged("post_install", "-at_install")
class TestComputeMethodValuesEdge(TransactionCase):
    """Cover the 'else: continue' branch in _compute_method_values.

    The 'return []' at the end (line 177) is unreachable in practice: calling
    _compute_method_values with an accessor not in DCI_METHOD_ACCESSORS causes
    a KeyError on line 161 before execution can reach line 177. This is dead
    code; it is reported but not tested here.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]

        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "CRVS Compute Edge",
                "code": "crvs_compute_edge_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )

    def test_unknown_event_arg_is_skipped(self):
        """An event arg that is not 'birth' or 'death' hits else-continue and is omitted.

        We temporarily extend the args list with an unknown event to exercise the
        defensive else-branch inside _compute_method_values.
        """
        from odoo.addons.spp_dci_indicators.models.dci_cel_fetcher import DCI_METHOD_ACCESSORS

        original_args = list(DCI_METHOD_ACCESSORS["crvs.dci.has_event"]["args"])
        DCI_METHOD_ACCESSORS["crvs.dci.has_event"]["args"] = ["birth", "unknown_event", "death"]
        try:
            with patch(VERIFY_BIRTH, return_value={"x": 1}), patch(CHECK_DEATH, return_value=False):
                partner = self.env["res.partner"].browse([])
                pairs = self.Fetcher._compute_method_values(
                    "crvs.dci.has_event",
                    self.dci_source,
                    partner,
                    "NID",
                    "VAL-EDGE",
                )
        finally:
            DCI_METHOD_ACCESSORS["crvs.dci.has_event"]["args"] = original_args

        arg_keys = [p[0]["arg"] for p in pairs]
        self.assertIn("birth", arg_keys)
        self.assertIn("death", arg_keys)
        self.assertNotIn("unknown_event", arg_keys)


@tagged("post_install", "-at_install")
class TestCronSyncAllRegistrants(TransactionCase):
    """Cover cron_sync_all_registrants: early-return and loop body."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]

        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "CRVS Cron Edge",
                "code": "crvs_cron_edge_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {
                "name": "CRVS Cron Prov",
                "code": "crvs_cron_edge_prov",
                "dci_data_source_id": cls.dci_source.id,
            }
        )
        cls.var_is_alive = cls.env["spp.cel.variable"].create(
            {
                "name": "zz_cron_edge.crvs.is_alive",
                "label": "DCI: Is Alive (cron edge)",
                "cel_accessor": "crvs.dci.is_alive",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": cls.provider.id,
                "cache_strategy": "ttl",
            }
        )

        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create(
            {"name": "zz_cron_edge Person", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-CRON-EDGE-1"}
        )

    def test_cron_returns_early_when_no_dci_backed_variables(self):
        """cron_sync_all_registrants must not touch partners when there are no variables."""
        empty = self.env["spp.cel.variable"]
        with patch.object(type(self.Fetcher), "_dci_backed_variables", return_value=empty):
            with patch.object(type(self.Fetcher), "sync_for_partners") as mock_sync:
                self.Fetcher.cron_sync_all_registrants()
        mock_sync.assert_not_called()

    def test_cron_syncs_registrants_in_loop(self):
        """The cron loop body runs when at least one registrant and variable exist."""
        with patch(CHECK_DEATH, return_value=False):
            # Use a very large batch_size so the loop runs exactly once.
            self.Fetcher.cron_sync_all_registrants(batch_size=10000)
        cached = self.env["spp.data.value"].search(
            [("variable_name", "=", "crvs.dci.is_alive"), ("subject_id", "=", self.partner.id)]
        )
        self.assertTrue(cached)


@tagged("post_install", "-at_install")
class TestSyncForPartnersNonMethodAccessor(TransactionCase):
    """Cover the precompute_variable branch in sync_for_partners (non-method accessor)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]

        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "CRVS Precompute Edge",
                "code": "crvs_precomp_edge_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {
                "name": "CRVS Precompute Prov",
                "code": "crvs_precomp_edge_prov",
                "dci_data_source_id": cls.dci_source.id,
            }
        )
        # crvs.dci.is_alive is NOT in DCI_METHOD_ACCESSORS, so it goes through
        # the precompute_variable path in sync_for_partners.
        cls.var_is_alive = cls.env["spp.cel.variable"].create(
            {
                "name": "zz_precomp_edge.crvs.is_alive",
                "label": "DCI: Is Alive (precompute edge)",
                "cel_accessor": "crvs.dci.is_alive",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": cls.provider.id,
                "cache_strategy": "ttl",
            }
        )

        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create(
            {"name": "zz_precomp_edge Person", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-PRECOMP-1"}
        )

    def test_non_method_accessor_calls_precompute_variable(self):
        """sync_for_partners calls mgr.precompute_variable for non-method accessors."""
        mgr = self.env["spp.data.cache.manager"]
        with patch.object(
            type(mgr),
            "precompute_variable",
            return_value={"cached": 1},
        ) as mock_precompute:
            count = self.Fetcher.sync_for_partners(
                [self.partner.id],
                variables=self.var_is_alive,
            )
        mock_precompute.assert_called_once_with(self.var_is_alive.name, [self.partner.id])
        self.assertEqual(count, 1)

    def test_non_method_accessor_precompute_returns_non_dict(self):
        """If precompute_variable returns a non-dict value, count stays at 0."""
        mgr = self.env["spp.data.cache.manager"]
        with patch.object(
            type(mgr),
            "precompute_variable",
            return_value=None,
        ):
            count = self.Fetcher.sync_for_partners(
                [self.partner.id],
                variables=self.var_is_alive,
            )
        self.assertEqual(count, 0)
