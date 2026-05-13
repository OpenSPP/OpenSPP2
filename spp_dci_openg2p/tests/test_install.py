from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci_openg2p import post_init_hook


@tagged("post_install", "-at_install")
class TestOpenG2PPresetInstall(TransactionCase):
    """Smoke test: the three preset records exist after install and are linked correctly."""

    def test_data_source_present(self):
        source = self.env.ref("spp_dci_openg2p.openg2p_dr_source")
        self.assertEqual(source.code, "openg2p_dr")
        self.assertEqual(source.registry_type, "DR")
        self.assertEqual(source.auth_type, "none")
        self.assertTrue(source.active)

    def test_provider_links_to_data_source(self):
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")
        source = self.env.ref("spp_dci_openg2p.openg2p_dr_source")
        self.assertEqual(provider.code, "openg2p_dr")
        self.assertEqual(provider.dci_data_source_id, source)
        self.assertTrue(provider.is_dci_backed)

    def test_cel_variable_rewired_to_dci_provider(self):
        """The preset overrides spp_studio.var_has_disability so the
        semantic `has_disability` CEL accessor sources from OpenG2P over
        DCI instead of from the local res.partner field."""
        variable = self.env.ref("spp_studio.var_has_disability")
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")
        self.assertEqual(variable.name, "has_disability")
        self.assertEqual(variable.cel_accessor, "has_disability")
        self.assertEqual(variable.source_type, "external")
        self.assertEqual(variable.value_type, "boolean")
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(variable.dci_attribute_path, "has_disability")
        self.assertEqual(variable.cache_strategy, "ttl")
        self.assertEqual(variable.cache_ttl_seconds, 300)
        self.assertEqual(variable.external_failure_policy, "null")
        # Local field source is cleared so the resolver does not also
        # try to expand to r.is_person_with_disability.
        self.assertFalse(variable.source_field)

    def test_cel_accessor_is_semantic_not_vendor_named(self):
        """ADR-023 §1a: CEL accessors must be vendor-neutral.

        The OpenG2P-ness lives only in the data-source/provider records,
        never in the CEL surface. This test asserts the convention.
        """
        variable = self.env.ref("spp_studio.var_has_disability")
        for forbidden in ("openg2p", "g2p", "vendor"):
            self.assertNotIn(forbidden, variable.cel_accessor.lower())
            self.assertNotIn(forbidden, variable.name.lower())

    def test_post_init_hook_re_asserts_after_studio_reset(self):
        """Simulate `-u spp_studio` resetting var_has_disability back to its
        original source_type='field' state, then run our hook. The hook
        must restore the DCI binding. Without this protection, an unrelated
        upgrade silently breaks the demo deployment."""
        variable = self.env.ref("spp_studio.var_has_disability")
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")

        # Simulate spp_studio re-applying its standard_variables.xml
        variable.write(
            {
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "is_person_with_disability",
                "external_provider_id": False,
                "dci_attribute_path": False,
                "cache_strategy": "none",
                "external_failure_policy": "null",
            }
        )
        # Confirm the reset took effect
        self.assertEqual(variable.source_type, "field")
        self.assertFalse(variable.external_provider_id)

        # Run the hook
        post_init_hook(self.env)

        # Verify the DCI binding was re-asserted
        variable.invalidate_recordset()
        self.assertEqual(variable.source_type, "external")
        self.assertFalse(variable.source_field)
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(variable.dci_attribute_path, "has_disability")
        self.assertEqual(variable.cache_strategy, "ttl")
        self.assertEqual(variable.cache_ttl_seconds, 300)

    def test_post_init_hook_is_idempotent(self):
        """Running the hook when the binding is already correct must not
        write or log noise. Verify no validation errors and the variable
        state is unchanged."""
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
