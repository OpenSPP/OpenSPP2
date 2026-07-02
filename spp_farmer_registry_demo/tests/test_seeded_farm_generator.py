# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for SeededFarmGenerator.

Tests cover:
- Farm name generation from Filipino name pool
- Member name generation with gender-aware names
- GPS coordinate generation for rural and peri-urban zones
- Vocabulary code lookup and caching
- Species resolution from code to vocabulary ID
- Farm activity creation (crop, livestock, aquaculture)
- Land record creation with polygons
- Farm polygon generation (rectangular approximation)
- Batch record creation for performance
- Phase execution (phases 1-5) of generate_all_farms
- Gender resolution for 'any' gender spec
- Head membership type assignment
- Enrollment in programs based on blueprint eligibility
"""

import json
import math
import time

from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorNames(TransactionCase):
    """Test name generation methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls._create_test_vocabularies()

    @classmethod
    def _create_test_vocabularies(cls):
        """Create minimal vocabularies for generator tests."""
        Vocabulary = cls.env["spp.vocabulary"]
        VocabCode = cls.env["spp.vocabulary.code"]

        vocab_defs = [
            {
                "name": "Farm Type",
                "namespace_uri": "urn:openspp:vocab:farm-type",
                "codes": [
                    ("crop", "Crop Farming"),
                    ("livestock", "Livestock Farming"),
                    ("mixed", "Mixed Farming"),
                    ("aquaculture", "Aquaculture"),
                ],
            },
            {
                "name": "Land Tenure",
                "namespace_uri": "urn:openspp:vocab:land-tenure",
                "codes": [
                    ("self", "Self-owned"),
                    ("family", "Family-owned"),
                    ("leased", "Leased"),
                ],
            },
            {
                "name": "Holder Type",
                "namespace_uri": "urn:openspp:vocab:holder-type",
                "codes": [("individual", "Individual")],
            },
            {
                "name": "Gender",
                "namespace_uri": "urn:openspp:vocab:gender",
                "codes": [("male", "Male"), ("female", "Female")],
            },
            {
                "name": "Group Membership Type",
                "namespace_uri": "urn:openspp:vocab:group-membership-type",
                "codes": [("head", "Head of Household")],
            },
            {
                "name": "Activity Purpose",
                "namespace_uri": "urn:openspp:vocab:activity-purpose",
                "codes": [
                    ("subsistence", "Subsistence"),
                    ("commercial", "Commercial"),
                    ("both", "Both"),
                ],
            },
        ]

        for vocab_def in vocab_defs:
            vocab = Vocabulary.search([("namespace_uri", "=", vocab_def["namespace_uri"])], limit=1)
            if not vocab:
                vocab = Vocabulary.create(
                    {
                        "name": vocab_def["name"],
                        "namespace_uri": vocab_def["namespace_uri"],
                    }
                )
                for code, display in vocab_def["codes"]:
                    VocabCode.create(
                        {
                            "vocabulary_id": vocab.id,
                            "namespace_uri": vocab_def["namespace_uri"],
                            "code": code,
                            "display": display,
                        }
                    )

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def test_generate_farm_name_returns_farm_suffix(self):
        """Farm names must end with ' Farm'."""
        gen = self._make_generator()
        name = gen._generate_farm_name()
        self.assertTrue(name.endswith(" Farm"), f"Expected 'X Farm', got '{name}'")

    def test_generate_farm_name_uses_filipino_surnames(self):
        """Farm names are owner-style ("{given} {family} Farm") and use a
        Filipino last name as the family component (OP#1114)."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _FILIPINO_LAST_NAMES,
        )

        gen = self._make_generator()
        name = gen._generate_farm_name()
        # Default descriptor is "Farm"; the family name is the token before it.
        surname = name.replace(" Farm", "").split()[-1]
        self.assertIn(surname, _FILIPINO_LAST_NAMES)

    def test_generate_farm_name_avoids_reserved(self):
        """Generated farm names must not be in the reserved set."""
        gen = self._make_generator()
        for _ in range(50):
            name = gen._generate_farm_name()
            self.assertNotIn(name, gen._reserved_names)

    def test_pick_given_name_male(self):
        """Male member given names should come from the male first name pool."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _FILIPINO_MALE_FIRST_NAMES,
        )

        gen = self._make_generator()
        given = gen._pick_given_name("male")
        self.assertIn(given, _FILIPINO_MALE_FIRST_NAMES)

    def test_pick_given_name_female(self):
        """Female member given names should come from the female first name pool."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _FILIPINO_FEMALE_FIRST_NAMES,
        )

        gen = self._make_generator()
        given = gen._pick_given_name("female")
        self.assertIn(given, _FILIPINO_FEMALE_FIRST_NAMES)

    def test_pick_given_name_avoids_excluded(self):
        """Excluding the name that would otherwise be picked yields a different one."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _FILIPINO_MALE_FIRST_NAMES,
        )

        # Same seed -> the un-excluded pick is deterministic; excluding it on an
        # identically-seeded generator must produce a different, valid name.
        first = self._make_generator()._pick_given_name("male")
        picked = self._make_generator()._pick_given_name("male", {first})
        self.assertNotEqual(picked, first)
        self.assertIn(picked, _FILIPINO_MALE_FIRST_NAMES)

    def test_household_identity_returns_owner_parts(self):
        """The identity's farm name is '{head_given} {family} {descriptor}'."""
        gen = self._make_generator()
        name, head_given, family = gen._generate_household_identity("crop", "female")
        self.assertTrue(name.startswith(f"{head_given} {family} "))
        self.assertNotIn(name, gen._reserved_names)

    def test_resolve_gender_male(self):
        """Specifying 'male' returns 'male'."""
        gen = self._make_generator()
        self.assertEqual(gen._resolve_gender("male"), "male")

    def test_resolve_gender_female(self):
        """Specifying 'female' returns 'female'."""
        gen = self._make_generator()
        self.assertEqual(gen._resolve_gender("female"), "female")

    def test_resolve_gender_any_returns_valid(self):
        """Specifying 'any' returns either 'male' or 'female'."""
        gen = self._make_generator()
        result = gen._resolve_gender("any")
        self.assertIn(result, ("male", "female"))

    def test_resolve_gender_any_is_deterministic(self):
        """Same seed with 'any' gender must produce same result."""
        gen1 = self._make_generator(seed=123)
        gen2 = self._make_generator(seed=123)
        r1 = gen1._resolve_gender("any")
        r2 = gen2._resolve_gender("any")
        self.assertEqual(r1, r2)


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorGPS(TransactionCase):
    """Test GPS coordinate generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def _area_map(self):
        """Synthetic {area_code: id} map covering every farmland anchor.

        `_pick_area_and_gps` only echoes the id back — it never reads the
        area record — so synthetic ids exercise the GPS logic without a DB.
        """
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _AREA_CENTERS,
        )

        return {code: idx + 1 for idx, code in enumerate(_AREA_CENTERS)}

    def test_pick_area_and_gps_returns_area_and_point(self):
        """Rural pick returns an area id and a (lng, lat) point."""
        gen = self._make_generator()
        area_id, gps = gen._pick_area_and_gps("rural", self._area_map())
        self.assertIn(area_id, self._area_map().values())
        self.assertIsInstance(gps, tuple)
        self.assertEqual(len(gps), 2)

    def test_gps_within_zone_anchor_bounds(self):
        """The point must sit within jitter of one of the zone's anchors."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _AREA_CENTERS,
            _AREAS_BY_ZONE,
            _GPS_JITTER,
        )

        gen = self._make_generator()
        _, (lng, lat) = gen._pick_area_and_gps("rural", self._area_map())
        near = any(
            abs(lng - _AREA_CENTERS[code][0]) <= _GPS_JITTER + 1e-6
            and abs(lat - _AREA_CENTERS[code][1]) <= _GPS_JITTER + 1e-6
            for code in _AREAS_BY_ZONE["rural"]
        )
        self.assertTrue(near, "GPS point must be within jitter of a rural anchor")

    def test_peri_urban_picks_peri_urban_area(self):
        """Peri-urban zone must pick from the peri-urban candidate areas."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            _AREAS_BY_ZONE,
        )

        gen = self._make_generator()
        area_map = self._area_map()
        area_id, _ = gen._pick_area_and_gps("peri_urban", area_map)
        peri_ids = {area_map[c] for c in _AREAS_BY_ZONE["peri_urban"]}
        self.assertIn(area_id, peri_ids)

    def test_unknown_zone_defaults_to_rural(self):
        """Unknown zone falls back to the rural candidate set."""
        gen = self._make_generator()
        area_id, gps = gen._pick_area_and_gps("unknown_zone", self._area_map())
        self.assertIsNotNone(gps)
        self.assertIn(area_id, self._area_map().values())

    def test_no_eligible_areas_returns_none(self):
        """With no matching demo areas, pick returns (None, None)."""
        gen = self._make_generator()
        area_id, gps = gen._pick_area_and_gps("rural", {})
        self.assertIsNone(area_id)
        self.assertIsNone(gps)

    def test_gps_is_deterministic(self):
        """Same seed must produce identical area + GPS."""
        area_map = self._area_map()
        gen1 = self._make_generator(seed=77)
        gen2 = self._make_generator(seed=77)
        self.assertEqual(
            gen1._pick_area_and_gps("rural", area_map),
            gen2._pick_area_and_gps("rural", area_map),
        )


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorVocab(TransactionCase):
    """Test vocabulary code lookup and species resolution."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls._create_test_vocabularies()

    @classmethod
    def _create_test_vocabularies(cls):
        """Create vocabularies for vocab lookup tests."""
        Vocabulary = cls.env["spp.vocabulary"]
        VocabCode = cls.env["spp.vocabulary.code"]

        # Farm type vocab
        vocab = Vocabulary.search([("namespace_uri", "=", "urn:openspp:vocab:farm-type")], limit=1)
        if not vocab:
            vocab = Vocabulary.create(
                {
                    "name": "Farm Type",
                    "namespace_uri": "urn:openspp:vocab:farm-type",
                }
            )
            VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": "urn:openspp:vocab:farm-type",
                    "code": "crop",
                    "display": "Crop Farming",
                }
            )

        # FAO species vocab for rice
        fao_vocab = Vocabulary.search([("namespace_uri", "=", "urn:fao:icc:1.1")], limit=1)
        if not fao_vocab:
            fao_vocab = Vocabulary.create(
                {
                    "name": "FAO ICC",
                    "namespace_uri": "urn:fao:icc:1.1",
                }
            )
            VocabCode.create(
                {
                    "vocabulary_id": fao_vocab.id,
                    "namespace_uri": "urn:fao:icc:1.1",
                    "code": "0116",
                    "display": "Rice",
                }
            )

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def test_get_vocab_code_existing(self):
        """Existing vocabulary code returns its ID."""
        gen = self._make_generator()
        code_id = gen._get_vocab_code("urn:openspp:vocab:farm-type", "crop")
        self.assertTrue(code_id)
        code = self.env["spp.vocabulary.code"].browse(code_id)
        self.assertEqual(code.code, "crop")

    def test_get_vocab_code_nonexistent(self):
        """Nonexistent vocabulary code returns False."""
        gen = self._make_generator()
        code_id = gen._get_vocab_code("urn:nonexistent", "bogus")
        self.assertFalse(code_id)

    def test_get_vocab_code_is_cached(self):
        """Second lookup of same code should use cache."""
        gen = self._make_generator()
        code_id1 = gen._get_vocab_code("urn:openspp:vocab:farm-type", "crop")
        code_id2 = gen._get_vocab_code("urn:openspp:vocab:farm-type", "crop")
        self.assertEqual(code_id1, code_id2)
        # Check the cache was populated
        self.assertIn(
            ("urn:openspp:vocab:farm-type", "crop"),
            gen._vocab_cache,
        )

    def test_resolve_species_known_code(self):
        """Known species code resolves to a vocabulary code ID."""
        gen = self._make_generator()
        species_id = gen._resolve_species("rice_irrigated")
        if species_id:
            code = self.env["spp.vocabulary.code"].browse(species_id)
            self.assertEqual(code.code, "0116")

    def test_resolve_species_unknown_code(self):
        """Unknown species code returns False."""
        gen = self._make_generator()
        species_id = gen._resolve_species("unknown_species")
        self.assertFalse(species_id)

    def test_resolve_species_is_cached(self):
        """Species resolution result should be cached."""
        gen = self._make_generator()
        gen._resolve_species("rice_irrigated")
        gen._resolve_species("rice_irrigated")
        self.assertIn("rice_irrigated", gen._species_cache)

    def test_get_gender_id(self):
        """Gender lookup maps the human label to its ISO 5218 numeric code.

        ``res.partner.gender_id`` is domain-locked to ISO 5218
        (`urn:iso:std:iso:5218`), where '1' = Male, '2' = Female. The helper
        translates 'male' → the vocab code whose ``code`` is '1'.
        """
        gen = self._make_generator()
        Vocabulary = self.env["spp.vocabulary"]
        VocabCode = self.env["spp.vocabulary.code"]
        iso_ns = "urn:iso:std:iso:5218"
        vocab = Vocabulary.search([("namespace_uri", "=", iso_ns)], limit=1)
        if not vocab:
            vocab = Vocabulary.create({"name": "ISO 5218 Gender", "namespace_uri": iso_ns})
        if not VocabCode.search([("namespace_uri", "=", iso_ns), ("code", "=", "1")], limit=1):
            VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": iso_ns,
                    "code": "1",
                    "display": "Male",
                }
            )
        gender_id = gen._get_gender_id("male")
        self.assertTrue(gender_id, "'male' should resolve to the ISO 5218 code '1'")
        code = self.env["spp.vocabulary.code"].browse(gender_id)
        self.assertEqual(code.code, "1")

    def test_get_head_type_id(self):
        """Head type lookup should return ID and cache it."""
        gen = self._make_generator()
        # Create membership type vocab if needed
        Vocabulary = self.env["spp.vocabulary"]
        VocabCode = self.env["spp.vocabulary.code"]
        vocab = Vocabulary.search([("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")], limit=1)
        if not vocab:
            vocab = Vocabulary.create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )
            VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                    "code": "head",
                    "display": "Head of Household",
                }
            )
        head_id = gen._get_head_type_id()
        if head_id:
            # Second call should use cached value
            head_id2 = gen._get_head_type_id()
            self.assertEqual(head_id, head_id2)


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorPolygon(TransactionCase):
    """Test farm polygon generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def test_polygon_returns_valid_geojson(self):
        """Generated polygon must be valid GeoJSON Polygon."""
        gen = self._make_generator()
        geojson_str = gen._generate_farm_polygon(121.0, 14.5, 2.0)
        geojson = json.loads(geojson_str)
        self.assertEqual(geojson["type"], "Polygon")
        self.assertIn("coordinates", geojson)

    def test_polygon_is_closed_ring(self):
        """Polygon ring must be closed (first == last coordinate)."""
        gen = self._make_generator()
        geojson_str = gen._generate_farm_polygon(121.0, 14.5, 1.0)
        geojson = json.loads(geojson_str)
        ring = geojson["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(len(ring), 5)  # 4 corners + closing point

    def test_polygon_center_matches_input(self):
        """Polygon should be centered approximately on the input coordinates."""
        gen = self._make_generator()
        center_lng, center_lat = 121.0, 14.5
        geojson_str = gen._generate_farm_polygon(center_lng, center_lat, 1.0)
        geojson = json.loads(geojson_str)
        ring = geojson["coordinates"][0]

        # Calculate centroid of the 4 corners
        lngs = [p[0] for p in ring[:4]]
        lats = [p[1] for p in ring[:4]]
        avg_lng = sum(lngs) / 4
        avg_lat = sum(lats) / 4

        self.assertAlmostEqual(avg_lng, center_lng, places=4)
        self.assertAlmostEqual(avg_lat, center_lat, places=4)

    def test_polygon_area_scales_with_hectares(self):
        """Larger hectares should produce a larger polygon bounding box."""
        gen = self._make_generator()
        small = json.loads(gen._generate_farm_polygon(121.0, 14.5, 1.0))
        large = json.loads(gen._generate_farm_polygon(121.0, 14.5, 10.0))

        def bbox_area(ring):
            lngs = [p[0] for p in ring[:4]]
            lats = [p[1] for p in ring[:4]]
            return (max(lngs) - min(lngs)) * (max(lats) - min(lats))

        small_area = bbox_area(small["coordinates"][0])
        large_area = bbox_area(large["coordinates"][0])
        self.assertGreater(large_area, small_area)

    def test_polygon_side_length_matches_hectares(self):
        """Side length should approximate sqrt(hectares * 10000) meters."""
        gen = self._make_generator()
        hectares = 4.0
        expected_side_m = math.sqrt(hectares * 10000)  # 200m

        geojson = json.loads(gen._generate_farm_polygon(121.0, 14.5, hectares))
        ring = geojson["coordinates"][0]

        # Width in degrees
        lng_span = abs(ring[1][0] - ring[0][0])
        # Convert to meters at latitude 14.5
        deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(14.5)))
        width_m = lng_span / deg_per_m

        self.assertAlmostEqual(width_m, expected_side_m, delta=1.0)


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorBatchCreate(TransactionCase):
    """Test batch record creation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def test_batch_create_empty_list(self):
        """Batch create with empty list returns empty recordset."""
        gen = self._make_generator()
        result = gen._batch_create("res.partner", [])
        self.assertEqual(len(result), 0)

    def test_batch_create_single_record(self):
        """Batch create with one record creates exactly one."""
        gen = self._make_generator()
        result = gen._batch_create(
            "res.partner",
            [{"name": _unique("Batch Test"), "is_registrant": True}],
        )
        self.assertEqual(len(result), 1)
        self.assertTrue(result.is_registrant)

    def test_batch_create_multiple_records(self):
        """Batch create with N records creates exactly N."""
        gen = self._make_generator()
        vals = [{"name": _unique(f"Batch Multi {i}"), "is_registrant": True} for i in range(5)]
        result = gen._batch_create("res.partner", vals)
        self.assertEqual(len(result), 5)


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorActivities(TransactionCase):
    """Test farm activity and land record creation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls._create_full_vocabularies()

    @classmethod
    def _create_full_vocabularies(cls):
        """Create all vocabularies needed for activity tests."""
        Vocabulary = cls.env["spp.vocabulary"]
        VocabCode = cls.env["spp.vocabulary.code"]

        vocab_defs = [
            {
                "name": "Farm Type",
                "namespace_uri": "urn:openspp:vocab:farm-type",
                "codes": [
                    ("crop", "Crop Farming"),
                    ("livestock", "Livestock Farming"),
                    ("mixed", "Mixed Farming"),
                    ("aquaculture", "Aquaculture"),
                ],
            },
            {
                "name": "Land Tenure",
                "namespace_uri": "urn:openspp:vocab:land-tenure",
                "codes": [("self", "Self-owned"), ("family", "Family-owned"), ("leased", "Leased")],
            },
            {
                "name": "Holder Type",
                "namespace_uri": "urn:openspp:vocab:holder-type",
                "codes": [("individual", "Individual")],
            },
            {
                "name": "Gender",
                "namespace_uri": "urn:openspp:vocab:gender",
                "codes": [("male", "Male"), ("female", "Female")],
            },
            {
                "name": "Group Membership Type",
                "namespace_uri": "urn:openspp:vocab:group-membership-type",
                "codes": [("head", "Head of Household")],
            },
            {
                "name": "Activity Purpose",
                "namespace_uri": "urn:openspp:vocab:activity-purpose",
                "codes": [
                    ("subsistence", "Subsistence"),
                    ("commercial", "Commercial"),
                    ("both", "Both"),
                ],
            },
            {
                "name": "FAO ICC",
                "namespace_uri": "urn:fao:icc:1.1",
                "codes": [
                    ("0116", "Rice, irrigated"),
                    ("0115", "Maize"),
                    ("02", "Vegetables"),
                ],
            },
            {
                "name": "FAO Livestock",
                "namespace_uri": "urn:fao:livestock:2020",
                "codes": [
                    ("3.2", "Goats"),
                    ("5.1", "Chickens"),
                    ("1", "Cattle"),
                ],
            },
            {
                "name": "FAO ASFIS",
                "namespace_uri": "urn:fao:asfis:2024",
                "codes": [("TIL", "Tilapia")],
            },
        ]

        for vocab_def in vocab_defs:
            vocab = Vocabulary.search([("namespace_uri", "=", vocab_def["namespace_uri"])], limit=1)
            if not vocab:
                vocab = Vocabulary.create(
                    {
                        "name": vocab_def["name"],
                        "namespace_uri": vocab_def["namespace_uri"],
                    }
                )
                for code, display in vocab_def["codes"]:
                    VocabCode.create(
                        {
                            "vocabulary_id": vocab.id,
                            "namespace_uri": vocab_def["namespace_uri"],
                            "code": code,
                            "display": display,
                        }
                    )

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def _create_season(self):
        """Create an active season for tests."""
        Season = self.env["spp.farm.season"]
        existing = Season.search([("state", "=", "active")], limit=1)
        if existing:
            return existing
        return Season.sudo().create(
            {
                "name": _unique("Test Season"),
                "date_start": "2026-01-01",
                "date_end": "2026-12-31",
                "state": "active",
            }
        )

    def test_create_farm_activities_with_crops(self):
        """Farm activities should create crop activity records."""
        gen = self._make_generator()
        self._create_season()

        # Create a simple crop blueprint and generate farms
        bp = {
            "id": "test_crop_act",
            "label": "Test",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (2.0, 2.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 30)},
            ],
            "activities": [
                {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.8},
            ],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        self.assertEqual(len(results), 1)

        farm = results[0]["group"]
        activities = self.env["spp.farm.activity"].search([("crop_farm_id", "=", farm.id)])
        # Activities are created if species vocab exists
        if gen._resolve_species("rice_irrigated"):
            self.assertGreaterEqual(len(activities), 1)
            self.assertEqual(activities[0].activity_type, "crop")

    def test_create_farm_activities_with_livestock(self):
        """Farm activities should create livestock activity records."""
        gen = self._make_generator()
        self._create_season()

        bp = {
            "id": "test_livestock_act",
            "label": "Test",
            "count": 1,
            "zone": "rural",
            "farm_type": "livestock",
            "size_range": (1.0, 1.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 30)},
            ],
            "activities": [
                {"type": "livestock", "species_code": "chickens", "quantity_range": (20, 20)},
            ],
            "land_tenure": "self",
            "land_use": "pasture",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        farm = results[0]["group"]
        activities = self.env["spp.farm.activity"].search([("livestock_farm_id", "=", farm.id)])
        if gen._resolve_species("chickens"):
            self.assertGreaterEqual(len(activities), 1)
            self.assertEqual(activities[0].activity_type, "livestock")

    def test_create_farm_activities_no_season_skips(self):
        """Without an active season, no activities should be created."""
        gen = self._make_generator()

        # Deactivate all seasons
        self.env["spp.farm.season"].search([("state", "=", "active")]).write({"state": "closed"})

        bp = {
            "id": "test_no_season",
            "label": "Test",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (1.0, 1.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 30)},
            ],
            "activities": [
                {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.8},
            ],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        farm = results[0]["group"]
        activities = self.env["spp.farm.activity"].search([("crop_farm_id", "=", farm.id)])
        self.assertEqual(len(activities), 0)

    def test_create_land_records(self):
        """Generated farms should have land records with polygons."""
        gen = self._make_generator()
        self._create_season()
        # Land records are anchored to the farm's GPS point, which is only
        # generated when the farm lands inside a known demo area. Seed one of
        # the rural anchor areas so a GPS point (and thus a parcel) is created.
        if not self.env["spp.area"].search([("code", "=", "PH-NUE")], limit=1):
            self.env["spp.area"].create({"draft_name": "Nueva Ecija", "code": "PH-NUE"})

        bp = {
            "id": "test_land_rec",
            "label": "Test",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (2.0, 2.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 30)},
            ],
            "activities": [],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        farm = results[0]["group"]

        if "spp.land.record" in self.env:
            land_records = self.env["spp.land.record"].search([("land_farm_id", "=", farm.id)])
            self.assertGreaterEqual(len(land_records), 1)
            # Verify polygon exists
            land = land_records[0]
            self.assertTrue(land.land_geo_polygon)
            # land_geo_polygon is a Shapely Polygon object, not JSON
            self.assertEqual(land.land_geo_polygon.geom_type, "Polygon")


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorPhases(TransactionCase):
    """Test the full phase execution of generate_all_farms."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )

        # Reuse the full vocabulary setup
        TestSeededFarmGeneratorActivities._create_full_vocabularies.__func__(cls)

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def test_generate_all_farms_mixed_farm_type(self):
        """Mixed farm type should split productive land among activity types."""
        gen = self._make_generator()

        # Create active season
        Season = self.env["spp.farm.season"]
        if not Season.search([("state", "=", "active")]):
            Season.sudo().create(
                {
                    "name": _unique("Test Season"),
                    "date_start": "2026-01-01",
                    "date_end": "2026-12-31",
                    "state": "active",
                }
            )

        bp = {
            "id": "test_mixed",
            "label": "Test Mixed",
            "count": 2,
            "zone": "rural",
            "farm_type": "mixed",
            "size_range": (3.0, 3.0),
            "experience_range": (10, 10),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (40, 40)},
                {"role": "spouse", "gender": "female", "age_range": (38, 38)},
            ],
            "activities": [
                {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.5},
                {"type": "livestock", "species_code": "chickens", "quantity_range": (10, 30)},
            ],
            "land_tenure": "family",
            "land_use": "mixed",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        self.assertEqual(len(results), 2)

        for result in results:
            farm = result["group"]
            self.assertTrue(farm.is_group)
            self.assertTrue(farm.is_registrant)
            self.assertEqual(len(result["members"]), 2)

            # Verify farm details
            details = farm.farm_details_id
            self.assertTrue(details)
            self.assertAlmostEqual(details.farm_total_size, 3.0, places=1)

    def test_generate_all_farms_aquaculture_type(self):
        """Aquaculture farm type should set under_aquaculture field."""
        gen = self._make_generator()

        Season = self.env["spp.farm.season"]
        if not Season.search([("state", "=", "active")]):
            Season.sudo().create(
                {
                    "name": _unique("Test Season Aqua"),
                    "date_start": "2026-01-01",
                    "date_end": "2026-12-31",
                    "state": "active",
                }
            )

        bp = {
            "id": "test_aqua",
            "label": "Test Aqua",
            "count": 1,
            "zone": "rural",
            "farm_type": "aquaculture",
            "size_range": (1.0, 1.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (35, 35)},
            ],
            "activities": [
                {"type": "aquaculture", "species_code": "tilapia", "quantity_range": (1000, 1000)},
            ],
            "land_tenure": "leased",
            "land_use": "aquaculture",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        farm = results[0]["group"]
        details = farm.farm_details_id
        self.assertAlmostEqual(details.farm_size_under_aquaculture, 1.0, places=1)

    def test_generate_all_farms_idle_land(self):
        """Blueprint with idle_pct should reduce productive area."""
        gen = self._make_generator()

        bp = {
            "id": "test_idle",
            "label": "Test Idle",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (4.0, 4.0),
            "experience_range": (10, 10),
            "head_gender": "male",
            "idle_pct": 0.25,
            "members": [
                {"role": "head", "gender": "male", "age_range": (40, 40)},
            ],
            "activities": [],
            "land_tenure": "self",
            "land_use": "fallow",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        details = results[0]["group"].farm_details_id
        self.assertAlmostEqual(details.farm_size_idle, 1.0, places=1)
        self.assertAlmostEqual(details.farm_size_under_crops, 3.0, places=1)

    def test_generate_all_farms_assigns_areas(self):
        """Farms should be assigned to demo areas if any exist."""
        gen = self._make_generator()

        # Seed one of the known anchor areas. The farm is only assigned an
        # area when its zone's candidate code (e.g. PH-NUE for rural) exists;
        # an arbitrary PH-* code that isn't an anchor would never be picked.
        if not self.env["spp.area"].search([("code", "=", "PH-NUE")], limit=1):
            self.env["spp.area"].create({"draft_name": "Nueva Ecija", "code": "PH-NUE"})

        bp = {
            "id": "test_area",
            "label": "Test Area",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (1.0, 1.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 30)},
            ],
            "activities": [],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        farm = results[0]["group"]
        self.assertTrue(farm.area_id, "Farm should have an area assigned")

    def test_generate_all_farms_result_structure(self):
        """Each result dict must have group, members, blueprint, size, gps keys."""
        gen = self._make_generator()

        bp = {
            "id": "test_struct",
            "label": "Test",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (1.0, 2.0),
            "experience_range": (5, 10),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 50)},
            ],
            "activities": [],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        result = results[0]
        self.assertIn("group", result)
        self.assertIn("members", result)
        self.assertIn("blueprint", result)
        self.assertIn("size", result)
        self.assertIn("gps", result)
        self.assertEqual(result["blueprint"]["id"], "test_struct")

    def test_farm_named_after_head_and_family_shares_surname(self):
        """OP#1114: the farm is named after its head member, and every member
        shares the head's family name (the household is a family of the head)."""
        gen = self._make_generator()

        bp = {
            "id": "test_family",
            "label": "Test Family",
            "count": 3,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (2.0, 2.0),
            "experience_range": (5, 5),
            "head_gender": "female",
            "members": [
                {"role": "head", "gender": "female", "age_range": (35, 35)},
                {"role": "spouse", "gender": "male", "age_range": (38, 38)},
                {"role": "child", "gender": "any", "age_range": (10, 10)},
            ],
            "activities": [],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {},
        }
        results = gen.generate_all_farms([bp])
        self.assertEqual(len(results), 3)

        for result in results:
            farm = result["group"]
            members = result["members"]
            head = members[0]  # blueprint lists the head first

            # 1) The farm is named after its head member.
            self.assertTrue(
                farm.name.startswith(head.name + " "),
                f"Farm '{farm.name}' should be named after head '{head.name}'",
            )
            # The head named in the farm is an actual member of the group.
            self.assertIn(head.name, [m.name for m in members])

            # 2) Every member shares the head's family name (one family).
            self.assertTrue(head.family_name)
            for member in members:
                self.assertEqual(member.family_name, head.family_name)


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorEnrollment(TransactionCase):
    """Test enrollment in programs based on blueprint eligibility."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        TestSeededFarmGeneratorActivities._create_full_vocabularies.__func__(cls)

    def _make_generator(self, seed=42):
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        return SeededFarmGenerator(self.env, locale="fil_PH", seed=seed)

    def test_enroll_in_programs_empty_inputs(self):
        """Enrollment with empty inputs should not error."""
        gen = self._make_generator()
        gen.enroll_in_programs([], {})
        gen.enroll_in_programs(None, None)

    def test_enroll_in_programs_no_eligible(self):
        """Farms with all-False eligibility should not enroll."""
        gen = self._make_generator()

        bp = {
            "id": "test_no_elig",
            "label": "Test",
            "count": 1,
            "zone": "rural",
            "farm_type": "crop",
            "size_range": (1.0, 1.0),
            "experience_range": (5, 5),
            "head_gender": "male",
            "members": [
                {"role": "head", "gender": "male", "age_range": (30, 30)},
            ],
            "activities": [],
            "land_tenure": "self",
            "land_use": "cultivation",
            "eligibility": {"program_a": False, "program_b": False},
        }
        results = gen.generate_all_farms([bp])

        # No programs in map, so nothing to enroll
        gen.enroll_in_programs(results, {})
        # Should not raise
