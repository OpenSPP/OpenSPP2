# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farm Activity model - V2 with vocabulary integration.

Tests cover:
- Cascading species selection (activity_type → species_namespace)
- Vocabulary-based species field
- Validation constraints (species namespace, closed seasons)
- Season integration
- Helper methods
"""

import time
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import FarmerTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestFarmActivity(TransactionCase, FarmerTestDataMixin):
    """Test spp.farm.activity model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        # Create species vocabularies with test-specific namespaces
        cls.species = cls._create_species_vocabularies()

        # Override namespace mappings in the model for testing
        # We need to patch the namespace map or use the actual namespaces
        cls.crop_ns = cls.species["crop"]["namespace_uri"]
        cls.livestock_ns = cls.species["livestock"]["namespace_uri"]
        cls.aqua_ns = cls.species["aquaculture"]["namespace_uri"]

        # Create test farm
        cls.farm = cls._create_test_farm(name=f"Activity Test Farm {cls._test_id}")

        # Create active season
        cls.season = cls._create_test_season(name=f"Activity Test Season {cls._test_id}")

    def test_species_namespace_computed_crop(self):
        """Test species_namespace computed for crop activity."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.new(
            {
                "activity_type": "crop",
            }
        )
        activity._compute_species_namespace()

        self.assertEqual(activity.species_namespace, "urn:fao:icc:1.1")

    def test_species_namespace_computed_livestock(self):
        """Test species_namespace computed for livestock activity."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.new(
            {
                "activity_type": "livestock",
            }
        )
        activity._compute_species_namespace()

        self.assertEqual(activity.species_namespace, "urn:fao:livestock:2020")

    def test_species_namespace_computed_aquaculture(self):
        """Test species_namespace computed for aquaculture activity."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.new(
            {
                "activity_type": "aquaculture",
            }
        )
        activity._compute_species_namespace()

        self.assertEqual(activity.species_namespace, "urn:fao:asfis:2024")

    def test_create_crop_activity(self):
        """Test creating a crop activity with species."""
        Activity = self.env["spp.farm.activity"]

        # Create activity with matching species namespace
        activity = Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
                "area_planted": 2.0,
            }
        )

        self.assertEqual(activity.activity_type, "crop")
        self.assertEqual(activity.farm_id, self.farm)
        self.assertEqual(activity.area_planted, 2.0)

    def test_create_livestock_activity(self):
        """Test creating a livestock activity."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["cattle"].id,
                "season_id": self.season.id,
                "quantity": 50,
                "quantity_unit": "heads",
            }
        )

        self.assertEqual(activity.activity_type, "livestock")
        self.assertEqual(activity.quantity, 50)
        self.assertEqual(activity.quantity_unit, "heads")

    def test_create_aquaculture_activity(self):
        """Test creating an aquaculture activity."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.create(
            {
                "aquaculture_farm_id": self.farm.id,
                "activity_type": "aquaculture",
                "species_id": self.species["aquaculture"]["tilapia"].id,
                "season_id": self.season.id,
                "quantity": 1000,
                "quantity_unit": "kg",
            }
        )

        self.assertEqual(activity.activity_type, "aquaculture")
        # Verify species matches the one from setup (code may vary)
        self.assertEqual(activity.species_id.id, self.species["aquaculture"]["tilapia"].id)

    def test_farm_id_computed_from_crop_farm(self):
        """Test farm_id computed from crop_farm_id."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )

        self.assertEqual(activity.farm_id, self.farm)

    def test_farm_id_computed_from_livestock_farm(self):
        """Test farm_id computed from livestock_farm_id."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["goats"].id,
                "season_id": self.season.id,
            }
        )

        self.assertEqual(activity.farm_id, self.farm)

    def test_default_season(self):
        """Test default season is set to active season."""
        Activity = self.env["spp.farm.activity"]

        defaults = Activity.default_get(["season_id"])
        self.assertEqual(defaults.get("season_id"), self.season.id)

    def test_yield_fields(self):
        """Test expected and actual yield fields."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["maize"].id,
                "season_id": self.season.id,
                "area_planted": 1.5,
                "expected_yield": 3000,
                "actual_yield": 2800,
            }
        )

        self.assertEqual(activity.expected_yield, 3000)
        self.assertEqual(activity.actual_yield, 2800)

    def test_get_species_code(self):
        """Test get_species_code helper method."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )

        self.assertEqual(activity.get_species_code(), "0113")

    def test_activity_count_on_season(self):
        """Test activity count is tracked on season."""
        Activity = self.env["spp.farm.activity"]

        initial_count = self.season.activity_count

        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )

        self.season.invalidate_recordset()
        self.assertEqual(self.season.activity_count, initial_count + 1)


@tagged("post_install", "-at_install")
class TestFarmActivitySeasonConstraints(TransactionCase, FarmerTestDataMixin):
    """Test farm activity season constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        cls.species = cls._create_species_vocabularies()
        cls.farm = cls._create_test_farm(name=f"Season Constraint Farm {cls._test_id}")

    def test_activity_in_closed_season_write(self):
        """Test cannot modify activity in closed season."""
        Season = self.env["spp.farm.season"]
        Activity = self.env["spp.farm.activity"]

        # Create season and activate it
        season = Season.create(
            {
                "name": _unique("Closed Season"),
                "date_start": date.today() - timedelta(days=90),
                "date_end": date.today() - timedelta(days=30),
                "allow_overlap": True,
                "force_close": True,
            }
        )
        season.action_activate()

        # Create activity
        activity = Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": season.id,
            }
        )

        # Close season
        season.action_close()

        # Try to modify activity - should fail
        with self.assertRaises(ValidationError):
            activity.write({"area_planted": 5.0})


@tagged("post_install", "-at_install")
class TestFarmActivityOnchange(TransactionCase, FarmerTestDataMixin):
    """Test farm activity onchange handlers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        cls.species = cls._create_species_vocabularies()
        cls.farm = cls._create_test_farm(name=f"Onchange Farm {cls._test_id}")
        cls.season = cls._create_test_season(name=f"Onchange Season {cls._test_id}")

    def test_onchange_activity_type_clears_species(self):
        """Test that changing activity type clears species selection."""
        Activity = self.env["spp.farm.activity"]

        activity = Activity.new(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
            }
        )

        # Simulate changing activity type
        activity.activity_type = "livestock"
        activity._onchange_activity_type()

        self.assertFalse(activity.species_id)
