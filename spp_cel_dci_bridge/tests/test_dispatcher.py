from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_cel_dci_bridge.exceptions import DCIConfigurationError


@tagged("post_install", "-at_install")
class TestDispatcherRouting(TransactionCase):
    """Verify the dispatcher routes by registry_type and tolerates missing setup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Provider = cls.env["spp.data.provider"]
        cls.Variable = cls.env["spp.cel.variable"]
        cls.DCISource = cls.env["spp.dci.data.source"]
        cls.dispatcher = cls.env["spp.cel.dci.dispatcher"]

    def _make_variable(self, registry_type, code_suffix):
        source = self.DCISource.create(
            {
                "name": f"Source {code_suffix}",
                "code": f"src_{code_suffix}",
                "registry_type": registry_type,
                "base_url": "https://example.invalid/api",
                "auth_type": "none",
                "our_sender_id": "test.openspp.example.org",
            }
        )
        provider = self.Provider.create(
            {
                "name": f"Provider {code_suffix}",
                "code": f"prov_{code_suffix}",
                "dci_data_source_id": source.id,
            }
        )
        var = self.Variable.create(
            {
                "name": f"var_{code_suffix}",
                "cel_accessor": f"var_{code_suffix}",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": provider.id,
                "dci_attribute_path": "x",
            }
        )
        return var, source, provider

    def test_empty_subjects_returns_empty_dict(self):
        var, _, _ = self._make_variable("DR", "empty")
        self.assertEqual(self.dispatcher.fetch_values_for_variable(var, [], "current"), {})

    def test_non_dci_provider_returns_empty(self):
        provider = self.Provider.create({"name": "Plain", "code": "plain_p"})
        var = self.Variable.create(
            {
                "name": "var_plain",
                "cel_accessor": "var_plain",
                "source_type": "external",
                "value_type": "number",
                "external_provider_id": provider.id,
            }
        )
        self.assertEqual(self.dispatcher.fetch_values_for_variable(var, [1], "current"), {})

    def test_inactive_source_returns_empty(self):
        var, source, _ = self._make_variable("DR", "inactive")
        source.active = False
        self.assertEqual(self.dispatcher.fetch_values_for_variable(var, [1], "current"), {})

    def test_unknown_registry_type_raises_configuration_error(self):
        var, source, _ = self._make_variable("DR", "unknown")
        # Bypass the registry_type constraint by writing raw. Selection is
        # validated at write time, not at the DB level.
        self.env.cr.execute(
            "UPDATE spp_dci_data_source SET registry_type = 'XX' WHERE id = %s",
            (source.id,),
        )
        source.invalidate_recordset()
        with self.assertRaises(DCIConfigurationError):
            self.dispatcher.fetch_values_for_variable(var, [1], "current")

    def test_sr_handler_raises_configuration_error(self):
        """Social Registry handler is a v1 stub — must surface, not silently
        return empty (which would cause silent eligibility failure)."""
        var, _, _ = self._make_variable("ns:org:RegistryType:Social", "sr_stub")
        with self.assertRaises(DCIConfigurationError):
            self.dispatcher.fetch_values_for_variable(var, [1], "current")

    def test_fr_handler_raises_configuration_error(self):
        """Functional Registry handler is a v1 stub — must surface."""
        var, _, _ = self._make_variable("ns:org:RegistryType:FR", "fr_stub")
        with self.assertRaises(DCIConfigurationError):
            self.dispatcher.fetch_values_for_variable(var, [1], "current")

    def test_dci_configuration_error_is_user_error(self):
        """DCIConfigurationError must inherit UserError so existing
        catch-blocks expecting UserError continue to handle it."""
        self.assertTrue(issubclass(DCIConfigurationError, UserError))

    def test_dr_handler_returns_empty_skeleton(self):
        var, _, _ = self._make_variable("DR", "dr_skel")
        result = self.dispatcher.fetch_values_for_variable(var, [1], "current")
        self.assertEqual(result, {})

    def test_extract_by_path_returns_top_level(self):
        result = self.dispatcher._extract_by_path({"has_disability": True}, "has_disability")
        self.assertIs(result, True)

    def test_extract_by_path_returns_nested(self):
        payload = {"functional_scores": {"cognition": 3}}
        result = self.dispatcher._extract_by_path(payload, "functional_scores.cognition")
        self.assertEqual(result, 3)

    def test_extract_by_path_missing_segment_returns_none(self):
        result = self.dispatcher._extract_by_path({"a": {"b": 1}}, "a.c")
        self.assertIsNone(result)

    def test_extract_by_path_none_payload(self):
        self.assertIsNone(self.dispatcher._extract_by_path(None, "x"))

    def test_extract_by_path_non_dict_segment(self):
        # Cannot descend into a non-dict value
        result = self.dispatcher._extract_by_path({"a": "not-a-dict"}, "a.b")
        self.assertIsNone(result)
