# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: GRM rules evaluate with their creator's identity, not superuser.

Regression tests for the GRM rule cluster:

- #379 (HIGH): the hourly escalation cron runs as superuser and applied rules
  bypassing record rules, so an officer could author an always-match rule
  escalating tickets to themselves and seize every ticket in the database.
  Rules must evaluate and act with the identity of whoever defined them
  (eval_as_user_id), so an officer's rule can only touch tickets the officer's
  own record rule already permits. Mirrors the spp_alerts #364 owner-identity fix.
- #381 (Medium): apply_routing / apply_escalations / check_escalations were
  public @api.model methods, RPC-dispatchable; they must be private.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

ROUTING = "spp.grm.routing.rule"
ESCALATION = "spp.grm.escalation.rule"


@tagged("post_install", "-at_install")
class TestGRMRuleOwnerIdentity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]
        internal = cls.env.ref("base.group_user")
        officer = cls.env.ref("spp_grm.group_grm_officer")
        manager = cls.env.ref("spp_grm.group_grm_manager")

        cls.officer = Users.create(
            {
                "name": "GRM Officer",
                "login": "grm_owner_officer",
                "group_ids": [Command.link(internal.id), Command.link(officer.id)],
            }
        )
        cls.manager = Users.create(
            {
                "name": "GRM Manager",
                "login": "grm_owner_manager",
                "group_ids": [Command.link(internal.id), Command.link(manager.id)],
            }
        )
        # Two teams; the officer is a member of team A only.
        Team = cls.env["spp.grm.team"]
        cls.team_a = Team.create({"name": "Team A", "member_ids": [Command.link(cls.officer.id)]})
        cls.team_b = Team.create({"name": "Team B"})

        partner = cls.env["res.partner"].create({"name": "Complainant"})
        Ticket = cls.env["spp.grm.ticket"]
        # A ticket owned by team B — outside the officer's record-rule scope.
        cls.foreign_ticket = Ticket.create(
            {
                "name": "Foreign grievance",
                "description": "Assigned to team B, officer cannot see it",
                "partner_id": partner.id,
                "team_id": cls.team_b.id,
                "severity": "critical",
            }
        )

    def test_officer_rule_cannot_seize_foreign_ticket(self):
        """#379: an officer's always-match escalation rule, applied by the
        superuser cron, must NOT escalate/reassign a ticket the officer cannot
        see. Owner-identity evaluation bounds the rule to the officer's scope."""
        self.env[ESCALATION].with_user(self.officer).create(
            {
                "name": "Seize everything",
                "condition_cel": "",  # empty == always matches
                "escalate_to_user_id": self.officer.id,
                "trigger_after_hours": 0,
            }
        )
        # Run the cron path as superuser (as ir.cron would).
        self.env[ESCALATION].sudo().check_escalations()
        self.foreign_ticket.invalidate_recordset()
        self.assertFalse(
            self.foreign_ticket.is_escalated,
            "Officer-authored rule must not escalate a ticket outside the officer's scope",
        )
        self.assertNotEqual(
            self.foreign_ticket.user_id,
            self.officer,
            "Officer-authored rule must not reassign a ticket it cannot see",
        )

    def test_manager_rule_applies_broadly(self):
        """A manager (broad record-rule scope) authoring the same rule DOES
        escalate — owner identity does not over-restrict legitimate rules."""
        self.env[ESCALATION].with_user(self.manager).create(
            {
                "name": "Manager broad rule",
                "condition_cel": "",
                "escalate_severity": "high",
                "trigger_after_hours": 0,
            }
        )
        self.env[ESCALATION].sudo().check_escalations()
        self.foreign_ticket.invalidate_recordset()
        self.assertTrue(
            self.foreign_ticket.is_escalated,
            "Manager-authored rule should apply across teams",
        )

    def test_eval_as_user_id_set_to_creator(self):
        rule = (
            self.env[ROUTING].with_user(self.officer).create({"name": "R", "condition_cel": "severity == 'critical'"})
        )
        self.assertEqual(rule.eval_as_user_id, self.officer)

    def test_eval_as_user_id_not_forgeable_via_context(self):
        rule = (
            self.env[ROUTING]
            .with_user(self.officer)
            .with_context(default_eval_as_user_id=self.env.ref("base.user_admin").id)
            .create({"name": "R2", "condition_cel": "severity == 'critical'"})
        )
        self.assertEqual(rule.eval_as_user_id, self.officer)

    def test_eval_as_user_id_not_writable_and_rebinds_on_retarget(self):
        rule = self.env[ROUTING].with_user(self.manager).create({"name": "R3", "condition_cel": "severity == 'low'"})
        # Direct write of the identity is ignored.
        rule.with_user(self.officer).write({"eval_as_user_id": self.env.ref("base.user_admin").id})
        rule.invalidate_recordset()
        self.assertNotEqual(rule.eval_as_user_id, self.env.ref("base.user_admin"))
        # Changing what the rule targets re-binds identity to the editor.
        rule.with_user(self.officer).write({"condition_cel": "severity == 'high'"})
        rule.invalidate_recordset()
        self.assertEqual(rule.eval_as_user_id, self.officer)

    def test_operational_toggle_does_not_rebind_owner(self):
        """Reordering or archiving/unarchiving a rule is a routine action that
        must NOT transfer ownership: otherwise a manager cleaning up an
        officer's rule would silently re-bind it to the manager's broad scope
        (a confused-deputy escalation)."""
        rule = self.env[ESCALATION].with_user(self.officer).create(
            {"name": "Officer rule", "condition_cel": "severity == 'critical'"}
        )
        self.assertEqual(rule.eval_as_user_id, self.officer)
        # Manager archives then re-enables and reorders it — owner stays the officer.
        rule.with_user(self.manager).write({"active": False})
        rule.with_user(self.manager).write({"active": True, "sequence": 99})
        rule.invalidate_recordset()
        self.assertEqual(
            rule.eval_as_user_id,
            self.officer,
            "Toggling active/sequence must not re-author rule ownership",
        )

    def test_escalation_counter_increments_under_owner_identity(self):
        """The escalation counter is incremented (atomically) when a manager's
        rule applies via the elevated cron path."""
        rule = self.env[ESCALATION].with_user(self.manager).create(
            {"name": "Counter rule", "condition_cel": "", "escalate_severity": "high"}
        )
        before = rule.escalation_count
        self.env[ESCALATION].sudo().check_escalations()
        rule.invalidate_recordset()
        self.assertEqual(rule.escalation_count, before + 1)

    def test_entry_points_not_rpc_callable(self):
        """#381: the three rule-engine methods must be rejected for RPC dispatch."""
        from odoo.service.model import call_kw

        for model, method, args in [
            (ROUTING, "apply_routing", [self.foreign_ticket.id]),
            (ESCALATION, "apply_escalations", [self.foreign_ticket.id]),
            (ESCALATION, "check_escalations", []),
        ]:
            with self.assertRaises(AccessError):
                call_kw(self.env[model], method, args, {})
