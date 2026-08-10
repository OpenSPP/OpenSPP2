"""Security: the assign_program detail must enforce parent-CR ownership.

Regression test for the reported "Assign-program detail ACL bypasses CR
ownership" issue: without an ir.rule, a low-privileged ``group_cr_user`` could
re-point ``program_id`` on a change request they do not own, enrolling a
beneficiary into an unauthorized program.
"""

from odoo.exceptions import AccessError
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
class TestAssignProgramDetailSecurity(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_type = cls.CRType.search([("code", "=", "assign_program")], limit=1)
        if not cls.cr_type:
            cls.cr_type = cls.CRType.create({"code": "assign_program", **ASSIGN_PROGRAM_CR_TYPE_DEFS})

        Program = cls.env["spp.program"]
        cls.program_a = Program.create({"name": "Program A", "target_type": "individual"})
        cls.program_b = Program.create({"name": "Program B", "target_type": "individual"})

        cls.internal_group = cls.env.ref("base.group_user")
        cls.user_group = cls.env.ref("spp_change_request_v2.group_cr_user")
        cls.validator_group = cls.env.ref("spp_change_request_v2.group_cr_validator")
        # Assign-program details validate that the writer can actually see the
        # target program, and that check runs a search in the writing user's
        # own context. Without read access to spp.program the search raises
        # AccessError before the validation can even evaluate, which would make
        # these fixtures fail for a reason unrelated to the record rules under
        # test. Tier-3 programs viewer grants exactly that read.
        cls.programs_viewer_group = cls.env.ref("spp_programs.group_programs_viewer")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.user_a = Users.create(
            {
                "name": "Assign User A",
                "login": "assign_user_a",
                "email": "assign_user_a@test.com",
                "group_ids": [
                    (4, cls.internal_group.id),
                    (4, cls.user_group.id),
                    (4, cls.programs_viewer_group.id),
                ],
            }
        )
        cls.user_b = Users.create(
            {
                "name": "Assign User B",
                "login": "assign_user_b",
                "email": "assign_user_b@test.com",
                "group_ids": [
                    (4, cls.internal_group.id),
                    (4, cls.user_group.id),
                    (4, cls.programs_viewer_group.id),
                ],
            }
        )
        cls.validator = Users.create(
            {
                "name": "Assign Validator",
                "login": "assign_validator",
                "email": "assign_validator@test.com",
                "group_ids": [
                    (4, cls.internal_group.id),
                    (4, cls.validator_group.id),
                    (4, cls.programs_viewer_group.id),
                ],
            }
        )

    def _make_cr_owned_by(self, user, program=None):
        cr = self.CR.with_user(user).create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.test_individual.id,
            }
        )
        detail = cr.with_user(user).get_detail()
        if program is not None:
            detail.with_user(user).program_id = program.id
        return cr, detail

    def test_cr_user_cannot_read_others_detail(self):
        _cr, detail = self._make_cr_owned_by(self.user_a, self.program_a)
        found = self.env["spp.cr.detail.assign_program"].with_user(self.user_b).search([("id", "=", detail.id)])
        self.assertFalse(found, "user B must not see user A's assign-program detail")
        with self.assertRaises(AccessError):
            detail.with_user(self.user_b).read(["program_id"])

    def test_cr_user_cannot_repoint_program_on_others_detail(self):
        """The exact reported attack: tamper with another user's program assignment."""
        _cr, detail = self._make_cr_owned_by(self.user_a, self.program_a)
        with self.assertRaises(AccessError):
            detail.with_user(self.user_b).write({"program_id": self.program_b.id})
        # The value is unchanged.
        self.assertEqual(detail.program_id, self.program_a)

    def test_owner_can_set_program(self):
        _cr, detail = self._make_cr_owned_by(self.user_a)
        detail.with_user(self.user_a).write({"program_id": self.program_a.id})
        self.assertEqual(detail.program_id, self.program_a)

    def test_validator_can_read_any_detail(self):
        _cr, detail = self._make_cr_owned_by(self.user_a, self.program_a)
        self.assertTrue(detail.with_user(self.validator).read(["program_id"]))
