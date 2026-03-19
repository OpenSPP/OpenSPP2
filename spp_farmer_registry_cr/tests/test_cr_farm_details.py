# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farm Details Change Request detail and strategy."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import FarmerCRTestMixin


@tagged("post_install", "-at_install")
class TestCRFarmDetails(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.detail.farm_details and update_farm_details strategy."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Models
        cls.CR = cls.env["spp.change.request"]
        cls.CRType = cls.env["spp.change.request.type"]
        cls.FarmDetails = cls.env["spp.cr.detail.farm_details"]
        cls.Partner = cls.env["res.partner"]

        # Create test vocabularies
        cls.farm_type_vocab = cls._create_farm_type_vocabulary()
        cls.land_tenure_vocab = cls._create_land_tenure_vocabulary()

        # Create a test farm with initial details
        cls.test_farm = cls._create_test_farm(name="Test Farm for CR")
        cls.test_farm.farm_details_id.write(
            {
                "farm_type_id": cls.farm_type_vocab["crop"].id,
                "land_tenure_id": cls.land_tenure_vocab["self"].id,
                "farm_total_size": 5.0,
                "farm_size_under_crops": 3.0,
                "experience_years": 10,
            }
        )

        # Create CR type for update farm details
        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Update Farm Details {test_id}",
            code=f"update_farm_details_{test_id}",
            detail_model="spp.cr.detail.farm_details",
            apply_model="spp.cr.apply.update_farm_details",
        )

    def test_detail_creation(self):
        """Test creating farm details CR detail record."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        self.assertTrue(detail, "Detail record should be created")
        self.assertEqual(detail._name, "spp.cr.detail.farm_details")
        self.assertEqual(detail.change_request_id, cr)
        self.assertEqual(detail.registrant_id, self.test_farm)

    def test_prefill_mapping(self):
        """Test that prefill mapping returns correct field mappings."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        mapping = detail._get_prefill_mapping()

        # Verify key fields are in mapping
        expected_fields = [
            "farm_type_id",
            "land_tenure_id",
            "farm_total_size",
            "farm_size_under_crops",
            "experience_years",
        ]
        for field in expected_fields:
            self.assertIn(field, mapping, f"Field {field} should be in prefill mapping")
            self.assertEqual(mapping[field], field, f"Field {field} should map to itself")

    def test_onchange_registrant_prefill(self):
        """Test that onchange pre-fills current values from registrant."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()

        # Manually trigger onchange (in tests, onchange doesn't auto-trigger)
        detail._onchange_registrant_id()

        # Verify values were pre-filled
        self.assertEqual(detail.farm_type_id, self.farm_type_vocab["crop"])
        self.assertEqual(detail.land_tenure_id, self.land_tenure_vocab["self"])
        self.assertEqual(detail.farm_total_size, 5.0)
        self.assertEqual(detail.farm_size_under_crops, 3.0)
        self.assertEqual(detail.experience_years, 10)

    def test_apply_model_updates_farm_details(self):
        """Test applying CR updates farm details."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "farm_type_id": self.farm_type_vocab["livestock"].id,
                "land_tenure_id": self.land_tenure_vocab["leased"].id,
                "farm_total_size": 10.0,
                "farm_size_under_livestock": 8.0,
                "experience_years": 15,
            }
        )

        # Apply CR
        cr.approval_state = "approved"
        cr.action_apply()

        # Verify farm was updated
        self.assertTrue(cr.is_applied)
        farm = cr.registrant_id
        self.assertEqual(farm.farm_type_id, self.farm_type_vocab["livestock"])
        self.assertEqual(farm.land_tenure_id, self.land_tenure_vocab["leased"])
        self.assertEqual(farm.farm_total_size, 10.0)
        self.assertEqual(farm.farm_size_under_livestock, 8.0)
        self.assertEqual(farm.experience_years, 15)

    def test_apply_model_requires_group(self):
        """Test that apply strategy requires registrant to be a group (farm)."""
        # Create individual (not a group)
        individual = self.Partner.create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=individual,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "farm_total_size": 5.0,
            }
        )

        # Try to apply - should fail
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as ctx:
            cr.action_apply()

        self.assertIn("must be a group", str(ctx.exception).lower())

    def test_apply_model_updates_new_farm_details(self):
        """Test that apply strategy updates farm_details on a new farm."""
        # With _inherits, farm_details_id is always created by ORM
        new_farm = self._create_test_farm(name="Farm Without Details")

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=new_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "farm_type_id": self.farm_type_vocab["crop"].id,
                "farm_total_size": 3.0,
            }
        )

        # Verify farm_details exists (created by _inherits) but fields are empty
        self.assertTrue(new_farm.farm_details_id)

        # Apply CR
        cr.approval_state = "approved"
        cr.action_apply()

        # Verify farm_details was populated
        self.assertEqual(new_farm.farm_type_id, self.farm_type_vocab["crop"])
        self.assertEqual(new_farm.farm_total_size, 3.0)

    def test_apply_model_partial_update(self):
        """Test that apply strategy only updates non-empty fields."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        # Only update farm_total_size, leave others empty
        detail.write(
            {
                "farm_total_size": 7.5,
            }
        )

        original_farm_type = self.test_farm.farm_type_id
        original_land_tenure = self.test_farm.land_tenure_id
        original_experience = self.test_farm.experience_years

        # Apply CR
        cr.approval_state = "approved"
        cr.action_apply()

        # Verify only farm_total_size was updated
        self.assertEqual(self.test_farm.farm_total_size, 7.5)
        self.assertEqual(self.test_farm.farm_type_id, original_farm_type)
        self.assertEqual(self.test_farm.land_tenure_id, original_land_tenure)
        self.assertEqual(self.test_farm.experience_years, original_experience)

    def test_apply_model_no_changes(self):
        """Test apply with no changes completes without error."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        # Don't fill any fields in detail
        # Apply CR - should succeed even with no changes
        cr.approval_state = "approved"
        cr.action_apply()

        # Verify CR was applied successfully
        self.assertTrue(cr.is_applied)

    def test_preview_changes(self):
        """Test preview method shows what will be changed."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "farm_total_size": 12.0,
                "experience_years": 20,
            }
        )

        # Get preview
        strategy = self.env["spp.cr.apply.update_farm_details"]
        preview = strategy.preview(cr)

        # Verify preview structure — flat dict with _action, _header, and field entries
        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "update_farm_details")
        self.assertIn("_header", preview)

        # Find the keys for total size and experience (field labels may vary)
        size_key = next((k for k in preview if "Total Size" in k), None)
        self.assertIsNotNone(size_key, f"Expected a 'Total Size' key in preview: {list(preview.keys())}")
        self.assertEqual(preview[size_key]["old"], 5.0)
        self.assertEqual(preview[size_key]["new"], 12.0)

        exp_key = next((k for k in preview if "Experience" in k), None)
        self.assertIsNotNone(exp_key, f"Expected an 'Experience' key in preview: {list(preview.keys())}")
        self.assertEqual(preview[exp_key]["old"], 10)
        self.assertEqual(preview[exp_key]["new"], 20)

    def test_tracking_enabled(self):
        """Test that farm details CR has mail tracking enabled."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()

        # Verify mail.thread is inherited
        self.assertTrue(hasattr(detail, "message_ids"))
        self.assertTrue(hasattr(detail, "message_post"))

    def test_detail_field_constraints(self):
        """Test that detail fields have proper constraints."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()

        # Test that vocabulary fields have correct domain
        farm_type_field = detail._fields["farm_type_id"]
        self.assertIn("farm-type", farm_type_field.domain)

        land_tenure_field = detail._fields["land_tenure_id"]
        self.assertIn("land-tenure", land_tenure_field.domain)

    def test_multiple_updates_in_sequence(self):
        """Test multiple sequential updates to farm details."""
        # First update
        cr1 = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail1 = cr1.get_detail()
        detail1.write({"farm_total_size": 8.0})
        cr1.approval_state = "approved"
        cr1.action_apply()

        self.assertEqual(self.test_farm.farm_total_size, 8.0)

        # Second update
        cr2 = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail2 = cr2.get_detail()
        detail2.write({"experience_years": 25})
        cr2.approval_state = "approved"
        cr2.action_apply()

        self.assertEqual(self.test_farm.farm_total_size, 8.0)
        self.assertEqual(self.test_farm.experience_years, 25)


@tagged("post_install", "-at_install")
class TestCRFarmDetailsEdgeCases(TransactionCase, FarmerCRTestMixin):
    """Edge case tests for farm details CR."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.CR = cls.env["spp.change.request"]
        cls.Partner = cls.env["res.partner"]

        cls.farm_type_vocab = cls._create_farm_type_vocabulary()
        cls.land_tenure_vocab = cls._create_land_tenure_vocabulary()

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Update Farm Details Edge {test_id}",
            code=f"update_farm_details_edge_{test_id}",
            detail_model="spp.cr.detail.farm_details",
            apply_model="spp.cr.apply.update_farm_details",
        )

    def test_apply_without_detail(self):
        """Test that apply without detail raises error."""
        farm = self._create_test_farm()
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=farm,
        )

        # Delete the detail record
        detail = cr.get_detail()
        detail.unlink()
        # Clear the stale reference so get_detail() returns None
        cr.write({"detail_res_id": False})

        # Try to apply - should raise error when detail is missing
        cr.approval_state = "approved"
        with self.assertRaises(UserError):
            cr.action_apply()

    def test_update_all_fields(self):
        """Test updating all available fields at once."""
        farm = self._create_test_farm()

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "farm_type_id": self.farm_type_vocab["crop"].id,
                "land_tenure_id": self.land_tenure_vocab["leased"].id,
                "farm_total_size": 15.5,
                "farm_size_under_crops": 10.0,
                "farm_size_under_livestock": 3.0,
                "farm_size_under_aquaculture": 1.0,
                "farm_size_leased_out": 0.5,
                "farm_size_idle": 1.0,
                "experience_years": 30,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify all fields updated
        self.assertEqual(farm.farm_type_id, self.farm_type_vocab["crop"])
        self.assertEqual(farm.land_tenure_id, self.land_tenure_vocab["leased"])
        self.assertEqual(farm.farm_total_size, 15.5)
        self.assertEqual(farm.farm_size_under_crops, 10.0)
        self.assertEqual(farm.farm_size_under_livestock, 3.0)
        self.assertEqual(farm.farm_size_under_aquaculture, 1.0)
        self.assertEqual(farm.farm_size_leased_out, 0.5)
        self.assertEqual(farm.farm_size_idle, 1.0)
        self.assertEqual(farm.experience_years, 30)
