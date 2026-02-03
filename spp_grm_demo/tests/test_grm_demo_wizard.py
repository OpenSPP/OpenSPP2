# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGRMDemoWizard(TransactionCase):
    """Test GRM Demo Wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test country for locale
        cls.test_country = cls.env.ref("base.us")

        # Create a test registrant for volume generation
        cls.test_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create GRM ticket stage if not exists
        cls.closed_stage = cls.env["spp.grm.ticket.stage"].search([("is_closed", "=", True)], limit=1)
        if not cls.closed_stage:
            cls.closed_stage = cls.env["spp.grm.ticket.stage"].create(
                {
                    "name": "Closed",
                    "is_closed": True,
                    "sequence": 100,
                }
            )

    def test_wizard_creation(self):
        """Test that wizard can be created with defaults."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Wizard",
            }
        )

        self.assertTrue(wizard.enroll_demo_stories)
        self.assertTrue(wizard.generate_volume)
        self.assertEqual(wizard.number_of_tickets, 50)
        self.assertEqual(wizard.tickets_days_back, 90)
        self.assertTrue(wizard.include_resolved)

    def test_wizard_constraints_valid_tickets(self):
        """Test that positive ticket count is valid."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test",
                "generate_volume": True,
                "number_of_tickets": 100,
            }
        )
        self.assertEqual(wizard.number_of_tickets, 100)

    def test_wizard_constraints_negative_tickets(self):
        """Test that negative ticket count raises error."""
        with self.assertRaises(UserError):
            self.env["spp.grm.demo.wizard"].create(
                {
                    "name": "Test",
                    "generate_volume": True,
                    "number_of_tickets": -1,
                }
            )

    def test_wizard_constraints_too_many_tickets(self):
        """Test that exceeding max tickets raises error."""
        with self.assertRaises(UserError):
            self.env["spp.grm.demo.wizard"].create(
                {
                    "name": "Test",
                    "number_of_tickets": 10001,
                }
            )

    def test_wizard_constraints_percentages(self):
        """Test percentage constraints."""
        # Valid percentages
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test",
                "resolved_percentage": 50.0,
                "escalated_percentage": 25.0,
            }
        )
        self.assertEqual(wizard.resolved_percentage, 50.0)

        # Invalid resolved percentage
        with self.assertRaises(UserError):
            self.env["spp.grm.demo.wizard"].create(
                {
                    "name": "Test",
                    "resolved_percentage": 150.0,
                }
            )

    def test_volume_generation_without_registrants(self):
        """Test that volume generation fails without registrants."""
        # Delete test registrant
        self.test_registrant.unlink()

        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test",
                "enroll_demo_stories": False,
                "generate_volume": True,
                "number_of_tickets": 5,
                "link_to_beneficiaries": True,
            }
        )

        with self.assertRaises(UserError):
            wizard.generate_tickets()

    def test_volume_generation_with_registrants(self):
        """Test volume generation with existing registrants."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Volume",
                "enroll_demo_stories": False,
                "generate_volume": True,
                "number_of_tickets": 5,
                "tickets_days_back": 30,
                "include_resolved": True,
                "resolved_percentage": 50.0,
                "link_to_beneficiaries": True,
                "locale_origin": self.test_country.id,
            }
        )

        result = wizard.generate_tickets()

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "spp.grm.ticket")

        # Check tickets were created
        ticket_ids = result.get("domain", [[]])[0][2]
        self.assertGreater(len(ticket_ids), 0)

    def test_story_tickets_without_registrants(self):
        """Test story tickets gracefully handles missing registrants."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Stories",
                "enroll_demo_stories": True,
                "generate_volume": False,
            }
        )

        # Should raise error since no story registrants exist
        with self.assertRaises(UserError):
            wizard.generate_tickets()

    def test_empty_generation(self):
        """Test generation with both options disabled."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Empty",
                "enroll_demo_stories": False,
                "generate_volume": False,
            }
        )

        # Should raise error since nothing to generate
        with self.assertRaises(UserError):
            wizard.generate_tickets()

    def test_load_scenarios(self):
        """Test that built-in scenarios are loaded."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Scenarios",
            }
        )

        scenarios = wizard._load_scenarios()

        self.assertIsInstance(scenarios, list)
        self.assertGreater(len(scenarios), 0)

        # Check expected scenario names
        scenario_names = [s.get("name") for s in scenarios]
        self.assertIn("Payment not received", scenario_names)
        self.assertIn("Information request", scenario_names)

    def test_scenario_weights(self):
        """Test that scenarios have weights for selection."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Weights",
            }
        )

        scenarios = wizard._load_scenarios()

        for scenario in scenarios:
            self.assertIn("weight", scenario)
            self.assertIsInstance(scenario["weight"], (int, float))
            self.assertGreater(scenario["weight"], 0)

    def test_get_or_create_category(self):
        """Test category creation."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Category",
            }
        )

        # Create new category
        category = wizard._get_or_create_category("test_category")
        self.assertIsNotNone(category)

        # Get existing category
        category2 = wizard._get_or_create_category("test_category")
        self.assertEqual(category.id, category2.id)

    def test_severity_distribution(self):
        """Test severity distribution generation."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Severity",
                "include_severity_distribution": True,
            }
        )

        # Generate multiple severities and check distribution
        severities = []
        for _ in range(100):
            severity = wizard._get_severity({})
            severities.append(severity)

        # Should have at least some low and medium
        self.assertIn("low", severities)
        self.assertIn("medium", severities)

    def test_sensitivity_distribution(self):
        """Test sensitivity distribution generation."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Sensitivity",
            }
        )

        # Generate multiple sensitivities
        sensitivities = []
        for _ in range(100):
            sensitivity = wizard._get_sensitivity({})
            sensitivities.append(sensitivity)

        # Should be mostly standard
        standard_count = sensitivities.count("standard")
        self.assertGreater(standard_count, 50)


@tagged("post_install", "-at_install")
class TestGRMDemoWizardWithStoryData(TransactionCase):
    """Test GRM Demo Wizard with story registrants."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_country = cls.env.ref("base.us")

        # Create closed stage
        cls.closed_stage = cls.env["spp.grm.ticket.stage"].search([("is_closed", "=", True)], limit=1)
        if not cls.closed_stage:
            cls.closed_stage = cls.env["spp.grm.ticket.stage"].create(
                {
                    "name": "Closed",
                    "is_closed": True,
                    "sequence": 100,
                }
            )

        # Create story registrants
        cls.juan = cls.env["res.partner"].create(
            {
                "name": "Juan Dela Cruz",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.fatima = cls.env["res.partner"].create(
            {
                "name": "Fatima Al-Rahman",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.ibrahim = cls.env["res.partner"].create(
            {
                "name": "Ibrahim Hassan",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.ahmed = cls.env["res.partner"].create(
            {
                "name": "Ahmed Said",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_story_tickets_creation(self):
        """Test that story tickets are created for existing registrants."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Story Tickets",
                "enroll_demo_stories": True,
                "generate_volume": False,
                "locale_origin": self.test_country.id,
            }
        )

        result = wizard.generate_tickets()

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("res_model"), "spp.grm.ticket")

        # Check Juan's ticket was created (updated title)
        juan_ticket = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.juan.id),
                ("name", "=", "Payment not received after house fire"),
            ]
        )
        self.assertEqual(len(juan_ticket), 1)

        # Check Fatima's ticket was created (updated title)
        fatima_ticket = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.fatima.id),
                ("name", "=", "How do I qualify for Universal Child Grant?"),
            ]
        )
        self.assertEqual(len(fatima_ticket), 1)

        # Check Ibrahim's ticket was created
        ibrahim_ticket = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.ibrahim.id),
                ("name", "=", "Request for resettlement support"),
            ]
        )
        self.assertEqual(len(ibrahim_ticket), 1)

        # Check Ahmed's multiple tickets were created
        ahmed_tickets = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.ahmed.id),
            ]
        )
        self.assertEqual(len(ahmed_tickets), 3)

    def test_story_ticket_resolution(self):
        """Test that story tickets have proper resolution workflows."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Resolution",
                "enroll_demo_stories": True,
                "generate_volume": False,
                "locale_origin": self.test_country.id,
            }
        )

        wizard.generate_tickets()

        # Juan's ticket should be closed with notes (updated title)
        juan_ticket = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.juan.id),
                ("name", "=", "Payment not received after house fire"),
            ]
        )

        self.assertEqual(juan_ticket.stage_id.is_closed, True)
        self.assertEqual(juan_ticket.decision, "upheld")

        # Should have resolution notes
        notes = juan_ticket.message_ids.filtered(lambda m: m.message_type == "comment")
        self.assertGreater(len(notes), 0)

    def test_story_ticket_open_status(self):
        """Test that open story tickets remain open."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Open",
                "enroll_demo_stories": True,
                "generate_volume": False,
                "locale_origin": self.test_country.id,
            }
        )

        wizard.generate_tickets()

        # Ibrahim's ticket should remain open
        ibrahim_ticket = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.ibrahim.id),
            ]
        )

        self.assertFalse(ibrahim_ticket.stage_id.is_closed)

    def test_combined_story_and_volume(self):
        """Test generating both story and volume tickets."""
        wizard = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Combined",
                "enroll_demo_stories": True,
                "generate_volume": True,
                "number_of_tickets": 5,
                "link_to_beneficiaries": True,
                "locale_origin": self.test_country.id,
            }
        )

        result = wizard.generate_tickets()

        # Get all created tickets
        ticket_ids = result.get("domain", [[]])[0][2]

        # Should have story tickets (6 total: 1 Juan, 1 Fatima, 1 Ibrahim, 3 Ahmed)
        # Plus 5 volume tickets = 11 total
        self.assertGreaterEqual(len(ticket_ids), 6)

    def test_idempotent_story_tickets(self):
        """Test that story tickets are created fresh each run."""
        # Run first generation
        wizard1 = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test First Run",
                "enroll_demo_stories": True,
                "generate_volume": False,
            }
        )
        wizard1.generate_tickets()

        # Count Juan's tickets
        juan_tickets_first = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.juan.id),
            ]
        )
        count_first = len(juan_tickets_first)

        # Run second generation
        wizard2 = self.env["spp.grm.demo.wizard"].create(
            {
                "name": "Test Second Run",
                "enroll_demo_stories": True,
                "generate_volume": False,
            }
        )
        wizard2.generate_tickets()

        # Should have double the tickets (no deduplication for demo)
        juan_tickets_second = self.env["spp.grm.ticket"].search(
            [
                ("partner_id", "=", self.juan.id),
            ]
        )
        self.assertEqual(len(juan_tickets_second), count_first * 2)
