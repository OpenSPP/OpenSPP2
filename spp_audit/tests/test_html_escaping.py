from odoo.tests.common import TransactionCase


class TestAuditHtmlEscaping(TransactionCase):
    """Tests that audit log HTML fields properly escape dynamic values."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model_partner = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.audit_rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.model_partner.id)], limit=1)
        if not cls.audit_rule:
            cls.audit_rule = cls.env["spp.audit.rule"].create(
                {
                    "name": "Test Rule",
                    "model_id": cls.model_partner.id,
                    "is_log_create": True,
                    "is_log_write": True,
                    "is_log_unlink": False,
                }
            )

    def _create_audit_log(self, old_vals, new_vals):
        """Create an audit log record with given old/new values."""
        data = repr({"old": old_vals, "new": new_vals})
        return self.env["spp.audit.log"].create(
            {
                "audit_rule_id": self.audit_rule.id,
                "user_id": self.env.uid,
                "model_id": self.model_partner.id,
                "res_id": 1,
                "method": "write",
                "data": data,
            }
        )

    def test_data_html_escapes_script_tags(self):
        """Verify data_html escapes <script> in field values."""
        xss_payload = '<script>alert("xss")</script>'
        log = self._create_audit_log(
            old_vals={"name": "Safe Name"},
            new_vals={"name": xss_payload},
        )
        html = log.data_html
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_data_html_escapes_html_entities(self):
        """Verify data_html escapes angle brackets and ampersands."""
        log = self._create_audit_log(
            old_vals={"name": "Before <b>bold</b>"},
            new_vals={"name": "After <img src=x onerror=alert(1)>"},
        )
        html = log.data_html
        self.assertNotIn("<img ", html)
        self.assertIn("&lt;img ", html)
        self.assertNotIn("<b>bold</b>", html)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", html)

    def test_data_html_renders_table_structure(self):
        """Verify data_html still produces valid table structure."""
        log = self._create_audit_log(
            old_vals={"name": "Old"},
            new_vals={"name": "New"},
        )
        html = log.data_html
        self.assertIn("<table", html)
        self.assertIn("<thead>", html)
        self.assertIn("<tbody>", html)
        self.assertIn("<td>", html)

    def test_parent_data_html_escapes_script_tags(self):
        """Verify parent_data_html escapes <script> in field values."""
        xss_payload = '<script>alert("xss")</script>'
        parent_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        log = self.env["spp.audit.log"].create(
            {
                "audit_rule_id": self.audit_rule.id,
                "user_id": self.env.uid,
                "model_id": self.model_partner.id,
                "res_id": 1,
                "method": "write",
                "data": repr({"old": {"name": "Safe"}, "new": {"name": xss_payload}}),
                "parent_model_id": parent_model.id,
                "parent_res_ids_str": "1",
            }
        )
        html = log.parent_data_html
        self.assertNotIn("<script>", html)
