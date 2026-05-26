# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Covers ``spp.disable.registrant.wizard``.

Two methods, both in ``spp_registry/wizard/disable_registrant.py``:

- ``default_get`` — pulls ``partner_id`` from ``context["active_id"]``.
- ``disable_registrant`` — stamps ``disabled``, ``disabled_reason`` and
  ``disabled_by`` onto the partner.
"""

from odoo.tests import tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class TestDisableRegistrantWizard(RegistryCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["spp.disable.registrant.wizard"]

    def test_default_get_pulls_partner_from_active_id(self):
        """Opening the wizard from a partner action prefills partner_id."""
        wiz = self.Wizard.with_context(active_id=self.individual_a.id).new({})
        self.assertEqual(wiz.partner_id, self.individual_a)

    def test_default_get_without_active_id_leaves_partner_empty(self):
        """Without an active_id the wizard requires explicit selection."""
        wiz = self.Wizard.new({})
        self.assertFalse(wiz.partner_id)

    def test_disable_registrant_stamps_audit_fields(self):
        self.assertFalse(self.individual_a.disabled)
        wiz = self.Wizard.create(
            {
                "partner_id": self.individual_a.id,
                "disabled_reason": "deceased",
            }
        )
        wiz.disable_registrant()

        self.assertTrue(self.individual_a.disabled)
        self.assertEqual(self.individual_a.disabled_reason, "deceased")
        self.assertEqual(self.individual_a.disabled_by, self.env.user)

    def test_disable_registrant_overwrites_existing_disabled_state(self):
        """Re-running the wizard updates the reason.

        The wizard uses ``rec.partner_id.update({...})`` without an
        ``if not rec.partner_id.disabled`` guard — unlike the
        ``disable_relationship`` method on ``spp.registry.relationship``.
        This is the contract today: tooling can re-disable, with the
        latest reason winning.
        """
        # First disable.
        self.Wizard.create({"partner_id": self.individual_a.id, "disabled_reason": "first reason"}).disable_registrant()
        first_ts = self.individual_a.disabled
        self.assertEqual(self.individual_a.disabled_reason, "first reason")

        # Re-disable with a different reason.
        self.Wizard.create(
            {"partner_id": self.individual_a.id, "disabled_reason": "second reason"}
        ).disable_registrant()

        self.assertEqual(self.individual_a.disabled_reason, "second reason")
        # Timestamp must be at least the original (it's bumped, not cleared).
        self.assertGreaterEqual(self.individual_a.disabled, first_ts)

    def test_disable_registrant_iterates_over_recordset(self):
        """The wizard loops ``for rec in self`` — a multi-row wizard
        recordset should stamp each partner.

        TransientModel.create supports a list of vals (api.model_create_multi
        on the base TransientModel since Odoo 17).
        """
        wiz_a = self.Wizard.create({"partner_id": self.individual_a.id, "disabled_reason": "a"})
        wiz_b = self.Wizard.create({"partner_id": self.individual_b.id, "disabled_reason": "b"})
        (wiz_a | wiz_b).disable_registrant()

        self.assertTrue(self.individual_a.disabled)
        self.assertEqual(self.individual_a.disabled_reason, "a")
        self.assertTrue(self.individual_b.disabled)
        self.assertEqual(self.individual_b.disabled_reason, "b")
