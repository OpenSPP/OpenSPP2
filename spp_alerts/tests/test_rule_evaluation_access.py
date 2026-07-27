# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: rule evaluation must respect the rule owner's record rules.

The evaluation cron runs elevated (`ir.cron` default user is the installer /
superuser). If the monitored search ran with that elevated identity, a rule
authored by a non-system-admin `group_alerts_manager` could surface records the
author is not allowed to see — the resulting alerts (readable by all alert
managers) then leak data across the record-rule boundary.

The fix evaluates each rule's monitored search as the rule's owner
(`create_uid`), so record rules are enforced against whoever configured the
rule regardless of who (or what cron) triggers the evaluation.
"""

from odoo import SUPERUSER_ID
from odoo.tests import tagged

from .common import AlertsTestCommon


@tagged("post_install", "-at_install")
class TestRuleEvaluationAccess(AlertsTestCommon):
    """Elevated evaluation of a manager-owned rule honors the manager's rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.field_color = cls.env["ir.model.fields"].search(
            [("model_id", "=", cls.partner_model.id), ("name", "=", "color")],
            limit=1,
        )

        # A plain internal user with no alert groups, so the record rule below does
        # not restrict them — stands in for an author whose visibility spans all
        # partners. (group_system transitively joins group_alerts_manager via the
        # SPP admin chain, so it would be restricted too — hence a bare group_user.)
        cls.user_unrestricted = cls.env["res.users"].create(
            {
                "name": "Unrestricted Rule Author",
                "login": "alert_unrestricted",
                "email": "unrestricted@test.com",
                "group_ids": [(4, cls.env.ref("base.group_user").id)],
            }
        )

        # Two registrants with a low color so both match a `< 8` threshold.
        cls.partner_visible = cls.env["res.partner"].create({"name": "Visible Partner", "color": 1})
        cls.partner_hidden = cls.env["res.partner"].create({"name": "Hidden Partner", "color": 1})

        # Record rule scoped to the Alerts Manager group: managers can see every
        # partner EXCEPT the hidden one. Admin/superuser is not in this group, so
        # the elevated cron identity would still see the hidden partner.
        cls.env["ir.rule"].create(
            {
                "name": "Alerts Manager cannot see Hidden Partner",
                "model_id": cls.partner_model.id,
                "groups": [(4, cls.env.ref("spp_alerts.group_alerts_manager").id)],
                "domain_force": f'[("id", "!=", {cls.partner_hidden.id})]',
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            }
        )

        cls.domain_both = f'[("id", "in", [{cls.partner_visible.id}, {cls.partner_hidden.id}])]'

    def _manager_rule(self, **kwargs):
        """Create a threshold rule OWNED by the alerts manager (create_uid)."""
        vals = {
            "name": "Manager Owned Rule",
            "alert_type_id": self.alert_type_threshold.id,
            "model_id": self.partner_model.id,
            "rule_type": "threshold",
            "monitored_field_id": self.field_color.id,
            "comparison": "lt",
            "threshold_value": 8.0,
            "domain_filter": self.domain_both,
            "priority": "medium",
        }
        vals.update(kwargs)
        return self.env["spp.alert.rule"].with_user(self.user_manager).create(vals)

    def _alert_res_ids(self, rule):
        return set(self.env["spp.alert"].search([("rule_id", "=", rule.id)]).mapped("res_id"))

    def test_manager_cannot_see_hidden_partner(self):
        """Sanity: the record rule actually hides the partner from the manager."""
        visible_to_manager = self.env["res.partner"].with_user(self.user_manager).search([]).ids
        self.assertIn(self.partner_visible.id, visible_to_manager)
        self.assertNotIn(self.partner_hidden.id, visible_to_manager)

    def test_elevated_eval_does_not_surface_owner_hidden_records(self):
        """A manager-owned rule, evaluated elevated, must not alert on hidden records."""
        rule = self._manager_rule()
        self.assertEqual(rule.create_uid, self.user_manager)

        # Evaluate as the superuser cron would (bypasses record rules itself).
        rule.with_user(SUPERUSER_ID)._evaluate_rule()

        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_visible.id, res_ids)
        self.assertNotIn(self.partner_hidden.id, res_ids)

    def test_cron_path_respects_owner_record_rules(self):
        """The full cron entrypoint likewise honors the rule owner's visibility."""
        rule = self._manager_rule()

        self.env["spp.alert.rule"].with_user(SUPERUSER_ID)._cron_evaluate_rules()

        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_visible.id, res_ids)
        self.assertNotIn(self.partner_hidden.id, res_ids)

    def test_unrestricted_owner_rule_still_spans_all_records(self):
        """A rule whose owner can see all partners keeps system-wide scope (intended)."""
        rule = self._manager_rule(name="Unrestricted Owned Rule")
        # Reassign ownership to the unrestricted user (create_uid is not ORM-writable).
        self.env.cr.execute(
            "UPDATE spp_alert_rule SET create_uid = %s WHERE id = %s",
            (self.user_unrestricted.id, rule.id),
        )
        rule.invalidate_recordset(["create_uid"])
        self.assertEqual(rule.create_uid, self.user_unrestricted)

        rule.with_user(SUPERUSER_ID)._evaluate_rule()

        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_visible.id, res_ids)
        self.assertIn(self.partner_hidden.id, res_ids)
