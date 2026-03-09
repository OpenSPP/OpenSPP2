# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSPPQueueJob(TransactionCase):
    """Test queue.job extension for attachment related action."""

    def test_related_action_attachment(self):
        """Test _related_action_attachment returns correct action dict."""
        job = self.env["queue.job"].new({"kwargs": {"att_id": 42}})
        action = job._related_action_attachment()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "ir.attachment")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["res_id"], 42)

    def test_related_action_attachment_no_att_id(self):
        """Test _related_action_attachment when att_id is not in kwargs."""
        job = self.env["queue.job"].new({"kwargs": {}})
        action = job._related_action_attachment()
        self.assertIsNone(action["res_id"])
