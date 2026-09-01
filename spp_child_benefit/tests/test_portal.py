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
            return mother, child

        birthdate = fields.Date.today() - relativedelta(months=3, day=5)
        cls.mother_a, cls.child_a = family("A", birthdate)
        cls.mother_b, cls.child_b = family("B", birthdate)

        # Schedule for child A so the detail page has content
        program = env["spp.program"].create({"name": "Portal Test Programme", "target_type": "individual"})
        manager = env["spp.program.entitlement.manager.schedule"].create(
            {"name": "Scheduled Cash Entitlement", "program_id": program.id}
        )
        membership = env["spp.program.membership"].create(
            {"partner_id": cls.child_a.id, "program_id": program.id, "state": "draft"}
        )
        manager.ensure_schedule(membership)

        cls.portal_user = env["res.users"].create(
            {
                "name": cls.mother_a.name,
                "login": "portal_mother_a",
                "password": "portal_mother_a_pwd",
                "partner_id": cls.mother_a.id,
                "group_ids": [Command.set([env.ref("base.group_portal").id])],
            }
        )

    def test_portal_sees_own_children_only(self):
        self.authenticate("portal_mother_a", "portal_mother_a_pwd")
        response = self.url_open("/my/benefits")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Portal Child A", response.text)
        self.assertNotIn("Portal Child B", response.text)
        self.assertNotIn("Birth Order", response.text)

    def test_portal_child_detail_scoped(self):
        self.authenticate("portal_mother_a", "portal_mother_a_pwd")
        own = self.url_open(f"/my/benefits/child/{self.child_a.id}")
        self.assertEqual(own.status_code, 200)
        self.assertIn("Portal Child A", own.text)
        self.assertNotIn("Birth Order", own.text)
        other = self.url_open(f"/my/benefits/child/{self.child_b.id}")
        self.assertEqual(other.status_code, 404)

    def test_portal_requires_login(self):
        response = self.url_open("/my/benefits")
        # Anonymous users are redirected to login, never shown data
        self.assertIn("/web/login", response.url)
