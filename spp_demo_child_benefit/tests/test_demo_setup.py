# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_demo_child_benefit.models.demo_setup import EXTRA_FAMILY_PROFILES, expected_qualified_count
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
        # Entitlements auto-approve so the demo flows straight to payment.
        cycle_mgr = program.get_manager(constants.MANAGER_CYCLE)
        self.assertTrue(cycle_mgr.auto_approve_entitlements)
        fund = self.env["spp.program.fund"].search([("program_id", "=", program.id), ("state", "=", "posted")])
        self.assertTrue(fund)
        # The programme must have a journal with a currency, or the payment
        # run cannot derive an entitlement currency and will fail.
        self.assertTrue(program.journal_id, "programme has no journal")
        self.assertTrue(program.journal_id.currency_id, "programme journal has no currency")

    def test_families_and_birth_orders(self):
        # The 8 curated families (edge cases) are always present.
        curated = self.env["res.partner"].search([("name", "like", "Demo Family%"), ("is_group", "=", True)])
        self.assertEqual(len(curated), 8)
        # Plus the extra population families.
        all_families = self.env["res.partner"].search([("is_group", "=", True), ("group_type_id.code", "=", "family")])
        self.assertEqual(len(all_families), 8 + len(EXTRA_FAMILY_PROFILES))

        def child(name):
            return self.env["res.partner"].search([("name", "=", name)], limit=1)

        self.assertEqual(child("Child One-C").birth_order, 3)
        self.assertEqual(child("Child Four-Twin2").birth_order, 3)
        self.assertEqual(child("Child Five-B").birth_order, 0)  # adopted, excluded
        self.assertEqual(child("Child Five-D").birth_order, 3)  # ranks shift past adopted sibling
        self.assertEqual(child("Child Six-Twin1").birth_order_state, "pending_determination")
        self.assertEqual(child("Child Seven-C").birth_order_state, "none")  # no date of birth
        self.assertEqual(child("Child Eight-D").birth_order, 4)

    def test_individuals_have_name_parts(self):
        # The registry stores given/family name parts alongside the display
        # name; the generator must fill all of them.
        mother = self.env["res.partner"].search([("name", "=", "Mother One")], limit=1)
        self.assertEqual((mother.given_name, mother.family_name), ("Mother", "One"))
        kid = self.env["res.partner"].search([("name", "=", "Child One-C")], limit=1)
        self.assertEqual((kid.given_name, kid.family_name), ("Child", "One-C"))

    def test_eligible_children_enrolled_with_schedules(self):
        program = self.env["spp.program"].search([("name", "=", "Child Benefit Programme")])
        memberships = self.env["spp.program.membership"].search([("program_id", "=", program.id)])
        enrolled = memberships.filtered(lambda m: m.state == "enrolled")
        # The curated 5 qualified children are always enrolled...
        curated = {"Child One-C", "Child Two-C", "Child Four-Twin2", "Child Five-D", "Child Eight-D"}
        self.assertTrue(curated.issubset(set(enrolled.mapped("partner_id.name"))))
        # ...alongside the extra population, for a deterministic total.
        self.assertEqual(len(enrolled), expected_qualified_count())
        schedules = self.env["spp.entitlement.schedule"].search(
            [("program_id", "=", program.id), ("state", "=", "active")]
        )
        self.assertEqual(len(schedules), expected_qualified_count())
        for schedule in schedules:
            self.assertEqual(schedule.line_count, 37)
        # Before any cycle runs every month is "Scheduled", and the badge tone
        # behind the translated label is a stable code.
        lines = schedules.mapped("line_ids")
        self.assertEqual(set(lines.mapped("payment_status")), {"Scheduled"})
        self.assertEqual(set(lines.mapped("payment_status_tone")), {"neutral"})

    def test_cycle_and_grievance(self):
        program = self.env["spp.program"].search([("name", "=", "Child Benefit Programme")])
        cycle = self.env["spp.cycle"].search([("program_id", "=", program.id)])
        self.assertEqual(len(cycle), 1)
        # The cycle itself must carry auto-approve (its own flag drives it, not
        # only the manager's) so the demo flows straight to payment.
        self.assertTrue(cycle.auto_approve_entitlements)
        # Cycle members are the children with a benefit installment in the
        # cycle's month (children born after the cycle month join later), so
        # the count is derived from the schedule lines in that month.
        july_beneficiaries = (
            self.env["spp.entitlement.schedule.line"]
            .search(
                [
                    ("schedule_id.state", "=", "active"),
                    ("benefit_month", ">=", cycle.start_date.replace(day=1)),
                    ("benefit_month", "<=", cycle.end_date),
                ]
            )
            .mapped("partner_id")
        )
        self.assertTrue(july_beneficiaries)
        self.assertEqual(
            self.env["spp.cycle.membership"].search_count([("cycle_id", "=", cycle.id)]),
            len(july_beneficiaries),
        )
        self.assertEqual(self.env["res.users"].search_count([("login", "in", ["officer", "manager"])]), 2)
        portal_user = self.env["res.users"].search([("login", "=", "parent")])
        self.assertTrue(portal_user)
        self.assertEqual(portal_user.partner_id.name, "Mother One")
        # Portal logins for a spread of families, including one with no
        # qualifying children (the empty-state demo).
        for login in ("parent", "gurung", "dahal", "no-benefit"):
            user = self.env["res.users"].search([("login", "=", login)], limit=1)
            self.assertTrue(user, f"portal login {login} missing")
            self.assertTrue(user.has_group("base.group_portal"))

    def test_grievances_open_and_resolved(self):
        """The GRM beat needs one open ticket to work through and one already
        resolved ticket to show a completed grievance history."""
        tickets = self.env["spp.grm.ticket"].search([])
        self.assertEqual(len(tickets), 2)
        open_ticket = tickets.filtered(lambda t: not t.is_closed)
        resolved = tickets.filtered(lambda t: t.is_closed)
        self.assertEqual(len(open_ticket), 1)
        self.assertEqual(len(resolved), 1)
        # The open ticket waits for an officer; the install user must not
        # appear as its assignee.
        self.assertFalse(open_ticket.user_id)
        self.assertEqual(resolved.user_id.login, "officer")
        self.assertEqual(resolved.stage_id.stage_type, "resolved")
        self.assertTrue(resolved.resolution_summary)
        self.assertTrue(resolved.closed_date)
        # Each ticket belongs to a portal login so both show up in the portal.
        parent = self.env["res.users"].search([("login", "=", "parent")], limit=1)
        gurung = self.env["res.users"].search([("login", "=", "gurung")], limit=1)
        self.assertEqual(open_ticket.partner_id, parent.partner_id)
        self.assertEqual(resolved.partner_id, gurung.partner_id)
        # Registrant and household are what the registrant/family records
        # count, so both seeded tickets must carry them.
        for ticket in tickets:
            self.assertEqual(ticket.registrant_id, ticket.partner_id)
            self.assertTrue(ticket.household_id.is_group)
            self.assertIn(ticket.registrant_id, ticket.household_id.group_membership_ids.mapped("individual"))

    def _loaded_root_menus(self, user):
        menus = self.env["ir.ui.menu"].with_user(user).load_menus(False)
        return {menus[c]["name"] for c in menus["root"]["children"]}, menus

    def test_demo_installs_every_menu_the_demo_needs(self):
        """The demo module must pull in everything the storyline clicks through.

        Uses load_menus (not _visible_menu_ids): the web client prunes menus
        whose ancestors are invisible or empty, and only load_menus applies
        that pruning. A root menu with no action and no visible children -
        e.g. Registry without spp_registry_search - silently disappears.
        """
        admin = self.env.ref("base.user_admin")
        roots, menus = self._loaded_root_menus(admin)
        for expected in ["Registry", "Programs", "Area", "Helpdesk", "Audit Log", "Approvals", "Change Requests"]:
            self.assertIn(expected, roots, f"'{expected}' root menu missing for admin")

        registry_root = self.env.ref("spp_registry.spp_main_menu_root")
        self.assertIn(registry_root.id, menus, "Registry root pruned (no visible children)")
        self.assertTrue(
            menus[registry_root.id]["children"],
            "Registry root has no visible children - registry browsing is unreachable",
        )

        schedule_menu = self.env.ref("spp_child_benefit.menu_entitlement_schedule")
        self.assertIn(schedule_menu.id, menus, "Benefit Schedules menu not reachable for admin")

    def test_demo_users_see_their_menus(self):
        for login in ("officer", "manager"):
            user = self.env["res.users"].search([("login", "=", login)], limit=1)
            self.assertTrue(user, f"demo user {login} missing")
            self.assertTrue(
                user.has_group("base.group_user"),
                f"demo user {login} is not an internal user and cannot use the back office",
            )
            roots, _ = self._loaded_root_menus(user)
            for expected in ("Programs", "Registry", "Change Requests"):
                self.assertIn(expected, roots, f"'{expected}' missing for {login}")

    def test_change_request_beat(self):
        """Base change-request types carry an approval workflow, and one
        request awaits the manager: officer submits, manager approves."""
        CRType = self.env["spp.change.request.type"]
        for code in ("edit_individual", "edit_group", "update_id"):
            cr_type = CRType.search([("code", "=", code)], limit=1)
            self.assertTrue(cr_type, f"CR type {code} missing")
            self.assertEqual(cr_type.approval_definition_id.approval_group_id.name, "Manager")
        # The advanced pack is deliberately not part of the demo.
        self.assertFalse(CRType.search([("code", "=", "exit_registrant")]))
        pending = self.env["spp.change.request"].search([("approval_state", "=", "pending")])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending.request_type_id.code, "edit_individual")
        self.assertEqual(pending.registrant_id.name, "Mother One")
        self.assertTrue(pending.approval_review_ids.filtered(lambda r: r.status == "pending"))
        detail = pending.get_detail()
        self.assertEqual(detail.phone, "+000 17 654 321")
        # Master record untouched until approved.
        self.assertNotEqual(pending.registrant_id.phone, "+000 17 654 321")
        officer = self.env["res.users"].search([("login", "=", "officer")], limit=1)
        manager = self.env["res.users"].search([("login", "=", "manager")], limit=1)
        self.assertEqual(pending.create_uid, officer)
        self.assertFalse(officer.has_group("spp_change_request_v2.group_cr_validator"))
        self.assertTrue(manager.has_group("spp_change_request_v2.group_cr_validator"))
        # Approvers are the group's explicit members, so the manager must be
        # a direct member of the approval group, not just an implied one.
        self.assertIn(manager, pending.request_type_id.approval_definition_id.get_approvers(pending))
        self.assertNotIn(officer, pending.request_type_id.approval_definition_id.get_approvers(pending))

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
