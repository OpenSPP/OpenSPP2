from unittest.mock import patch

from odoo import Command
from odoo.tests.common import TransactionCase


class AuditDisableCommon(TransactionCase):
    """Shared fixture: a res.partner audit rule with all methods logged."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.audit_rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.partner_model.id)], limit=1)
        if not cls.audit_rule:
            cls.audit_rule = cls.env["spp.audit.rule"].create(
                {
                    "name": "Audit Disable Test Rule",
                    "model_id": cls.partner_model.id,
                    "is_log_create": True,
                    "is_log_write": True,
                    "is_log_unlink": True,
                }
            )
        else:
            cls.audit_rule.write({"is_log_create": True, "is_log_write": True, "is_log_unlink": True})

    def _logs(self, records, method):
        return self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", method),
                ("res_id", "in", records.ids),
            ]
        )

    def _classic_write_read_spy(self):
        """Context manager patching res.partner.read to record full-record
        (load="_classic_write") reads — the decorator's snapshot reads."""
        partner_cls = type(self.env["res.partner"])
        real_read = partner_cls.read
        reads = []

        def spy(records, fields=None, load="lazy"):
            if load == "_classic_write":
                reads.append(records.ids)
            return real_read(records, fields, load=load)

        return patch.object(partner_cls, "read", spy), reads


class TestAuditDisableContext(AuditDisableCommon):
    """audit_disable context: machine flows (e.g. cross-instance replication
    of records already audited at their source) must be able to bypass audit
    logging AND its full-record snapshot reads entirely."""

    def test_create_bypassed(self):
        patcher, reads = self._classic_write_read_spy()
        with patcher:
            partner = self.env["res.partner"].with_context(audit_disable=True).create({"name": "Disable Create"})
        self.assertTrue(partner.exists())
        self.assertFalse(self._logs(partner, "create"))
        self.assertFalse(reads, "audit_disable must skip the full-record snapshot read on create")

    def test_write_bypassed(self):
        partner = self.env["res.partner"].create({"name": "Disable Write"})
        patcher, reads = self._classic_write_read_spy()
        with patcher:
            partner.with_context(audit_disable=True).write({"name": "Disable Write Changed"})
        self.assertEqual(partner.name, "Disable Write Changed")
        self.assertFalse(self._logs(partner, "write"))
        self.assertFalse(reads, "audit_disable must skip the full-record snapshot reads on write")

    def test_unlink_bypassed(self):
        partner = self.env["res.partner"].create({"name": "Disable Unlink"})
        partner_id = partner.id
        patcher, reads = self._classic_write_read_spy()
        with patcher:
            partner.with_context(audit_disable=True).unlink()
        self.assertFalse(partner.exists())
        self.assertFalse(
            self._logs(self.env["res.partner"].browse(partner_id), "unlink"),
            "audit_disable must skip the unlink log",
        )
        self.assertFalse(reads, "audit_disable must skip the full-record snapshot read on unlink")

    def test_without_flag_still_audited(self):
        # Control: the same operations without the flag keep their audit trail.
        partner = self.env["res.partner"].create({"name": "Still Audited"})
        partner.write({"name": "Still Audited Changed"})
        self.assertTrue(self._logs(partner, "create"))
        self.assertTrue(self._logs(partner, "write"))


class TestNoMatchingRuleNoRead(AuditDisableCommon):
    """With no rule matching the method, the decorator must not pay the
    full-record snapshot read — previously audit_create read unconditionally
    and audit_write did its post-write read even with zero matching rules."""

    def test_create_without_create_rule(self):
        self.audit_rule.write({"is_log_create": False})
        patcher, reads = self._classic_write_read_spy()
        with patcher:
            partner = self.env["res.partner"].create({"name": "No Create Rule"})
        self.assertTrue(partner.exists())
        self.assertFalse(self._logs(partner, "create"))
        self.assertFalse(reads, "no create rule -> no full-record snapshot read")

    def test_write_without_write_rule(self):
        partner = self.env["res.partner"].create({"name": "No Write Rule"})
        self.audit_rule.write({"is_log_write": False})
        patcher, reads = self._classic_write_read_spy()
        with patcher:
            partner.write({"name": "No Write Rule Changed"})
        self.assertEqual(partner.name, "No Write Rule Changed")
        self.assertFalse(self._logs(partner, "write"))
        self.assertFalse(reads, "no write rule -> no full-record snapshot reads")

    def test_unlink_without_unlink_rule(self):
        partner = self.env["res.partner"].create({"name": "No Unlink Rule"})
        partner_id = partner.id
        self.audit_rule.write({"is_log_unlink": False})
        patcher, reads = self._classic_write_read_spy()
        with patcher:
            partner.unlink()
        self.assertFalse(partner.exists())
        self.assertFalse(
            self._logs(self.env["res.partner"].browse(partner_id), "unlink"),
            "no unlink rule -> no unlink log",
        )
        self.assertFalse(reads, "no unlink rule -> no full-record snapshot read")


class TestMarkupValuesLogged(AuditDisableCommon):
    """Markup field values (Html fields, e.g. res.partner.comment) must be
    stringified before the audit payload is logged."""

    def test_html_field_value_is_stringified_in_log(self):
        # Make sure the Html field is among the rule's logged fields (a
        # pre-existing rule may restrict field_to_log_ids to a fixed list).
        comment_field = self.env["ir.model.fields"]._get("res.partner", "comment")
        self.audit_rule.write({"field_to_log_ids": [Command.link(comment_field.id)]})
        partner = self.env["res.partner"].create(
            {
                "name": "Markup Partner",
                "comment": "<p>Audit Markup Body</p>",
            }
        )
        logs = self._logs(partner, "create")
        self.assertTrue(logs, "create with an Html field must still be logged")
        self.assertIn(
            "Audit Markup Body",
            logs[0].data or "",
            "the Html field's content must appear in the logged data as plain text",
        )
