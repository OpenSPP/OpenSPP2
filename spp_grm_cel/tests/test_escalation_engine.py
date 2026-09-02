# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Escalation engine behaviour under owner-identity evaluation.

Covers the engine mechanics around #379's owner-identity model: what happens
when a rule's side effects are denied to its owner, how the hourly pass isolates
failures, that a rule applies once per ticket, that the SLA-breach path (which
runs from a stored compute and is deferred to precommit) behaves in batches, and
that the "Check Escalation" button works for users who cannot read the rules.
"""

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

ESCALATION = "spp.grm.escalation.rule"
ESC_LOGGER = "odoo.addons.spp_grm_cel.models.grm_escalation_rule"
TICKET_LOGGER = "odoo.addons.spp_grm_cel.models.grm_ticket"
GRM_TICKET_LOGGER = "odoo.addons.spp_grm.models.grm_ticket"


@tagged("post_install", "-at_install")
class TestEscalationEngine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]
        internal = cls.env.ref("base.group_user")
        officer = cls.env.ref("spp_grm.group_grm_officer")
        manager = cls.env.ref("spp_grm.group_grm_manager")
        cls.officer = Users.create(
            {
                "name": "Engine Officer",
                "login": "grm_engine_officer",
                "group_ids": [Command.link(internal.id), Command.link(officer.id)],
            }
        )
        cls.manager = Users.create(
            {
                "name": "Engine Manager",
                "login": "grm_engine_manager",
                "group_ids": [Command.link(internal.id), Command.link(manager.id)],
            }
        )
        cls.plain_internal = Users.create(
            {
                "name": "Engine Plain Internal",
                "login": "grm_engine_plain",
                "group_ids": [Command.link(internal.id)],
            }
        )
        Team = cls.env["spp.grm.team"]
        cls.team_a = Team.create({"name": "Engine Team A", "member_ids": [Command.link(cls.officer.id)]})
        cls.team_b = Team.create({"name": "Engine Team B"})
        cls.partner = cls.env["res.partner"].create({"name": "Engine Complainant"})

    def _ticket(self, name, team=None, **extra):
        vals = {
            "name": name,
            "description": name,
            "partner_id": self.partner.id,
            "team_id": (team or self.team_a).id,
            "severity": "critical",
        }
        vals.update(extra)
        return self.env["spp.grm.ticket"].create(vals)

    def _officer_rule(self, **vals):
        base = {"name": "Officer rule", "condition_cel": "", "trigger_after_hours": 0}
        base.update(vals)
        return self.env[ESCALATION].with_user(self.officer).create(base)

    def _manager_rule(self, **vals):
        base = {"name": "Manager rule", "condition_cel": "", "trigger_after_hours": 0}
        base.update(vals)
        return self.env[ESCALATION].with_user(self.manager).create(base)

    def _breach_batch(self, batch):
        """Move the batch to a category whose SLA is already past: sla_deadline
        and sla_status recompute for the whole batch in one compute call, each
        breach schedules the hook, and the flush's precommit stage runs it."""
        past = self.env["spp.grm.ticket.category"].create({"name": "Past SLA", "default_sla_hours": -1})
        self.env.flush_all()
        batch.write({"category_id": past.id})
        # cr.flush() is what commit does: run the pending computes (which
        # schedule the breach hooks), then the precommit hooks.
        self.env.cr.flush()
        batch.invalidate_recordset()

    def _db_rows(self, batch):
        self.env.cr.execute(
            "SELECT id, sla_status, is_escalated, team_id, severity FROM spp_grm_ticket WHERE id IN %s ORDER BY id",
            (tuple(batch.ids),),
        )
        return self.env.cr.fetchall()

    # ---- SLA-breach path: batch compute, savepoint rollbacks, precommit deferral

    @mute_logger(GRM_TICKET_LOGGER, ESC_LOGGER, TICKET_LOGGER)
    def test_batch_breach_out_of_scope_rule_rolls_back_every_ticket(self):
        """An officer-owned rule reassigning tickets out of the officer's own
        scope is rolled back for each ticket of a batch breach; the batch's
        computed sla_status survives intact."""
        self._officer_rule(escalate_to_team_id=self.team_b.id)
        batch = self._ticket("t1") | self._ticket("t2") | self._ticket("t3")
        self.env.flush_all()
        self.assertEqual([t.sla_status for t in batch], ["on_track"] * 3)
        self._breach_batch(batch)
        rows = self._db_rows(batch)
        self.assertEqual([r[1] for r in rows], ["breached"] * 3, rows)
        self.assertEqual([r[2] for r in rows], [False] * 3, rows)
        self.assertEqual([r[3] for r in rows], [self.team_a.id] * 3, rows)
        self.assertEqual([t.sla_status for t in batch], ["breached"] * 3)

    @mute_logger(GRM_TICKET_LOGGER, ESC_LOGGER, TICKET_LOGGER)
    def test_batch_breach_in_scope_rule_applies_to_every_ticket(self):
        self._manager_rule(escalate_severity="critical")
        batch = (
            self._ticket("t1", severity="low") | self._ticket("t2", severity="low") | self._ticket("t3", severity="low")
        )
        self.env.flush_all()
        self._breach_batch(batch)
        rows = self._db_rows(batch)
        self.assertEqual([r[1] for r in rows], ["breached"] * 3, rows)
        self.assertEqual([r[2] for r in rows], [True] * 3, rows)
        self.assertEqual([r[4] for r in rows], ["critical"] * 3, rows)

    @mute_logger(GRM_TICKET_LOGGER, ESC_LOGGER, TICKET_LOGGER)
    def test_batch_breach_mixed_scope(self):
        """t2 sits in team B (owner cannot read it -> rule does not apply);
        its in-scope neighbours are escalated and keep their values."""
        self._officer_rule(escalate_to_user_id=self.officer.id)
        batch = self._ticket("t1") | self._ticket("t2", team=self.team_b) | self._ticket("t3")
        self.env.flush_all()
        self._breach_batch(batch)
        rows = self._db_rows(batch)
        self.assertEqual([r[1] for r in rows], ["breached"] * 3, rows)
        self.assertEqual([r[2] for r in rows], [True, False, True], rows)

    @mute_logger(GRM_TICKET_LOGGER, ESC_LOGGER, TICKET_LOGGER)
    def test_breach_hook_is_deferred_out_of_the_compute(self):
        """Inside the transaction, right after the write that breaches the SLA,
        nothing has been escalated yet: the engine runs at precommit."""
        self._manager_rule(escalate_severity="critical")
        ticket = self._ticket("deferred", severity="low")
        past = self.env["spp.grm.ticket.category"].create({"name": "Past SLA", "default_sla_hours": -1})
        self.env.flush_all()
        ticket.write({"category_id": past.id})
        self.assertEqual(ticket.sla_status, "breached")  # compute ran, hook only scheduled
        self.assertFalse(ticket.is_escalated)
        self.env.cr.flush()
        self.assertTrue(ticket.is_escalated)
        self.assertEqual(ticket.severity, "critical")

    # ---- side effects the owner is not entitled to fail the escalation closed

    @mute_logger(ESC_LOGGER)
    def test_case_creation_denied_to_owner_rolls_escalation_back(self):
        """An officer without case-management rights owns a rule with
        create_case: the case create is denied, so the escalation is rolled
        back and reported as not applied — never 'applied' with no case."""
        case_type = self.env["spp.case.type"].create({"name": "Escalation", "code": "ESC"})
        rule = self._officer_rule(create_case=True, case_type_id=case_type.id, escalate_to_user_id=self.officer.id)
        ticket = self._ticket("case denied")
        applied = self.env[ESCALATION].sudo().apply_escalations(ticket)
        self.assertFalse(applied)
        ticket.invalidate_recordset()
        self.assertFalse(ticket.is_escalated)
        self.assertEqual(rule.escalation_count, 0)
        self.assertFalse(self.env["spp.case"].sudo().search([("name", "ilike", ticket.number)]))

    @mute_logger(ESC_LOGGER)
    def test_case_creation_by_entitled_owner_creates_case(self):
        """A superuser-owned rule (shell/data-load created) with create_case
        actually creates the case, with the required case worker set."""
        case_type = self.env["spp.case.type"].create({"name": "Escalation", "code": "ESC"})
        self.env[ESCALATION].create(
            {"name": "Case rule", "condition_cel": "", "create_case": True, "case_type_id": case_type.id}
        )
        ticket = self._ticket("case created", user_id=self.officer.id)
        applied = self.env[ESCALATION].sudo().apply_escalations(ticket)
        self.assertTrue(applied)
        case = self.env["spp.case"].sudo().search([("name", "ilike", ticket.number)])
        self.assertEqual(len(case), 1)
        self.assertEqual(case.case_worker_id, self.officer)
        self.assertEqual(case.partner_id, self.partner)

    def test_notification_sent_under_owner_identity(self):
        model = self.env["ir.model"]._get("spp.grm.ticket")
        template = self.env["mail.template"].create(
            {
                "name": "Escalation template",
                "model_id": model.id,
                "subject": "Escalated {{ object.number }}",
                "body_html": "<p>Escalated</p>",
                "email_to": "escalations@example.com",
            }
        )
        self._officer_rule(
            should_send_notification=True,
            notification_template_id=template.id,
            escalate_to_user_id=self.officer.id,
        )
        ticket = self._ticket("notified")
        Mail = self.env["mail.mail"].sudo()
        domain = [("model", "=", "spp.grm.ticket"), ("res_id", "=", ticket.id)]
        before = Mail.search_count(domain)
        self.assertTrue(self.env[ESCALATION].sudo().apply_escalations(ticket))
        self.assertEqual(Mail.search_count(domain) - before, 1)

    # ---- pass-level behaviour

    @mute_logger(ESC_LOGGER)
    def test_rule_applies_once_per_ticket(self):
        rule = self._manager_rule(escalate_severity="critical")
        ticket = self._ticket("once", severity="low")
        self.env[ESCALATION].sudo().check_escalations()
        self.env[ESCALATION].sudo().check_escalations()
        rule.invalidate_recordset()
        posts = (
            self.env["mail.message"]
            .sudo()
            .search_count(
                [("model", "=", "spp.grm.ticket"), ("res_id", "=", ticket.id), ("subject", "=", "Ticket Escalated")]
            )
        )
        self.assertEqual((rule.escalation_count, posts), (1, 1))

    def test_one_failing_ticket_does_not_abort_the_pass(self):
        rule = self._manager_rule(escalate_severity="critical")
        failing = self._ticket("failing", severity="low")
        healthy = self._ticket("healthy", severity="low")
        Model = self.env.registry[ESCALATION]
        original = Model.apply_escalation

        def flaky(rule_rec, ticket):
            if ticket.id == failing.id:
                raise UserError(self.env._("simulated constraint failure"))
            return original(rule_rec, ticket)

        with patch.object(Model, "apply_escalation", flaky), self.assertLogs(ESC_LOGGER, level="ERROR") as cm:
            self.env[ESCALATION].sudo().check_escalations()
        self.assertTrue(any("rolled back and skipped" in line for line in cm.output), cm.output)
        (failing | healthy).invalidate_recordset()
        self.assertFalse(failing.is_escalated)
        self.assertTrue(healthy.is_escalated)
        rule.invalidate_recordset()
        self.assertEqual(rule.escalation_count, 1)

    def test_owner_warnings_logged_once_per_pass(self):
        """A superuser-owned rule is warned about once per cron pass, not once
        per open ticket."""
        self.env[ESCALATION].create({"name": "Shell-created rule", "condition_cel": "severity == 'nonexistent'"})
        self._ticket("t1")
        self._ticket("t2")
        with self.assertLogs(ESC_LOGGER, level="WARNING") as cm:
            self.env[ESCALATION].sudo().check_escalations()
        hits = [line for line in cm.output if "Shell-created rule" in line and "owned by the superuser" in line]
        self.assertEqual(len(hits), 1, cm.output)

    def test_check_escalation_button_for_user_without_rule_access(self):
        """A plain internal user (no GRM group, no read on the rules) presses
        "Check Escalation": the engine loads the rules itself and applies a
        manager's rule with the manager's identity — no swallowed AccessError."""
        self._manager_rule(escalate_severity="critical")
        ticket = self._ticket("button", severity="low")
        with self.assertNoLogs(TICKET_LOGGER, level="ERROR"):
            res = ticket.with_user(self.plain_internal).action_escalate()
        self.assertEqual(res["params"]["type"], "info")
        ticket.invalidate_recordset()
        self.assertTrue(ticket.is_escalated)
