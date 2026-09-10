# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.pii.audit.log (PII access audit trail)."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPIIAuditLog(TransactionCase):
    """log_field_access and history query helpers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Audit = cls.env["spp.pii.audit.log"]
        cls.partner_a = cls.env["res.partner"].create({"name": "Audit Target A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Audit Target B"})

    def test_log_field_access(self):
        log = self.Audit.log_field_access("res.partner", self.partner_a.id, "name", "reveal", reason="support call")

        self.assertTrue(log)
        self.assertEqual(log.model_name, "res.partner")
        self.assertEqual(log.record_id, self.partner_a.id)
        self.assertEqual(log.field_name, "name")
        self.assertEqual(log.action, "reveal")
        self.assertEqual(log.reason, "support call")
        self.assertEqual(log.user_id, self.env.user)
        # display_name is computed from action/model/field.
        self.assertEqual(log.display_name, "reveal res.partner.name")

    def test_log_field_access_rejects_unknown_model(self):
        """Forged entries pointing at nonexistent models are refused."""
        with self.assertRaises(ValidationError):
            self.Audit.log_field_access("no.such.model", 1, "name", "reveal")

    def test_log_field_access_rejects_unknown_field(self):
        """Forged entries pointing at nonexistent fields are refused."""
        with self.assertRaises(ValidationError):
            self.Audit.log_field_access("res.partner", self.partner_a.id, "no_such_field", "reveal")

    def test_log_field_access_rejects_missing_record(self):
        """Forged entries pointing at nonexistent records are refused."""
        missing_id = self.partner_b.id
        self.partner_b.unlink()
        with self.assertRaises(ValidationError):
            self.Audit.log_field_access("res.partner", missing_id, "name", "reveal")

    def test_get_access_history(self):
        other = self.env["res.partner"].create({"name": "Audit Target C"})
        self.Audit.log_field_access("res.partner", self.partner_a.id, "email", "reveal")
        self.Audit.log_field_access("res.partner", self.partner_a.id, "email", "export")
        # An entry for a different record should be excluded.
        self.Audit.log_field_access("res.partner", other.id, "email", "reveal")

        history = self.Audit.get_access_history("res.partner", self.partner_a.id)
        self.assertEqual(len(history), 2)
        self.assertTrue(all(h.record_id == self.partner_a.id for h in history))

    def test_get_user_access_history(self):
        self.Audit.log_field_access("res.partner", self.partner_a.id, "phone", "reveal")

        history = self.Audit.get_user_access_history(self.env.user.id)
        self.assertTrue(history)
        self.assertTrue(all(h.user_id == self.env.user for h in history))

    def test_get_user_access_history_window_excludes_old_entries(self):
        """The days window is applied against UTC create_date."""
        recent = self.Audit.log_field_access("res.partner", self.partner_a.id, "phone", "reveal")
        old = self.Audit.log_field_access("res.partner", self.partner_a.id, "phone", "export")
        # Backdate the second entry beyond the queried window.
        self.env.cr.execute(
            "UPDATE spp_pii_audit_log SET create_date = create_date - interval '40 days' WHERE id = %s",
            (old.id,),
        )
        old.invalidate_recordset(["create_date"])

        history = self.Audit.get_user_access_history(self.env.user.id, days=30)
        self.assertIn(recent, history)
        self.assertNotIn(old, history)

        wider = self.Audit.get_user_access_history(self.env.user.id, days=60)
        self.assertIn(old, wider)
