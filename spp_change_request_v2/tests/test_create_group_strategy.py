# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the redesigned Create Group strategy (OP#876)."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestCreateGroupStrategy(TransactionCase):
    """Tests for Create Group custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        cls.head_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.member_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "member")
        cls.group_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")

        cls.existing_head = cls.partner_model.create(
            {
                "name": "Existing Head",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Placeholder registrant — required by the base CR model even though
        # the apply strategy replaces registrant_id with the newly-created
        # group at the end of apply.
        cls.dummy_group = cls.partner_model.create(
            {
                "name": "Placeholder",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.cr_type = get_or_create_cr_type(cls.env, "create_group")
        # Default: groups don't have to be empty, head not required, members allowed.
        cls.cr_type.write({"allow_empty_members": True, "requires_head": False})

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    def _make_cr(self, **detail_vals):
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,
            }
        )
        cr.get_detail().write(detail_vals)
        return cr

    # ──────────────────────────────────────────────────────────────────
    # Basic create — empty group allowed by config
    # ──────────────────────────────────────────────────────────────────
    def test_create_group_basic_no_members(self):
        self.cr_type.write({"allow_empty_members": True, "requires_head": False})
        cr = self._make_cr(
            group_name="New Household",
            group_type_id=self.group_kind.id if self.group_kind else False,
            address="123 Main St, Manila",
        )

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        detail = cr.get_detail()
        self.assertTrue(detail.created_group_id)
        new_group = detail.created_group_id
        self.assertEqual(new_group.name, "New Household")
        self.assertTrue(new_group.is_registrant)
        self.assertTrue(new_group.is_group)
        self.assertEqual(new_group.address, "123 Main St, Manila")

    # ──────────────────────────────────────────────────────────────────
    # Existing member becomes the head
    # ──────────────────────────────────────────────────────────────────
    def test_create_group_with_existing_head(self):
        cr = self._make_cr(
            group_name="Group with Head",
            member_existing_ids=[
                (
                    0,
                    0,
                    {
                        "individual_id": self.existing_head.id,
                        "membership_type_id": self.head_kind.id if self.head_kind else False,
                    },
                ),
            ],
        )

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        new_group = cr.get_detail().created_group_id
        membership = self.membership_model.search(
            [("group", "=", new_group.id), ("individual", "=", self.existing_head.id)]
        )
        self.assertTrue(membership, "Head should be member of new group")
        if self.head_kind:
            self.assertIn(self.head_kind, membership.membership_type_ids)

    # ──────────────────────────────────────────────────────────────────
    # New individual is created and attached as head
    # ──────────────────────────────────────────────────────────────────
    def test_create_group_with_new_head(self):
        cr = self._make_cr(
            group_name="Group with New Head",
            member_new_ids=[
                (
                    0,
                    0,
                    {
                        "given_name": "Juan",
                        "family_name": "Dela Cruz",
                        "phone_line_ids": [(0, 0, {"phone_no": "+63987654321"})],
                        "membership_type_id": self.head_kind.id if self.head_kind else False,
                    },
                ),
            ],
        )

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        new_group = cr.get_detail().created_group_id
        membership = self.membership_model.search([("group", "=", new_group.id), ("status", "=", "active")])
        self.assertTrue(membership)
        new_head = membership.individual
        self.assertEqual(new_head.given_name, "Juan")
        self.assertEqual(new_head.family_name, "Dela Cruz")
        self.assertTrue(new_head.is_registrant)
        self.assertFalse(new_head.is_group)

    # ──────────────────────────────────────────────────────────────────
    # Multiple members of mixed origin all attached
    # ──────────────────────────────────────────────────────────────────
    def test_create_group_mixed_members(self):
        spouse = self.partner_model.create({"name": "Existing Spouse", "is_registrant": True, "is_group": False})

        cr = self._make_cr(
            group_name="Mixed-membership Group",
            member_existing_ids=[
                (
                    0,
                    0,
                    {
                        "individual_id": self.existing_head.id,
                        "membership_type_id": self.head_kind.id if self.head_kind else False,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "individual_id": spouse.id,
                        "membership_type_id": self.member_kind.id if self.member_kind else False,
                    },
                ),
            ],
            member_new_ids=[
                (
                    0,
                    0,
                    {
                        "given_name": "Anak",
                        "family_name": "Dela Cruz",
                        "membership_type_id": self.member_kind.id if self.member_kind else False,
                    },
                ),
            ],
        )

        cr.approval_state = "approved"
        cr.action_apply()

        new_group = cr.get_detail().created_group_id
        memberships = self.membership_model.search([("group", "=", new_group.id)])
        self.assertEqual(len(memberships), 3, "all 3 members should be attached")

    # ──────────────────────────────────────────────────────────────────
    # Validation: group name still required
    # ──────────────────────────────────────────────────────────────────
    def test_create_group_without_name_fails(self):
        cr = self._make_cr(address="Manila")
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("name", str(cm.exception).lower())

    # ──────────────────────────────────────────────────────────────────
    # Validation: allow_empty_members=False forces at least one member
    # ──────────────────────────────────────────────────────────────────
    def test_apply_blocks_when_members_required_but_absent(self):
        self.cr_type.write({"allow_empty_members": False, "requires_head": False})
        cr = self._make_cr(group_name="Members Required Group")
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("member", str(cm.exception).lower())

    # ──────────────────────────────────────────────────────────────────
    # Validation: requires_head=True forces exactly one Head
    # ──────────────────────────────────────────────────────────────────
    def test_apply_blocks_when_head_required_but_absent(self):
        self.cr_type.write({"allow_empty_members": True, "requires_head": True})
        cr = self._make_cr(
            group_name="Headless Group",
            member_new_ids=[
                (
                    0,
                    0,
                    {
                        "given_name": "Member",
                        "family_name": "Only",
                        "membership_type_id": self.member_kind.id if self.member_kind else False,
                    },
                ),
            ],
        )
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("head", str(cm.exception).lower())

    # ──────────────────────────────────────────────────────────────────
    # Validation: at most one Head — caught at write-time on the detail
    # ──────────────────────────────────────────────────────────────────
    def test_two_heads_is_rejected(self):
        if not self.head_kind:
            self.skipTest("head membership-type code missing in vocabulary")
        from odoo.exceptions import ValidationError

        cr = self._make_cr(group_name="Two-Head Group")
        detail = cr.get_detail()
        with self.assertRaises(ValidationError):
            detail.write(
                {
                    "member_existing_ids": [
                        (0, 0, {"individual_id": self.existing_head.id, "membership_type_id": self.head_kind.id}),
                    ],
                    "member_new_ids": [
                        (
                            0,
                            0,
                            {
                                "given_name": "Another",
                                "family_name": "Head",
                                "membership_type_id": self.head_kind.id,
                            },
                        ),
                    ],
                }
            )

    # ──────────────────────────────────────────────────────────────────
    # Multi-value sub-records: phones, banks, ID docs
    # ──────────────────────────────────────────────────────────────────
    def test_phones_banks_id_docs_attach_to_created_group(self):
        id_type = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1
        )
        cr = self._make_cr(
            group_name="Fully-loaded Group",
            phone_line_ids=[
                (0, 0, {"phone_no": "+63912345678", "is_primary": True}),
                (0, 0, {"phone_no": "+63923456789", "is_primary": False}),
            ],
            bank_line_ids=[
                (0, 0, {"acc_number": "PH00 ACME 1234 5678", "acc_holder_name": "Group Account"}),
            ],
            id_doc_line_ids=(
                [(0, 0, {"id_type_id": id_type.id, "value": "X-12345", "expiry_date": "2030-01-01"})] if id_type else []
            ),
        )
        cr.approval_state = "approved"
        cr.action_apply()

        new_group = cr.get_detail().created_group_id

        phones = self.env["spp.phone.number"].search([("partner_id", "=", new_group.id)])
        self.assertEqual(len(phones), 2)

        banks = self.env["res.partner.bank"].search([("partner_id", "=", new_group.id)])
        self.assertEqual(len(banks), 1)
        self.assertEqual(banks.acc_number, "PH00 ACME 1234 5678")

        # Group header phone should match the primary entry.
        self.assertEqual(new_group.phone, "+63912345678")

        if id_type:
            ids = self.env["spp.registry.id"].search([("partner_id", "=", new_group.id)])
            self.assertEqual(len(ids), 1)
            self.assertEqual(ids.value, "X-12345")

    # ──────────────────────────────────────────────────────────────────
    # preview returns counts + head label
    # ──────────────────────────────────────────────────────────────────
    def test_preview(self):
        cr = self._make_cr(
            group_name="Preview Group",
            group_type_id=self.group_kind.id if self.group_kind else False,
            member_new_ids=[
                (
                    0,
                    0,
                    {
                        "given_name": "Head",
                        "family_name": "Person",
                        "membership_type_id": self.head_kind.id if self.head_kind else False,
                    },
                ),
            ],
            bank_line_ids=[(0, 0, {"acc_number": "12-34-56"})],
        )
        preview = cr.action_preview_changes()
        self.assertEqual(preview["_action"], "create_group")
        self.assertEqual(preview["group_name"], "Preview Group")
        self.assertEqual(preview["new_member_count"], 1)
        self.assertEqual(preview["bank_count"], 1)
        if self.head_kind:
            self.assertEqual(preview["head_of_household"], "PERSON, Head")

    # ──────────────────────────────────────────────────────────────────
    # Wizard flow (OP#876 round 2): Add Member wizard, both modes
    # ──────────────────────────────────────────────────────────────────
    def _make_wizard(self, detail, mode, **extra):
        Wizard = self.env["spp.cr.detail.create_group.member.wizard"]
        return Wizard.create({"detail_id": detail.id, "mode": mode, **extra})

    def test_wizard_add_existing_close_creates_row(self):
        cr = self._make_cr(group_name="Wizard Existing Group")
        detail = cr.get_detail()
        wiz = self._make_wizard(
            detail,
            "existing",
            individual_id=self.existing_head.id,
            membership_type_id=self.head_kind.id if self.head_kind else False,
        )
        action = wiz.action_add_close()
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        self.assertEqual(len(detail.member_existing_ids), 1)
        self.assertEqual(detail.member_existing_ids.individual_id, self.existing_head)

    def test_wizard_add_existing_keeps_window_open(self):
        cr = self._make_cr(group_name="Wizard Add-More Group")
        detail = cr.get_detail()
        wiz = self._make_wizard(detail, "existing", individual_id=self.existing_head.id)
        action = wiz.action_add()
        # The row is persisted...
        self.assertEqual(len(detail.member_existing_ids), 1)
        # ...and the wizard returns a follow-up act_window for itself.
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cr.detail.create_group.member.wizard")
        self.assertEqual(action["context"]["default_mode"], "existing")

    def test_wizard_add_new_close_creates_row(self):
        cr = self._make_cr(group_name="Wizard New-Member Group")
        detail = cr.get_detail()
        wiz = self._make_wizard(
            detail,
            "new",
            given_name="Wizard",
            family_name="Added",
            phone_line_ids=[(0, 0, {"phone_no": "+639000", "is_primary": True})],
            membership_type_id=self.head_kind.id if self.head_kind else False,
        )
        wiz.action_add_close()
        self.assertEqual(len(detail.member_new_ids), 1)
        row = detail.member_new_ids
        self.assertEqual(row.given_name, "Wizard")
        self.assertEqual(row.family_name, "Added")
        self.assertEqual(row.full_name, "ADDED, Wizard")
        # The wizard's phone line is persisted onto the member_new row.
        self.assertEqual(row.phone_line_ids.phone_no, "+639000")

    def test_wizard_edit_new_member_updates_row(self):
        cr = self._make_cr(group_name="Edit-Wizard Group")
        detail = cr.get_detail()
        # Seed a new-member row first, with a phone (regression: editing a
        # member that already has phone rows must not orphan them).
        wiz = self._make_wizard(
            detail,
            "new",
            given_name="Old",
            family_name="Name",
            phone_line_ids=[(0, 0, {"phone_no": "+63111", "is_primary": True})],
        )
        wiz.action_add_close()
        row = detail.member_new_ids
        self.assertEqual(row.full_name, "NAME, Old")
        self.assertEqual(row.phone_line_ids.phone_no, "+63111")

        # Open the wizard for that row in edit mode.
        open_action = row.action_open_edit_wizard()
        self.assertEqual(open_action["context"]["default_editing_member_new_id"], row.id)
        # The edit context carries the existing phone rows.
        self.assertTrue(open_action["context"]["default_phone_line_ids"])

        # Recreate the wizard with the edit context as Odoo would (incl. a
        # changed phone set).
        edit_wiz = self.env["spp.cr.detail.create_group.member.wizard"].create(
            {
                "detail_id": detail.id,
                "mode": "new",
                "editing_member_new_id": row.id,
                "given_name": "New",
                "family_name": "Name",
                "phone_line_ids": [(0, 0, {"phone_no": "+63222", "is_primary": True})],
            }
        )
        self.assertTrue(edit_wiz.is_editing)
        action = edit_wiz.action_add()
        # Edit branch should close the window in one shot.
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        # ...and only one row remains, with the updated name and phone.
        self.assertEqual(len(detail.member_new_ids), 1)
        self.assertEqual(detail.member_new_ids.given_name, "New")
        self.assertEqual(detail.member_new_ids.phone_line_ids.phone_no, "+63222")

    def test_wizard_existing_blocks_duplicate(self):
        cr = self._make_cr(group_name="Dedup-Wizard Group")
        detail = cr.get_detail()
        self._make_wizard(detail, "existing", individual_id=self.existing_head.id).action_add_close()
        # Trying to add the same individual again must fail.
        dup_wiz = self._make_wizard(detail, "existing", individual_id=self.existing_head.id)
        with self.assertRaises(UserError):
            dup_wiz.action_add_close()

    def test_wizard_new_requires_names(self):
        cr = self._make_cr(group_name="Bad-Wizard Group")
        detail = cr.get_detail()
        wiz = self._make_wizard(detail, "new", given_name="Only")
        with self.assertRaises(UserError):
            wiz.action_add_close()

    def test_wizard_blocks_second_head(self):
        """A second Head added via the wizard is rejected (OP#876 QA round 1).

        The parent-level @api.constrains doesn't fire on rows the wizard creates
        directly, so the wizard guard + the per-row constraint must catch it.
        """
        if not self.head_kind:
            self.skipTest("head membership-type code missing in vocabulary")
        cr = self._make_cr(group_name="Wizard Two-Head Group")
        detail = cr.get_detail()
        # First head — existing individual.
        self._make_wizard(
            detail,
            "existing",
            individual_id=self.existing_head.id,
            membership_type_id=self.head_kind.id,
        ).action_add_close()
        # Second head — new individual via wizard. Must be rejected.
        second = self._make_wizard(
            detail,
            "new",
            given_name="Second",
            family_name="Head",
            membership_type_id=self.head_kind.id,
        )
        with self.assertRaises(UserError):
            second.action_add_close()

    # ──────────────────────────────────────────────────────────────────
    # New individual carries the full registry profile (OP#876 QA round 1)
    # ──────────────────────────────────────────────────────────────────
    def test_new_member_full_profile_written(self):
        occupation = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:ilo:isco-08")], limit=1
        )
        civil = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:un:unsd:pop-census:marital-status")], limit=1
        )
        cr = self._make_cr(
            group_name="Full-Profile Group",
            member_new_ids=[
                (
                    0,
                    0,
                    {
                        "given_name": "Maria",
                        "family_name": "Cruz",
                        "middle_name": "Santos",
                        "birthdate": "1990-05-20",
                        "is_approximate_birthdate": True,
                        "birth_place": "Cebu",
                        "income": 12345.0,
                        "address": "10 Rizal St, Cebu",
                        "email": "maria@example.com",
                        "phone_line_ids": [
                            (0, 0, {"phone_no": "+63911", "is_primary": True}),
                            (0, 0, {"phone_no": "+63922"}),
                        ],
                        "occupation_id": occupation.id if occupation else False,
                        "civil_status_id": civil.id if civil else False,
                        "membership_type_id": self.head_kind.id if self.head_kind else False,
                    },
                ),
            ],
        )
        cr.approval_state = "approved"
        cr.action_apply()

        detail = cr.get_detail()
        # Middle name is captured on the CR row (res.partner has no native field;
        # name_change() recomposes the partner name from given+family only).
        self.assertEqual(detail.member_new_ids.middle_name, "Santos")

        new_group = detail.created_group_id
        membership = self.membership_model.search([("group", "=", new_group.id), ("status", "=", "active")])
        individual = membership.individual
        self.assertEqual(individual.given_name, "Maria")
        self.assertEqual(individual.family_name, "Cruz")
        self.assertEqual(individual.birth_place, "Cebu")
        self.assertTrue(individual.birthdate_not_exact)
        self.assertEqual(individual.address, "10 Rizal St, Cebu")
        self.assertEqual(individual.email, "maria@example.com")
        self.assertEqual(individual.income, 12345.0)
        # Multiple captured phone numbers are folded (primary first) into the
        # partner's single header phone field.
        self.assertEqual(individual.phone, "+63911, +63922")
        if occupation:
            self.assertEqual(individual.occupation_id, occupation)
        if civil:
            self.assertEqual(individual.civil_status_id, civil)
