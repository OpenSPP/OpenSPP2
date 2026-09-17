# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: rule evaluation must respect the rule owner's record rules.

The evaluation cron runs elevated (`ir.cron` default user is the installer /
superuser). If the monitored search ran with that elevated identity, a rule
authored by a non-system-admin `group_alerts_manager` could surface records the
author is not allowed to see — the resulting alerts (readable by all alert
managers) then leak data across the record-rule boundary.

The fix evaluates each rule's monitored search as the user who configured what
the rule targets (system-managed `eval_as_user_id`, re-bound to the editor on any
targeting change and never client-writable), so record rules are enforced against
that user's visibility regardless of who (or what cron) triggers the evaluation.
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

    def _set_eval_owner(self, rule, user):
        """Force a rule's ownership + evaluation identity to `user` (bypasses ORM).

        Stands in for a rule authored by that user (create_uid / eval_as_user_id
        are system-managed and not writable through the ORM).
        """
        self.env.cr.execute(
            "UPDATE spp_alert_rule SET create_uid = %s, eval_as_user_id = %s WHERE id = %s",
            (user.id, user.id, rule.id),
        )
        rule.invalidate_recordset(["create_uid", "eval_as_user_id"])

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
        self._set_eval_owner(rule, self.user_unrestricted)

        rule.with_user(SUPERUSER_ID)._evaluate_rule()

        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_visible.id, res_ids)
        self.assertIn(self.partner_hidden.id, res_ids)

    def test_manager_repointing_owner_rule_de_escalates(self):
        """A manager who repoints an unrestricted-owned rule re-binds it to themselves.

        Managers have model-wide write on rules; without re-binding, editing an
        admin-authored rule's targeting would still evaluate as the admin and leak.
        """
        rule = self._manager_rule(name="Admin Authored Rule")
        self._set_eval_owner(rule, self.user_unrestricted)

        # Manager repoints the rule's domain (still matching both partners).
        new_domain = (
            f'[("id", "in", [{self.partner_visible.id}, {self.partner_hidden.id}]), ("active", "in", [True, False])]'
        )
        rule.with_user(self.user_manager).write({"domain_filter": new_domain})
        self.assertEqual(rule.eval_as_user_id, self.user_manager)

        rule.with_user(SUPERUSER_ID)._evaluate_rule()
        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_visible.id, res_ids)
        self.assertNotIn(self.partner_hidden.id, res_ids)

    def test_manager_editing_nontargeting_field_preserves_owner_scope(self):
        """Editing a non-targeting field must NOT re-bind the evaluation identity."""
        rule = self._manager_rule(name="Admin Authored Rule 2")
        self._set_eval_owner(rule, self.user_unrestricted)

        # priority is not a targeting field — the rule still targets what the owner defined.
        rule.with_user(self.user_manager).write({"priority": "high"})
        self.assertEqual(rule.eval_as_user_id, self.user_unrestricted)

        rule.with_user(SUPERUSER_ID)._evaluate_rule()
        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_hidden.id, res_ids)

    def test_eval_as_user_id_not_client_writable(self):
        """A client cannot forge the evaluation identity via create or write."""
        rule = (
            self.env["spp.alert.rule"]
            .with_user(self.user_manager)
            .create(
                {
                    "name": "Forge Attempt Rule",
                    "alert_type_id": self.alert_type_threshold.id,
                    "model_id": self.partner_model.id,
                    "rule_type": "threshold",
                    "monitored_field_id": self.field_color.id,
                    "comparison": "lt",
                    "threshold_value": 8.0,
                    "domain_filter": self.domain_both,
                    "priority": "medium",
                    "eval_as_user_id": self.user_unrestricted.id,
                }
            )
        )
        self.assertEqual(rule.eval_as_user_id, self.user_manager)

        rule.with_user(self.user_manager).write({"eval_as_user_id": self.user_unrestricted.id})
        self.assertEqual(rule.eval_as_user_id, self.user_manager)

    def test_eval_as_user_id_not_forgeable_via_context_default(self):
        """A `default_eval_as_user_id` context key must not seed the evaluation identity.

        Popping (vs force-setting) the field would leave it missing and let
        default_get honour this client-controlled context key.
        """
        rule = (
            self.env["spp.alert.rule"]
            .with_user(self.user_manager)
            .with_context(default_eval_as_user_id=SUPERUSER_ID)
            .create(
                {
                    "name": "Context Forge Rule",
                    "alert_type_id": self.alert_type_threshold.id,
                    "model_id": self.partner_model.id,
                    "rule_type": "threshold",
                    "monitored_field_id": self.field_color.id,
                    "comparison": "lt",
                    "threshold_value": 8.0,
                    "domain_filter": self.domain_both,
                    "priority": "medium",
                }
            )
        )
        self.assertEqual(rule.eval_as_user_id, self.user_manager)

    def test_copy_rebinds_evaluation_identity_to_copier(self):
        """Duplicating a rule (incl. via a context default) binds it to the copier."""
        rule = self._manager_rule(name="Original Rule")
        self._set_eval_owner(rule, self.user_unrestricted)

        copied = rule.with_user(self.user_manager).with_context(default_eval_as_user_id=SUPERUSER_ID).copy()
        self.assertEqual(copied.eval_as_user_id, self.user_manager)

    def test_threshold_change_rebinds_and_de_escalates(self):
        """Changing a post-search filter field (threshold) re-binds the identity."""
        rule = self._manager_rule(name="Dormant Admin Rule")
        self._set_eval_owner(rule, self.user_unrestricted)

        # threshold_value is not the model/domain, but it changes which records leak.
        rule.with_user(self.user_manager).write({"threshold_value": 999.0})
        self.assertEqual(rule.eval_as_user_id, self.user_manager)

        rule.with_user(SUPERUSER_ID)._evaluate_rule()
        res_ids = self._alert_res_ids(rule)
        self.assertNotIn(self.partner_hidden.id, res_ids)

    def test_reactivating_rule_rebinds_identity(self):
        """(Re)activating a rule re-binds the identity to whoever activated it."""
        rule = self._manager_rule(name="Inactive Admin Rule", active=False)
        self._set_eval_owner(rule, self.user_unrestricted)

        rule.with_user(self.user_manager).write({"active": True})
        self.assertEqual(rule.eval_as_user_id, self.user_manager)

    def test_no_eval_user_fails_closed(self):
        """With no resolvable owner, evaluation must skip rather than run elevated."""
        rule = self._manager_rule(name="Orphaned Rule")
        self.env.cr.execute(
            "UPDATE spp_alert_rule SET create_uid = NULL, eval_as_user_id = NULL WHERE id = %s",
            (rule.id,),
        )
        rule.invalidate_recordset(["create_uid", "eval_as_user_id"])

        count = rule.with_user(SUPERUSER_ID)._evaluate_rule()
        self.assertEqual(count, 0)
        self.assertFalse(self.env["spp.alert"].search([("rule_id", "=", rule.id)]))

    def test_evaluation_scoped_to_owner_companies(self):
        """The search runs in the owner's company scope, not the triggering cron's."""
        main = self.company_main
        secondary = self.company_secondary
        # A global multi-company rule on res.partner so company scoping is deterministic.
        self.env["ir.rule"].create(
            {
                "name": "Partner multi-company (test)",
                "model_id": self.partner_model.id,
                "global": True,
                "domain_force": "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
            }
        )
        # Owner belongs only to the main company.
        owner = self.env["res.users"].create(
            {
                "name": "Main-Company Owner",
                "login": "alert_main_owner",
                "email": "main_owner@test.com",
                "company_id": main.id,
                "company_ids": [(6, 0, [main.id])],
                "group_ids": [(4, self.env.ref("base.group_user").id)],
            }
        )
        partner_secondary = self.env["res.partner"].create(
            {"name": "Secondary Co Partner", "color": 1, "company_id": secondary.id}
        )
        rule = self._manager_rule(
            name="Company Scoped Rule",
            domain_filter=f'[("id", "in", [{self.partner_visible.id}, {partner_secondary.id}])]',
        )
        self._set_eval_owner(rule, owner)

        # Cron sees both companies; the owner only sees main — the secondary-company
        # record must be filtered by the owner's scope, not surfaced by the cron's.
        rule.with_user(SUPERUSER_ID).with_context(allowed_company_ids=[main.id, secondary.id])._evaluate_rule()

        res_ids = self._alert_res_ids(rule)
        self.assertIn(self.partner_visible.id, res_ids)
        self.assertNotIn(partner_secondary.id, res_ids)

    def _load_post_migration(self):
        import importlib.util
        import os

        path = os.path.join(os.path.dirname(__file__), "..", "migrations", "19.0.2.0.1", "post-migration.py")
        spec = importlib.util.spec_from_file_location("spp_alerts_post_migration_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_backfills_eval_as_user_id_authoritatively(self):
        """The shipped migration sets eval_as_user_id = create_uid for existing rules.

        Guards against the IS-NULL-only regression: on a real upgrade Odoo's
        _init_column pre-fills the new column with the upgrade user, so the backfill
        must overwrite it (not skip non-NULL rows) to bind each rule to its creator.
        """
        rule = self._manager_rule(name="Pre-upgrade Rule")
        # Simulate the upgrade state: create_uid is the real author; eval_as_user_id
        # was wrongly pre-filled with a different (elevated) user by _init_column.
        self.env.cr.execute(
            "UPDATE spp_alert_rule SET create_uid = %s, eval_as_user_id = %s WHERE id = %s",
            (self.user_manager.id, self.user_unrestricted.id, rule.id),
        )
        rule.invalidate_recordset(["create_uid", "eval_as_user_id"])
        self.assertEqual(rule.eval_as_user_id, self.user_unrestricted)  # wrong, pre-migration

        self._load_post_migration().migrate(self.env.cr, "19.0.2.0.0")
        rule.invalidate_recordset(["eval_as_user_id"])

        self.assertEqual(rule.eval_as_user_id, self.user_manager)
