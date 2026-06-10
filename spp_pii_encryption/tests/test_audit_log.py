# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.pii.audit.log (PII access audit trail)."""

from odoo.tests.common import TransactionCase


class TestPIIAuditLog(TransactionCase):
    """log_field_access and history query helpers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Audit = cls.env["spp.pii.audit.log"]

    def test_log_field_access(self):
        log = self.Audit.log_field_access("res.partner", 1, "name", "reveal", reason="support call")

        self.assertTrue(log)
        self.assertEqual(log.model_name, "res.partner")
        self.assertEqual(log.record_id, 1)
        self.assertEqual(log.field_name, "name")
        self.assertEqual(log.action, "reveal")
        self.assertEqual(log.reason, "support call")
        self.assertEqual(log.user_id, self.env.user)
        # display_name is computed from action/model/field.
        self.assertEqual(log.display_name, "reveal res.partner.name")

    def test_get_access_history(self):
        self.Audit.log_field_access("res.partner", 7, "email", "reveal")
        self.Audit.log_field_access("res.partner", 7, "email", "export")
        # An entry for a different record should be excluded.
        self.Audit.log_field_access("res.partner", 8, "email", "reveal")

        history = self.Audit.get_access_history("res.partner", 7)
        self.assertEqual(len(history), 2)
        self.assertTrue(all(h.record_id == 7 for h in history))

    def test_get_user_access_history(self):
        self.Audit.log_field_access("res.partner", 9, "phone", "reveal")

        history = self.Audit.get_user_access_history(self.env.user.id)
        self.assertTrue(history)
        self.assertTrue(all(h.user_id == self.env.user for h in history))
