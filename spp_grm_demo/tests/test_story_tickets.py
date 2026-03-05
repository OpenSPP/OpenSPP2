# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase


class TestStoryTicketDefinitions(TransactionCase):
    """Test GRM story ticket definitions."""

    def test_grm_story_tickets_defined(self):
        """Test that GRM story tickets are properly defined."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        self.assertIsInstance(GRM_STORY_TICKETS, dict)
        self.assertGreater(len(GRM_STORY_TICKETS), 0)

        # Check expected stories exist (aligned with MIS demo personas)
        expected_stories = [
            "juan_dela_cruz",
            "fatima_al_rahman",
            "ibrahim_hassan",
            "ahmed_said",
            "david_martinez",
            "maria_santos",
            "rosa_garcia",
            "carlos_morales",
        ]
        for story_id in expected_stories:
            self.assertIn(
                story_id,
                GRM_STORY_TICKETS,
                f"Story '{story_id}' should be defined in GRM_STORY_TICKETS",
            )

    def test_story_tickets_have_required_fields(self):
        """Test that all story tickets have required fields."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        required_fields = ["title", "description", "category", "priority", "days_back"]

        for story_id, story_data in GRM_STORY_TICKETS.items():
            self.assertIn("tickets", story_data, f"Story '{story_id}' missing 'tickets' key")

            for i, ticket in enumerate(story_data["tickets"]):
                for field in required_fields:
                    self.assertIn(
                        field,
                        ticket,
                        f"Story '{story_id}' ticket {i} missing required field '{field}'",
                    )

    def test_juan_dela_cruz_story(self):
        """Test Juan Dela Cruz story ticket definition."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        juan = GRM_STORY_TICKETS.get("juan_dela_cruz")
        self.assertIsNotNone(juan)

        tickets = juan.get("tickets", [])
        self.assertEqual(len(tickets), 1)

        ticket = tickets[0]
        self.assertEqual(ticket["title"], "Payment not received after house fire")
        self.assertEqual(ticket["category"], "payment")
        self.assertEqual(ticket["priority"], "high")
        self.assertEqual(ticket["program_name"], "Cash Transfer Program")
        self.assertTrue(ticket.get("escalate_to_case"))  # Should escalate to case management

        # Should have resolution
        resolution = ticket.get("resolution")
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["decision"], "upheld")
        self.assertGreater(len(resolution.get("notes", [])), 0)

    def test_fatima_al_rahman_story(self):
        """Test Fatima Al-Rahman story ticket definition."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        fatima = GRM_STORY_TICKETS.get("fatima_al_rahman")
        self.assertIsNotNone(fatima)

        tickets = fatima.get("tickets", [])
        self.assertEqual(len(tickets), 1)

        ticket = tickets[0]
        self.assertEqual(ticket["title"], "How do I qualify for Universal Child Grant?")
        self.assertEqual(ticket["priority"], "low")
        self.assertEqual(ticket["program_name"], "Universal Child Grant")
        self.assertTrue(ticket.get("escalate_to_case"))  # Should escalate to case assessment

        # Should have quick resolution
        resolution = ticket.get("resolution")
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["days_to_close"], 2)

    def test_ibrahim_hassan_story(self):
        """Test Ibrahim Hassan story ticket definition."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        ibrahim = GRM_STORY_TICKETS.get("ibrahim_hassan")
        self.assertIsNotNone(ibrahim)

        tickets = ibrahim.get("tickets", [])
        self.assertEqual(len(tickets), 1)

        ticket = tickets[0]
        self.assertEqual(ticket["title"], "Request for resettlement support")

        # Should remain open (no resolution)
        self.assertIsNone(ticket.get("resolution"))

    def test_ahmed_said_story(self):
        """Test Ahmed Said story with multiple tickets."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        ahmed = GRM_STORY_TICKETS.get("ahmed_said")
        self.assertIsNotNone(ahmed)

        tickets = ahmed.get("tickets", [])
        self.assertEqual(len(tickets), 3)

        # Check different ticket types (updated titles)
        titles = [t["title"] for t in tickets]
        self.assertIn("Payment delayed - third occurrence", titles)
        self.assertIn("Update bank account information", titles)
        self.assertIn("Question about next payment schedule", titles)

        # All should have resolutions
        for ticket in tickets:
            self.assertIsNotNone(
                ticket.get("resolution"),
                f"Ahmed's ticket '{ticket['title']}' should have resolution",
            )

    def test_valid_categories(self):
        """Test that all tickets use valid categories."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        valid_categories = [
            "payment",
            "eligibility",
            "service",
            "general",
            "registration",
            "feedback",
        ]

        for story_id, story_data in GRM_STORY_TICKETS.items():
            for ticket in story_data.get("tickets", []):
                category = ticket.get("category")
                self.assertIn(
                    category,
                    valid_categories,
                    f"Story '{story_id}' uses invalid category '{category}'",
                )

    def test_valid_priorities(self):
        """Test that all tickets use valid priorities."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        valid_priorities = ["low", "medium", "high", "very_high"]

        for story_id, story_data in GRM_STORY_TICKETS.items():
            for ticket in story_data.get("tickets", []):
                priority = ticket.get("priority")
                self.assertIn(
                    priority,
                    valid_priorities,
                    f"Story '{story_id}' uses invalid priority '{priority}'",
                )

    def test_valid_decisions(self):
        """Test that all resolutions use valid decisions."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        valid_decisions = [
            "upheld",
            "partially_upheld",
            "rejected",
            "withdrawn",
            "redirected",
        ]

        for story_id, story_data in GRM_STORY_TICKETS.items():
            for ticket in story_data.get("tickets", []):
                resolution = ticket.get("resolution")
                if resolution:
                    decision = resolution.get("decision")
                    self.assertIn(
                        decision,
                        valid_decisions,
                        f"Story '{story_id}' uses invalid decision '{decision}'",
                    )

    def test_days_back_positive(self):
        """Test that all days_back values are positive."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        for story_id, story_data in GRM_STORY_TICKETS.items():
            for ticket in story_data.get("tickets", []):
                days_back = ticket.get("days_back", 0)
                self.assertGreater(
                    days_back,
                    0,
                    f"Story '{story_id}' should have positive days_back",
                )

    def test_resolution_notes_have_text(self):
        """Test that resolution notes have text content."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        for story_id, story_data in GRM_STORY_TICKETS.items():
            for ticket in story_data.get("tickets", []):
                resolution = ticket.get("resolution")
                if resolution:
                    notes = resolution.get("notes", [])
                    for i, note in enumerate(notes):
                        self.assertIn(
                            "text",
                            note,
                            f"Story '{story_id}' note {i} missing 'text' field",
                        )
                        self.assertGreater(
                            len(note["text"]),
                            0,
                            f"Story '{story_id}' note {i} has empty text",
                        )

    def test_story_alignment_with_demo_stories(self):
        """Test that GRM stories match demo_stories.py personas."""
        from ..models.generate_tickets import GRM_STORY_TICKETS

        # These should match the names in spp_demo/models/demo_stories.py
        # and spp_mis_demo_v2/data/demo_personas.xml
        expected_name_mapping = {
            "juan_dela_cruz": "Juan Dela Cruz",
            "ibrahim_hassan": "Ibrahim Hassan",
            "fatima_al_rahman": "Fatima Al-Rahman",
            "ahmed_said": "Ahmed Said",
            "david_martinez": "David Martinez",
            "maria_santos": "Maria Santos",
            "rosa_garcia": "Rosa Garcia",
            "carlos_morales": "Carlos Morales",
        }

        for story_id in GRM_STORY_TICKETS.keys():
            self.assertIn(
                story_id,
                expected_name_mapping,
                f"Story ID '{story_id}' should be mapped to a demo story name",
            )
