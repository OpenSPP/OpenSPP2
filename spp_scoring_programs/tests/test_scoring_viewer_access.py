# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: a scoring viewer must not get broad program-membership PII access.

``spp.program.membership`` ``_inherits`` ``res.partner``, so read access to it
exposes registrant PII (names, addresses, contacts, IDs, bank details, etc.).
The bridge module must NOT grant ``spp_scoring.group_scoring_viewer`` direct
read on the membership model — membership access is governed by ``spp_programs``
ACLs. A scoring viewer keeps its own remit (scoring models/results) and program
read; it sees memberships only if it also holds a program/registry viewer role.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringViewerMembershipAccess(TransactionCase):
    """A pure scoring viewer cannot read program memberships."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Program = cls.env["spp.program"]
        cls.Membership = cls.env["spp.program.membership"]

        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Scoring PII Test Registrant",
                "given_name": "Scoring",
                "family_name": "Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.program = cls.Program.create({"name": "Scoring PII Test Program"})
        cls.membership = cls.Membership.create({"partner_id": cls.registrant.id, "program_id": cls.program.id})

        scoring_viewer_group = cls.env.ref("spp_scoring.group_scoring_viewer")
        programs_viewer_group = cls.env.ref("spp_programs.group_programs_viewer")

        # Pure scoring viewer — scoring remit only, no program/registry role.
        cls.scoring_viewer = cls.env["res.users"].create(
            {
                "name": "Pure Scoring Viewer",
                "login": "scoring_viewer_pii_test",
                "group_ids": [(6, 0, [scoring_viewer_group.id])],
            }
        )
        # Scoring viewer who is ALSO a program viewer — membership access comes
        # from spp_programs and must be unaffected.
        cls.dual_viewer = cls.env["res.users"].create(
            {
                "name": "Scoring + Program Viewer",
                "login": "scoring_program_viewer_pii_test",
                "group_ids": [(6, 0, [scoring_viewer_group.id, programs_viewer_group.id])],
            }
        )

    def test_pure_scoring_viewer_cannot_read_membership(self):
        with self.assertRaises(AccessError):
            self.Membership.with_user(self.scoring_viewer).search_read(
                [("id", "=", self.membership.id)], ["partner_id"]
            )

    def test_scoring_viewer_can_still_read_program(self):
        # The spp.program read grant is retained (scoring viewers see which
        # programs use a scoring model).
        found = self.Program.with_user(self.scoring_viewer).search([("id", "=", self.program.id)])
        self.assertIn(self.program, found)

    def test_combined_viewer_can_read_membership(self):
        found = self.Membership.with_user(self.dual_viewer).search([("id", "=", self.membership.id)])
        self.assertIn(self.membership, found)
