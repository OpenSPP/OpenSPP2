"""Tests for spp_cr_type_assign_program."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.spp_change_request_v2.tests.common import CRTestCase

ASSIGN_PROGRAM_CR_TYPE_DEFS = {
    "name": "Assign to Program",
    "target_type": "both",
    "detail_model": "spp.cr.detail.assign_program",
    "apply_strategy": "custom",
    "apply_model": "spp.cr.apply.assign_program",
}


@tagged("post_install", "-at_install")
class TestAssignProgram(CRTestCase):
    """Detail model and apply strategy for the assign-program CR type."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Program = cls.env["spp.program"]
        cls.ProgramMembership = cls.env["spp.program.membership"]

        cls.cr_type = cls.CRType.search([("code", "=", "assign_program")], limit=1)
        if not cls.cr_type:
            cls.cr_type = cls.CRType.create({"code": "assign_program", **ASSIGN_PROGRAM_CR_TYPE_DEFS})

        cls.group_program_active = cls.Program.create({"name": "Group Program (Active)", "target_type": "group"})
        cls.indiv_program_active = cls.Program.create(
            {"name": "Individual Program (Active)", "target_type": "individual"}
        )
        cls.indiv_program_inactive = cls.Program.create(
            {"name": "Individual Program (Inactive)", "target_type": "individual"}
        )
        cls.indiv_program_inactive.state = "ended"

        cls.disabled_individual = cls.Partner.create(
            {
                "name": "Disabled Individual",
                "given_name": "Disabled",
                "family_name": "Individual",
                "is_registrant": True,
                "is_group": False,
                "disabled": fields.Datetime.now(),
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_cr(self, registrant, program=None):
        """Create a CR of this type and (optionally) preset its detail's program.

        Returns (change_request, detail).
        """
        cr = self.CR.create({"request_type_id": self.cr_type.id, "registrant_id": registrant.id})
        detail = cr.get_detail()
        if program is not None:
            detail.program_id = program.id
        return cr, detail

    def _strategy(self):
        return self.env["spp.cr.apply.assign_program"]

    # ------------------------------------------------------------------
    # Detail model — computed fields (D1-D4)
    # ------------------------------------------------------------------

    def test_d1_registrant_target_type_for_group(self):
        _cr, detail = self._make_cr(self.test_group)
        self.assertEqual(detail.registrant_target_type, "group")

    def test_d2_registrant_target_type_for_individual(self):
        _cr, detail = self._make_cr(self.test_individual)
        self.assertEqual(detail.registrant_target_type, "individual")

    def test_d3_allowed_programs_for_group_registrant(self):
        _cr, detail = self._make_cr(self.test_group)
        allowed = detail.allowed_program_ids
        self.assertIn(self.group_program_active, allowed)
        self.assertNotIn(self.indiv_program_active, allowed)
        self.assertNotIn(self.indiv_program_inactive, allowed)

    def test_d4_allowed_programs_for_individual_registrant(self):
        _cr, detail = self._make_cr(self.test_individual)
        allowed = detail.allowed_program_ids
        self.assertIn(self.indiv_program_active, allowed)
        self.assertNotIn(self.group_program_active, allowed)
        self.assertNotIn(self.indiv_program_inactive, allowed)

    # ------------------------------------------------------------------
    # Apply strategy
    # ------------------------------------------------------------------

    def test_a1_apply_creates_membership_for_individual(self):
        cr, detail = self._make_cr(self.test_individual, self.indiv_program_active)

        result = self._strategy().apply(cr)

        self.assertTrue(result)
        self.assertTrue(detail.created_membership_id)
        membership = detail.created_membership_id
        self.assertEqual(membership.partner_id, self.test_individual)
        self.assertEqual(membership.program_id, self.indiv_program_active)
        self.assertEqual(membership.state, "draft")

    def test_a4_apply_without_program_raises(self):
        cr, _detail = self._make_cr(self.test_individual)

        with self.assertRaises(UserError):
            self._strategy().apply(cr)

    def test_a2_apply_creates_membership_for_group(self):
        cr, detail = self._make_cr(self.test_group, self.group_program_active)

        self._strategy().apply(cr)

        self.assertTrue(detail.created_membership_id)
        self.assertEqual(detail.created_membership_id.partner_id, self.test_group)
        self.assertEqual(detail.created_membership_id.program_id, self.group_program_active)
        self.assertEqual(detail.created_membership_id.state, "draft")

    def test_a5_apply_with_disabled_registrant_raises(self):
        cr, _detail = self._make_cr(self.disabled_individual, self.indiv_program_active)

        with self.assertRaises(UserError) as cm:
            self._strategy().apply(cr)

        self.assertIn("disabled", str(cm.exception).lower())

    def test_a6_apply_with_inactive_program_raises(self):
        cr, _detail = self._make_cr(self.test_individual, self.indiv_program_inactive)

        with self.assertRaises(UserError) as cm:
            self._strategy().apply(cr)

        self.assertIn("active", str(cm.exception).lower())

    def test_a7_apply_with_target_type_mismatch_raises(self):
        # Group registrant + individual program — domain would normally prevent
        # this in the UI, but the strategy must still defend against direct ID
        # writes.
        cr, _detail = self._make_cr(self.test_group, self.indiv_program_active)

        with self.assertRaises(UserError) as cm:
            self._strategy().apply(cr)

        self.assertIn("target", str(cm.exception).lower())

    def test_a8_apply_with_existing_membership_raises_friendly_error(self):
        # First apply succeeds.
        cr_first, _detail = self._make_cr(self.test_individual, self.indiv_program_active)
        self._strategy().apply(cr_first)

        # Second CR for the same (registrant, program) pair must be rejected
        # with our own friendly message (not the raw DB unique-constraint
        # error).
        cr_second, _detail2 = self._make_cr(self.test_individual, self.indiv_program_active)

        with self.assertRaises(UserError) as cm:
            self._strategy().apply(cr_second)

        self.assertIn("already", str(cm.exception).lower())

    # ------------------------------------------------------------------
    # Conflict detection (F2, F3)
    # ------------------------------------------------------------------

    def test_f2_two_crs_for_same_registrant_program_block_second(self):
        cr1, _d1 = self._make_cr(self.test_individual, self.indiv_program_active)
        cr2, _d2 = self._make_cr(self.test_individual, self.indiv_program_active)

        cr2._run_conflict_checks()

        self.assertEqual(cr2.conflict_status, "blocked")
        self.assertIn(cr1, cr2.conflicting_cr_ids)

    def test_f3_two_crs_for_same_registrant_different_programs_allowed(self):
        # Two distinct active individual programs targeting the same registrant
        # must both be able to proceed.
        other_indiv_program = self.Program.create({"name": "Other Individual Program", "target_type": "individual"})

        _cr1, _d1 = self._make_cr(self.test_individual, self.indiv_program_active)
        cr2, _d2 = self._make_cr(self.test_individual, other_indiv_program)

        cr2._run_conflict_checks()

        self.assertEqual(cr2.conflict_status, "none")
        self.assertFalse(cr2.conflicting_cr_ids)

    def test_a9_preview_returns_expected_shape(self):
        cr, _detail = self._make_cr(self.test_individual, self.indiv_program_active)

        preview = self._strategy().preview(cr)

        self.assertEqual(preview.get("_action"), "create_program_membership")
        self.assertEqual(preview.get("registrant"), self.test_individual.display_name)
        self.assertEqual(preview.get("program"), self.indiv_program_active.display_name)
        self.assertEqual(preview.get("initial_state"), "draft")
