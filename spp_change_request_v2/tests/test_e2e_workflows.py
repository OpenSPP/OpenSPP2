# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""End-to-End workflow tests for Change Request system.

These tests cover complete real-world scenarios that may span multiple
CR types and verify the system works correctly in production-like conditions.
"""

from odoo import Command, fields
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type, get_or_create_membership_kind


class TestE2EWorkflows(TransactionCase):
    """End-to-End workflow tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.id_model = cls.env["spp.registry.id"]
        cls.id_type_model = cls.env["spp.id.type"]
        cls.cr_model = cls.env["spp.change.request"]

        # Get head membership kind from vocabulary
        cls.head_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

        # Get or create spouse/child kinds from vocabulary
        cls.spouse_kind = get_or_create_membership_kind(cls.env, "spouse")
        cls.child_kind = get_or_create_membership_kind(cls.env, "child")

        # Create ID type
        cls.national_id = cls.id_type_model.create(
            {
                "name": "E2E National ID",
                "namespace_uri": "urn:test:e2e-national-id",
            }
        )

        # Get or create CR types
        cls.add_member_type = get_or_create_cr_type(cls.env, "add_member")
        cls.remove_member_type = get_or_create_cr_type(cls.env, "remove_member")
        cls.change_hoh_type = get_or_create_cr_type(cls.env, "change_hoh")
        cls.exit_registrant_type = get_or_create_cr_type(cls.env, "exit_registrant")
        cls.transfer_member_type = get_or_create_cr_type(cls.env, "transfer_member")
        cls.update_id_type = get_or_create_cr_type(cls.env, "update_id")
        cls.create_group_type = get_or_create_cr_type(cls.env, "create_group")
        cls.split_household_type = get_or_create_cr_type(cls.env, "split_household")
        cls.merge_registrants_type = get_or_create_cr_type(cls.env, "merge_registrants")

    def _approve_and_apply(self, cr):
        """Helper to approve and apply a CR."""
        cr.approval_state = "approved"
        cr.action_apply()
        return cr

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 1: New household registration flow
    # ═══════════════════════════════════════════════════════════════════════════

    def test_scenario_new_household_registration(self):
        """
        Scenario: Register a new household with head and add members.

        Steps:
        1. Create new group via CR
        2. Add spouse member
        3. Add child members
        4. Add ID documents
        """
        # Step 1: Create new group with head
        placeholder = self.partner_model.create(
            {
                "name": "Placeholder",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cr1 = self.cr_model.create(
            {
                "request_type_id": self.create_group_type.id,
                "registrant_id": placeholder.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "group_name": "Dela Cruz Household",
                "create_new_head": True,
                "head_given_name": "Juan",
                "head_family_name": "Dela Cruz",
                "head_name": "Juan Dela Cruz",
                "address_line1": "123 Mabini St",
                "city": "Quezon City",
                "phone": "+639123456789",
            }
        )
        self._approve_and_apply(cr1)

        household = detail1.created_group_id
        self.assertTrue(household)
        self.assertEqual(household.name, "Dela Cruz Household")

        # Find the head
        head_membership = self.membership_model.search(
            [
                ("group", "=", household.id),
                ("status", "=", "active"),
            ]
        )
        head = head_membership.individual
        self.assertEqual(head.name, "DELA CRUZ, JUAN")

        # Step 2: Add spouse
        cr2 = self.cr_model.create(
            {
                "request_type_id": self.add_member_type.id,
                "registrant_id": household.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "Maria",
                "family_name": "Dela Cruz",
                "member_name": "Maria Dela Cruz",
                "relationship_id": self.spouse_kind.id,
            }
        )
        self._approve_and_apply(cr2)

        spouse = detail2.created_individual_id
        self.assertEqual(spouse.name, "DELA CRUZ, MARIA")

        # Step 3: Add children
        for i, name in enumerate(["Pedro", "Ana"]):
            cr = self.cr_model.create(
                {
                    "request_type_id": self.add_member_type.id,
                    "registrant_id": household.id,
                }
            )
            detail = cr.get_detail()
            detail.write(
                {
                    "given_name": name,
                    "family_name": "Dela Cruz",
                    "member_name": f"{name} Dela Cruz",
                    "relationship_id": self.child_kind.id,
                }
            )
            self._approve_and_apply(cr)

        # Verify household has 4 members
        memberships = self.membership_model.search(
            [
                ("group", "=", household.id),
                ("status", "=", "active"),
            ]
        )
        self.assertEqual(len(memberships), 4)

        # Step 4: Add ID to head
        cr4 = self.cr_model.create(
            {
                "request_type_id": self.update_id_type.id,
                "registrant_id": head.id,
            }
        )
        detail4 = cr4.get_detail()
        detail4.write(
            {
                "operation": "add",
                "id_type_id": self.national_id.id,
                "id_value": "NID-2024-001",
            }
        )
        self._approve_and_apply(cr4)

        # Verify ID added
        head_id = self.id_model.search(
            [
                ("partner_id", "=", head.id),
                ("id_type_id", "=", self.national_id.id),
            ]
        )
        self.assertTrue(head_id)
        self.assertEqual(head_id.value, "NID-2024-001")

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 2: Marriage and household split
    # ═══════════════════════════════════════════════════════════════════════════

    def test_scenario_marriage_household_split(self):
        """
        Scenario: Adult child gets married and splits to form new household.

        Steps:
        1. Create original household with members
        2. Adult child gets married - split household
        3. Add spouse to new household
        """
        # Setup: Create original household
        original = self.partner_model.create(
            {
                "name": "Original Family",
                "is_registrant": True,
                "is_group": True,
            }
        )
        parent1 = self.partner_model.create(
            {
                "name": "Parent 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        parent2 = self.partner_model.create(
            {
                "name": "Parent 2",
                "is_registrant": True,
                "is_group": False,
            }
        )
        child = self.partner_model.create(
            {
                "name": "Adult Child",
                "is_registrant": True,
                "is_group": False,
            }
        )

        mem_parent1 = self.membership_model.create(
            {
                "group": original.id,
                "individual": parent1.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(self.head_kind.id)] if self.head_kind else [],
            }
        )
        self.membership_model.create(
            {
                "group": original.id,
                "individual": parent2.id,
                "start_date": fields.Datetime.now(),
            }
        )
        mem_child = self.membership_model.create(
            {
                "group": original.id,
                "individual": child.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Step 1: Split household - child moves out
        cr1 = self.cr_model.create(
            {
                "request_type_id": self.split_household_type.id,
                "registrant_id": original.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "members_to_split_ids": [(6, 0, [mem_child.id])],
                "new_head_membership_id": mem_child.id,
                "new_group_name": "New Family",
                "split_reason": "marriage",
                "effective_date": fields.Date.today(),
                "copy_address": False,
                "address_line1": "456 New St",
                "city": "Makati",
            }
        )
        self._approve_and_apply(cr1)

        new_household = detail1.created_group_id
        self.assertTrue(new_household)
        self.assertEqual(new_household.name, "New Family")
        self.assertEqual(new_household.street, "456 New St")

        # Verify child is in new household
        child_membership = self.membership_model.search(
            [
                ("group", "=", new_household.id),
                ("individual", "=", child.id),
                ("status", "=", "active"),
            ]
        )
        self.assertTrue(child_membership)

        # Step 2: Add spouse to new household
        cr2 = self.cr_model.create(
            {
                "request_type_id": self.add_member_type.id,
                "registrant_id": new_household.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "New",
                "family_name": "Spouse",
                "member_name": "New Spouse",
                "relationship_id": self.spouse_kind.id,
            }
        )
        self._approve_and_apply(cr2)

        # Verify new household has 2 members
        new_memberships = self.membership_model.search(
            [
                ("group", "=", new_household.id),
                ("status", "=", "active"),
            ]
        )
        self.assertEqual(len(new_memberships), 2)

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 3: Head of household deceased
    # ═══════════════════════════════════════════════════════════════════════════

    def test_scenario_hoh_deceased(self):
        """
        Scenario: Head of household passes away.

        Steps:
        1. Create household with head and spouse
        2. Change head of household to spouse
        3. Exit deceased head
        """
        # Setup
        household = self.partner_model.create(
            {
                "name": "Test HOH Deceased",
                "is_registrant": True,
                "is_group": True,
            }
        )
        head = self.partner_model.create(
            {
                "name": "Original Head",
                "is_registrant": True,
                "is_group": False,
            }
        )
        spouse = self.partner_model.create(
            {
                "name": "Surviving Spouse",
                "is_registrant": True,
                "is_group": False,
            }
        )

        head_mem = self.membership_model.create(
            {
                "group": household.id,
                "individual": head.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(self.head_kind.id)] if self.head_kind else [],
            }
        )
        spouse_mem = self.membership_model.create(
            {
                "group": household.id,
                "individual": spouse.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(self.spouse_kind.id)],
            }
        )

        # Step 1: Change HOH to spouse
        cr1 = self.cr_model.create(
            {
                "request_type_id": self.change_hoh_type.id,
                "registrant_id": household.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "new_head_membership_id": spouse_mem.id,
                "reason": "deceased",
                "effective_date": fields.Date.today(),
            }
        )
        self._approve_and_apply(cr1)

        # Verify spouse is now head
        if self.head_kind:
            spouse_mem.invalidate_recordset()
            self.assertIn(self.head_kind, spouse_mem.membership_type_ids)

        # Step 2: Exit deceased head
        cr2 = self.cr_model.create(
            {
                "request_type_id": self.exit_registrant_type.id,
                "registrant_id": head.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "exit_reason": "deceased",
                "exit_date": fields.Date.today(),
                "death_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )
        self._approve_and_apply(cr2)

        # Verify head is disabled and membership ended
        self.assertTrue(head.disabled)
        head_mem.invalidate_recordset()
        self.assertEqual(head_mem.status, "inactive")

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 4: Duplicate registrant cleanup
    # ═══════════════════════════════════════════════════════════════════════════

    def test_scenario_duplicate_cleanup(self):
        """
        Scenario: System has duplicate registrant records that need merging.

        Steps:
        1. Identify duplicates (simulated with test data)
        2. Merge duplicates into primary record
        3. Verify data consolidated correctly
        """
        # Setup: Create "duplicate" records
        primary = self.partner_model.create(
            {
                "name": "John Smith Primary",
                "is_registrant": True,
                "is_group": False,
            }
        )
        duplicate = self.partner_model.create(
            {
                "name": "John Smith Duplicate",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Duplicate has some data we want to preserve
        group = self.partner_model.create(
            {
                "name": "Duplicate's Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        dup_membership = self.membership_model.create(
            {
                "group": group.id,
                "individual": duplicate.id,
                "start_date": fields.Datetime.now(),
            }
        )
        dup_id = self.id_model.create(
            {
                "partner_id": duplicate.id,
                "id_type_id": self.national_id.id,
                "value": "DUP-NID-001",
                "status": "valid",
            }
        )

        # Merge duplicates
        cr = self.cr_model.create(
            {
                "request_type_id": self.merge_registrants_type.id,
                "registrant_id": primary.id,
            }
        )
        detail = cr.get_detail()
        detail.write(
            {
                "duplicate_registrant_ids": [(6, 0, [duplicate.id])],
                "reason": "duplicate_entry",
                "merge_strategy": "keep_primary",
                "is_merge_memberships": True,
                "is_merge_ids": True,
                "is_deactivate_duplicates": True,
            }
        )
        self._approve_and_apply(cr)

        # Verify merge results
        # Duplicate deactivated
        self.assertTrue(duplicate.disabled)

        # Membership transferred
        dup_membership.invalidate_recordset()
        self.assertEqual(dup_membership.individual.id, primary.id)

        # ID transferred
        dup_id.invalidate_recordset()
        self.assertEqual(dup_id.partner_id.id, primary.id)

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 5: Member transfer between households
    # ═══════════════════════════════════════════════════════════════════════════

    def test_scenario_member_transfer(self):
        """
        Scenario: Adult member relocates to join another household.

        Steps:
        1. Create source and target households
        2. Transfer member from source to target
        3. Verify membership changes
        """
        # Setup
        source = self.partner_model.create(
            {
                "name": "Source Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        target = self.partner_model.create(
            {
                "name": "Target Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        member = self.partner_model.create(
            {
                "name": "Relocating Member",
                "is_registrant": True,
                "is_group": False,
            }
        )

        source_mem = self.membership_model.create(
            {
                "group": source.id,
                "individual": member.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Transfer member
        cr = self.cr_model.create(
            {
                "request_type_id": self.transfer_member_type.id,
                "registrant_id": source.id,
            }
        )
        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": source_mem.id,
                "target_group_id": target.id,
                "transfer_reason": "relocation",
                "transfer_date": fields.Date.today(),
            }
        )
        self._approve_and_apply(cr)

        # Verify transfer
        source_mem.invalidate_recordset()
        self.assertEqual(source_mem.status, "inactive")

        target_mem = self.membership_model.search(
            [
                ("group", "=", target.id),
                ("individual", "=", member.id),
                ("status", "=", "active"),
            ]
        )
        self.assertTrue(target_mem)

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 6: Full lifecycle - registration to exit
    # ═══════════════════════════════════════════════════════════════════════════

    def test_scenario_full_lifecycle(self):
        """
        Scenario: Complete lifecycle of a household.

        Steps:
        1. Create new household
        2. Add members over time
        3. Update member information
        4. Member leaves household
        5. Exit remaining member (e.g., emigration)
        6. Exit household
        """
        # Step 1: Create household
        placeholder = self.partner_model.create(
            {
                "name": "Lifecycle Placeholder",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cr1 = self.cr_model.create(
            {
                "request_type_id": self.create_group_type.id,
                "registrant_id": placeholder.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "group_name": "Lifecycle Household",
                "create_new_head": True,
                "head_name": "Lifecycle Head",
            }
        )
        self._approve_and_apply(cr1)

        household = detail1.created_group_id
        head_mem = self.membership_model.search(
            [
                ("group", "=", household.id),
                ("status", "=", "active"),
            ]
        )
        head = head_mem.individual

        # Step 2: Add member
        cr2 = self.cr_model.create(
            {
                "request_type_id": self.add_member_type.id,
                "registrant_id": household.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "member_name": "Lifecycle Member",
                "relationship_id": self.spouse_kind.id,
            }
        )
        self._approve_and_apply(cr2)

        member = detail2.created_individual_id
        member_mem = self.membership_model.search(
            [
                ("group", "=", household.id),
                ("individual", "=", member.id),
                ("status", "=", "active"),
            ]
        )

        # Step 3: Member leaves household
        cr3 = self.cr_model.create(
            {
                "request_type_id": self.remove_member_type.id,
                "registrant_id": household.id,
            }
        )
        detail3 = cr3.get_detail()
        detail3.write(
            {
                "membership_id": member_mem.id,
                "end_date": fields.Date.today(),
                "end_reason": "left_household",
            }
        )
        self._approve_and_apply(cr3)

        member_mem.invalidate_recordset()
        self.assertEqual(member_mem.status, "inactive")

        # Step 4: Exit member (emigration)
        cr4 = self.cr_model.create(
            {
                "request_type_id": self.exit_registrant_type.id,
                "registrant_id": member.id,
            }
        )
        detail4 = cr4.get_detail()
        detail4.write(
            {
                "exit_reason": "emigrated",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )
        self._approve_and_apply(cr4)

        self.assertTrue(member.disabled)

        # Step 5: Exit head
        cr5 = self.cr_model.create(
            {
                "request_type_id": self.exit_registrant_type.id,
                "registrant_id": head.id,
            }
        )
        detail5 = cr5.get_detail()
        detail5.write(
            {
                "exit_reason": "emigrated",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )
        self._approve_and_apply(cr5)

        self.assertTrue(head.disabled)

        # Step 6: Exit household
        cr6 = self.cr_model.create(
            {
                "request_type_id": self.exit_registrant_type.id,
                "registrant_id": household.id,
            }
        )
        detail6 = cr6.get_detail()
        detail6.write(
            {
                "exit_reason": "ineligible",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )
        self._approve_and_apply(cr6)

        self.assertTrue(household.disabled)
