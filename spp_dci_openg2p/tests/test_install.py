from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci_openg2p import post_init_hook

_PRESET_VARIABLE_XMLIDS = (
    "spp_dci_openg2p.var_is_poor",
    "spp_dci_openg2p.var_has_dependent_under_school_age",
)


@tagged("post_install", "-at_install")
class TestOpenG2PPresetInstall(TransactionCase):
    """Smoke test: the preset records exist after install and are linked correctly."""

    # ------------------------------------------------------------------
    # Vocabulary code
    # ------------------------------------------------------------------

    def test_uin_id_type_vocab_code_present(self):
        """The preset ships a `UIN` vocabulary code on the urn:openspp:vocab:id-type
        vocabulary so operators can pick it as `ID Type` on the registrant's
        Identity tab. The code value (UIN, uppercase) matches the SPDCI wire
        convention and the first entry in OpenG2PSocialService.IDENTIFIER_PRIORITY.
        """
        code = self.env.ref("spp_dci_openg2p.id_type_uin")
        self.assertEqual(code.code, "UIN")
        self.assertEqual(code.target_type, "individual")
        self.assertEqual(
            code.vocabulary_id,
            self.env.ref("spp_vocabulary.vocab_id_type"),
        )

    def test_uin_code_matches_service_priority_first(self):
        """Regression: the vocab code must equal the first entry in the
        service's IDENTIFIER_PRIORITY tuple, otherwise the dispatcher would
        not pick up a partner's UIN reg_id when querying OpenG2P."""
        from odoo.addons.spp_dci_openg2p.services.openg2p_social_service import (
            IDENTIFIER_PRIORITY,
        )

        code = self.env.ref("spp_dci_openg2p.id_type_uin")
        self.assertEqual(IDENTIFIER_PRIORITY[0], code.code)

    # ------------------------------------------------------------------
    # Data source and provider
    # ------------------------------------------------------------------

    def test_data_source_present(self):
        source = self.env.ref("spp_dci_openg2p.openg2p_dr_source")
        self.assertEqual(source.code, "openg2p_dr")
        # OpenG2P plays the Social Registry role in the federated topology
        # (ADR-024). Disability data lives on a separate OpenSPP-DR instance.
        self.assertEqual(source.registry_type, "ns:org:RegistryType:Social")
        self.assertEqual(source.vendor, "openg2p")
        self.assertEqual(source.auth_type, "none")
        self.assertTrue(source.active)

    def test_provider_links_to_data_source(self):
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")
        source = self.env.ref("spp_dci_openg2p.openg2p_dr_source")
        self.assertEqual(provider.code, "openg2p_dr")
        self.assertEqual(provider.dci_data_source_id, source)
        self.assertTrue(provider.is_dci_backed)

    # ------------------------------------------------------------------
    # CEL variables: preset ships two SR-sourced variables
    # ------------------------------------------------------------------

    def test_var_is_poor_bound_to_dci_provider(self):
        variable = self.env.ref("spp_dci_openg2p.var_is_poor")
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")
        self.assertEqual(variable.name, "is_poor")
        self.assertEqual(variable.cel_accessor, "is_poor")
        self.assertEqual(variable.source_type, "external")
        # OpenG2P SR exposes `income_level` as a string ("low" / "medium" /
        # "high"); the preset binds is_poor to that raw value rather than
        # synthesizing a boolean. CEL rules match `is_poor == "low"`.
        self.assertEqual(variable.value_type, "string")
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(variable.dci_attribute_path, "income_level")
        self.assertEqual(variable.cache_strategy, "ttl")
        self.assertEqual(variable.cache_ttl_seconds, 300)
        self.assertEqual(variable.external_failure_policy, "null")
        self.assertEqual(variable.state, "active")
        self.assertTrue(variable.active)

    def test_var_has_dependent_under_school_age_parked_inactive(self):
        """Deferred: OpenG2P's reg_records[0] doesn't expose household
        composition / dependent birth dates. The variable record stays
        registered (so revival is a config-only change) but is parked
        inactive so the dispatcher's pre-warm skips it."""
        variable = self.env.ref("spp_dci_openg2p.var_has_dependent_under_school_age")
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")
        self.assertEqual(variable.name, "has_dependent_under_school_age")
        self.assertEqual(variable.cel_accessor, "has_dependent_under_school_age")
        self.assertEqual(variable.source_type, "external")
        self.assertEqual(variable.value_type, "boolean")
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(
            variable.dci_attribute_path,
            "has_dependent_under_school_age",
        )
        self.assertEqual(variable.state, "inactive")
        self.assertFalse(variable.active)

    def test_cel_accessors_are_semantic_not_vendor_named(self):
        """ADR-023 §1a: CEL accessors must be vendor-neutral. OpenG2P-ness
        lives only in data-source/provider records, never in the CEL surface."""
        for xml_id in _PRESET_VARIABLE_XMLIDS:
            variable = self.env.ref(xml_id)
            for forbidden in ("openg2p", "g2p", "vendor"):
                self.assertNotIn(forbidden, variable.cel_accessor.lower())
                self.assertNotIn(forbidden, variable.name.lower())

    def test_preset_does_not_override_var_has_disability(self):
        """ADR-024: disability data lives on the OpenSPP-DR instance, not
        OpenG2P. This preset must NOT rebind var_has_disability — that
        belongs to the DR-side preset (spp_dci_openspp_dr).

        We can't assert the variable is at its spp_studio default (a
        previous version of this preset may have already bound it, and
        bindings stick across upgrades), but we CAN assert no XML record
        in this preset is responsible for the binding.
        """
        # Look up the ir.model.data entries that reference var_has_disability
        # and verify none come from this module.
        variable = self.env.ref("spp_studio.var_has_disability")
        owners = self.env["ir.model.data"].search(
            [
                ("model", "=", "spp.cel.variable"),
                ("res_id", "=", variable.id),
                ("module", "=", "spp_dci_openg2p"),
            ]
        )
        self.assertFalse(
            owners,
            "spp_dci_openg2p must not own var_has_disability bindings — "
            "that responsibility belongs to spp_dci_openspp_dr per ADR-024.",
        )

    # ------------------------------------------------------------------
    # post_init_hook: drift correction
    # ------------------------------------------------------------------

    def test_post_init_hook_re_asserts_after_reset(self):
        """Simulate var_is_poor getting reset back to draft state, then run
        the hook. The hook must restore the DCI binding. Without this
        protection, an unrelated upgrade silently breaks the demo."""
        variable = self.env.ref("spp_dci_openg2p.var_is_poor")
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")

        # Simulate someone resetting the variable to draft / no provider
        variable.write(
            {
                "external_provider_id": False,
                "dci_attribute_path": False,
                "cache_strategy": "none",
                "state": "draft",
                "active": False,
            }
        )
        self.assertFalse(variable.external_provider_id)
        self.assertEqual(variable.state, "draft")

        post_init_hook(self.env)

        variable.invalidate_recordset()
        self.assertEqual(variable.source_type, "external")
        self.assertEqual(variable.external_provider_id, provider)
        self.assertEqual(variable.dci_attribute_path, "income_level")
        self.assertEqual(variable.value_type, "string")
        self.assertEqual(variable.cache_strategy, "ttl")
        self.assertEqual(variable.cache_ttl_seconds, 300)
        self.assertEqual(variable.state, "active")
        self.assertTrue(variable.active)

    def test_post_init_hook_parks_deferred_variable_inactive(self):
        """has_dependent_under_school_age is a deferred-feature placeholder.
        Even if someone activates it manually (e.g., via the UI), the next
        hook run must drag it back to state='inactive' / active=False so
        the dispatcher's pre-warm skips it. This prevents accidental DCI
        round-trips for a field OpenG2P does not expose."""
        var_dep = self.env.ref("spp_dci_openg2p.var_has_dependent_under_school_age")
        # Simulate someone activating it
        var_dep.write(
            {
                "external_provider_id": False,
                "dci_attribute_path": False,
                "state": "active",
                "active": True,
            }
        )

        post_init_hook(self.env)

        var_dep.invalidate_recordset()
        provider = self.env.ref("spp_dci_openg2p.openg2p_dr_provider")
        self.assertEqual(var_dep.external_provider_id, provider)
        self.assertEqual(var_dep.dci_attribute_path, "has_dependent_under_school_age")
        # Hook re-parks it inactive
        self.assertEqual(var_dep.state, "inactive")
        self.assertFalse(var_dep.active)

    def test_post_init_hook_handles_missing_variable_gracefully(self):
        """If a preset variable is missing (e.g., data load failed), the
        hook must log and continue — not raise — so partial-install
        scenarios don't break the database initialization."""
        original_ref = self.env.ref

        def selective_ref(xmlid, *args, **kwargs):
            if xmlid == "spp_dci_openg2p.var_is_poor":
                # raise_if_not_found defaults to True, so we have to
                # honour it for non-matching xmlids
                if kwargs.get("raise_if_not_found", True):
                    raise ValueError(f"Mock: {xmlid} not found")
                return self.env["spp.cel.variable"].browse()
            return original_ref(xmlid, *args, **kwargs)

        with patch.object(type(self.env), "ref", side_effect=selective_ref):
            # Should not raise
            post_init_hook(self.env)

    def test_post_init_hook_handles_missing_provider_gracefully(self):
        """If the OpenG2P provider record was deleted post-install, the
        hook must log an error and return early — not raise."""
        original_ref = self.env.ref

        def selective_ref(xmlid, *args, **kwargs):
            if xmlid == "spp_dci_openg2p.openg2p_dr_provider":
                return self.env["spp.data.provider"].browse()  # empty
            return original_ref(xmlid, *args, **kwargs)

        with patch.object(type(self.env), "ref", side_effect=selective_ref):
            # Should not raise
            post_init_hook(self.env)

    def test_post_init_hook_is_idempotent(self):
        """Running the hook when the bindings are already correct must
        not change anything."""
        before = {}
        for xml_id in _PRESET_VARIABLE_XMLIDS:
            variable = self.env.ref(xml_id)
            before[xml_id] = {
                "source_type": variable.source_type,
                "external_provider_id": variable.external_provider_id.id,
                "dci_attribute_path": variable.dci_attribute_path,
            }

        post_init_hook(self.env)

        for xml_id in _PRESET_VARIABLE_XMLIDS:
            variable = self.env.ref(xml_id)
            variable.invalidate_recordset()
            self.assertEqual(
                {
                    "source_type": variable.source_type,
                    "external_provider_id": variable.external_provider_id.id,
                    "dci_attribute_path": variable.dci_attribute_path,
                },
                before[xml_id],
            )
