from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci_openspp_dr import post_init_hook


@tagged("post_install", "-at_install")
class TestOpenSPPDRPresetInstall(TransactionCase):
    """Smoke test: the preset records exist after install and are linked correctly."""

    def test_service_priority_first_is_uin(self):
        """The SP-side service walks the partner's reg_ids by
        IDENTIFIER_PRIORITY; UIN must be the first entry so the canonical
        SPDCI identifier wins over national-registry-specific codes."""
        from odoo.addons.spp_dci_openspp_dr.services.openspp_dr_service import (
            IDENTIFIER_PRIORITY,
        )

        self.assertEqual(IDENTIFIER_PRIORITY[0], "UIN")

    def test_data_source_present(self):
        source = self.env.ref("spp_dci_openspp_dr.openspp_dr_source")
        self.assertEqual(source.code, "openspp_dr")
        self.assertEqual(source.registry_type, "DR")
        self.assertEqual(source.vendor, "openspp")
        self.assertEqual(source.search_endpoint, "/dci/disability/registry/sync/search")
        self.assertTrue(source.active)

    def test_provider_links_to_data_source(self):
        provider = self.env.ref("spp_dci_openspp_dr.openspp_dr_provider")
        source = self.env.ref("spp_dci_openspp_dr.openspp_dr_source")
        self.assertEqual(provider.code, "openspp_dr")
        self.assertEqual(provider.dci_data_source_id, source)
        self.assertTrue(provider.is_dci_backed)

    def test_cel_variable_rewired_to_dci_provider(self):
        variable = self.env.ref("spp_studio.var_has_disability")
        provider = self.env.ref("spp_dci_openspp_dr.openspp_dr_provider")
        self.assertEqual(variable.name, "has_disability")
        self.assertEqual(variable.cel_accessor, "has_disability")
        self.assertEqual(variable.source_type, "external")
        self.assertEqual(variable.value_type, "boolean")
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(variable.dci_attribute_path, "has_disability")
        self.assertEqual(variable.cache_strategy, "ttl")
        self.assertEqual(variable.cache_ttl_seconds, 300)
        self.assertEqual(variable.external_failure_policy, "null")
        self.assertFalse(variable.source_field)
        self.assertEqual(variable.state, "active")
        self.assertTrue(variable.active)

    def test_cel_accessor_is_semantic_not_vendor_named(self):
        """ADR-023 §1a: CEL accessors must be vendor-neutral."""
        variable = self.env.ref("spp_studio.var_has_disability")
        for forbidden in ("openspp_dr", "openspp-dr", "vendor"):
            self.assertNotIn(forbidden, variable.cel_accessor.lower())
            self.assertNotIn(forbidden, variable.name.lower())

    def test_post_init_hook_re_asserts_after_studio_reset(self):
        """Simulate `-u spp_studio` resetting var_has_disability back to
        its original source_type='field' state, then run our hook. The
        hook must restore the DCI binding."""
        variable = self.env.ref("spp_studio.var_has_disability")
        provider = self.env.ref("spp_dci_openspp_dr.openspp_dr_provider")

        variable.write(
            {
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "is_person_with_disability",
                "external_provider_id": False,
                "dci_attribute_path": False,
                "cache_strategy": "none",
                "external_failure_policy": "null",
                "state": "draft",
            }
        )

        post_init_hook(self.env)

        variable.invalidate_recordset()
        self.assertEqual(variable.source_type, "external")
        self.assertFalse(variable.source_field)
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(variable.dci_attribute_path, "has_disability")
        self.assertEqual(variable.state, "active")
        self.assertTrue(variable.active)

    def test_post_init_hook_handles_missing_variable_gracefully(self):
        with patch("odoo.api.Environment.ref") as mock_ref:
            mock_ref.return_value = self.env["spp.cel.variable"].browse()
            post_init_hook(self.env)

    def test_post_init_hook_handles_missing_provider_gracefully(self):
        original_ref = self.env.ref

        def selective_ref(xmlid, *args, **kwargs):
            if xmlid == "spp_dci_openspp_dr.openspp_dr_provider":
                return self.env["spp.data.provider"].browse()
            return original_ref(xmlid, *args, **kwargs)

        with patch.object(type(self.env), "ref", side_effect=selective_ref):
            post_init_hook(self.env)

    def test_post_init_hook_is_idempotent(self):
        variable = self.env.ref("spp_studio.var_has_disability")
        before = {
            "source_type": variable.source_type,
            "external_provider_id": variable.external_provider_id.id,
            "dci_attribute_path": variable.dci_attribute_path,
        }
        post_init_hook(self.env)
        variable.invalidate_recordset()
        after = {
            "source_type": variable.source_type,
            "external_provider_id": variable.external_provider_id.id,
            "dci_attribute_path": variable.dci_attribute_path,
        }
        self.assertEqual(before, after)
