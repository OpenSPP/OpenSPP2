from datetime import date

from odoo.tests import TransactionCase


class TestCreateEventWizard(TransactionCase):
    """Tests for the create event wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant for Event",
                "is_registrant": True,
            }
        )
        # Create an event type for testing
        cls.event_type = cls.env["spp.event.type"].create(
            {
                "name": "Wizard Test Event",
                "code": "wizard_test",
                "category": "survey",
            }
        )

    def test_create_event_with_event_type(self):
        """Test creating an event using the new event_type_id approach."""
        wizard = self.env["spp.create.event.wizard"].create(
            {
                "event_type_id": self.event_type.id,
                "partner_id": self.registrant.id,
                "registrar": "Test Registrar",
                "collection_date": date(2024, 1, 15),
                "expiry_date": date(2025, 1, 15),
            }
        )

        action = wizard.create_event()

        # Verify that an spp.event.data record was created with correct values
        event_data = self.env["spp.event.data"].search([("partner_id", "=", self.registrant.id)])
        self.assertEqual(len(event_data), 1, "An spp.event.data record should have been created.")
        self.assertEqual(event_data.event_type_id, self.event_type)
        self.assertEqual(event_data.collector_name, "Test Registrar")
        self.assertEqual(event_data.collection_date, date(2024, 1, 15))

        # Verify the action returns to the event form
        self.assertEqual(action["res_model"], "spp.event.data")
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_wizard_default_close(self):
        """Test wizard closes when no event type selected."""
        wizard = self.env["spp.create.event.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "collection_date": date(2024, 1, 15),
            }
        )

        # Without event_type_id, next_page should close
        action = wizard.next_page()
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_get_event_data_vals(self):
        """Test get_event_data_vals returns correct dictionary."""
        wizard = self.env["spp.create.event.wizard"].create(
            {
                "event_type_id": self.event_type.id,
                "partner_id": self.registrant.id,
                "registrar": "Test Collector",
                "collection_date": date(2024, 6, 15),
            }
        )

        vals = wizard.get_event_data_vals()

        self.assertEqual(vals["partner_id"], self.registrant.id)
        self.assertEqual(vals["event_type_id"], self.event_type.id)
        self.assertEqual(vals["collector_name"], "Test Collector")
        self.assertEqual(vals["collection_date"], date(2024, 6, 15))
