# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: GRM automation rules must not be writable by portal users.

Regression test for "Portal users can create global GRM automation rules": the
ACL granted ``base.group_portal`` read/write/create on ``spp.grm.routing.rule``
and ``spp.grm.escalation.rule``. These are global config models (no record
rules), and routing rules run on ticket creation while escalation rules run on
stage changes and via the hourly cron over all open tickets. A portal user could
therefore plant an always-matching rule via RPC and disrupt grievance handling
globally.

Portal users must never hold write/create/unlink. The retained portal READ row
is a current implementation dependency, not a security requirement: rule
evaluation runs as the acting user, and portal users can reach it by creating
or stage-writing tickets over direct RPC (they hold write/create on
``spp.grm.ticket``), so dropping read today would silently skip routing and
escalation on those paths. Tightening it requires moving rule evaluation to
``sudo()`` first — tracked in OpenSPP2 issue #413 together with the missing
portal record rule on ``spp.grm.ticket``. GRM staff retain full management.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

ROUTING_MODEL = "spp.grm.routing.rule"
ESCALATION_MODEL = "spp.grm.escalation.rule"


@tagged("post_install", "-at_install")
class TestGRMRuleAcl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "GRM Portal User",
                "login": "grm_portal_acl_test",
                "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
            }
        )
        # base.group_user matters: the spp_grm group chain links no user-type
        # group, so a manager without it would be created share=True (a
        # non-internal principal), and the staff tests below would not prove
        # that *internal* GRM staff retain management.
        cls.grm_manager = cls.env["res.users"].create(
            {
                "name": "GRM Manager",
                "login": "grm_manager_acl_test",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_grm.group_grm_manager").id),
                ],
            }
        )
        # An existing rule (created as admin) to test write access against.
        cls.routing_rule = cls.env[ROUTING_MODEL].create(
            {"name": "Test Routing Rule", "condition_cel": "severity == 'critical'"}
        )
        cls.escalation_rule = cls.env[ESCALATION_MODEL].create(
            {"name": "Test Escalation Rule", "condition_cel": "days_open > 3"}
        )

    def test_portal_user_cannot_create_routing_rule(self):
        """A portal user must NOT be able to create routing rules."""
        with self.assertRaises(AccessError):
            self.env[ROUTING_MODEL].with_user(self.portal_user).create({"name": "Portal Rule"})

    def test_portal_user_cannot_create_escalation_rule(self):
        """A portal user must NOT be able to create escalation rules."""
        with self.assertRaises(AccessError):
            self.env[ESCALATION_MODEL].with_user(self.portal_user).create({"name": "Portal Rule"})

    def test_portal_user_cannot_write_routing_rule(self):
        """A portal user must NOT be able to modify routing rules."""
        with self.assertRaises(AccessError):
            self.routing_rule.with_user(self.portal_user).write({"name": "Hijacked"})

    def test_portal_user_cannot_write_escalation_rule(self):
        """A portal user must NOT be able to modify escalation rules."""
        with self.assertRaises(AccessError):
            self.escalation_rule.with_user(self.portal_user).write({"name": "Hijacked"})

    def test_portal_user_can_read_rules(self):
        """Portal read is a CURRENT IMPLEMENTATION DEPENDENCY, not a security
        requirement: rule evaluation runs as the acting user, and portal users
        reach it via direct-RPC ticket create/stage-write. When rule evaluation
        moves to sudo() (issue #413), replace this with a read-denial test."""
        self.env[ROUTING_MODEL].with_user(self.portal_user).check_access("read")
        self.env[ESCALATION_MODEL].with_user(self.portal_user).check_access("read")

    def test_rule_readonly_caller_escalation_increments_counter(self):
        """A caller with read-only rule access must still get a fully applied
        escalation — the counter write runs with elevated rights. Regression
        test for the 19.0.2.0.1 sudo fix: with it reverted, the counter write
        raises AccessError and this test fails loudly."""
        rule = self.env[ESCALATION_MODEL].create({"name": "Counter Rule", "condition_cel": "severity == 'critical'"})
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Counter Test Ticket",
                "description": "Escalation counter regression",
                "partner_id": self.portal_user.partner_id.id,
                "severity": "critical",
            }
        )
        before = rule.escalation_count
        applied = (
            self.env[ESCALATION_MODEL].with_user(self.portal_user).apply_escalations(ticket.with_user(self.portal_user))
        )
        self.assertTrue(applied)
        self.assertEqual(rule.escalation_count, before + 1)
        self.assertTrue(ticket.is_escalated)

    def test_grm_manager_can_create_rules(self):
        """GRM staff must retain full management of both rule models."""
        routing = self.env[ROUTING_MODEL].with_user(self.grm_manager).create({"name": "Manager Routing Rule"})
        escalation = self.env[ESCALATION_MODEL].with_user(self.grm_manager).create({"name": "Manager Escalation Rule"})
        self.assertTrue(routing.id)
        self.assertTrue(escalation.id)
