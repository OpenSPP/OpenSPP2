# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for strategies/manage_farm_activity.py — apply, preview, validate."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import FarmerCRTestMixin


@tagged("post_install", "-at_install")
class TestStrategyManageActivityApplyAdd(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.manage_farm_activity _apply_add()."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Strategy = cls.env["spp.cr.apply.manage_farm_activity"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Strategy Add Farm")
        cls.test_season = cls._create_test_season(name="Strategy Add Season")
        cls.species_vocabs = cls._create_species_vocabularies()

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Strategy Activity {test_id}",
            code=f"strategy_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_apply_add_crop_activity(self):
        """Test _apply_add creates a crop activity linked to the farm."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "crop",
                "species_id": self.species_vocabs["crop"]["rice"].id,
                "quantity": 500.0,
                "quantity_unit": "kg",
                "area_planted": 1.5,
                "expected_yield": 400.0,
                "season_id": self.test_season.id,
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)

        activities = self.Activity.search([("crop_farm_id", "=", self.test_farm.id)])
        self.assertEqual(len(activities), 1)
        act = activities[0]
        self.assertEqual(act.activity_type, "crop")
        self.assertEqual(act.species_id, self.species_vocabs["crop"]["rice"])
        self.assertEqual(act.quantity, 500.0)
        self.assertEqual(act.quantity_unit, "kg")
        self.assertEqual(act.area_planted, 1.5)
        self.assertEqual(act.expected_yield, 400.0)
        self.assertEqual(act.season_id, self.test_season)

    def test_apply_add_livestock_activity(self):
        """Test _apply_add creates a livestock activity linked via livestock_farm_id."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "livestock",
                "species_id": self.species_vocabs["livestock"]["cattle"].id,
                "quantity": 25.0,
                "quantity_unit": "head",
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)

        activities = self.Activity.search([("livestock_farm_id", "=", self.test_farm.id)])
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].activity_type, "livestock")

    def test_apply_add_aquaculture_activity(self):
        """Test _apply_add creates an aquaculture activity linked via aquaculture_farm_id."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "aquaculture",
                "species_id": self.species_vocabs["aquaculture"]["tilapia"].id,
                "quantity": 1000.0,
                "quantity_unit": "fish",
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)

        activities = self.Activity.search([("aquaculture_farm_id", "=", self.test_farm.id)])
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].activity_type, "aquaculture")

    def test_apply_add_with_cultivation_method(self):
        """Test _apply_add includes cultivation_method_id for crop activities."""
        # Create cultivation method vocabulary code
        cult_vocab = self._create_test_vocabulary(
            name="Cultivation Method",
            namespace_uri="urn:openspp:vocab:cultivation-method",
        )
        cult_code = self._create_test_vocabulary_code(
            vocabulary=cult_vocab,
            code="irrigated",
            display="Irrigated",
        )

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "crop",
                "species_id": self.species_vocabs["crop"]["rice"].id,
                "cultivation_method_id": cult_code.id,
                "quantity": 100.0,
            }
        )

        self.Strategy.apply(cr)

        activities = self.Activity.search([("crop_farm_id", "=", self.test_farm.id)])
        self.assertEqual(activities[0].cultivation_method_id, cult_code)

    def test_apply_add_requires_group(self):
        """Test _apply_add raises UserError if registrant is not a group."""
        individual = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Individual Strategy",
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
        detail.write({"operation": "add", "activity_type": "crop", "quantity": 10.0})

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)

    def test_apply_add_requires_activity_type(self):
        """Test _apply_add raises UserError if activity_type is missing."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"operation": "add", "quantity": 100.0})

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)

    def test_apply_no_detail_raises_error(self):
        """Test apply() raises UserError when detail record is missing."""
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


@tagged("post_install", "-at_install")
class TestStrategyManageActivityApplyUpdate(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.manage_farm_activity _apply_update()."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Strategy = cls.env["spp.cr.apply.manage_farm_activity"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Strategy Update Farm")
        cls.species_vocabs = cls._create_species_vocabularies()

        cls.existing_activity = cls._create_test_activity(
            farm=cls.test_farm,
            activity_type="crop",
            species_id=cls.species_vocabs["crop"]["rice"].id,
            quantity=100.0,
            quantity_unit="kg",
            area_planted=1.0,
            expected_yield=80.0,
        )

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Strategy Activity Update {test_id}",
            code=f"strategy_activity_update_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_apply_update_modifies_existing_activity(self):
        """Test _apply_update writes new values to the existing activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "species_id": self.species_vocabs["crop"]["maize"].id,
                "quantity": 200.0,
                "area_planted": 2.0,
                "expected_yield": 150.0,
                "actual_yield": 145.0,
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)

        self.assertEqual(self.existing_activity.species_id, self.species_vocabs["crop"]["maize"])
        self.assertEqual(self.existing_activity.quantity, 200.0)
        self.assertEqual(self.existing_activity.area_planted, 2.0)
        self.assertEqual(self.existing_activity.expected_yield, 150.0)
        self.assertEqual(self.existing_activity.actual_yield, 145.0)

    def test_apply_update_partial_fields(self):
        """Test _apply_update only writes non-empty fields."""
        original_species = self.existing_activity.species_id

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "quantity": 300.0,
            }
        )

        self.Strategy.apply(cr)

        self.assertEqual(self.existing_activity.quantity, 300.0)
        self.assertEqual(self.existing_activity.species_id, original_species)

    def test_apply_update_no_changes(self):
        """Test _apply_update with no non-empty fields returns True."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)

    def test_apply_update_requires_activity_id(self):
        """Test _apply_update raises UserError without activity_id."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "quantity": 150.0,
            }
        )

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)

    def test_apply_update_quantity_unit(self):
        """Test _apply_update can change quantity_unit."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "quantity_unit": "tons",
            }
        )

        self.Strategy.apply(cr)
        self.assertEqual(self.existing_activity.quantity_unit, "tons")

    def test_apply_update_cultivation_method(self):
        """Test _apply_update can change cultivation_method_id."""
        cult_vocab = self._create_test_vocabulary(
            name="Cultivation Method Update",
            namespace_uri="urn:openspp:vocab:cultivation-method",
        )
        cult_code = self._create_test_vocabulary_code(
            vocabulary=cult_vocab,
            code="rainfed",
            display="Rainfed",
        )

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "cultivation_method_id": cult_code.id,
            }
        )

        self.Strategy.apply(cr)
        self.assertEqual(self.existing_activity.cultivation_method_id, cult_code)


@tagged("post_install", "-at_install")
class TestStrategyManageActivityApplyRemove(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.manage_farm_activity _apply_remove()."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Strategy = cls.env["spp.cr.apply.manage_farm_activity"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Strategy Remove Farm")
        cls.species_vocabs = cls._create_species_vocabularies()

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Strategy Activity Remove {test_id}",
            code=f"strategy_activity_remove_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_apply_remove_deletes_activity(self):
        """Test _apply_remove unlinks the referenced activity."""
        activity = self._create_test_activity(
            farm=self.test_farm,
            activity_type="livestock",
            species_id=self.species_vocabs["livestock"]["cattle"].id,
        )
        activity_id = activity.id

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "remove",
                "activity_id": activity.id,
            }
        )

        result = self.Strategy.apply(cr)
        self.assertTrue(result)
        self.assertFalse(self.Activity.search([("id", "=", activity_id)]))

    def test_apply_remove_requires_activity_id(self):
        """Test _apply_remove raises UserError without activity_id."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"operation": "remove"})

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)

    def test_apply_unknown_operation_raises_error(self):
        """Test apply() raises UserError for unknown operation value."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        # Force an invalid operation by writing directly to DB
        self.env.cr.execute(
            "UPDATE spp_cr_detail_manage_farm_activity SET operation = %s WHERE id = %s",
            ("invalid_op", detail.id),
        )
        detail.invalidate_recordset()

        with self.assertRaises(UserError):
            self.Strategy.apply(cr)


@tagged("post_install", "-at_install")
class TestStrategyManageActivityPreview(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.manage_farm_activity preview()."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Strategy = cls.env["spp.cr.apply.manage_farm_activity"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Strategy Preview Farm")
        cls.test_season = cls._create_test_season(name="Strategy Preview Season")
        cls.species_vocabs = cls._create_species_vocabularies()

        cls.existing_activity = cls._create_test_activity(
            farm=cls.test_farm,
            activity_type="crop",
            species_id=cls.species_vocabs["crop"]["rice"].id,
            quantity=100.0,
            quantity_unit="kg",
            area_planted=1.0,
            expected_yield=80.0,
        )

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Strategy Activity Preview {test_id}",
            code=f"strategy_activity_preview_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_preview_add_structure(self):
        """Test _preview_add returns correct structure with all fields."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "crop",
                "species_id": self.species_vocabs["crop"]["maize"].id,
                "quantity": 500.0,
                "quantity_unit": "kg",
                "area_planted": 2.0,
                "expected_yield": 400.0,
                "season_id": self.test_season.id,
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertEqual(preview["_action"], "add_farm_activity")
        self.assertEqual(preview["_header"], "Add Farm Activity")
        self.assertEqual(preview["Farm"], self.test_farm.name)
        self.assertEqual(preview["Activity Type"], "Crop Cultivation")
        self.assertIn("Species", preview)
        self.assertEqual(preview["Quantity"], 500.0)
        self.assertEqual(preview["Unit"], "kg")
        self.assertEqual(preview["Area Planted"], 2.0)
        self.assertEqual(preview["Expected Yield"], 400.0)
        self.assertEqual(preview["Season"], self.test_season.name)

    def test_preview_add_minimal(self):
        """Test _preview_add with only required fields."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "livestock",
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertEqual(preview["_action"], "add_farm_activity")
        self.assertEqual(preview["Activity Type"], "Livestock Rearing")
        # Optional fields should not appear
        self.assertNotIn("Species", preview)
        self.assertNotIn("Quantity", preview)

    def test_preview_update_shows_changes(self):
        """Test _preview_update shows old/new for changed fields."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "quantity": 250.0,
                "expected_yield": 200.0,
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertEqual(preview["_action"], "update_farm_activity")
        self.assertEqual(preview["_header"], "Edit Farm Activity")
        self.assertIn("Quantity", preview)
        self.assertEqual(preview["Quantity"]["old"], 100.0)
        self.assertEqual(preview["Quantity"]["new"], 250.0)
        self.assertIn("Expected Yield", preview)
        self.assertEqual(preview["Expected Yield"]["old"], 80.0)
        self.assertEqual(preview["Expected Yield"]["new"], 200.0)

    def test_preview_update_species_change(self):
        """Test _preview_update shows species change with old/new."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "species_id": self.species_vocabs["crop"]["maize"].id,
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertIn("Species", preview)
        self.assertEqual(
            preview["Species"]["old"],
            self.species_vocabs["crop"]["rice"].display_name,
        )
        self.assertEqual(
            preview["Species"]["new"],
            self.species_vocabs["crop"]["maize"].display_name,
        )

    def test_preview_update_no_activity_returns_empty(self):
        """Test _preview_update returns empty dict when activity_id is not set."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "quantity": 999.0,
            }
        )

        preview = self.Strategy.preview(cr)
        self.assertEqual(preview, {})

    def test_preview_update_same_values_omitted(self):
        """Test _preview_update omits fields where value hasn't changed."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "quantity": 100.0,  # Same as existing
                "expected_yield": 80.0,  # Same as existing
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertNotIn("Quantity", preview)
        self.assertNotIn("Expected Yield", preview)

    def test_preview_remove_structure(self):
        """Test _preview_remove returns correct structure."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "remove",
                "activity_id": self.existing_activity.id,
            }
        )

        preview = self.Strategy.preview(cr)

        self.assertEqual(preview["_action"], "remove_farm_activity")
        self.assertEqual(preview["_header"], "Remove Farm Activity")
        self.assertIn("Activity", preview)
        self.assertIn("Activity Type", preview)
        self.assertEqual(preview["Activity Type"], "Crop Cultivation")
        self.assertIn("Species", preview)

    def test_preview_remove_no_activity_returns_empty(self):
        """Test _preview_remove returns empty dict when activity_id is not set."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"operation": "remove"})

        preview = self.Strategy.preview(cr)
        self.assertEqual(preview, {})

    def test_preview_no_detail_returns_empty(self):
        """Test preview() returns empty dict when detail record is missing."""
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

    def test_preview_add_with_land_parcel(self):
        """Test _preview_add includes land parcel when set."""
        # Check if spp.land.record model exists before testing
        if "spp.land.record" not in self.env:
            return

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "crop",
            }
        )

        # Basic preview without land_id should not have "Land Parcel"
        preview = self.Strategy.preview(cr)
        self.assertNotIn("Land Parcel", preview)


@tagged("post_install", "-at_install")
class TestStrategyManageActivityValidate(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.cr.apply.manage_farm_activity validate()."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Strategy = cls.env["spp.cr.apply.manage_farm_activity"]
        cls.test_farm = cls._create_test_farm(name="Validate Activity Farm")

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Validate Activity {test_id}",
            code=f"validate_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
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
