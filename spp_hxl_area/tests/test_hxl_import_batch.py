# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHxlImportBatch(TransactionCase):
    """Test HXL Import Batch model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Batch = cls.env["spp.hxl.import.batch"]
        cls.Profile = cls.env["spp.hxl.import.profile"]
        cls.Rule = cls.env["spp.hxl.aggregation.rule"]
        cls.Indicator = cls.env["spp.hxl.area.indicator"]
        cls.Area = cls.env["spp.area"]

        # Create test profile
        cls.profile = cls.Profile.create(
            {
                "name": "Test Profile",
                "code": "test_batch_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
                "area_level": 2,
            }
        )

        cls.rule = cls.Rule.create(
            {
                "profile_id": cls.profile.id,
                "name": "Count All",
                "aggregation_type": "count",
                "output_hxl_tag": "#meta+count",
            }
        )

        # Create test areas
        cls.area1 = cls.Area.create(
            {
                "draft_name": "Test Area 1",
                "code": "A1",
                "level": 2,
            }
        )

    def test_create_batch(self):
        """Test creating a basic import batch."""
        batch = self.Batch.create(
            {
                "name": "Test Batch",
                "profile_id": self.profile.id,
            }
        )

        self.assertEqual(batch.name, "Test Batch")
        self.assertEqual(batch.profile_id, self.profile)
        self.assertEqual(batch.state, "draft")

    def test_batch_state_transitions(self):
        """Test batch state transitions."""
        batch = self.Batch.create(
            {
                "name": "State Test Batch",
                "profile_id": self.profile.id,
            }
        )

        self.assertEqual(batch.state, "draft")

        # Simulate state transitions
        batch.write({"state": "mapped"})
        self.assertEqual(batch.state, "mapped")

        batch.write({"state": "processing"})
        self.assertEqual(batch.state, "processing")

        batch.write({"state": "done"})
        self.assertEqual(batch.state, "done")

    def test_action_detect_columns_no_file(self):
        """Test column detection fails without file."""
        batch = self.Batch.create(
            {
                "name": "No File Batch",
                "profile_id": self.profile.id,
            }
        )

        with self.assertRaises(UserError):
            batch.action_detect_columns()

    def test_action_process_without_mapping(self):
        """Test processing fails without column mapping."""
        batch = self.Batch.create(
            {
                "name": "No Mapping Batch",
                "profile_id": self.profile.id,
                "state": "draft",
            }
        )

        with self.assertRaises(UserError):
            batch.action_process()

    def test_action_view_indicators(self):
        """Test action to view indicators."""
        batch = self.Batch.create(
            {
                "name": "View Test Batch",
                "profile_id": self.profile.id,
            }
        )

        action = batch.action_view_indicators()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.hxl.area.indicator")
        self.assertEqual(action["domain"], [("batch_id", "=", batch.id)])

    def test_action_reset(self):
        """Test resetting a batch."""
        batch = self.Batch.create(
            {
                "name": "Reset Test Batch",
                "profile_id": self.profile.id,
                "state": "done",
                "total_rows": 100,
                "matched_rows": 90,
            }
        )

        # Create some indicators
        self.Indicator.create(
            {
                "batch_id": batch.id,
                "area_id": self.area1.id,
                "value": 10,
            }
        )

        batch.action_reset()

        self.assertEqual(batch.state, "draft")
        self.assertEqual(batch.total_rows, 0)
        self.assertEqual(batch.matched_rows, 0)
        self.assertEqual(len(batch.indicator_ids), 0)

    def test_batch_with_period_and_incident(self):
        """Test batch with period and incident context."""
        batch = self.Batch.create(
            {
                "name": "Context Test Batch",
                "profile_id": self.profile.id,
                "period_key": "2024-03",
            }
        )

        self.assertEqual(batch.period_key, "2024-03")

    def test_batch_statistics_fields(self):
        """Test batch statistics fields."""
        batch = self.Batch.create(
            {
                "name": "Stats Test Batch",
                "profile_id": self.profile.id,
                "total_rows": 100,
                "matched_rows": 85,
                "unmatched_rows": 15,
                "areas_updated": 10,
                "indicators_created": 20,
            }
        )

        self.assertEqual(batch.total_rows, 100)
        self.assertEqual(batch.matched_rows, 85)
        self.assertEqual(batch.unmatched_rows, 15)
        self.assertEqual(batch.areas_updated, 10)
        self.assertEqual(batch.indicators_created, 20)

    def test_batch_error_log(self):
        """Test error log field."""
        batch = self.Batch.create(
            {
                "name": "Error Test Batch",
                "profile_id": self.profile.id,
                "state": "failed",
                "error_log": "Test error message",
            }
        )

        self.assertEqual(batch.state, "failed")
        self.assertEqual(batch.error_log, "Test error message")

    def test_create_mappings(self):
        """Test creation of column mappings."""
        batch = self.Batch.create(
            {
                "name": "Mapping Test Batch",
                "profile_id": self.profile.id,
            }
        )

        # Simulate detected columns
        hxl_columns = [
            {"index": 0, "header": "Area Code", "tag": "#adm2+pcode"},
            {"index": 1, "header": "Value", "tag": "#value"},
            {"index": 2, "header": "Other", "tag": "#other"},
        ]

        batch._create_mappings(hxl_columns)

        self.assertEqual(len(batch.mapping_ids), 3)

        # Area column should be mapped as "area"
        area_mapping = batch.mapping_ids.filtered(lambda m: m.detected_hxl_tag == "#adm2+pcode")
        self.assertEqual(area_mapping.mapping_type, "area")
        self.assertEqual(area_mapping.confidence, 1.0)

    def test_batch_with_source_url(self):
        """Test batch with source URL."""
        batch = self.Batch.create(
            {
                "name": "URL Test Batch",
                "profile_id": self.profile.id,
                "source_url": "https://example.com/data.csv",
            }
        )

        self.assertEqual(batch.source_url, "https://example.com/data.csv")

    def test_batch_message_tracking(self):
        """Test that batch inherits mail tracking."""
        batch = self.Batch.create(
            {
                "name": "Message Test Batch",
                "profile_id": self.profile.id,
            }
        )

        # Post a message
        batch.message_post(body="Test message", subject="Test")

        # Should have message
        self.assertTrue(batch.message_ids)
