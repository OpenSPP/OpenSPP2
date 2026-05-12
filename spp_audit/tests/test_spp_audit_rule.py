from odoo.tests.common import TransactionCase


class AuditRuleTest(TransactionCase):
    """Tests for spp.audit.rule core functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.model_1 = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.res_partner_rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.model_1.id)], limit=1)
        if not cls.res_partner_rule:
            cls.res_partner_rule = AuditRuleTest.create_audit_rule(
                name="Rule 1", model_id=cls.model_1.id, is_log_unlink=False
            )
        else:
            cls.res_partner_rule.update(
                {
                    "is_log_create": True,
                    "is_log_write": True,
                    "is_log_unlink": False,
                }
            )

        cls.res_partner = cls.env["res.partner"].create(
            {
                "name": "Res Partner Group",
                "phone": "+639266716XXX",  # Masked phone number for testing
            }
        )

    @classmethod
    def create_audit_rule(cls, **kwargs):
        return cls.env["spp.audit.rule"].create(kwargs)

    def test_get_audit_rules(self):
        self.assertIsNotNone(self.res_partner.get_audit_rules("create").id)
        self.assertIsNotNone(self.res_partner.get_audit_rules("write").id)
        self.assertFalse(self.res_partner.get_audit_rules("unlink").id)

    def test_register_hook(self):
        self.assertTrue(self.env["spp.audit.rule"]._register_hook([self.res_partner_rule.id]))
        self.assertFalse(self.env["spp.audit.rule"]._register_hook([0]))

    def test_format_data_to_log(self):
        id_val = 1
        field = "name"
        old_name = "old name"
        new_name = "new name"
        not_included_field = "active"

        old_values = {
            "id": id_val,
            field: old_name,
            not_included_field: False,
        }
        new_values = {
            "id": id_val,
            field: new_name,
            not_included_field: True,
        }
        fields_to_log = [field]
        data = self.env["spp.audit.rule"]._format_data_to_log(old_values, new_values, fields_to_log)

        self.assertIn(id_val, data.keys())
        self.assertIn("old", data[id_val].keys())
        self.assertIn("new", data[id_val].keys())
        self.assertIn(field, data[id_val]["old"].keys())
        self.assertIn(field, data[id_val]["new"].keys())
        self.assertNotIn(not_included_field, data[id_val]["old"].keys())
        self.assertNotIn(not_included_field, data[id_val]["new"].keys())
        self.assertEqual(data[id_val]["old"][field], old_name)
        self.assertEqual(data[id_val]["new"][field], new_name)

    def test_get_audit_log_vals(self):
        res_id = 1
        method = "write"
        data = {res_id: {}}
        vals = self.res_partner_rule.get_audit_log_vals(res_id, method, data)

        self.assertIn("user_id", vals.keys())
        self.assertIn("model_id", vals.keys())
        self.assertIn("res_id", vals.keys())
        self.assertIn("method", vals.keys())
        self.assertIn("data", vals.keys())

        self.assertEqual(self.res_partner_rule._uid, vals["user_id"])
        self.assertEqual(self.res_partner_rule.model_id.id, vals["model_id"])
        self.assertEqual(res_id, vals["res_id"])
        self.assertEqual(method, vals["method"])
        self.assertEqual(repr(data[res_id]), vals["data"])


class TestAuditCreateMulti(TransactionCase):
    """Regression tests for audit_create with @api.model_create_multi.

    The audit decorator monkey-patches create() on audited models. It must
    use @api.model_create_multi so the vals_list flows correctly through
    the origin chain to downstream create overrides.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        # Ensure an audit rule with create logging exists for res.partner
        cls.audit_rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.partner_model.id)], limit=1)
        if not cls.audit_rule:
            cls.audit_rule = cls.env["spp.audit.rule"].create(
                {
                    "name": "Test Partner Audit",
                    "model_id": cls.partner_model.id,
                    "is_log_create": True,
                    "is_log_write": False,
                    "is_log_unlink": False,
                }
            )
        else:
            cls.audit_rule.write({"is_log_create": True})

    def test_multi_create_returns_all_records(self):
        """Creating multiple records in one call must return all of them."""
        partners = self.env["res.partner"].create(
            [
                {"name": "Audit Multi A"},
                {"name": "Audit Multi B"},
                {"name": "Audit Multi C"},
            ]
        )
        self.assertEqual(len(partners), 3)
        self.assertEqual(partners[0].name, "Audit Multi A")
        self.assertEqual(partners[1].name, "Audit Multi B")
        self.assertEqual(partners[2].name, "Audit Multi C")

    def test_multi_create_produces_audit_logs(self):
        """Each record from a multi-create should have an audit log entry."""
        partners = self.env["res.partner"].create(
            [
                {"name": "Audit Log A"},
                {"name": "Audit Log B"},
            ]
        )
        logs = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "create"),
                ("res_id", "in", partners.ids),
            ]
        )
        logged_ids = set(logs.mapped("res_id"))
        for partner in partners:
            self.assertIn(
                partner.id,
                logged_ids,
                f"Audit log missing for partner {partner.name} (id={partner.id})",
            )

    def test_single_create_still_works(self):
        """Single-dict create must still work with the model_create_multi decorator."""
        partner = self.env["res.partner"].create({"name": "Audit Single"})
        self.assertTrue(partner.exists())
        self.assertEqual(partner.name, "Audit Single")


class TestAuditWrite(TransactionCase):
    """Tests for the audit_write decorator method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.audit_rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.partner_model.id)], limit=1)
        if not cls.audit_rule:
            cls.audit_rule = cls.env["spp.audit.rule"].create(
                {
                    "name": "Test Partner Audit Write",
                    "model_id": cls.partner_model.id,
                    "is_log_create": False,
                    "is_log_write": True,
                    "is_log_unlink": False,
                }
            )
        else:
            cls.audit_rule.write({"is_log_write": True})

    def test_write_produces_audit_log(self):
        """Writing to an audited record should produce an audit log entry."""
        partner = self.env["res.partner"].create({"name": "Write Test"})
        partner.write({"name": "Write Test Updated"})

        logs = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "write"),
                ("res_id", "=", partner.id),
            ]
        )
        self.assertTrue(logs, "Expected an audit log for the write operation")

    def test_write_captures_old_and_new_values(self):
        """Audit log data should contain both old and new values."""
        partner = self.env["res.partner"].create({"name": "Old Name"})
        partner.write({"name": "New Name"})

        log = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "write"),
                ("res_id", "=", partner.id),
            ],
            limit=1,
            order="id desc",
        )
        self.assertTrue(log)
        # The data field stores repr() of the diff dict which includes old/new
        self.assertIn("old", log.data)
        self.assertIn("new", log.data)

    def test_write_multiple_records(self):
        """Writing to multiple records at once should log each one."""
        partners = self.env["res.partner"].create(
            [
                {"name": "Batch Write A"},
                {"name": "Batch Write B"},
            ]
        )
        partners.write({"phone": "+1234567890"})

        logs = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "write"),
                ("res_id", "in", partners.ids),
            ]
        )
        logged_ids = set(logs.mapped("res_id"))
        for partner in partners:
            self.assertIn(partner.id, logged_ids)

    def test_write_no_recursive_audit(self):
        """Write with audit_in_progress context should not create duplicate logs."""
        partner = self.env["res.partner"].create({"name": "Recurse Test"})

        # Count logs before
        log_count_before = self.env["spp.audit.log"].search_count(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "write"),
                ("res_id", "=", partner.id),
            ]
        )

        # Write with audit_in_progress flag — should skip audit logging
        partner.with_context(audit_in_progress=True).write({"name": "Skipped"})

        log_count_after = self.env["spp.audit.log"].search_count(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "write"),
                ("res_id", "=", partner.id),
            ]
        )
        self.assertEqual(
            log_count_before,
            log_count_after,
            "audit_in_progress context should prevent audit logging",
        )


class TestAuditUnlink(TransactionCase):
    """Tests for the audit_unlink decorator method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.audit_rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.partner_model.id)], limit=1)
        if not cls.audit_rule:
            cls.audit_rule = cls.env["spp.audit.rule"].create(
                {
                    "name": "Test Partner Audit Unlink",
                    "model_id": cls.partner_model.id,
                    "is_log_create": False,
                    "is_log_write": False,
                    "is_log_unlink": True,
                }
            )
        else:
            cls.audit_rule.write({"is_log_unlink": True})

    def test_unlink_produces_audit_log(self):
        """Deleting an audited record should produce an audit log entry."""
        partner = self.env["res.partner"].create({"name": "Delete Me"})
        partner_id = partner.id
        partner.unlink()

        logs = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "unlink"),
                ("res_id", "=", partner_id),
            ]
        )
        self.assertTrue(logs, "Expected an audit log for the unlink operation")

    def test_unlink_logs_old_values(self):
        """Audit log for unlink should contain the old values of the deleted record."""
        partner = self.env["res.partner"].create({"name": "Unlink Values Test"})
        partner_id = partner.id
        partner.unlink()

        log = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "unlink"),
                ("res_id", "=", partner_id),
            ],
            limit=1,
            order="id desc",
        )
        self.assertTrue(log)
        # Unlink logs old values (the state before deletion)
        self.assertIn("old", log.data)

    def test_unlink_multiple_records(self):
        """Deleting multiple records at once should log each one."""
        partners = self.env["res.partner"].create(
            [
                {"name": "Batch Delete A"},
                {"name": "Batch Delete B"},
            ]
        )
        partner_ids = partners.ids
        partners.unlink()

        logs = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("method", "=", "unlink"),
                ("res_id", "in", partner_ids),
            ]
        )
        logged_ids = set(logs.mapped("res_id"))
        for pid in partner_ids:
            self.assertIn(pid, logged_ids)

    def test_unlink_record_is_actually_deleted(self):
        """The record should actually be deleted after audit logging."""
        partner = self.env["res.partner"].create({"name": "Really Delete"})
        partner_id = partner.id
        partner.unlink()

        self.assertFalse(
            self.env["res.partner"].search([("id", "=", partner_id)]),
            "Record should be deleted after audit_unlink",
        )
