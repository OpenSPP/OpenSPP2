# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBirthOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Vocab = cls.env["spp.vocabulary.code"]
        cls.type_family = Vocab.get_code("urn:openspp:vocab:group-type", "family")
        cls.role_head = Vocab.get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.role_child = cls.env.ref("spp_child_benefit.code_membership_type_child")
        cls.role_mother = cls.env.ref("spp_child_benefit.code_membership_type_mother")
        cls.Partner = cls.env["res.partner"]
        cls.Membership = cls.env["spp.group.membership"]

    def _individual(self, name, birthdate=None, citizen_by="descent", birth_sequence=0):
        return self.Partner.create(
            {
                "name": name,
                "is_registrant": True,
                "is_group": False,
                "birthdate": birthdate,
                "citizen_by": citizen_by,
                "birth_sequence": birth_sequence,
            }
        )

    def _family(self, name, mother, children):
        family = self.Partner.create(
            {
                "name": name,
                "is_registrant": True,
                "is_group": True,
                "group_type_id": self.type_family.id,
            }
        )
        self.Membership.create(
            {
                "group": family.id,
                "individual": mother.id,
                "membership_type_ids": [Command.set([self.role_head.id, self.role_mother.id])],
            }
        )
        for child in children:
            self.Membership.create(
                {
                    "group": family.id,
                    "individual": child.id,
                    "membership_type_ids": [Command.set([self.role_child.id])],
                }
            )
        return family

    def test_basic_ranking(self):
        mother = self._individual("Mother A", date(1994, 5, 1))
        k1 = self._individual("A1", date(2019, 1, 10))
        k2 = self._individual("A2", date(2021, 6, 20))
        k3 = self._individual("A3", date(2024, 7, 16))
        self._family("Family A", mother, [k1, k2, k3])
        self.assertEqual((k1.birth_order, k2.birth_order, k3.birth_order), (1, 2, 3))
        self.assertTrue(all(k.birth_order_state == "computed" for k in (k1, k2, k3)))
        self.assertEqual(mother.birth_order, 0)
        self.assertEqual(mother.birth_order_state, "none")

    def test_adopted_excluded(self):
        mother = self._individual("Mother B", date(1990, 2, 2))
        k1 = self._individual("B1", date(2018, 3, 1))
        k2 = self._individual("B2 adopted", date(2020, 4, 2), citizen_by="adopted")
        k3 = self._individual("B3", date(2023, 5, 3))
        self._family("Family B", mother, [k1, k2, k3])
        # Adopted child is excluded from the ranking entirely (BR-3 #7)
        self.assertEqual(k2.birth_order, 0)
        self.assertEqual(k2.birth_order_state, "none")
        self.assertEqual((k1.birth_order, k3.birth_order), (1, 2))

    def test_multiple_birth_with_sequence(self):
        # BR-3A example: one existing child, then twins -> twins rank 2 and 3
        mother = self._individual("Mother C", date(1992, 8, 8))
        k1 = self._individual("C1", date(2020, 1, 1))
        twin1 = self._individual("C twin 1", date(2024, 9, 9), birth_sequence=1)
        twin2 = self._individual("C twin 2", date(2024, 9, 9), birth_sequence=2)
        self._family("Family C", mother, [k1, twin1, twin2])
        self.assertEqual(k1.birth_order, 1)
        self.assertEqual(twin1.birth_order, 2)
        self.assertEqual(twin2.birth_order, 3)
        self.assertTrue(all(k.birth_order_state == "computed" for k in (twin1, twin2)))

    def test_twins_as_third_and_fourth_both_rank(self):
        # Two older siblings, then twins: they rank 3 and 4 individually (never
        # a shared rank), so both are at or above the third-child threshold.
        mother = self._individual("Mother C2", date(1990, 5, 5))
        k1 = self._individual("C2-1", date(2018, 3, 3))
        k2 = self._individual("C2-2", date(2021, 6, 6))
        twin1 = self._individual("C2 twin 1", date(2026, 2, 2), birth_sequence=1)
        twin2 = self._individual("C2 twin 2", date(2026, 2, 2), birth_sequence=2)
        self._family("Family C2", mother, [k1, k2, twin1, twin2])
        self.assertEqual((k1.birth_order, k2.birth_order), (1, 2))
        self.assertEqual(twin1.birth_order, 3)
        self.assertEqual(twin2.birth_order, 4)
        self.assertTrue(all(k.birth_order_state == "computed" for k in (twin1, twin2)))
        self.assertEqual(len({k.birth_order for k in (k1, k2, twin1, twin2)}), 4)

    def test_multiple_birth_without_sequence_pending(self):
        # BR-3A.6: no recorded sequence -> refer to PMU, no automatic rank
        mother = self._individual("Mother D", date(1991, 3, 3))
        k1 = self._individual("D1", date(2019, 2, 2))
        twin1 = self._individual("D twin 1", date(2023, 4, 4))
        twin2 = self._individual("D twin 2", date(2023, 4, 4))
        k4 = self._individual("D4", date(2025, 12, 1))
        self._family("Family D", mother, [k1, twin1, twin2, k4])
        self.assertEqual(k1.birth_order, 1)
        self.assertEqual(twin1.birth_order, 0)
        self.assertEqual(twin2.birth_order, 0)
        self.assertEqual(twin1.birth_order_state, "pending_determination")
        self.assertEqual(twin2.birth_order_state, "pending_determination")
        # The tie does not block ranking of a later-born sibling
        self.assertEqual(k4.birth_order, 4)
        self.assertEqual(k4.birth_order_state, "computed")

    def test_pmu_determination_resolves_pending(self):
        mother = self._individual("Mother E", date(1993, 6, 6))
        twin1 = self._individual("E twin 1", date(2024, 5, 5))
        twin2 = self._individual("E twin 2", date(2024, 5, 5))
        self._family("Family E", mother, [twin1, twin2])
        self.assertEqual(twin1.birth_order_state, "pending_determination")
        # PMU records the birth sequence (tracked field on the individual form)
        twin1.birth_sequence = 1
        twin2.birth_sequence = 2
        self.assertEqual((twin1.birth_order, twin2.birth_order), (1, 2))
        self.assertTrue(all(k.birth_order_state == "computed" for k in (twin1, twin2)))

    def test_new_member_triggers_recompute(self):
        mother = self._individual("Mother F", date(1995, 7, 7))
        k1 = self._individual("F1", date(2020, 10, 10))
        family = self._family("Family F", mother, [k1])
        self.assertEqual(k1.birth_order, 1)
        # A new baby arrives from the civil registry
        k2 = self._individual("F2", date(2026, 1, 15))
        self.Membership.create(
            {
                "group": family.id,
                "individual": k2.id,
                "membership_type_ids": [Command.set([self.role_child.id])],
            }
        )
        self.assertEqual(k2.birth_order, 2)
        # An earlier-born child surfaces later (late registration) and shifts ranks
        k0 = self._individual("F0", date(2018, 9, 9))
        self.Membership.create(
            {
                "group": family.id,
                "individual": k0.id,
                "membership_type_ids": [Command.set([self.role_child.id])],
            }
        )
        self.assertEqual((k0.birth_order, k1.birth_order, k2.birth_order), (1, 2, 3))

    def test_birthdate_change_triggers_recompute(self):
        mother = self._individual("Mother G", date(1990, 1, 1))
        k1 = self._individual("G1", date(2020, 3, 3))
        k2 = self._individual("G2", date(2022, 4, 4))
        self._family("Family G", mother, [k1, k2])
        self.assertEqual((k1.birth_order, k2.birth_order), (1, 2))
        # A date-of-birth correction swaps the order
        k1.birthdate = date(2023, 1, 1)
        self.assertEqual((k2.birth_order, k1.birth_order), (1, 2))

    def test_household_group_does_not_rank(self):
        household_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")
        k1 = self._individual("H1", date(2021, 2, 2))
        group = self.Partner.create(
            {
                "name": "Household H",
                "is_registrant": True,
                "is_group": True,
                "group_type_id": household_type.id,
            }
        )
        self.Membership.create(
            {
                "group": group.id,
                "individual": k1.id,
                "membership_type_ids": [Command.set([self.role_child.id])],
            }
        )
        self.assertEqual(k1.birth_order, 0)
        self.assertEqual(k1.birth_order_state, "none")

    def test_no_birthdate_not_ranked(self):
        mother = self._individual("Mother I", date(1992, 2, 2))
        k1 = self._individual("I1", date(2019, 6, 6))
        k2 = self._individual("I2 no dob")
        self._family("Family I", mother, [k1, k2])
        self.assertEqual(k1.birth_order, 1)
        self.assertEqual(k2.birth_order, 0)
        self.assertEqual(k2.birth_order_state, "none")
