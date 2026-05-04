"""Tests for spp_cr_type_assign_program."""

from odoo import fields
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
