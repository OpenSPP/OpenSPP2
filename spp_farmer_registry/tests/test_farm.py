# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farm model (res.partner extension) - V2 with vocabulary integration.

Tests cover:
- create() auto-creation of farm_details
- write() ensuring farm_details exists
- Computed activity counts (crop, livestock, aquaculture)
- Computed land_parcel_count
- Computed total_livestock_heads
- get_group_head_member()
- is_female_farmer()
- get_farm_type_code(), get_land_tenure_code(), is_farm_type()
- get_all_species(), get_crop_diversity_count(), has_irrigation()
- action_view_* methods
- get_geojson() and _process_record_to_feature()
"""

import json
import time

from odoo.tests import TransactionCase, tagged

from .common import FarmerTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestFarmCreate(TransactionCase, FarmerTestDataMixin):
    """Test Farm CRUD overrides (create/write with auto farm_details)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.farm_types = cls._create_farm_type_vocabulary()
        cls.land_tenures = cls._create_land_tenure_vocabulary()

    def test_create_with_farm_detail_fields(self):
        """Test that farm detail fields are set on create via _inherits delegation."""
        farm = self._create_test_farm(name=_unique("AutoDetail Farm"), farm_total_size=10.0)
        self.assertTrue(farm.farm_details_id, "farm_details should be auto-created via _inherits")
        self.assertEqual(farm.farm_details_id.farm_total_size, 10.0)

    def test_create_always_creates_farm_details(self):
        """Test that _inherits auto-creates farm_details for every partner."""
        farm = self._create_test_farm(name=_unique("NoDetail Farm"))
        self.assertTrue(farm.farm_details_id, "farm_details should always exist via _inherits")

    def test_write_farm_detail_fields(self):
        """Test that writing farm detail fields delegates to spp.farm.details."""
        farm = self._create_test_farm(name=_unique("WriteDetail Farm"))
        farm.write({"farm_total_size": 7.5})
        self.assertEqual(farm.farm_total_size, 7.5)
        self.assertEqual(farm.farm_details_id.farm_total_size, 7.5)

    def test_write_farm_detail_fields_reuses_existing_details(self):
        """Test that writing farm detail fields reuses existing farm_details record."""
        farm = self._create_test_farm(name=_unique("ReuseDetail Farm"))
        details_id = farm.farm_details_id.id

        farm.write({"farm_total_size": 3.0})
        self.assertEqual(farm.farm_details_id.id, details_id, "Should reuse existing farm_details")


@tagged("post_install", "-at_install")
class TestFarmComputedFields(TransactionCase, FarmerTestDataMixin):
    """Test computed fields on the farm model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.species = cls._create_species_vocabularies()
        cls.farm = cls._create_test_farm(name=f"Computed Test Farm {cls._test_id}")
        cls.season = cls._create_test_season(name=f"Computed Test Season {cls._test_id}")

    def test_compute_activity_counts_empty(self):
        """Test activity counts are zero when no activities exist."""
        self.assertEqual(self.farm.crop_activity_count, 0)
        self.assertEqual(self.farm.livestock_activity_count, 0)
        self.assertEqual(self.farm.aquaculture_activity_count, 0)

    def test_compute_crop_activity_count(self):
        """Test crop_activity_count increments when crop activities are added."""
        Activity = self.env["spp.farm.activity"]
        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )
        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["maize"].id,
                "season_id": self.season.id,
            }
        )
        self.farm.invalidate_recordset()
        self.assertEqual(self.farm.crop_activity_count, 2)

    def test_compute_livestock_activity_count(self):
        """Test livestock_activity_count increments when livestock activities are added."""
        Activity = self.env["spp.farm.activity"]
        Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["cattle"].id,
                "season_id": self.season.id,
                "quantity": 50,
            }
        )
        self.farm.invalidate_recordset()
        self.assertEqual(self.farm.livestock_activity_count, 1)

    def test_compute_aquaculture_activity_count(self):
        """Test aquaculture_activity_count increments when aquaculture activities are added."""
        Activity = self.env["spp.farm.activity"]
        Activity.create(
            {
                "aquaculture_farm_id": self.farm.id,
                "activity_type": "aquaculture",
                "species_id": self.species["aquaculture"]["tilapia"].id,
                "season_id": self.season.id,
                "quantity": 500,
            }
        )
        self.farm.invalidate_recordset()
        self.assertEqual(self.farm.aquaculture_activity_count, 1)

    def test_compute_land_parcel_count_empty(self):
        """Test land_parcel_count is zero when no land records exist."""
        self.assertEqual(self.farm.land_parcel_count, 0)

    def test_compute_land_parcel_count(self):
        """Test land_parcel_count increments when land records are added."""
        LandRecord = self.env["spp.land.record"]
        LandRecord.create(
            {
                "land_farm_id": self.farm.id,
                "land_name": "Parcel A",
                "land_acreage": 2.0,
            }
        )
        LandRecord.create(
            {
                "land_farm_id": self.farm.id,
                "land_name": "Parcel B",
                "land_acreage": 3.0,
            }
        )
        self.farm.invalidate_recordset()
        self.assertEqual(self.farm.land_parcel_count, 2)

    def test_compute_total_livestock_heads_empty(self):
        """Test total_livestock_heads is zero when no livestock activities exist."""
        self.assertEqual(self.farm.total_livestock_heads, 0.0)

    def test_compute_total_livestock_heads(self):
        """Test total_livestock_heads sums all livestock activity quantities."""
        Activity = self.env["spp.farm.activity"]
        Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["cattle"].id,
                "season_id": self.season.id,
                "quantity": 50,
            }
        )
        Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["goats"].id,
                "season_id": self.season.id,
                "quantity": 30,
            }
        )
        self.farm.invalidate_recordset()
        self.assertEqual(self.farm.total_livestock_heads, 80.0)

    def test_compute_total_livestock_heads_with_none_quantity(self):
        """Test total_livestock_heads handles None/zero quantity gracefully."""
        Activity = self.env["spp.farm.activity"]
        Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["cattle"].id,
                "season_id": self.season.id,
                "quantity": 0,
            }
        )
        self.farm.invalidate_recordset()
        self.assertEqual(self.farm.total_livestock_heads, 0.0)


@tagged("post_install", "-at_install")
class TestFarmHelperMethods(TransactionCase, FarmerTestDataMixin):
    """Test farm helper methods (head member, female farmer, etc.)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.farm_types = cls._create_farm_type_vocabulary()
        cls.land_tenures = cls._create_land_tenure_vocabulary()
        cls.species = cls._create_species_vocabularies()

    def test_get_group_head_member_no_members(self):
        """Test get_group_head_member returns None when no members exist."""
        farm = self._create_test_farm(name=_unique("Empty Farm"))
        result = farm.get_group_head_member()
        self.assertIsNone(result)

    def test_get_group_head_member_not_group(self):
        """Test get_group_head_member returns None for non-group partner."""
        individual = self._create_test_farmer(name=_unique("Individual"))
        result = individual.get_group_head_member()
        self.assertIsNone(result)

    def test_get_group_head_member_with_head(self):
        """Test get_group_head_member returns head member when present."""
        farm = self._create_test_farm(name=_unique("HeadMember Farm"))
        farmer = self._create_test_farmer(name=_unique("Head Farmer"))

        # Get or create "head" membership type code
        head_ns = "urn:openspp:vocab:group-membership-type"
        head_vocab = self._get_or_create_vocabulary(head_ns, "Group Membership Type")
        head_kind = self._get_or_create_vocabulary_code(head_vocab, head_ns, "head", "Head")

        # Create membership
        self.env["spp.group.membership"].create(
            {
                "group": farm.id,
                "individual": farmer.id,
                "membership_type_ids": [(4, head_kind.id)],
            }
        )

        result = farm.get_group_head_member()
        self.assertEqual(result, farmer)

    def test_get_group_head_member_no_head_type(self):
        """Test get_group_head_member returns None when no member has head type."""
        farm = self._create_test_farm(name=_unique("NoHead Farm"))
        farmer = self._create_test_farmer(name=_unique("Regular Farmer"))

        self.env["spp.group.membership"].create(
            {
                "group": farm.id,
                "individual": farmer.id,
            }
        )

        result = farm.get_group_head_member()
        self.assertIsNone(result)

    def test_is_female_farmer_no_head(self):
        """Test is_female_farmer returns False when no head member."""
        farm = self._create_test_farm(name=_unique("NoHead Female"))
        self.assertFalse(farm.is_female_farmer())

    def test_is_female_farmer_female_head(self):
        """Test is_female_farmer returns True when head is female."""
        farm = self._create_test_farm(name=_unique("Female Farm"))

        # Create female gender vocab code
        gender_ns = "urn:openspp:vocab:gender"
        gender_vocab = self._get_or_create_vocabulary(gender_ns, "Gender")
        female_code = self._get_or_create_vocabulary_code(gender_vocab, gender_ns, "female", "Female")

        farmer = self._create_test_farmer(
            name=_unique("Female Farmer"),
            gender_id=female_code.id,
        )

        head_ns = "urn:openspp:vocab:group-membership-type"
        head_vocab = self._get_or_create_vocabulary(head_ns, "Group Membership Type")
        head_kind = self._get_or_create_vocabulary_code(head_vocab, head_ns, "head", "Head")

        self.env["spp.group.membership"].create(
            {
                "group": farm.id,
                "individual": farmer.id,
                "membership_type_ids": [(4, head_kind.id)],
            }
        )

        self.assertTrue(farm.is_female_farmer())

    def test_is_female_farmer_male_head(self):
        """Test is_female_farmer returns False when head is male."""
        farm = self._create_test_farm(name=_unique("Male Farm"))

        gender_ns = "urn:openspp:vocab:gender"
        gender_vocab = self._get_or_create_vocabulary(gender_ns, "Gender")
        male_code = self._get_or_create_vocabulary_code(gender_vocab, gender_ns, "male", "Male")

        farmer = self._create_test_farmer(
            name=_unique("Male Farmer"),
            gender_id=male_code.id,
        )

        head_ns = "urn:openspp:vocab:group-membership-type"
        head_vocab = self._get_or_create_vocabulary(head_ns, "Group Membership Type")
        head_kind = self._get_or_create_vocabulary_code(head_vocab, head_ns, "head", "Head")

        self.env["spp.group.membership"].create(
            {
                "group": farm.id,
                "individual": farmer.id,
                "membership_type_ids": [(4, head_kind.id)],
            }
        )

        self.assertFalse(farm.is_female_farmer())

    def test_is_female_farmer_head_no_gender(self):
        """Test is_female_farmer returns False when head has no gender set."""
        farm = self._create_test_farm(name=_unique("NoGender Farm"))
        farmer = self._create_test_farmer(name=_unique("NoGender Farmer"))

        head_ns = "urn:openspp:vocab:group-membership-type"
        head_vocab = self._get_or_create_vocabulary(head_ns, "Group Membership Type")
        head_kind = self._get_or_create_vocabulary_code(head_vocab, head_ns, "head", "Head")

        self.env["spp.group.membership"].create(
            {
                "group": farm.id,
                "individual": farmer.id,
                "membership_type_ids": [(4, head_kind.id)],
            }
        )

        self.assertFalse(farm.is_female_farmer())

    def test_get_farm_type_code(self):
        """Test get_farm_type_code returns the correct code string."""
        farm = self._create_test_farm(name=_unique("TypeCode Farm"))

        farm.write({"farm_type_id": self.farm_types["crop"].id})

        self.assertEqual(farm.get_farm_type_code(), "crop")

    def test_get_farm_type_code_none(self):
        """Test get_farm_type_code returns None when farm_type not set."""
        farm = self._create_test_farm(name=_unique("NoType Farm"))
        self.assertIsNone(farm.get_farm_type_code())

    def test_get_land_tenure_code(self):
        """Test get_land_tenure_code returns the correct code string."""
        farm = self._create_test_farm(name=_unique("TenureCode Farm"))

        farm.write({"land_tenure_id": self.land_tenures["leased"].id})

        self.assertEqual(farm.get_land_tenure_code(), "leased")

    def test_get_land_tenure_code_none(self):
        """Test get_land_tenure_code returns None when land_tenure not set."""
        farm = self._create_test_farm(name=_unique("NoTenure Farm"))
        self.assertIsNone(farm.get_land_tenure_code())

    def test_is_farm_type_match(self):
        """Test is_farm_type returns True when code matches."""
        farm = self._create_test_farm(name=_unique("TypeMatch Farm"))

        farm.write({"farm_type_id": self.farm_types["livestock"].id})

        self.assertTrue(farm.is_farm_type("livestock"))

    def test_is_farm_type_no_match(self):
        """Test is_farm_type returns False when code does not match."""
        farm = self._create_test_farm(name=_unique("TypeNoMatch Farm"))

        farm.write({"farm_type_id": self.farm_types["crop"].id})

        self.assertFalse(farm.is_farm_type("livestock"))

    def test_is_farm_type_not_set(self):
        """Test is_farm_type returns falsy when farm_type not set."""
        farm = self._create_test_farm(name=_unique("TypeNotSet Farm"))
        self.assertFalse(farm.is_farm_type("crop"))


@tagged("post_install", "-at_install")
class TestFarmVocabularyAccess(TransactionCase, FarmerTestDataMixin):
    """Test vocabulary access methods on the farm model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.species = cls._create_species_vocabularies()
        cls.farm = cls._create_test_farm(name=f"VocabAccess Farm {cls._test_id}")
        cls.season = cls._create_test_season(name=f"VocabAccess Season {cls._test_id}")

    def test_get_all_species_empty(self):
        """Test get_all_species returns empty recordset when no activities."""
        result = self.farm.get_all_species()
        self.assertEqual(len(result), 0)

    def test_get_all_species_mixed_activities(self):
        """Test get_all_species returns unique species across all activity types."""
        Activity = self.env["spp.farm.activity"]

        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )
        Activity.create(
            {
                "livestock_farm_id": self.farm.id,
                "activity_type": "livestock",
                "species_id": self.species["livestock"]["cattle"].id,
                "season_id": self.season.id,
            }
        )
        Activity.create(
            {
                "aquaculture_farm_id": self.farm.id,
                "activity_type": "aquaculture",
                "species_id": self.species["aquaculture"]["tilapia"].id,
                "season_id": self.season.id,
            }
        )

        result = self.farm.get_all_species()
        self.assertEqual(len(result), 3)

    def test_get_all_species_deduplicates(self):
        """Test get_all_species deduplicates species across activities."""
        Activity = self.env["spp.farm.activity"]

        # Two crop activities with the same species
        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )
        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )

        result = self.farm.get_all_species()
        self.assertEqual(len(result), 1)

    def test_get_crop_diversity_count_empty(self):
        """Test get_crop_diversity_count returns 0 when no crop activities."""
        self.assertEqual(self.farm.get_crop_diversity_count(), 0)

    def test_get_crop_diversity_count(self):
        """Test get_crop_diversity_count returns count of unique crop species."""
        Activity = self.env["spp.farm.activity"]

        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )
        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["maize"].id,
                "season_id": self.season.id,
            }
        )
        # Duplicate rice
        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
            }
        )

        self.assertEqual(self.farm.get_crop_diversity_count(), 2)

    def test_has_irrigation_false_no_activities(self):
        """Test has_irrigation returns False when no crop activities."""
        self.assertFalse(self.farm.has_irrigation())

    def test_has_irrigation_true(self):
        """Test has_irrigation returns True when a crop activity uses irrigated method."""
        Activity = self.env["spp.farm.activity"]

        # Create irrigated cultivation method
        cult_ns = "urn:openspp:vocab:cultivation-method"
        cult_vocab = self._get_or_create_vocabulary(cult_ns, "Cultivation Method")
        irrigated = self._get_or_create_vocabulary_code(cult_vocab, cult_ns, "irrigated", "Irrigated")

        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
                "cultivation_method_id": irrigated.id,
            }
        )

        self.assertTrue(self.farm.has_irrigation())

    def test_has_irrigation_false_rainfed_only(self):
        """Test has_irrigation returns False when all activities are rainfed."""
        Activity = self.env["spp.farm.activity"]

        cult_ns = "urn:openspp:vocab:cultivation-method"
        cult_vocab = self._get_or_create_vocabulary(cult_ns, "Cultivation Method")
        rainfed = self._get_or_create_vocabulary_code(cult_vocab, cult_ns, "rainfed", "Rainfed")

        Activity.create(
            {
                "crop_farm_id": self.farm.id,
                "activity_type": "crop",
                "species_id": self.species["crop"]["rice"].id,
                "season_id": self.season.id,
                "cultivation_method_id": rainfed.id,
            }
        )

        self.assertFalse(self.farm.has_irrigation())


@tagged("post_install", "-at_install")
class TestFarmActionMethods(TransactionCase, FarmerTestDataMixin):
    """Test action_view_* methods on the farm model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.farm = cls._create_test_farm(name=f"Action Test Farm {cls._test_id}")

    def test_action_view_crop_activities(self):
        """Test action_view_crop_activities returns correct action dict."""
        action = self.farm.action_view_crop_activities()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.farm.activity")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["domain"], [("crop_farm_id", "=", self.farm.id)])
        self.assertEqual(action["context"]["default_crop_farm_id"], self.farm.id)
        self.assertEqual(action["context"]["default_activity_type"], "crop")

    def test_action_view_livestock_activities(self):
        """Test action_view_livestock_activities returns correct action dict."""
        action = self.farm.action_view_livestock_activities()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.farm.activity")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["domain"], [("livestock_farm_id", "=", self.farm.id)])
        self.assertEqual(action["context"]["default_livestock_farm_id"], self.farm.id)
        self.assertEqual(action["context"]["default_activity_type"], "livestock")

    def test_action_view_aquaculture_activities(self):
        """Test action_view_aquaculture_activities returns correct action dict."""
        action = self.farm.action_view_aquaculture_activities()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.farm.activity")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["domain"], [("aquaculture_farm_id", "=", self.farm.id)])
        self.assertEqual(action["context"]["default_aquaculture_farm_id"], self.farm.id)
        self.assertEqual(action["context"]["default_activity_type"], "aquaculture")

    def test_action_view_land_parcels(self):
        """Test action_view_land_parcels returns correct action dict."""
        action = self.farm.action_view_land_parcels()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.land.record")
        self.assertEqual(action["view_mode"], "list,form,gis")
        self.assertEqual(action["domain"], [("land_farm_id", "=", self.farm.id)])
        self.assertEqual(action["context"]["default_land_farm_id"], self.farm.id)


@tagged("post_install", "-at_install")
class TestFarmGeoJSON(TransactionCase, FarmerTestDataMixin):
    """Test GeoJSON methods on the farm model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_get_geojson_empty(self):
        """Test get_geojson returns valid empty FeatureCollection for domain with no results."""
        Partner = self.env["res.partner"]
        result = Partner.get_geojson(domain=[("id", "=", -1)])
        data = json.loads(result)

        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 0)

    def test_get_geojson_returns_valid_json(self):
        """Test get_geojson returns valid JSON string."""
        Partner = self.env["res.partner"]
        # Use a domain that likely matches no records to keep it simple
        result = Partner.get_geojson(domain=[("id", "=", -1)])
        data = json.loads(result)

        self.assertIn("type", data)
        self.assertIn("features", data)

    def test_process_record_to_feature_no_coordinates(self):
        """Test _process_record_to_feature returns None when no coordinates."""
        import pyproj

        farm = self._create_test_farm(name=_unique("NoCoord Farm"))
        proj_from = pyproj.Proj("epsg:3857")
        proj_to = pyproj.Proj("epsg:4326")
        transformer = pyproj.Transformer.from_proj(proj_from, proj_to, always_xy=True).transform

        result = farm._process_record_to_feature(farm, transformer)
        self.assertIsNone(result)
