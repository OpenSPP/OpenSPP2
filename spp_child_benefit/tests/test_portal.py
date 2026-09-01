# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestBenefitPortal(HttpCase):
    """Access scoping for the read-only benefit monitoring portal.

    The portal must show a family head exactly their own family's children —
    nothing from other families, no birth-order data, and no write paths.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Vocab = env["spp.vocabulary.code"]
        cls.type_family = Vocab.get_code("urn:openspp:vocab:group-type", "family")
        cls.role_head = Vocab.get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.role_child = env.ref("spp_child_benefit.code_membership_type_child")
        cls.role_mother = env.ref("spp_child_benefit.code_membership_type_mother")

        def family(tag, child_birthdate):
            mother = env["res.partner"].create(
                {
                    "name": f"Portal Mother {tag}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date(1992, 4, 2),
                }
            )
            child = env["res.partner"].create(
                {"name": f"Portal Child {tag}", "is_registrant": True, "is_group": False, "birthdate": child_birthdate}
            )
            group = env["res.partner"].create(
                {
                    "name": f"Portal Family {tag}",
                    "is_registrant": True,
                    "is_group": True,
                    "group_type_id": cls.type_family.id,
                }
            )
            env["spp.group.membership"].create(
                {
                    "group": group.id,
                    "individual": mother.id,
                    "membership_type_ids": [Command.set([cls.role_head.id, cls.role_mother.id])],
                }
            )
            env["spp.group.membership"].create(
                {"group": group.id, "individual": child.id, "membership_type_ids": [Command.set([cls.role_child.id])]}
            )
            role_father = env.ref("spp_child_benefit.code_membership_type_father")
            father = env["res.partner"].create(
                {
                    "name": f"Portal Father {tag}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date(1990, 1, 1),
                }
            )
            env["spp.group.membership"].create(
                {"group": group.id, "individual": father.id, "membership_type_ids": [Command.set([role_father.id])]}
            )
            return mother, father, child, group

        birthdate = fields.Date.today() - relativedelta(months=3, day=5)
        cls.mother_a, cls.father_a, cls.child_a, cls.group_a = family("A", birthdate)
        cls.mother_b, cls.father_b, cls.child_b, cls.group_b = family("B", birthdate)

        # Schedule for child A so the detail page has content
        program = env["spp.program"].create({"name": "Portal Test Programme", "target_type": "individual"})
        manager = env["spp.program.entitlement.manager.schedule"].create(
            {"name": "Scheduled Cash Entitlement", "program_id": program.id}
        )
        membership = env["spp.program.membership"].create(
            {"partner_id": cls.child_a.id, "program_id": program.id, "state": "draft"}
        )
        manager.ensure_schedule(membership)

        portal_group = env.ref("base.group_portal")

        def portal_login(partner, login):
            return env["res.users"].create(
                {
                    "name": partner.name,
                    "login": login,
                    "password": f"{login}_pwd",
                    "partner_id": partner.id,
                    "group_ids": [Command.set([portal_group.id])],
                }
            )

        cls.user_mother_a = portal_login(cls.mother_a, "portal_mother_a")
        cls.user_father_a = portal_login(cls.father_a, "portal_father_a")

    def test_portal_sees_own_children_only(self):
        self.authenticate("portal_mother_a", "portal_mother_a_pwd")
        response = self.url_open("/my/benefits")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Portal Child A", response.text)
        self.assertNotIn("Portal Child B", response.text)
        # No sibling-derived registry data on the page (assert on values,
        # not on a label string no template emits).
        self.assertEqual(self.child_a.birth_order, 1)
        self.assertNotIn("citizen", response.text.lower())
        self.assertNotIn("birth_order", response.text)

    def test_portal_child_detail_scoped(self):
        self.authenticate("portal_mother_a", "portal_mother_a_pwd")
        own = self.url_open(f"/my/benefits/child/{self.child_a.id}")
        self.assertEqual(own.status_code, 200)
        self.assertIn("Portal Child A", own.text)
        other = self.url_open(f"/my/benefits/child/{self.child_b.id}")
        self.assertEqual(other.status_code, 404)

    def test_portal_nonexistent_child_is_404(self):
        self.authenticate("portal_mother_a", "portal_mother_a_pwd")
        # A missing id and someone else's id take the identical path -> 404,
        # never a different code that would confirm existence.
        missing = self.url_open("/my/benefits/child/99999999")
        self.assertEqual(missing.status_code, 404)

    def test_father_role_is_not_a_payee(self):
        # F3: only head/mother roles are payees; a father sees nothing.
        self.authenticate("portal_father_a", "portal_father_a_pwd")
        response = self.url_open("/my/benefits")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Portal Child A", response.text)
        detail = self.url_open(f"/my/benefits/child/{self.child_a.id}")
        self.assertEqual(detail.status_code, 404)

    def test_ended_membership_revokes_access(self):
        # F2: access must drop once the head/mother membership has ended,
        # even though is_ended is a stored compute that would stay False.
        membership = self.env["spp.group.membership"].search(
            [("group", "=", self.group_a.id), ("individual", "=", self.mother_a.id)]
        )
        membership.write(
            {
                "start_date": fields.Datetime.now() - relativedelta(days=30),
                "ended_date": fields.Datetime.now() - relativedelta(days=1),
            }
        )
        self.authenticate("portal_mother_a", "portal_mother_a_pwd")
        response = self.url_open("/my/benefits")
        self.assertNotIn("Portal Child A", response.text)
        detail = self.url_open(f"/my/benefits/child/{self.child_a.id}")
        self.assertEqual(detail.status_code, 404)

    def test_namespace_confusion_role_denied(self):
        # F3: a same-named 'head' code from a different vocabulary must not
        # grant payee access.
        rel_head = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:relationship", "head")
        if not rel_head:
            self.skipTest("relationship 'head' code not present in this dataset")
        membership = self.env["spp.group.membership"].search(
            [("group", "=", self.group_b.id), ("individual", "=", self.father_b.id)]
        )
        membership.membership_type_ids = [Command.set([rel_head.id])]
        user = self.env["res.users"].create(
            {
                "name": self.father_b.name,
                "login": "portal_father_b",
                "password": "portal_father_b_pwd",
                "partner_id": self.father_b.id,
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        self.assertTrue(user)
        self.authenticate("portal_father_b", "portal_father_b_pwd")
        response = self.url_open("/my/benefits")
        self.assertNotIn("Portal Child B", response.text)

    def test_portal_requires_login(self):
        response = self.url_open("/my/benefits")
        # Anonymous users are redirected to login, never shown data
        self.assertIn("/web/login", response.url)
