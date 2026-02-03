# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo.tests import TransactionCase


class TestEventData(TransactionCase):
    """Tests for spp.event.data model - Legacy and New approaches."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_partner = cls.env["res.partner"].create(
            {
                "name": "Cao Cao",
                "is_registrant": True,
            }
        )
        # Create an event type for new-style tests
        cls._event_type = cls.env["spp.event.type"].create(
            {
                "name": "Test Survey",
                "code": "test_survey",
                "category": "survey",
                "target_type": "both",
                "is_one_active_per_registrant": True,
            }
        )

    # ══════════════════════════════════════════════════════════════
    # LEGACY TESTS (backward compatibility)
    # Note: Legacy model-based events are deprecated in favor of
    # event_type_id based events. These tests verify basic creation
    # but the full lifecycle management requires event_type_id.
    # ══════════════════════════════════════════════════════════════

    def create_mock_event(self):
        """Create a legacy-style event using model reference."""
        return self.env["spp.event.data"].create(
            {
                "partner_id": self._test_partner.id,
                "model": "res.partner",
                "res_id": self._test_partner.id,
            }
        )

    def test_01_mock_event_type(self):
        """Legacy: Mock event should be created successfully."""
        mock_event = self.create_mock_event()
        # Legacy events can be created without event_type_id
        self.assertTrue(mock_event.id, "Mock event should be created!")
        self.assertEqual(mock_event.state, "draft")

    def test_02_mock_event_state(self):
        """Legacy: Events without event_type_id stay in draft state.

        Note: Full lifecycle management (superseding previous events)
        requires event_type_id with one_active_per_registrant=True.
        """
        mock_event_1 = self.create_mock_event()
        mock_event_2 = self.create_mock_event()
        # Legacy events without event_type_id don't have automatic lifecycle management
        self.assertEqual(mock_event_1.state, "draft")
        self.assertEqual(mock_event_2.state, "draft")

    def test_03_active_mock_event(self):
        """Legacy: _get_active_event_id requires event_type_code for new events.

        Legacy model-based lookup still works for backward compatibility.
        """
        mock_event_2 = self.create_mock_event()
        # Manually activate the second event
        mock_event_2.write({"state": "active"})

        active_id = self._test_partner._get_active_event_id(model=self._test_partner._name)
        self.assertEqual(
            active_id,
            mock_event_2.id,
            "Mock event 2 should be active event for test_partner!",
        )

    # ══════════════════════════════════════════════════════════════
    # NEW TESTS (event_type based)
    # ══════════════════════════════════════════════════════════════

    def create_typed_event(self, data_json=None, state="draft"):
        """Create a new-style event using event_type_id."""
        vals = {
            "partner_id": self._test_partner.id,
            "event_type_id": self._event_type.id,
            "collection_date": date.today(),
            "state": state,
        }
        if data_json:
            vals["data_json"] = data_json
        return self.env["spp.event.data"].create(vals)

    def test_10_create_typed_event(self):
        """New: Create event with event_type_id."""
        event = self.create_typed_event(data_json={"income": 5000, "household_size": 4})
        self.assertEqual(event.event_type_id, self._event_type)
        self.assertEqual(event.event_type_code, "test_survey")
        self.assertEqual(event.state, "draft")

    def test_11_event_name_computation(self):
        """New: Event name should be computed from type, partner, and date."""
        event = self.create_typed_event()
        self.assertIn("Test Survey", event.name)
        self.assertIn("Cao Cao", event.name)

    def test_12_data_values_json(self):
        """New: data_values should return JSON data."""
        test_data = {"income": 5000, "members": ["A", "B", "C"]}
        event = self.create_typed_event(data_json=test_data)
        self.assertEqual(event.data_values.get("income"), 5000)
        self.assertEqual(len(event.data_values.get("members", [])), 3)

    def test_13_get_data_value_helper(self):
        """New: get_data_value helper method."""
        event = self.create_typed_event(data_json={"score": 85})
        self.assertEqual(event.get_data_value("score"), 85)
        self.assertEqual(event.get_data_value("missing", "default"), "default")

    def test_14_set_data_value_helper(self):
        """New: set_data_value helper method."""
        event = self.create_typed_event(data_json={"initial": True})
        event.set_data_value("new_field", "new_value")
        self.assertEqual(event.data_json.get("new_field"), "new_value")
        self.assertTrue(event.data_json.get("initial"))

    def test_15_activation_supersedes(self):
        """New: Activating event should supersede previous active."""
        event1 = self.create_typed_event()
        event1.action_activate()
        self.assertEqual(event1.state, "active")

        event2 = self.create_typed_event()
        # event2 should have supersedes_id set to event1
        self.assertEqual(event2.supersedes_id, event1)

        event2.action_activate()
        self.assertEqual(event2.state, "active")
        self.assertEqual(event1.state, "superseded")
        self.assertEqual(event1.superseded_by_id, event2)

    def test_16_cancel_event(self):
        """New: Cancel event should set state to cancelled."""
        event = self.create_typed_event()
        event.action_cancel()
        self.assertEqual(event.state, "cancelled")

    def test_17_reset_to_draft(self):
        """New: Reset cancelled event to draft."""
        event = self.create_typed_event()
        event.action_cancel()
        event.action_set_draft()
        self.assertEqual(event.state, "draft")

    def test_18_auto_expire_date(self):
        """New: Auto-expire days should set expiry_date on create."""
        # Create event type with auto_expire
        expire_type = self.env["spp.event.type"].create(
            {
                "name": "Expiring Survey",
                "code": "expire_test",
                "auto_expire_days": 30,
            }
        )
        event = self.env["spp.event.data"].create(
            {
                "partner_id": self._test_partner.id,
                "event_type_id": expire_type.id,
                "collection_date": date.today(),
            }
        )
        expected_expiry = date.today() + timedelta(days=30)
        self.assertEqual(event.expiry_date, expected_expiry)

    def test_19_is_expired_computation(self):
        """New: is_expired should be computed based on expiry_date."""
        event = self.create_typed_event()
        event.expiry_date = date.today() - timedelta(days=1)
        event.invalidate_recordset(["is_expired"])
        self.assertTrue(event.is_expired)

        event.expiry_date = date.today() + timedelta(days=1)
        event.invalidate_recordset(["is_expired"])
        self.assertFalse(event.is_expired)

    def test_20_get_active_event_by_type_code(self):
        """New: _get_active_event_id with event_type_code."""
        event = self.create_typed_event()
        event.action_activate()

        active_id = self._test_partner._get_active_event_id(event_type_code="test_survey")
        self.assertEqual(active_id, event.id)

    def test_21_get_active_event_helper(self):
        """New: get_active_event returns record."""
        event = self.create_typed_event()
        event.action_activate()

        active_event = self._test_partner.get_active_event("test_survey")
        self.assertEqual(active_event, event)

    def test_22_get_event_data_value_helper(self):
        """New: Partner helper to get event data value."""
        event = self.create_typed_event(data_json={"target_score": 75})
        event.action_activate()

        score = self._test_partner.get_event_data_value("test_survey", "target_score")
        self.assertEqual(score, 75)

    def test_23_source_tracking_fields(self):
        """New: External source tracking fields."""
        event = self.env["spp.event.data"].create(
            {
                "partner_id": self._test_partner.id,
                "event_type_id": self._event_type.id,
                "collection_date": date.today(),
                "source_reference": "odk-12345",
                "source_url": "https://odk.example.com/submission/12345",
                "source_raw_data": {"raw": "data", "from": "odk"},
            }
        )
        self.assertEqual(event.source_reference, "odk-12345")
        self.assertEqual(event.source_raw_data.get("from"), "odk")
