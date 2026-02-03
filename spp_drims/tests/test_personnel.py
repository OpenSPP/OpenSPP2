# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.tests.common import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsPersonnel(DrimsTestCommon):
    """Test cases for DRIMS Personnel functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Link warehouse to incident
        cls.warehouse.incident_ids = [(4, cls.incident.id)]

        # Create a partner for testing
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "John Smith",
                "phone": "+94771234567",
                "email": "john.smith@example.com",
            }
        )

        # Get personnel role vocabulary codes (if they exist)
        cls.role_field_officer = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:personnel-roles"),
                ("code", "=", "field_officer"),
            ],
            limit=1,
        )

        # Create an organization
        cls.organization = cls.env["res.partner"].create(
            {
                "name": "Red Cross",
                "is_drims_organization": True,
            }
        )

    def test_personnel_creation(self):
        """Test creating personnel record, verify default status."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Jane Doe",
                "incident_id": self.incident.id,
                "deployment_area_id": self.area.id,
                "phone": "+94777654321",
                "email": "jane@example.com",
            }
        )

        # Verify default status is "deployed"
        self.assertEqual(personnel.status, "deployed")
        self.assertEqual(personnel.name, "Jane Doe")
        self.assertEqual(personnel.incident_id, self.incident)
        self.assertEqual(personnel.deployment_area_id, self.area)
        self.assertEqual(personnel.phone, "+94777654321")
        self.assertEqual(personnel.email, "jane@example.com")

    def test_days_deployed_computation(self):
        """Test days_deployed computed correctly."""
        # Create personnel deployed 10 days ago
        deployment_date = date.today() - timedelta(days=10)
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Test Personnel",
                "incident_id": self.incident.id,
                "deployment_date": deployment_date,
                "status": "deployed",
            }
        )

        # Verify days_deployed is 10
        self.assertEqual(personnel.days_deployed, 10)

        # Mark as returned today
        personnel.action_mark_returned()

        # Days deployed should still be 10
        self.assertEqual(personnel.days_deployed, 10)

    def test_status_transitions(self):
        """Test all action methods (mark_deployed, mark_returned, etc.)."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Test Personnel",
                "incident_id": self.incident.id,
                "status": "deployed",
            }
        )

        # Test mark_on_leave
        personnel.action_mark_on_leave()
        self.assertEqual(personnel.status, "on_leave")

        # Test mark_standby
        personnel.action_mark_standby()
        self.assertEqual(personnel.status, "standby")

        # Test mark_deployed
        personnel.action_mark_deployed()
        self.assertEqual(personnel.status, "deployed")
        self.assertFalse(personnel.actual_return_date)

        # Test mark_returned
        personnel.action_mark_returned()
        self.assertEqual(personnel.status, "returned")
        self.assertEqual(personnel.actual_return_date, date.today())

        # Test mark_deployed again (should clear return date)
        personnel.action_mark_deployed()
        self.assertEqual(personnel.status, "deployed")
        self.assertFalse(personnel.actual_return_date)

    def test_partner_onchange(self):
        """Test setting partner auto-fills name/phone/email."""
        # Create personnel with minimal required fields
        personnel = self.env["spp.drims.personnel"].new(
            {
                "incident_id": self.incident.id,
            }
        )

        # Set partner and trigger onchange
        personnel.partner_id = self.partner
        personnel._onchange_partner_id()

        # Verify fields are auto-filled
        self.assertEqual(personnel.name, "John Smith")
        self.assertEqual(personnel.phone, "+94771234567")
        self.assertEqual(personnel.email, "john.smith@example.com")

    def test_partner_onchange_preserves_existing_values(self):
        """Test partner onchange doesn't overwrite existing values."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Existing Name",
                "phone": "+94111111111",
                "email": "existing@example.com",
                "incident_id": self.incident.id,
            }
        )

        # Set partner and trigger onchange
        personnel.partner_id = self.partner
        personnel._onchange_partner_id()

        # Verify existing values are preserved
        self.assertEqual(personnel.name, "Existing Name")
        self.assertEqual(personnel.phone, "+94111111111")
        self.assertEqual(personnel.email, "existing@example.com")

    def test_display_name_computation(self):
        """Test display_name includes role and organization."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "John Doe",
                "incident_id": self.incident.id,
                "organization_id": self.organization.id,
            }
        )

        # Verify display name includes organization
        self.assertIn("John Doe", personnel.display_name)
        self.assertIn("Red Cross", personnel.display_name)

        # Add role if available
        if self.role_field_officer:
            personnel.role_id = self.role_field_officer
            # Force recompute
            personnel._compute_display_name()
            self.assertIn("John Doe", personnel.display_name)

    def test_deployment_with_warehouse(self):
        """Test personnel can be assigned to a warehouse."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Warehouse Manager",
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.assertEqual(personnel.warehouse_id, self.warehouse)

    def test_expected_vs_actual_return_date(self):
        """Test expected vs actual return date tracking."""
        expected_return = date.today() + timedelta(days=30)
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Test Personnel",
                "incident_id": self.incident.id,
                "deployment_date": date.today(),
                "expected_return_date": expected_return,
            }
        )

        # Verify expected return date is set
        self.assertEqual(personnel.expected_return_date, expected_return)
        self.assertFalse(personnel.actual_return_date)

        # Mark as returned
        personnel.action_mark_returned()

        # Verify actual return date is set
        self.assertEqual(personnel.actual_return_date, date.today())
        self.assertEqual(personnel.expected_return_date, expected_return)  # Unchanged

    def test_personnel_skills_and_certifications(self):
        """Test personnel skills and language fields."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Specialist",
                "incident_id": self.incident.id,
                "skills": "First Aid, Water Purification, Shelter Construction",
                "languages": "Sinhala, Tamil, English",
                "radio_callsign": "ALPHA-7",
            }
        )

        self.assertEqual(personnel.skills, "First Aid, Water Purification, Shelter Construction")
        self.assertEqual(personnel.languages, "Sinhala, Tamil, English")
        self.assertEqual(personnel.radio_callsign, "ALPHA-7")

    def test_days_deployed_with_no_deployment_date(self):
        """Test days_deployed is 0 when no deployment date is set."""
        personnel = self.env["spp.drims.personnel"].create(
            {
                "name": "Test Personnel",
                "incident_id": self.incident.id,
            }
        )

        # Clear deployment date
        personnel.deployment_date = False

        # Verify days_deployed is 0
        self.assertEqual(personnel.days_deployed, 0)
