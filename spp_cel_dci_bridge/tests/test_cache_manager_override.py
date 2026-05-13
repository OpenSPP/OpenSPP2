from unittest.mock import MagicMock, patch

from odoo.tests.common import tagged

from .common import BridgeTestBase, make_dr_search_response


@tagged("post_install", "-at_install")
class TestCacheManagerOverride(BridgeTestBase):
    """Verify _compute_variable_values routes DCI-backed externals through dispatcher."""

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dci_backed_external_routes_to_dispatcher(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(has_disability=True)
        mock_client_class.return_value = mock_client

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr._compute_variable_values(
            self.variable,
            [self.partner_a.id],
            "current",
            program_id=None,
        )

        self.assertEqual(result, {self.partner_a.id: True})

    def test_non_dci_external_falls_back_to_super(self):
        """A bare 'external' variable without a DCI provider goes through
        the parent implementation, which returns {} and logs a warning."""
        plain_provider = self.Provider.create({"name": "Plain", "code": "plain_super"})
        var = self.Variable.create(
            {
                "name": "var_no_dci",
                "cel_accessor": "var_no_dci",
                "source_type": "external",
                "value_type": "number",
                "external_provider_id": plain_provider.id,
                "cache_strategy": "ttl",
                "cache_ttl_seconds": 300,
            }
        )

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr._compute_variable_values(var, [self.partner_a.id], "current", program_id=None)

        # Parent returns {} for external source_type without our override
        self.assertEqual(result, {})

    def test_field_source_type_unaffected(self):
        """source_type='field' must still route through the parent."""
        field_var = self.Variable.create(
            {
                "name": "var_field",
                "cel_accessor": "var_field",
                "source_type": "field",
                "value_type": "string",
                "source_model": "res.partner",
                "source_field": "name",
                "cache_strategy": "ttl",
                "cache_ttl_seconds": 300,
            }
        )

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr._compute_variable_values(field_var, [self.partner_a.id], "current", program_id=None)

        # Parent _compute_field_values reads the name field
        self.assertEqual(result, {self.partner_a.id: self.partner_a.name})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_precompute_writes_to_spp_data_value(self, mock_client_class):
        """End-to-end through precompute_variable: cache row appears."""
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(has_disability=True)
        mock_client_class.return_value = mock_client

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr.precompute_variable(
            self.variable.name,
            [self.partner_a.id],
            period_key="current",
        )

        self.assertTrue(result["success"], result.get("error_message"))
        self.assertEqual(result["computed"], 1)
        self.assertEqual(result["cached"], 1)

        DataValue = self.env["spp.data.value"]
        rows = DataValue.search(
            [
                ("variable_name", "=", self.variable.name),
                ("subject_id", "=", self.partner_a.id),
                ("period_key", "=", "current"),
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.value_json, {"value": True})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dispatcher_exception_yields_null_not_raise(self, mock_client_class):
        """An unhandled exception inside the dispatcher must not crash the
        cache manager. Under the default null policy, the queried subject
        appears in the result with an explicit None value so the cache is
        complete and CEL evaluation can fall through to false."""
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = RuntimeError("boom")
        mock_client_class.return_value = mock_client

        cache_mgr = self.env["spp.data.cache.manager"]
        # Should not raise
        result = cache_mgr._compute_variable_values(self.variable, [self.partner_a.id], "current", program_id=None)

        # Per-subject error is swallowed by the handler; cache manager fills
        # the missing subject with explicit None.
        self.assertEqual(result, {self.partner_a.id: None})
