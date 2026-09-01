# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_programs.models import constants


@tagged("post_install", "-at_install")
class TestDemoSetup(TransactionCase):
    """Verify the post_init_hook produced a complete, consistent demo environment."""

    def test_program_configured(self):
        program = self.env["spp.program"].search([("name", "=", "Child Benefit Programme")])
        self.assertEqual(len(program), 1)
        ent = program.get_manager(constants.MANAGER_ENTITLEMENT)
        self.assertEqual(ent._name, "spp.program.entitlement.manager.schedule")
        pay = program.get_manager(constants.MANAGER_PAYMENT)
        self.assertEqual(pay._name, "spp.program.payment.manager.csv")
        elig = program.eligibility_manager_ids.mapped("manager_ref_id")
        self.assertTrue(elig and elig[0].eligibility_mode == "cel")
        self.assertIn("birth_order", elig[0].cel_expression)
        fund = self.env["spp.program.fund"].search([("program_id", "=", program.id), ("state", "=", "posted")])
        self.assertTrue(fund)

    def test_families_and_birth_orders(self):
        families = self.env["res.partner"].search([("name", "like", "Demo Family%"), ("is_group", "=", True)])
        self.assertEqual(len(families), 8)

        def child(name):
            return self.env["res.partner"].search([("name", "=", name)], limit=1)

        self.assertEqual(child("Child One-C").birth_order, 3)
        self.assertEqual(child("Child Four-Twin2").birth_order, 3)
        self.assertEqual(child("Child Five-B").birth_order, 0)  # adopted, excluded
        self.assertEqual(child("Child Five-D").birth_order, 3)  # ranks shift past adopted sibling
        self.assertEqual(child("Child Six-Twin1").birth_order_state, "pending_determination")
        self.assertEqual(child("Child Seven-C").birth_order_state, "none")  # no date of birth
        self.assertEqual(child("Child Eight-D").birth_order, 4)

    def test_eligible_children_enrolled_with_schedules(self):
        program = self.env["spp.program"].search([("name", "=", "Child Benefit Programme")])
        memberships = self.env["spp.program.membership"].search([("program_id", "=", program.id)])
        enrolled = memberships.filtered(lambda m: m.state == "enrolled")
        expected = {"Child One-C", "Child Two-C", "Child Four-Twin2", "Child Five-D", "Child Eight-D"}
        self.assertEqual(set(enrolled.mapped("partner_id.name")), expected)
        schedules = self.env["spp.entitlement.schedule"].search(
            [("program_id", "=", program.id), ("state", "=", "active")]
        )
        self.assertEqual(set(schedules.mapped("partner_id.name")), expected)
        for schedule in schedules:
            self.assertEqual(schedule.line_count, 37)

    def test_cycle_and_grievance(self):
        program = self.env["spp.program"].search([("name", "=", "Child Benefit Programme")])
        cycle = self.env["spp.cycle"].search([("program_id", "=", program.id)])
        self.assertEqual(len(cycle), 1)
        self.assertEqual(
            self.env["spp.cycle.membership"].search_count([("cycle_id", "=", cycle.id)]),
            5,
        )
        self.assertTrue(self.env["spp.grm.ticket"].search_count([]))
        self.assertEqual(self.env["res.users"].search_count([("login", "in", ["officer", "manager"])]), 2)
        portal_user = self.env["res.users"].search([("login", "=", "parent")])
        self.assertTrue(portal_user)
        self.assertEqual(portal_user.partner_id.name, "Mother One")

    def test_portal_grievance_acl_hardened(self):
        """F1: the portal login must not be able to read other people's
        grievances or write/create tickets over RPC."""
        from odoo.exceptions import AccessError

        portal_user = self.env["res.users"].search([("login", "=", "parent")], limit=1)
        self.assertTrue(portal_user)
        Ticket = self.env["spp.grm.ticket"].with_user(portal_user)

        # Portal group has no write and no create on tickets
        self.assertFalse(Ticket.has_access("write"))
        self.assertFalse(Ticket.has_access("create"))

        # And an ir.rule scopes reads to the user's own partner: a ticket
        # belonging to someone else is invisible, not merely hidden in a view.
        other_ticket = self.env["spp.grm.ticket"].search([("partner_id", "!=", portal_user.partner_id.id)], limit=1)
        if other_ticket:
            self.assertFalse(Ticket.search([("id", "=", other_ticket.id)]))

        # Team roster and SLA rules are not readable by the portal group.
        with self.assertRaises(AccessError):
            self.env["spp.grm.team"].with_user(portal_user).search([])
