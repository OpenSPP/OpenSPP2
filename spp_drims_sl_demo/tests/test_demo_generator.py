# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from odoo.addons.spp_drims.tests.common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDemoGenerator(DrimsTestCommon):
    """Tests for DRIMS Demo Generator."""

    def setUp(self):
        super().setUp()
        # Clean up any existing demo incidents to avoid unique constraint violations
        # Demo incidents have codes starting with "SL-2025-"
        existing_incidents = self.env["spp.hazard.incident"].search(
            [
                ("code", "=like", "SL-2025-%"),
            ]
        )
        if existing_incidents:
            # Delete related records first
            self.env["spp.drims.donation"].search(
                [
                    ("incident_id", "in", existing_incidents.ids),
                ]
            ).unlink()
            self.env["spp.drims.request"].search(
                [
                    ("incident_id", "in", existing_incidents.ids),
                ]
            ).unlink()
            self.env["spp.drims.alert"].search(
                [
                    ("incident_id", "in", existing_incidents.ids),
                ]
            ).unlink()
            existing_incidents.unlink()

    def test_generator_creates_wizard(self):
        """Test demo generator wizard can be created."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "name": "Test Demo",
                "demo_mode": "quick",
            }
        )
        self.assertEqual(wizard.state, "draft")
        # Note: onchange not triggered during create(), uses default value
        self.assertEqual(wizard.incident_count, 2)

    def test_generator_mode_quick(self):
        """Test quick mode sets minimal values."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "demo_mode": "quick",
            }
        )
        wizard._onchange_demo_mode()
        self.assertEqual(wizard.incident_count, 1)
        self.assertEqual(wizard.donations_per_incident, 3)
        self.assertEqual(wizard.requests_per_incident, 5)

    def test_generator_mode_standard(self):
        """Test standard mode sets balanced values."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "demo_mode": "standard",
            }
        )
        wizard._onchange_demo_mode()
        self.assertEqual(wizard.incident_count, 2)
        self.assertEqual(wizard.donations_per_incident, 5)
        self.assertEqual(wizard.requests_per_incident, 10)

    def test_generator_mode_full(self):
        """Test full mode sets comprehensive values."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "demo_mode": "full",
            }
        )
        wizard._onchange_demo_mode()
        self.assertEqual(wizard.incident_count, 3)
        self.assertEqual(wizard.donations_per_incident, 8)
        self.assertEqual(wizard.requests_per_incident, 15)

    def test_get_demo_warehouses(self):
        """Test warehouse retrieval."""
        wizard = self.env["spp.drims.demo.generator"].create({})
        warehouses = wizard._get_demo_warehouses()
        # Should find DRIMS warehouses
        self.assertTrue(all(w.is_drims_warehouse for w in warehouses))

    def test_action_generate_quick_mode(self):
        """Test full demo generation in quick mode creates expected records."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "name": "Integration Test Demo",
                "demo_mode": "quick",
                "is_import_areas": False,  # Skip area import for test speed
            }
        )
        wizard._onchange_demo_mode()

        # Run the generation
        wizard.action_generate()

        # Verify wizard completed
        self.assertEqual(wizard.state, "completed")

        # Verify actual records exist in database (demo incidents use SL- code prefix)
        incidents = self.env["spp.hazard.incident"].search(
            [
                ("code", "=like", "SL-2025-%"),
            ]
        )
        self.assertGreater(len(incidents), 0, "No incidents were created")

        donations = self.env["spp.drims.donation"].search(
            [
                ("incident_id", "in", incidents.ids),
            ]
        )
        self.assertGreater(len(donations), 0, "No donations were created")

        requests = self.env["spp.drims.request"].search(
            [
                ("incident_id", "in", incidents.ids),
            ]
        )
        self.assertGreater(len(requests), 0, "No requests were created")

    def test_action_generate_creates_valid_donations(self):
        """Test that generated donations have valid state transitions."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "name": "Donation State Test",
                "demo_mode": "quick",
                "is_import_areas": False,
                "incident_count": 1,
                "donations_per_incident": 5,
                "requests_per_incident": 0,  # Skip requests
            }
        )

        wizard.action_generate()

        # Get generated donations (demo incidents use SL- code prefix)
        incidents = self.env["spp.hazard.incident"].search(
            [
                ("code", "=like", "SL-2025-%"),
            ]
        )
        donations = self.env["spp.drims.donation"].search(
            [
                ("incident_id", "in", incidents.ids),
            ]
        )

        # Verify donations exist and have valid states
        self.assertGreater(len(donations), 0)
        valid_states = ["announced", "received", "inspected", "stocked", "cancelled"]
        for donation in donations:
            self.assertIn(
                donation.state, valid_states, f"Donation {donation.reference} has invalid state: {donation.state}"
            )

    def test_action_generate_creates_valid_requests(self):
        """Test that generated requests have valid state transitions."""
        wizard = self.env["spp.drims.demo.generator"].create(
            {
                "name": "Request State Test",
                "demo_mode": "quick",
                "is_import_areas": False,
                "incident_count": 1,
                "donations_per_incident": 0,  # Skip donations
                "requests_per_incident": 5,
            }
        )

        wizard.action_generate()

        # Get generated requests (demo incidents use SL- code prefix)
        incidents = self.env["spp.hazard.incident"].search(
            [
                ("code", "=like", "SL-2025-%"),
            ]
        )
        requests = self.env["spp.drims.request"].search(
            [
                ("incident_id", "in", incidents.ids),
            ]
        )

        # Verify requests exist and have valid states
        self.assertGreater(len(requests), 0)
        valid_states = [
            "draft",
            "submitted",
            "pending",
            "revision",
            "approved",
            "rejected",
            "allocated",
            "fulfilled",
            "cancelled",
        ]
        for request in requests:
            self.assertIn(
                request.state, valid_states, f"Request {request.reference} has invalid state: {request.state}"
            )
