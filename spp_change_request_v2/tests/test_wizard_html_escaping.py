import json
from unittest.mock import patch

from odoo.tests import tagged

from .test_change_request import TestChangeRequestBase


@tagged("post_install", "-at_install")
class TestWizardHtmlEscaping(TestChangeRequestBase):
    """Tests that the preview wizard properly escapes HTML in dynamic values."""

    def _create_cr(self, registrant=None, cr_type=None):
        """Helper to create a CR for testing."""
        vals = {
            "request_type_id": (cr_type or self.cr_type_add_member).id,
        }
        if registrant is not False:
            vals["registrant_id"] = (registrant or self.group).id
        return self.cr_model.create(vals)

    def _create_wizard(self, cr):
        """Create a preview wizard for the given CR."""
        return self.env["spp.cr.preview.wizard"].create(
            {"change_request_id": cr.id}
        )

    def test_wizard_preview_escapes_action(self):
        """Verify wizard preview_html escapes XSS in action value."""
        cr = self._create_cr()
        wizard = self._create_wizard(cr)
        xss_changes = {
            "_action": '<script>alert("action")</script>',
            "field": "value",
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = xss_changes
            wizard.invalidate_recordset()
            html = wizard.preview_html

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_wizard_preview_escapes_field_values(self):
        """Verify wizard preview_html escapes XSS in field keys and values."""
        cr = self._create_cr()
        wizard = self._create_wizard(cr)
        xss_changes = {
            "_action": "update",
            "safe_field": '<img src=x onerror=alert(1)>',
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = xss_changes
            wizard.invalidate_recordset()
            html = wizard.preview_html

        self.assertNotIn("<img ", html)
        self.assertIn("&lt;img ", html)

    def test_wizard_preview_escapes_list_values(self):
        """Verify wizard preview_html escapes list items."""
        cr = self._create_cr()
        wizard = self._create_wizard(cr)
        xss_changes = {
            "_action": "update",
            "tags": ['<script>alert(1)</script>', "safe"],
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = xss_changes
            wizard.invalidate_recordset()
            html = wizard.preview_html

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("safe", html)

    def test_wizard_preview_from_snapshot_escapes(self):
        """Verify wizard escapes values from stored JSON snapshots."""
        cr = self._create_cr()
        xss_snapshot = json.dumps({
            "_action": "update",
            "name": '<script>alert("snapshot")</script>',
        })
        cr.write({"is_applied": True, "preview_json_snapshot": xss_snapshot})
        wizard = self._create_wizard(cr)
        wizard.invalidate_recordset()
        html = wizard.preview_html

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_wizard_preview_preserves_safe_content(self):
        """Verify safe content renders correctly in wizard preview."""
        cr = self._create_cr()
        wizard = self._create_wizard(cr)
        safe_changes = {
            "_action": "create",
            "full_name": "John Doe",
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = safe_changes
            wizard.invalidate_recordset()
            html = wizard.preview_html

        self.assertIn("John Doe", html)
        self.assertIn("Full Name", html)
        self.assertIn("create", html)
