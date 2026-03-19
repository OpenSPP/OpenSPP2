from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class MembershipTest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registrant_1 = cls.env["res.partner"].create(
            {
                "family_name": "Butay",
                "given_name": "Red",
                "name": "Red Butay",
                "is_group": False,
                "is_registrant": True,
            }
        )
        cls.kind_1 = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")
        cls.group_1 = cls.env["res.partner"].create(
            {
                "name": "Group 1",
                "is_group": True,
                "is_registrant": True,
                "group_type_id": cls.kind_1.id,
            }
        )
        cls.group_membership_1 = cls.env["spp.group.membership"].create(
            {
                "group": cls.group_1.id,
                "individual": cls.registrant_1.id,
                "start_date": fields.Datetime.now(),
            }
        )

    def test_compute_individual_domain_default(self):
        """Test domain when group type does NOT allow all member types (default)."""
        self.group_membership_1._compute_individual_domain()

        self.assertIsInstance(self.group_membership_1.individual_domain, list)
        self.assertEqual(len(self.group_membership_1.individual_domain), 2)
        self.assertIn(("is_registrant", "=", True), self.group_membership_1.individual_domain)
        self.assertIn(("is_group", "=", False), self.group_membership_1.individual_domain)

    def test_compute_individual_domain_allow_all(self):
        """Test domain when group type allows all member types (groups + individuals)."""
        # Create a non-system test vocabulary with a code that allows all member types
        test_vocab = self.env["spp.vocabulary"].create(
            {
                "name": "Test Group Type",
                "namespace_uri": "urn:test:group-type",
                "is_system": False,
            }
        )
        coop_type = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": test_vocab.id,
                "namespace_uri": "urn:test:group-type",
                "code": "test_coop",
                "display": "Test Cooperative",
                "allow_all_member_type": True,
            }
        )
        self.group_1.group_type_id = coop_type
        self.group_membership_1._compute_individual_domain()

        self.assertIsInstance(self.group_membership_1.individual_domain, list)
        self.assertEqual(len(self.group_membership_1.individual_domain), 2)
        self.assertIn(("is_registrant", "=", True), self.group_membership_1.individual_domain)
        self.assertIn(("id", "!=", self.group_membership_1.group.id), self.group_membership_1.individual_domain)

    def test_compute_individual_domain_no_type(self):
        """Test domain when group has no type set."""
        self.group_1.group_type_id = False
        self.group_membership_1._compute_individual_domain()

        self.assertIsInstance(self.group_membership_1.individual_domain, list)
        self.assertEqual(len(self.group_membership_1.individual_domain), 2)
        self.assertIn(("is_registrant", "=", True), self.group_membership_1.individual_domain)
        self.assertIn(("is_group", "=", False), self.group_membership_1.individual_domain)

    def test_open_member_form(self):
        member_form = self.group_membership_1.open_member_form()

        self.assertIsInstance(member_form, dict)
        self.assertEqual(member_form["name"], "Individual Member")
        self.assertEqual(member_form["view_mode"], "form")
        self.assertEqual(member_form["res_model"], "res.partner")
        self.assertEqual(member_form["res_id"], self.registrant_1.id)
        self.assertEqual(member_form["view_id"], self.env.ref("spp_registry.view_individuals_form").id)
        self.assertEqual(member_form["type"], "ir.actions.act_window")
        self.assertEqual(member_form["target"], "new")
        self.assertEqual(member_form["context"], {"default_is_group": False})
        self.assertEqual(member_form["flags"], {"mode": "readonly"})

        farm_id = self.env["res.partner"].create(
            {
                "family_name": "Test",
                "given_name": "Head",
                "name": "Test Head",
                "is_group": True,
                "is_registrant": True,
            }
        )
        membership = self.env["spp.group.membership"].create(
            {
                "group": self.registrant_1.id,
                "individual": farm_id.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [
                    Command.link(
                        self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head").id
                    )
                ],
            }
        )

        member_form = membership.open_member_form()
        self.assertIsInstance(member_form, dict)
        self.assertEqual(member_form["name"], "Group Membership")
        self.assertEqual(member_form["view_mode"], "form")
        self.assertEqual(member_form["res_model"], "res.partner")
        self.assertEqual(member_form["res_id"], farm_id.id)
        self.assertEqual(member_form["view_id"], self.env.ref("spp_registry.view_individuals_form").id)
        self.assertEqual(member_form["type"], "ir.actions.act_window")
        self.assertEqual(member_form["target"], "new")
        self.assertEqual(member_form["context"], {"default_is_group": True})
        self.assertEqual(member_form["flags"], {"mode": "readonly"})

        self.group_membership_1.individual = False
        with self.assertRaisesRegex(UserError, "A group or individual must be specified for this member."):
            self.group_membership_1.open_member_form()
