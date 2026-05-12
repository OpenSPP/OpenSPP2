# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for strategies/update_farm_details.py — apply, preview, validate."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import FarmerCRTestMixin


@tagged("post_install", "-at_install")
class TestStrategyUpdateFarmDetailsApply(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.update_farm_details apply() method."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Strategy = cls.env["spp.cr.apply.update_farm_details"]

        cls.farm_type_vocab = cls._create_farm_type_vocabulary()
        cls.land_tenure_vocab = cls._create_land_tenure_vocabulary()

        cls.test_farm = cls._create_test_farm(name="Strategy Test Farm")
        cls.test_farm.farm_details_id.write(
            {
                "farm_type_id": cls.farm_type_vocab["crop"].id,
                "land_tenure_id": cls.land_tenure_vocab["self"].id,
                "farm_total_size": 5.0,
                "farm_size_under_crops": 3.0,
                "experience_years": 10,
            }
        )

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Strategy Farm Details {test_id}",
            code=f"strategy_farm_details_{test_id}",
            detail_model="spp.cr.detail.farm_details",
            apply_model="spp.cr.apply.update_farm_details",
        )

    def test_apply_updates_vocabulary_fields(self):
        """Test apply() writes vocabulary Many2one fields to farm_details."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "farm_type_id": self.farm_type_vocab["livestock"].id,
                "land_tenure_id": self.land_tenure_vocab["leased"].id,
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)
        self.assertEqual(
            self.test_farm.farm_details_id.farm_type_id,
            self.farm_type_vocab["livestock"],
        )
        self.assertEqual(
            self.test_farm.farm_details_id.land_tenure_id,
            self.land_tenure_vocab["leased"],
        )

    def test_apply_updates_numeric_fields(self):
        """Test apply() writes numeric fields to farm_details."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "farm_total_size": 20.0,
                "farm_size_under_crops": 12.0,
                "farm_size_under_livestock": 5.0,
                "farm_size_under_aquaculture": 2.0,
                "farm_size_leased_out": 0.5,
                "farm_size_idle": 0.5,
                "experience_years": 25,
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)
        fd = self.test_farm.farm_details_id
        self.assertEqual(fd.farm_total_size, 20.0)
        self.assertEqual(fd.farm_size_under_crops, 12.0)
        self.assertEqual(fd.farm_size_under_livestock, 5.0)
        self.assertEqual(fd.farm_size_under_aquaculture, 2.0)
        self.assertEqual(fd.farm_size_leased_out, 0.5)
        self.assertEqual(fd.farm_size_idle, 0.5)
        self.assertEqual(fd.experience_years, 25)

    def test_apply_no_changes_returns_true(self):
        """Test apply() with no non-empty fields returns True without writing."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        # Don't set any fields on the detail
        result = self.Strategy.apply(cr)
        self.assertTrue(result)

    def test_apply_requires_group(self):
        """Test apply() raises UserError if registrant is not a group."""
        individual = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Individual for Strategy",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
        )
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=individual,
        )
        detail = cr.get_detail()
        detail.write({"farm_total_size": 5.0})

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)

    def test_apply_requires_detail(self):
        """Test apply() raises error if no detail record exists."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.unlink()
        # Clear the stale reference so get_detail() returns None
        cr.write({"detail_res_id": False})

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)

    def test_apply_updates_new_farm_details(self):
        """Test apply() updates farm_details on a new farm created with _inherits."""
        new_farm = self._create_test_farm(name="Farm No Details Strategy")
        # With _inherits, farm_details_id is always created by ORM
        self.assertTrue(new_farm.farm_details_id)

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=new_farm,
        )
        detail = cr.get_detail()
        detail.write({"farm_total_size": 7.0})

        self.Strategy.apply(cr)
        self.assertEqual(new_farm.farm_details_id.farm_total_size, 7.0)

    def test_apply_partial_update_preserves_existing(self):
        """Test apply() only writes non-empty fields, preserving others."""
        original_type = self.test_farm.farm_details_id.farm_type_id
        original_tenure = self.test_farm.farm_details_id.land_tenure_id

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"experience_years": 99})

        self.Strategy.apply(cr)

        fd = self.test_farm.farm_details_id
        self.assertEqual(fd.experience_years, 99)
        self.assertEqual(fd.farm_type_id, original_type)
        self.assertEqual(fd.land_tenure_id, original_tenure)


@tagged("post_install", "-at_install")
class TestStrategyUpdateFarmDetailsPreview(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.update_farm_details preview() method."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Strategy = cls.env["spp.cr.apply.update_farm_details"]

        cls.farm_type_vocab = cls._create_farm_type_vocabulary()
        cls.land_tenure_vocab = cls._create_land_tenure_vocabulary()

        cls.test_farm = cls._create_test_farm(name="Preview Strategy Farm")
        cls.test_farm.farm_details_id.write(
            {
                "farm_type_id": cls.farm_type_vocab["crop"].id,
                "land_tenure_id": cls.land_tenure_vocab["self"].id,
                "farm_total_size": 5.0,
                "experience_years": 10,
            }
        )

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Preview Farm Details {test_id}",
            code=f"preview_farm_details_{test_id}",
            detail_model="spp.cr.detail.farm_details",
            apply_model="spp.cr.apply.update_farm_details",
        )

    def test_preview_vocabulary_field_change(self):
        """Test preview() shows old/new for vocabulary field changes."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "farm_type_id": self.farm_type_vocab["livestock"].id,
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertEqual(preview["_action"], "update_farm_details")
        self.assertEqual(preview["_header"], "Update Farm Details")
        self.assertIn("Farm Type", preview)
        self.assertEqual(preview["Farm Type"]["new"], self.farm_type_vocab["livestock"].display_name)
        self.assertEqual(preview["Farm Type"]["old"], self.farm_type_vocab["crop"].display_name)

    def test_preview_numeric_field_change(self):
        """Test preview() shows old/new for numeric field changes."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"farm_total_size": 12.0, "experience_years": 20})

        preview = self.Strategy.preview(cr)

        self.assertIn("Total Size (hectares)", preview)
        self.assertEqual(preview["Total Size (hectares)"]["old"], 5.0)
        self.assertEqual(preview["Total Size (hectares)"]["new"], 12.0)

        self.assertIn("Experience Years", preview)
        self.assertEqual(preview["Experience Years"]["old"], 10)
        self.assertEqual(preview["Experience Years"]["new"], 20)

    def test_preview_no_change_scenario(self):
        """Test preview() omits fields that have not changed."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        # Set same value as current
        detail.write(
            {
                "farm_type_id": self.farm_type_vocab["crop"].id,
                "farm_total_size": 5.0,
            }
        )

        preview = self.Strategy.preview(cr)

        # Same values should not appear in preview
        self.assertNotIn("Farm Type", preview)
        self.assertNotIn("Total Size (hectares)", preview)

    def test_preview_default_farm_details(self):
        """Test preview() when farm has default (empty) farm_details from _inherits."""
        new_farm = self._create_test_farm(name="No Details Preview Farm")
        # With _inherits, farm_details is auto-created with default values

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=new_farm,
        )
        detail = cr.get_detail()
        detail.write({"farm_total_size": 8.0})

        preview = self.Strategy.preview(cr)

        # Should still work; old value should be 0.0 (default)
        self.assertIn("Total Size (hectares)", preview)
        self.assertEqual(preview["Total Size (hectares)"]["new"], 8.0)

    def test_preview_empty_returns_action_header_only(self):
        """Test preview() with no changes returns only action and header."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        # Don't write anything to detail

        preview = self.Strategy.preview(cr)

        self.assertEqual(preview["_action"], "update_farm_details")
        self.assertEqual(preview["_header"], "Update Farm Details")
        # No other keys besides _action and _header
        other_keys = {k for k in preview if not k.startswith("_")}
        self.assertEqual(len(other_keys), 0)

    def test_preview_missing_detail_and_farm(self):
        """Test preview() returns empty dict when detail is missing."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.unlink()
        # Clear the stale reference so get_detail() returns None
        cr.write({"detail_res_id": False})

        preview = self.Strategy.preview(cr)
        self.assertEqual(preview, {})

    def test_preview_vocabulary_old_is_none_when_unset(self):
        """Test preview() shows None for old value when vocab field was unset."""
        new_farm = self._create_test_farm(name="Preview Unset Vocab Farm")
        # With _inherits, farm_details exists but farm_type_id is not set

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=new_farm,
        )
        detail = cr.get_detail()
        detail.write({"farm_type_id": self.farm_type_vocab["crop"].id})

        preview = self.Strategy.preview(cr)

        self.assertIn("Farm Type", preview)
        self.assertIsNone(preview["Farm Type"]["old"])
        self.assertEqual(preview["Farm Type"]["new"], self.farm_type_vocab["crop"].display_name)


@tagged("post_install", "-at_install")
class TestStrategyUpdateFarmDetailsValidate(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.update_farm_details validate() method."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Strategy = cls.env["spp.cr.apply.update_farm_details"]
        cls.test_farm = cls._create_test_farm(name="Validate Strategy Farm")

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Validate Farm Details {test_id}",
            code=f"validate_farm_details_{test_id}",
            detail_model="spp.cr.detail.farm_details",
            apply_model="spp.cr.apply.update_farm_details",
        )

    def test_validate_passes_for_valid_cr(self):
        """Test validate() passes without error for a valid change request."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        # validate() is inherited from base and is a no-op by default
        result = self.Strategy.validate(cr)
        self.assertIsNone(result)
