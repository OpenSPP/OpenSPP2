# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: GRM automation rules must not be writable by portal users.

Regression test for "Portal users can create global GRM automation rules": the
ACL granted ``base.group_portal`` read/write/create on ``spp.grm.routing.rule``
and ``spp.grm.escalation.rule``. These are global config models (no record
rules), and routing rules run on ticket creation while escalation rules run on
stage changes and via the hourly cron over all open tickets. A portal user could
therefore plant an always-matching rule via RPC and disrupt grievance handling
globally.

Portal users must never hold write/create/unlink — and, as of #379, no read
either: rules now evaluate with their owner's identity (``eval_as_user_id``), so
the acting/portal user never needs to read them. Dropping the portal and
base-user read rows closes the rule-enumeration surface (#380). GRM staff retain
full management.
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

    def test_portal_user_cannot_read_rules(self):
        """Portal users have no read on the rule models. Rules are evaluated with
        their owner's identity (eval_as_user_id), so the acting/portal user never
        needs to read them — closing the enumeration surface (#380). The escalation
        counter write is exercised under owner identity in
        test_rule_owner_identity.py."""
        with self.assertRaises(AccessError):
            self.env[ROUTING_MODEL].with_user(self.portal_user).check_access("read")
        with self.assertRaises(AccessError):
            self.env[ESCALATION_MODEL].with_user(self.portal_user).check_access("read")

    def test_grm_manager_can_create_rules(self):
        """GRM staff must retain full management of both rule models."""
        routing = self.env[ROUTING_MODEL].with_user(self.grm_manager).create({"name": "Manager Routing Rule"})
        escalation = self.env[ESCALATION_MODEL].with_user(self.grm_manager).create({"name": "Manager Escalation Rule"})
        self.assertTrue(routing.id)
        self.assertTrue(escalation.id)
