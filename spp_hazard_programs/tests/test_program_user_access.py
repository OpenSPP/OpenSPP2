# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Regression: emergency-eligibility logic must work for non-hazard program users.

After tightening the hazard-impact ACL (removing the broad ``base.group_user``
read grant), the program eligibility computes read ``spp.hazard.impact`` via
``sudo`` so a program user without any hazard group can still use them. Without
that sudo, ``affected_registrant_count`` / ``get_emergency_eligible_registrants``
would raise ``AccessError`` for such users.
"""

from odoo import Command
from odoo.tests import tagged

from .common import HazardProgramsTestCase


@tagged("post_install", "-at_install")
class TestProgramUserHazardAccess(HazardProgramsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program_user = cls.env["res.users"].create(
            {
                "name": "Program Manager (no hazard group)",
                "login": "program_mgr_no_hazard_test",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_programs.group_programs_manager").id),
                ],
            }
        )
        cls.program.write(
            {
                "target_incident_ids": [Command.link(cls.incident_active.id)],
                "qualifying_damage_levels": "any",
            }
        )

    def test_program_user_without_hazard_group_can_compute_eligibility(self):
        """A program user with no hazard group must still compute emergency
        eligibility (the impact reads are sudo'd)."""
        self.assertFalse(self.program_user.has_group("spp_hazard.group_hazard_read"))
        program = self.program.with_user(self.program_user)
        # Non-stored compute -> runs live as this user; reads impact via sudo.
        self.assertEqual(program.affected_registrant_count, 2)
        # Method -> runs live as this user; reads impact via sudo.
        eligible = program.get_emergency_eligible_registrants()
        self.assertIn(self.registrant_1, eligible)
        self.assertIn(self.registrant_2, eligible)
