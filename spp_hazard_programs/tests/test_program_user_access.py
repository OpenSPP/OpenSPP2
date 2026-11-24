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
        # Method -> runs live as this user; reads impact via sudo. Private so it
        # is reachable from Python (eligibility, overrides) but not over RPC.
        eligible = program._get_emergency_eligible_registrants()
        self.assertIn(self.registrant_1, eligible)
        self.assertIn(self.registrant_2, eligible)

    def test_eligible_registrants_method_is_not_rpc_callable(self):
        """The eligible-registrant list is the identity linkage the impact ACL
        protects. It must not be exposed as a public (call_kw-reachable) method."""
        self.assertFalse(hasattr(type(self.program), "get_emergency_eligible_registrants"))
        self.assertTrue(hasattr(type(self.program), "_get_emergency_eligible_registrants"))

    def test_program_user_without_impact_read_cannot_open_affected_registrants(self):
        """The 'Affected' stat button opens the list of impacted registrants. A
        program user without impact read keeps the aggregate count but must be
        refused the list, server-side (buttons are RPC-callable) and in the arch."""
        from odoo.exceptions import AccessError

        program = self.program.with_user(self.program_user)
        self.assertEqual(program.affected_registrant_count, 2)
        with self.assertRaises(AccessError):
            program.action_view_affected_registrants()
        arch = self.env["spp.program"].with_user(self.program_user).get_view(view_type="form")["arch"]
        self.assertNotIn("action_view_affected_registrants", arch)

    def test_hazard_user_can_open_affected_registrants(self):
        """A user with impact read (hazard viewer + program manager) keeps the list."""
        hazard_program_user = self.env["res.users"].create(
            {
                "name": "Program Manager with hazard read",
                "login": "program_mgr_hazard_read_test",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("spp_programs.group_programs_manager").id),
                    Command.link(self.env.ref("spp_hazard.group_hazard_viewer").id),
                ],
            }
        )
        program = self.program.with_user(hazard_program_user)
        action = program.action_view_affected_registrants()
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(set(action["domain"][0][2]), {self.registrant_1.id, self.registrant_2.id})
        arch = self.env["spp.program"].with_user(hazard_program_user).get_view(view_type="form")["arch"]
        self.assertIn("action_view_affected_registrants", arch)
