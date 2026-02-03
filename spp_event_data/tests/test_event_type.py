# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestEventType(TransactionCase):
    """Tests for the spp.event.type model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.EventType = cls.env["spp.event.type"]
        cls.EventField = cls.env["spp.event.field"]

    def test_01_create_event_type(self):
        """Test basic event type creation."""
        event_type = self.EventType.create(
            {
                "name": "Household Survey",
                "code": "hh_survey",
                "category": "survey",
                "target_type": "group",
            }
        )
        self.assertEqual(event_type.name, "Household Survey")
        self.assertEqual(event_type.code, "hh_survey")
        self.assertEqual(event_type.category, "survey")
        self.assertEqual(event_type.storage_mode, "json")

    def test_02_event_type_unique_code(self):
        """Test that event type code must be unique."""
        self.EventType.create({"name": "Survey 1", "code": "unique_code"})
        with mute_logger("odoo.sql_db"):
            with self.assertRaises(IntegrityError):
                self.EventType.create({"name": "Survey 2", "code": "unique_code"})

    def test_03_storage_mode_computation(self):
        """Test storage mode is computed correctly."""
        # JSON mode (no model, no fields)
        event_type = self.EventType.create({"name": "JSON Event", "code": "json_event"})
        self.assertEqual(event_type.storage_mode, "json")

        # Fields mode (has field_ids)
        event_type_with_fields = self.EventType.create({"name": "Fields Event", "code": "fields_event"})
        self.EventField.create(
            {
                "event_type_id": event_type_with_fields.id,
                "name": "income",
                "label": "Household Income",
                "field_type": "float",
            }
        )
        # Recompute
        event_type_with_fields.invalidate_recordset()
        self.assertEqual(event_type_with_fields.storage_mode, "fields")

    def test_04_event_field_creation(self):
        """Test creating fields for an event type."""
        event_type = self.EventType.create({"name": "Assessment", "code": "assessment"})

        # Create multiple fields
        field1 = self.EventField.create(
            {
                "event_type_id": event_type.id,
                "name": "score",
                "label": "Assessment Score",
                "field_type": "integer",
                "required": True,
            }
        )
        field2 = self.EventField.create(
            {
                "event_type_id": event_type.id,
                "name": "notes",
                "label": "Notes",
                "field_type": "text",
            }
        )

        self.assertEqual(len(event_type.field_ids), 2)
        self.assertEqual(field1.required, True)
        self.assertEqual(field2.field_type, "text")

    def test_05_field_unique_per_type(self):
        """Test that field names must be unique per event type."""
        event_type = self.EventType.create({"name": "Unique Fields", "code": "unique_fields"})
        self.EventField.create(
            {
                "event_type_id": event_type.id,
                "name": "field1",
                "label": "Field 1",
                "field_type": "char",
            }
        )
        with mute_logger("odoo.sql_db"):
            with self.assertRaises(IntegrityError):
                self.EventField.create(
                    {
                        "event_type_id": event_type.id,
                        "name": "field1",
                        "label": "Duplicate Field",
                        "field_type": "char",
                    }
                )

    def test_06_lifecycle_rules(self):
        """Test event type lifecycle rule fields."""
        event_type = self.EventType.create(
            {
                "name": "Expiring Event",
                "code": "expiring",
                "is_one_active_per_registrant": True,
                "auto_expire_days": 365,
            }
        )
        self.assertTrue(event_type.is_one_active_per_registrant)
        self.assertEqual(event_type.auto_expire_days, 365)

    def test_07_external_source_config(self):
        """Test external source configuration fields."""
        event_type = self.EventType.create(
            {
                "name": "ODK Survey",
                "code": "odk_survey",
                "source_type": "odk",
                "external_server_url": "https://odk.example.com",
                "external_project_id": "proj-123",
                "external_form_id": "hh_survey_v1",
                "registrant_id_field": "beneficiary_id",
            }
        )
        self.assertEqual(event_type.source_type, "odk")
        self.assertEqual(event_type.external_server_url, "https://odk.example.com")
        self.assertEqual(event_type.registrant_id_field, "beneficiary_id")
