# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError

from .common import HazardTestCase


class TestRegistrant(HazardTestCase):
    """Test cases for res.partner hazard extension."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Registrant Test Incident",
                "code": "REG-TEST-INC-001",
                "category_id": cls.category_typhoon.id,
                "start_date": "2024-01-01",
                "severity": "3",
            }
        )
        cls.impact = cls.env["spp.hazard.impact"].create(
            {
                "incident_id": cls.incident.id,
                "registrant_id": cls.registrant.id,
                "impact_type_id": cls.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )

    def test_hazard_impact_count(self):
        """Test that impact count updates when impacts are created/deleted."""
        self.assertEqual(self.registrant.hazard_impact_count, 1)

        # Create another impact
        impact2 = self.env["spp.hazard.impact"].create(
            {
                "incident_id": self.incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_property.id,
                "damage_level": "severe",
                "impact_date": "2024-01-02",
            }
        )
        self.assertEqual(self.registrant.hazard_impact_count, 2)

        # Delete impact
        impact2.unlink()
        self.assertEqual(self.registrant.hazard_impact_count, 1)

    def test_has_active_impact_with_active_incident(self):
        """Test flag is True when incident is active."""
        self.assertEqual(self.incident.status, "active")
        self.assertTrue(self.registrant.has_active_impact)

    def test_has_active_impact_with_closed_incident(self):
        """Test flag is False when incident is closed."""
        self.incident.write({"status": "closed", "end_date": "2024-01-15"})
        self.assertFalse(self.registrant.has_active_impact)

    def test_has_active_impact_transitions(self):
        """Test flag updates when incident status changes."""
        self.incident.write({"status": "active", "end_date": False})
        self.assertTrue(self.registrant.has_active_impact)

        # Move to recovery - should still be active
        self.incident.action_set_recovery()
        self.assertTrue(self.registrant.has_active_impact)

        # Close - should no longer be active
        self.incident.action_close()
        self.assertFalse(self.registrant.has_active_impact)

    def test_action_view_hazard_impacts(self):
        """Test the action returns correct domain and model."""
        action = self.registrant.action_view_hazard_impacts()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.hazard.impact")
        self.assertEqual(action["domain"], [("registrant_id", "=", self.registrant.id)])

    def test_get_impact_history(self):
        """Test impact history returns impacts sorted by date desc."""
        # Create a second impact with an earlier date
        self.env["spp.hazard.impact"].create(
            {
                "incident_id": self.incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_property.id,
                "damage_level": "minimal",
                "impact_date": "2024-01-01",
            }
        )
        history = self.registrant.get_impact_history()
        self.assertEqual(len(history), 2)
        # Most recent date first
        self.assertGreaterEqual(history[0].impact_date, history[1].impact_date)

    def test_get_active_incident_impacts(self):
        """Test filtering to only active/alert/recovery incidents."""
        self.incident.write({"status": "active", "end_date": False})
        active_impacts = self.registrant.get_active_incident_impacts()
        self.assertEqual(len(active_impacts), 1)

        # Close the incident
        self.incident.write({"status": "closed", "end_date": "2024-01-15"})
        active_impacts = self.registrant.get_active_incident_impacts()
        self.assertEqual(len(active_impacts), 0)

    def test_no_impacts(self):
        """Test fresh registrant has no impacts."""
        fresh = self.env["res.partner"].create(
            {
                "name": "Fresh Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.assertEqual(fresh.hazard_impact_count, 0)
        self.assertFalse(fresh.has_active_impact)
        self.assertEqual(len(fresh.get_impact_history()), 0)
        self.assertEqual(len(fresh.get_active_incident_impacts()), 0)

    def test_group_registrant_hazard_fields(self):
        """Test that group registrants also support hazard fields."""
        group = self.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.assertEqual(group.hazard_impact_count, 0)
        self.assertFalse(group.has_active_impact)


class TestRegistrantSecurity(HazardTestCase):
    """Test security access for hazard impacts on registrants."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Security Test Incident",
                "code": "SEC-TEST-INC-001",
                "category_id": cls.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )

    def test_viewer_can_read_impacts(self):
        """Test that viewers can read impact records (validates 1.3 fix)."""
        impact = self.env["spp.hazard.impact"].create(
            {
                "incident_id": self.incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )
        # Viewer should be able to read
        impact.with_user(self.hazard_viewer).read(["damage_level"])

    def test_viewer_cannot_create_incidents(self):
        """Test that viewers cannot create incidents."""
        with self.assertRaises(AccessError):
            self.env["spp.hazard.incident"].with_user(self.hazard_viewer).create(
                {
                    "name": "Viewer Incident",
                    "code": "VIEWER-INC",
                    "category_id": self.category_typhoon.id,
                    "start_date": "2024-01-01",
                }
            )

    def test_officer_can_create_incidents(self):
        """Test that officers can create incidents."""
        incident = (
            self.env["spp.hazard.incident"]
            .with_user(self.hazard_officer)
            .create(
                {
                    "name": "Officer Incident",
                    "code": "OFFICER-INC",
                    "category_id": self.category_typhoon.id,
                    "start_date": "2024-01-01",
                }
            )
        )
        self.assertTrue(incident)

    def test_officer_cannot_delete_incidents(self):
        """Test that officers cannot delete incidents."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Delete Test",
                "code": "DEL-TEST-INC",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )
        with self.assertRaises(AccessError):
            incident.with_user(self.hazard_officer).unlink()

    def test_officer_cannot_write_categories(self):
        """Test that officers cannot modify categories (validates 1.4 fix)."""
        with self.assertRaises(AccessError):
            self.category_typhoon.with_user(self.hazard_officer).write({"name": "Hacked"})

    def test_officer_cannot_create_categories(self):
        """Test that officers cannot create categories (validates 1.4 fix)."""
        with self.assertRaises(AccessError):
            self.env["spp.hazard.category"].with_user(self.hazard_officer).create(
                {
                    "name": "Unauthorized",
                    "code": "UNAUTH_CAT",
                }
            )

    def test_manager_has_full_access(self):
        """Test that managers can create and delete records."""
        incident = (
            self.env["spp.hazard.incident"]
            .with_user(self.hazard_manager)
            .create(
                {
                    "name": "Manager Incident",
                    "code": "MGR-INC",
                    "category_id": self.category_typhoon.id,
                    "start_date": "2024-01-01",
                }
            )
        )
        self.assertTrue(incident)
        incident.with_user(self.hazard_manager).unlink()
