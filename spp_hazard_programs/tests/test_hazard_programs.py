# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged

from .common import HazardProgramsTestCase


@tagged("post_install", "-at_install")
class TestProgramHazardIntegration(HazardProgramsTestCase):
    """Test program extensions for hazard integration."""

    def test_target_incident_count(self):
        """Test that target_incident_count computes correctly."""
        self.assertEqual(self.program.target_incident_count, 0)

        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.assertEqual(self.program.target_incident_count, 1)

        self.program.write({"target_incident_ids": [Command.link(self.incident_closed.id)]})
        self.assertEqual(self.program.target_incident_count, 2)

    def test_is_emergency_program_with_active_incident(self):
        """Test is_emergency_program is True when linked to active incidents."""
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.assertTrue(self.program.is_emergency_program)

    def test_is_emergency_program_with_closed_incident(self):
        """Test is_emergency_program is False when only linked to closed incidents."""
        self.program.write({"target_incident_ids": [Command.link(self.incident_closed.id)]})
        self.assertFalse(self.program.is_emergency_program)

    def test_is_emergency_program_no_incidents(self):
        """Test is_emergency_program is False with no linked incidents."""
        self.assertFalse(self.program.is_emergency_program)

    def test_is_emergency_program_alert_status(self):
        """Test is_emergency_program is True for alert status."""
        self.incident_active.status = "alert"
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.assertTrue(self.program.is_emergency_program)

    def test_is_emergency_program_recovery_status(self):
        """Test is_emergency_program is True for recovery status."""
        self.incident_active.status = "recovery"
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.assertTrue(self.program.is_emergency_program)

    def test_affected_registrant_count_any_damage(self):
        """Test affected count with 'any' damage level (only verified impacts)."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "any",
            }
        )
        # 2 verified impacts (registrant_1=critical, registrant_2=moderate)
        # registrant_3 is unverified so excluded
        self.assertEqual(self.program.affected_registrant_count, 2)

    def test_affected_registrant_count_critical_only(self):
        """Test affected count with 'critical_only' damage level."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "critical_only",
            }
        )
        # Only registrant_1 has critical damage and is verified
        self.assertEqual(self.program.affected_registrant_count, 1)

    def test_affected_registrant_count_severe_up(self):
        """Test affected count with 'severe_up' damage level."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "severe_up",
            }
        )
        # Only registrant_1 (critical, verified) qualifies
        # registrant_2 is moderate (below threshold), registrant_3 is unverified
        self.assertEqual(self.program.affected_registrant_count, 1)

    def test_affected_registrant_count_moderate_up(self):
        """Test affected count with 'moderate_up' damage level."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "moderate_up",
            }
        )
        # registrant_1 (critical, verified) and registrant_2 (moderate, verified)
        self.assertEqual(self.program.affected_registrant_count, 2)

    def test_affected_registrant_count_no_incidents(self):
        """Test affected count is 0 with no linked incidents."""
        self.assertEqual(self.program.affected_registrant_count, 0)

    def test_get_damage_level_domain_any(self):
        """Test damage level domain for 'any'."""
        self.program.qualifying_damage_levels = "any"
        domain = self.program._get_damage_level_domain()
        self.assertEqual(domain, [])

    def test_get_damage_level_domain_moderate_up(self):
        """Test damage level domain for 'moderate_up'."""
        self.program.qualifying_damage_levels = "moderate_up"
        domain = self.program._get_damage_level_domain()
        self.assertEqual(len(domain), 1)
        self.assertIn("moderate", domain[0][2])
        self.assertIn("severe", domain[0][2])
        self.assertIn("critical", domain[0][2])

    def test_get_damage_level_domain_severe_up(self):
        """Test damage level domain for 'severe_up'."""
        self.program.qualifying_damage_levels = "severe_up"
        domain = self.program._get_damage_level_domain()
        self.assertEqual(len(domain), 1)
        self.assertNotIn("moderate", domain[0][2])
        self.assertIn("severe", domain[0][2])
        self.assertIn("critical", domain[0][2])

    def test_get_damage_level_domain_critical_only(self):
        """Test damage level domain for 'critical_only'."""
        self.program.qualifying_damage_levels = "critical_only"
        domain = self.program._get_damage_level_domain()
        self.assertEqual(len(domain), 1)
        self.assertIn("critical", domain[0][2])
        self.assertNotIn("moderate", domain[0][2])
        self.assertNotIn("severe", domain[0][2])

    def test_get_emergency_eligible_registrants(self):
        """Test getting eligible registrants for emergency program."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "any",
            }
        )
        registrants = self.program.get_emergency_eligible_registrants()
        self.assertEqual(len(registrants), 2)
        self.assertIn(self.registrant_1, registrants)
        self.assertIn(self.registrant_2, registrants)
        # Unverified registrant should not be included
        self.assertNotIn(self.registrant_3, registrants)

    def test_get_emergency_eligible_registrants_no_incidents(self):
        """Test eligible registrants returns empty when no incidents linked."""
        registrants = self.program.get_emergency_eligible_registrants()
        self.assertEqual(len(registrants), 0)

    def test_get_emergency_eligible_registrants_with_filter(self):
        """Test eligible registrants respects damage level filter."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "critical_only",
            }
        )
        registrants = self.program.get_emergency_eligible_registrants()
        self.assertEqual(len(registrants), 1)
        self.assertIn(self.registrant_1, registrants)

    def test_action_view_target_incidents(self):
        """Test action returns correct window action for target incidents."""
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        action = self.program.action_view_target_incidents()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.hazard.incident")
        self.assertEqual(action["domain"], [("id", "in", self.program.target_incident_ids.ids)])

    def test_action_view_affected_registrants(self):
        """Test action returns correct window action for affected registrants."""
        self.program.write(
            {
                "target_incident_ids": [Command.link(self.incident_active.id)],
                "qualifying_damage_levels": "any",
            }
        )
        action = self.program.action_view_affected_registrants()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        # Should contain the 2 verified registrants
        self.assertEqual(len(action["domain"][0][2]), 2)

    def test_bidirectional_many2many(self):
        """Test that the many2many relationship is bidirectional."""
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.assertIn(self.program, self.incident_active.program_ids)
        self.assertIn(self.incident_active, self.program.target_incident_ids)


@tagged("post_install", "-at_install")
class TestIncidentProgramIntegration(HazardProgramsTestCase):
    """Test incident extensions for program integration."""

    def test_program_count(self):
        """Test that program_count computes correctly."""
        self.assertEqual(self.incident_active.program_count, 0)

        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.incident_active.invalidate_recordset(["program_ids", "program_count"])
        self.assertEqual(self.incident_active.program_count, 1)

    def test_program_count_multiple_programs(self):
        """Test program_count with multiple programs linked."""
        program_2 = self.env["spp.program"].create({"name": "Second Emergency Program"})
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        program_2.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.incident_active.invalidate_recordset(["program_ids", "program_count"])
        self.assertEqual(self.incident_active.program_count, 2)

    def test_action_view_programs(self):
        """Test action returns correct window action for programs."""
        self.program.write({"target_incident_ids": [Command.link(self.incident_active.id)]})
        self.incident_active.invalidate_recordset(["program_ids", "program_count"])
        action = self.incident_active.action_view_programs()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.program")
        self.assertEqual(action["domain"], [("id", "in", self.incident_active.program_ids.ids)])
