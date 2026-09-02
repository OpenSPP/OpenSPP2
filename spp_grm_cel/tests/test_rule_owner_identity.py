# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: GRM rules evaluate with their creator's identity, not superuser.

Regression tests for the GRM rule cluster:

- #379 (HIGH): the hourly escalation cron runs as superuser and applied rules
  bypassing record rules, so an officer could author an always-match rule
  escalating tickets to themselves and seize every ticket in the database.
  Rules must evaluate and act with the identity of whoever defined them
  (eval_as_user_id), so an officer's rule can only touch tickets the officer's
  own record rule already permits. Mirrors the spp_alerts #364 owner-identity fix.
- #381 (Medium): apply_routing / apply_escalations / apply_escalation /
  check_escalations were public methods, RPC-dispatchable; they must be private.
"""

from odoo import Command
from odoo.exceptions import AccessError, UserError
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

    def test_officer_rule_cannot_seize_foreign_ticket_via_condition(self):
        """Same seize scenario, but with a non-empty CEL condition: evaluating
        the condition must READ the ticket, which the owner cannot, so the rule
        is skipped on the evaluate path (not just denied on the write path —
        an empty condition short-circuits evaluate() without touching the
        ticket, so only this variant pins the read-side bound)."""
        self.env[ESCALATION].with_user(self.officer).create(
            {
                "name": "Seize critical tickets",
                "condition_cel": "severity == 'critical'",  # foreign_ticket matches
                "escalate_to_user_id": self.officer.id,
                "trigger_after_hours": 0,
            }
        )
        self.env[ESCALATION].sudo().check_escalations()
        self.foreign_ticket.invalidate_recordset()
        self.assertFalse(
            self.foreign_ticket.is_escalated,
            "Rule condition must not be evaluated against a ticket its owner cannot read",
        )

    def test_officer_escalation_out_of_scope_rolls_back_cleanly(self):
        """An officer's rule that reassigns a ticket OUT of the officer's own
        scope must not leave a half-applied escalation: the reassignment write
        succeeds (access is checked pre-write), but the follow-up steps then
        fail for lack of access — the savepoint must roll the whole escalation
        back: no state change, no counter increment, no chatter message."""
        own_ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Own-team grievance",
                "description": "In team A, inside the officer's scope",
                "partner_id": self.foreign_ticket.partner_id.id,
                "team_id": self.team_a.id,
                "severity": "critical",
            }
        )
        rule = (
            self.env[ESCALATION]
            .with_user(self.officer)
            .create(
                {
                    "name": "Escalate out of scope",
                    "condition_cel": "",
                    "escalate_to_team_id": self.team_b.id,  # officer is not in team B
                    "trigger_after_hours": 0,
                }
            )
        )
        messages_before = len(own_ticket.message_ids)
        applied = self.env[ESCALATION].sudo().apply_escalations(own_ticket)
        own_ticket.invalidate_recordset()
        rule.invalidate_recordset()
        self.assertFalse(applied, "Out-of-scope escalation must report not-applied")
        self.assertFalse(own_ticket.is_escalated, "Escalation state must be rolled back")
        self.assertEqual(own_ticket.team_id, self.team_a, "Reassignment must be rolled back")
        self.assertEqual(rule.escalation_count, 0, "Counter must not survive the rollback")
        self.assertEqual(
            len(own_ticket.message_ids),
            messages_before,
            "No chatter message may survive a rolled-back escalation",
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
        # Direct write of the identity is refused — loudly, so a data fix that
        # tries it cannot report success while the rule keeps its old owner.
        with self.assertRaises(UserError):
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
        rule = (
            self.env[ESCALATION]
            .with_user(self.officer)
            .create({"name": "Officer rule", "condition_cel": "severity == 'critical'"})
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

    def test_take_ownership_rebinds_to_acting_user(self):
        """The remediation path for superuser-, archived- or mis-scoped owners:
        "Take Ownership" re-binds the rule to whoever presses it, on both models."""
        for model in (ROUTING, ESCALATION):
            rule = self.env[model].with_user(self.officer).create({"name": "Handed over", "condition_cel": ""})
            self.assertEqual(rule.eval_as_user_id, self.officer)
            rule.with_user(self.manager).action_take_ownership()
            rule.invalidate_recordset()
            self.assertEqual(rule.eval_as_user_id, self.manager, model)

    def test_eval_as_user_id_client_write_only_accepted_for_self(self):
        """A direct write may only set the identity to the acting user; any other
        value is refused (the forgery guard from #379 stands). It raises rather
        than being dropped: a silent no-op returning True leaves an operator
        believing rules.write({"eval_as_user_id": new_owner.id}) re-homed them."""
        rule = self.env[ESCALATION].with_user(self.officer).create({"name": "Self only", "condition_cel": ""})
        with self.assertRaises(UserError):
            rule.with_user(self.manager).write({"eval_as_user_id": self.env.ref("base.user_admin").id})
        rule.invalidate_recordset()
        self.assertEqual(rule.eval_as_user_id, self.officer, "third-party identity must not take effect")
        rule.with_user(self.manager).write({"eval_as_user_id": self.manager.id})
        rule.invalidate_recordset()
        self.assertEqual(rule.eval_as_user_id, self.manager, "self identity is the take-ownership path")

    def test_archived_owner_rule_does_not_fire(self):
        """An offboarded (archived) owner's scope must not keep driving
        automation: the rule is skipped with a warning until someone takes
        ownership. Both engines."""
        officer_ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Officer ticket",
                "description": "In the officer's team",
                "partner_id": self.foreign_ticket.partner_id.id,
                "team_id": self.team_a.id,
                "severity": "critical",
            }
        )
        esc_rule = (
            self.env[ESCALATION]
            .with_user(self.officer)
            .create({"name": "Archived owner", "condition_cel": "", "escalate_to_user_id": self.officer.id})
        )
        route_rule = (
            self.env[ROUTING]
            .with_user(self.officer)
            .create({"name": "Archived owner", "condition_cel": "", "assign_user_id": self.officer.id})
        )
        self.officer.sudo().write({"active": False})

        with self.assertLogs("odoo.addons.spp_grm_cel.models.grm_escalation_rule", level="WARNING") as cm:
            self.env[ESCALATION].sudo().check_escalations()
        self.assertTrue(any("archived user" in line for line in cm.output), cm.output)
        officer_ticket.invalidate_recordset()
        self.assertFalse(officer_ticket.is_escalated)
        self.assertEqual(esc_rule.escalation_count, 0)

        with self.assertLogs("odoo.addons.spp_grm_cel.models.grm_routing_rule", level="WARNING") as cm:
            routed = self.env["spp.grm.ticket"].create(
                {
                    "name": "New ticket",
                    "description": "Routed after the owner was archived",
                    "partner_id": self.foreign_ticket.partner_id.id,
                    "team_id": self.team_a.id,
                }
            )
        self.assertTrue(any("archived user" in line for line in cm.output), cm.output)
        self.assertNotEqual(routed.user_id, self.officer)
        self.assertNotEqual(routed.routing_rule_id, route_rule)

    def test_escalation_counter_increments_under_owner_identity(self):
        """The escalation counter is incremented (atomically) when a manager's
        rule applies via the elevated path. Applied to one explicit ticket —
        not via the DB-wide check_escalations scan — so the +1 assertion stays
        valid if a fixture ever adds another open ticket."""
        rule = (
            self.env[ESCALATION]
            .with_user(self.manager)
            .create({"name": "Counter rule", "condition_cel": "", "escalate_severity": "high"})
        )
        before = rule.escalation_count
        applied = self.env[ESCALATION].sudo().apply_escalations(self.foreign_ticket)
        self.assertTrue(applied)
        rule.invalidate_recordset()
        self.assertEqual(rule.escalation_count, before + 1)
        self.foreign_ticket.invalidate_recordset()
        self.assertTrue(self.foreign_ticket.is_escalated)

    def test_entry_points_not_rpc_callable(self):
        """#381: all four rule-engine methods must be rejected for RPC dispatch."""
        from odoo.service.model import call_kw

        rule = self.env[ESCALATION].create({"name": "Dispatch probe", "condition_cel": ""})
        for model, method, args in [
            (ROUTING, "apply_routing", [self.foreign_ticket.id]),
            (ESCALATION, "apply_escalations", [self.foreign_ticket.id]),
            (ESCALATION, "apply_escalation", [[rule.id], self.foreign_ticket.id]),
            (ESCALATION, "check_escalations", []),
        ]:
            with self.assertRaises(AccessError):
                call_kw(self.env[model], method, args, {})
