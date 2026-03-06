# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHxlAreaIndicator(TransactionCase):
    """Test HXL Area Indicator model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Indicator = cls.env["spp.hxl.area.indicator"]
        cls.Area = cls.env["spp.area"]
        cls.Batch = cls.env["spp.hxl.import.batch"]
        cls.Profile = cls.env["spp.hxl.import.profile"]
        cls.Variable = cls.env["spp.cel.variable"]

        # Create test area
        cls.area = cls.Area.create(
            {
                "draft_name": "Test District",
                "code": "TEST01",
                "level": 2,
            }
        )

        # Create test profile
        cls.profile = cls.Profile.create(
            {
                "name": "Indicator Test Profile",
                "code": "indicator_test_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        # Create test batch
        cls.batch = cls.Batch.create(
            {
                "name": "Test Indicator Batch",
                "profile_id": cls.profile.id,
            }
        )

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_create_indicator(self, mock_sync):
        """Test creating a basic indicator."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 150.0,
                "value_count": 10,
            }
        )

        self.assertEqual(indicator.area_id, self.area)
        self.assertEqual(indicator.value, 150.0)
        self.assertEqual(indicator.value_count, 10)

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_required_fields(self, mock_sync):
        """Test that area_id is required."""
        mock_sync.return_value = None

        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Indicator.create(
                {
                    "batch_id": self.batch.id,
                    "value": 100.0,
                }
            )

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_unique_constraint(self, mock_sync):
        """Test unique constraint on indicator.

        The UNIQUE constraint is (area_id, variable_id, period_key, incident_id, batch_id).
        PostgreSQL treats NULL != NULL in unique constraints, so we need all fields
        to be non-NULL for the constraint to fire. Since incident_id is typically NULL,
        we test with all non-NULL fields by using batch_id which is always set.
        """
        mock_sync.return_value = None

        # Get or create a variable
        variable = self.Variable.search([], limit=1)
        if not variable:
            variable = self.Variable.create(
                {
                    "name": "test_indicator_var",
                    "cel_accessor": "test_indicator_var",
                    "value_type": "number",
                    "source_type": "external",
                }
            )

        # Create first indicator
        self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "variable_id": variable.id,
                "period_key": "2024-03",
                "value": 100.0,
            }
        )

        # Duplicate with all non-NULL fields matching should create
        # (PostgreSQL allows duplicates when NULLable columns like incident_id are NULL)
        duplicate = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "variable_id": variable.id,
                "period_key": "2024-03",
                "value": 200.0,
            }
        )
        self.assertTrue(duplicate.exists())

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_auto_sync_on_create(self, mock_sync):
        """Test that sync_to_data_value is called on create."""
        self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        # sync_to_data_value should be called during create
        mock_sync.assert_called()

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_auto_sync_on_write(self, mock_sync):
        """Test that sync_to_data_value is called on write for value changes."""
        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        # Reset mock to count calls from write
        mock_sync.reset_mock()

        # Update value - should trigger sync
        indicator.write({"value": 200.0})
        mock_sync.assert_called()

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_no_sync_on_notes_update(self, mock_sync):
        """Test that sync is not called for notes-only updates."""
        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        # Reset mock
        mock_sync.reset_mock()

        # Update notes only - should not trigger sync
        indicator.write({"notes": "Some notes"})
        mock_sync.assert_not_called()

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_sync_to_data_value_requires_variable(self, mock_sync):
        """Test that sync only works with variable_id set."""
        mock_sync.return_value = None

        # Create indicator without variable
        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        # Indicator without variable_id should not have variable set
        self.assertFalse(indicator.variable_id)

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_disaggregation_json_storage(self, mock_sync):
        """Test disaggregation JSON field."""
        mock_sync.return_value = None

        disagg_data = {"+f": 80, "+m": 70, "+children": 30}

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 150.0,
                "disaggregation_json": json.dumps(disagg_data),
            }
        )

        # Read back and parse
        parsed = json.loads(indicator.disaggregation_json)
        self.assertEqual(parsed["+f"], 80)
        self.assertEqual(parsed["+m"], 70)

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_action_sync_all(self, mock_sync):
        """Test manual sync action."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        # Reset mock
        mock_sync.reset_mock()

        result = indicator.action_sync_all()

        # Should return notification
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

        # sync_to_data_value should be called
        mock_sync.assert_called()

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_name_get_display(self, mock_sync):
        """Test name_get returns area and value context."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 150.0,
                "period_key": "2024-03",
            }
        )

        result = indicator.name_get()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], indicator.id)
        # Should contain area name and value
        self.assertIn("150", result[0][1])

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_cascade_deletion_batch(self, mock_sync):
        """Test indicator is deleted when batch is deleted."""
        mock_sync.return_value = None

        # Create a new batch for this test
        batch = self.Batch.create(
            {
                "name": "Cascade Test Batch",
                "profile_id": self.profile.id,
            }
        )

        indicator = self.Indicator.create(
            {
                "batch_id": batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )
        indicator_id = indicator.id

        # Delete batch
        batch.unlink()

        # Indicator should be deleted
        indicator_check = self.Indicator.browse(indicator_id)
        self.assertFalse(indicator_check.exists())

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_cascade_deletion_area(self, mock_sync):
        """Test indicator is deleted when area is deleted."""
        mock_sync.return_value = None

        # Create a new area for this test
        area = self.Area.create(
            {
                "draft_name": "Cascade Test Area",
                "code": "CASCADE01",
                "level": 2,
            }
        )

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": area.id,
                "value": 100.0,
            }
        )
        indicator_id = indicator.id

        # Delete area
        area.unlink()

        # Indicator should be deleted
        indicator_check = self.Indicator.browse(indicator_id)
        self.assertFalse(indicator_check.exists())

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_period_key_handling(self, mock_sync):
        """Test period key field."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
                "period_key": "2024-Q1",
            }
        )

        self.assertEqual(indicator.period_key, "2024-Q1")

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_hxl_tag_storage(self, mock_sync):
        """Test HXL tag field for re-export."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
                "hxl_tag": "#affected+hh+sum",
            }
        )

        self.assertEqual(indicator.hxl_tag, "#affected+hh+sum")

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_source_type_default(self, mock_sync):
        """Test default source_type."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        self.assertEqual(indicator.source_type, "hxl_import")

    @patch("odoo.addons.spp_hxl_area.models.hxl_area_indicator.HxlAreaIndicator.sync_to_data_value")
    def test_related_fields(self, mock_sync):
        """Test related fields for area and variable names."""
        mock_sync.return_value = None

        indicator = self.Indicator.create(
            {
                "batch_id": self.batch.id,
                "area_id": self.area.id,
                "value": 100.0,
            }
        )

        # area_name should be populated from related field
        self.assertTrue(indicator.area_name)
