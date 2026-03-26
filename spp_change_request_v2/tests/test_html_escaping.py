from unittest.mock import patch

from odoo.tests import tagged

from .test_change_request import TestChangeRequestBase


@tagged("post_install", "-at_install")
class TestHtmlEscaping(TestChangeRequestBase):
    """Tests that computed HTML fields properly escape dynamic values."""

    def _create_cr(self, registrant=None, cr_type=None):
        """Helper to create a CR for testing."""
        vals = {
            "request_type_id": (cr_type or self.cr_type_add_member).id,
        }
        if registrant is not False:
            vals["registrant_id"] = (registrant or self.group).id
        return self.cr_model.create(vals)

    def test_registrant_summary_escapes_name(self):
        """Verify registrant_summary_html escapes XSS in registrant name."""
        xss_name = '<script>alert("xss")</script>'
        registrant = self.partner_model.create(
            {
                "name": xss_name,
                "is_registrant": True,
                "is_group": False,
            }
        )
        cr = self._create_cr(registrant=registrant)
        cr.invalidate_recordset()
        html = cr.registrant_summary_html
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_registrant_summary_escapes_address(self):
        """Verify registrant_summary_html escapes XSS in street/city."""
        registrant = self.partner_model.create(
            {
                "name": "Safe Name",
                "is_registrant": True,
                "is_group": False,
                "street": '<img src=x onerror=alert(1)>',
                "city": '<b onmouseover=alert(2)>City</b>',
            }
        )
        cr = self._create_cr(registrant=registrant)
        cr.invalidate_recordset()
        html = cr.registrant_summary_html
        self.assertNotIn("<img ", html)
        self.assertNotIn("<b ", html)
        self.assertIn("&lt;img ", html)
        self.assertIn("&lt;b ", html)

    def test_registrant_summary_escapes_spp_id(self):
        """Verify registrant_summary_html escapes XSS in spp_id."""
        registrant = self.partner_model.create(
            {
                "name": "Safe Name",
                "is_registrant": True,
                "is_group": False,
            }
        )
        if hasattr(registrant, "spp_id"):
            registrant.spp_id = '<script>alert("id")</script>'
            cr = self._create_cr(registrant=registrant)
            cr.invalidate_recordset()
            html = cr.registrant_summary_html
            self.assertNotIn("<script>", html)

    def test_preview_html_escapes_field_values(self):
        """Verify _generate_preview_html escapes dynamic values."""
        cr = self._create_cr()
        xss_changes = {
            "_action": "update",
            "name": {
                "old": '<script>alert("old")</script>',
                "new": '<img src=x onerror=alert("new")>',
            },
            "notes": '<script>alert("notes")</script>',
        }
        # Mock the strategy.preview() to return XSS payloads
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = xss_changes
            cr.invalidate_recordset()
            html = cr._generate_preview_html()

        self.assertNotIn("<script>", html)
        self.assertNotIn("<img ", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img ", html)

    def test_preview_html_escapes_list_values(self):
        """Verify _generate_preview_html escapes list values."""
        cr = self._create_cr()
        xss_changes = {
            "_action": "update",
            "tags": ['<script>alert(1)</script>', "safe value"],
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = xss_changes
            cr.invalidate_recordset()
            html = cr._generate_preview_html()

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("safe value", html)

    def test_preview_html_escapes_action_label(self):
        """Verify _generate_preview_html escapes unknown action labels."""
        cr = self._create_cr()
        xss_changes = {
            "_action": '<img src=x onerror=alert("action")>',
            "field": "value",
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = xss_changes
            cr.invalidate_recordset()
            html = cr._generate_preview_html()

        # .title() changes case, so check case-insensitively
        self.assertNotIn("<img ", html.lower())
        self.assertIn("&lt;", html)

    def test_preview_html_preserves_safe_content(self):
        """Verify normal content renders correctly after escaping."""
        cr = self._create_cr()
        safe_changes = {
            "_action": "update",
            "full_name": {"old": "Old Name", "new": "New Name"},
        }
        with patch.object(type(cr.request_type_id), "get_apply_strategy") as mock_strategy:
            mock_strategy.return_value.preview.return_value = safe_changes
            cr.invalidate_recordset()
            html = cr._generate_preview_html()

        self.assertIn("Old Name", html)
        self.assertIn("New Name", html)
        self.assertIn("Full Name", html)
        self.assertIn("<table", html)
