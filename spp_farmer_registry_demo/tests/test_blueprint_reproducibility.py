# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for blueprint reproducibility and structure integrity.

Tests cover:
- Blueprint structure (all required fields present)
- Total count targets (~730 farms)
- Deterministic output (same seed = same result)
- Reserved name collision avoidance
- Eligibility flags reference valid programs
"""

import time

from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestBlueprintStructure(TransactionCase):
    """Test blueprint definitions are well-formed."""

    def test_all_blueprints_have_required_fields(self):
        """Every blueprint must have id, label, count, members, activities."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        required_fields = {
            "id",
            "label",
            "count",
            "zone",
            "farm_type",
            "size_range",
            "experience_range",
            "head_gender",
            "members",
            "activities",
            "land_tenure",
            "land_use",
            "eligibility",
        }

        for bp in FARMER_BLUEPRINTS:
            for field in required_fields:
                self.assertIn(
                    field,
                    bp,
                    f"Blueprint {bp.get('id', '?')} missing required field: {field}",
                )

    def test_blueprint_ids_unique(self):
        """Blueprint IDs must be unique."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        ids = [bp["id"] for bp in FARMER_BLUEPRINTS]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate blueprint IDs found")

    def test_total_farm_count_target(self):
        """Total farm count should be ~730 (within reasonable range)."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            get_total_farm_count,
        )

        total = get_total_farm_count()
        self.assertGreaterEqual(total, 600, f"Too few farms: {total}")
        self.assertLessEqual(total, 900, f"Too many farms: {total}")

    def test_members_have_required_fields(self):
        """Each member spec must have role, gender, age_range."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        for bp in FARMER_BLUEPRINTS:
            for member in bp["members"]:
                self.assertIn("role", member, f"Blueprint {bp['id']} member missing role")
                self.assertIn("gender", member, f"Blueprint {bp['id']} member missing gender")
                self.assertIn("age_range", member, f"Blueprint {bp['id']} member missing age_range")
                self.assertEqual(
                    len(member["age_range"]),
                    2,
                    f"Blueprint {bp['id']} member age_range must be (min, max)",
                )

    def test_size_range_valid(self):
        """size_range must be (min, max) with min <= max."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        for bp in FARMER_BLUEPRINTS:
            lo, hi = bp["size_range"]
            self.assertLessEqual(lo, hi, f"Blueprint {bp['id']} has invalid size_range")
            self.assertGreater(lo, 0, f"Blueprint {bp['id']} has non-positive size_range min")

    def test_eligibility_flags_reference_known_programs(self):
        """Eligibility keys must match demo program IDs."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            DEMO_PROGRAMS,
        )
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        valid_ids = {p["id"] for p in DEMO_PROGRAMS}

        for bp in FARMER_BLUEPRINTS:
            for key in bp["eligibility"]:
                self.assertIn(
                    key,
                    valid_ids,
                    f"Blueprint {bp['id']} references unknown program: {key}",
                )

    def test_activities_have_species_code(self):
        """Each activity must have a type and species_code."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        for bp in FARMER_BLUEPRINTS:
            for act in bp["activities"]:
                self.assertIn("type", act, f"Blueprint {bp['id']} activity missing type")
                self.assertIn(
                    "species_code",
                    act,
                    f"Blueprint {bp['id']} activity missing species_code",
                )

    def test_farm_type_values_valid(self):
        """farm_type must be one of crop, livestock, mixed, aquaculture."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            FARMER_BLUEPRINTS,
        )

        valid_types = {"crop", "livestock", "mixed", "aquaculture"}
        for bp in FARMER_BLUEPRINTS:
            self.assertIn(
                bp["farm_type"],
                valid_types,
                f"Blueprint {bp['id']} has invalid farm_type: {bp['farm_type']}",
            )


@tagged("post_install", "-at_install")
class TestSeededFarmGeneratorDeterminism(TransactionCase):
    """Test deterministic output of SeededFarmGenerator."""

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
        # Create required vocabularies
        cls._create_test_vocabularies()

    @classmethod
    def _create_test_vocabularies(cls):
        """Create vocabularies needed for farm generation."""
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
                    ("cooperative", "Cooperative"),
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

    def test_same_seed_produces_identical_rng_sequence(self):
        """Two generators with same seed must produce identical RNG sequences.

        Tests that the core seeded random.Random produces deterministic
        structural data (sizes, experience, GPS coordinates).
        """
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        gen1 = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        seq1 = [gen1.rng.uniform(1.0, 10.0) for _ in range(20)]

        gen2 = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        seq2 = [gen2.rng.uniform(1.0, 10.0) for _ in range(20)]

        self.assertEqual(seq1, seq2, "Same seed should produce identical RNG sequence")

    def test_different_seed_produces_different_names(self):
        """Different seeds must produce different farm names."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        test_blueprints = [
            {
                "id": "test_bp_diff",
                "label": "Test",
                "count": 5,
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
            },
        ]

        gen1 = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        results1 = gen1.generate_all_farms(test_blueprints)
        names1 = [r["group"].name for r in results1]

        gen2 = SeededFarmGenerator(self.env, locale="fil_PH", seed=99)
        results2 = gen2.generate_all_farms(test_blueprints)
        names2 = [r["group"].name for r in results2]

        self.assertNotEqual(names1, names2, "Different seeds should produce different names")

    def test_blueprint_count_matches_output(self):
        """Output count must match sum of blueprint counts."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        test_blueprints = [
            {
                "id": "test_bp_count_a",
                "label": "A",
                "count": 3,
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
            },
            {
                "id": "test_bp_count_b",
                "label": "B",
                "count": 4,
                "zone": "rural",
                "farm_type": "livestock",
                "size_range": (2.0, 5.0),
                "experience_range": (3, 8),
                "head_gender": "female",
                "members": [
                    {"role": "head", "gender": "female", "age_range": (25, 45)},
                    {"role": "spouse", "gender": "male", "age_range": (28, 50)},
                ],
                "activities": [],
                "land_tenure": "family",
                "land_use": "pasture",
                "eligibility": {},
            },
        ]

        gen = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        results = gen.generate_all_farms(test_blueprints)

        self.assertEqual(len(results), 7, "Total should be 3 + 4 = 7")
        # Check members: first 3 have 1 member each, next 4 have 2 each
        for r in results[:3]:
            self.assertEqual(len(r["members"]), 1)
        for r in results[3:]:
            self.assertEqual(len(r["members"]), 2)

    def test_reserved_names_avoided(self):
        """Generated farm names must not collide with story farm names."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        test_blueprints = [
            {
                "id": "test_bp_reserved",
                "label": "Test",
                "count": 20,
                "zone": "rural",
                "farm_type": "crop",
                "size_range": (1.0, 3.0),
                "experience_range": (3, 15),
                "head_gender": "male",
                "members": [
                    {"role": "head", "gender": "male", "age_range": (25, 55)},
                ],
                "activities": [],
                "land_tenure": "self",
                "land_use": "cultivation",
                "eligibility": {},
            },
        ]

        gen = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        results = gen.generate_all_farms(test_blueprints)

        reserved = {
            "Santos Farm",
            "Dela Cruz Farm",
            "Garcia Farm",
            "Mangudadatu Farm",
            "Martinez Farm",
            "Dela Cruz Fishpond",
            "Pangandaman Farm",
            "Villanueva Farm",
        }

        generated_names = {r["group"].name for r in results}
        collisions = generated_names & reserved
        self.assertEqual(
            len(collisions),
            0,
            f"Generated names collide with reserved: {collisions}",
        )

    def test_farm_names_and_registry_ids_unique(self):
        """OP#1114: generated farm names — and the registry IDs derived from
        them — must be unique even when the 86-surname pool is exhausted by a
        much larger farm count."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        test_blueprints = [
            {
                "id": "test_bp_unique",
                "label": "Unique",
                "count": 40,
                "zone": "rural",
                "farm_type": "crop",
                "size_range": (1.0, 3.0),
                "experience_range": (3, 15),
                "head_gender": "male",
                "members": [
                    {"role": "head", "gender": "male", "age_range": (25, 55)},
                ],
                "activities": [],
                "land_tenure": "self",
                "land_use": "cultivation",
                "eligibility": {},
            },
        ]

        gen = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        results = gen.generate_all_farms(test_blueprints)

        names = [r["group"].name for r in results]
        self.assertEqual(len(names), len(set(names)), f"Duplicate farm names generated: {sorted(names)}")

        group_ids = [r["group"].id for r in results]
        reg_values = self.env["spp.registry.id"].search([("partner_id", "in", group_ids)]).mapped("value")
        self.assertTrue(reg_values, "expected registry IDs to be created for the farms")
        self.assertEqual(len(reg_values), len(set(reg_values)), "Duplicate registry ID values across farms")

    def test_farms_are_groups_with_members(self):
        """Generated farms must be groups with at least one member."""
        from odoo.addons.spp_farmer_registry_demo.models.seeded_farm_generator import (
            SeededFarmGenerator,
        )

        test_blueprints = [
            {
                "id": "test_bp_group",
                "label": "Test",
                "count": 3,
                "zone": "rural",
                "farm_type": "crop",
                "size_range": (1.0, 2.0),
                "experience_range": (5, 10),
                "head_gender": "male",
                "members": [
                    {"role": "head", "gender": "male", "age_range": (30, 50)},
                    {"role": "spouse", "gender": "female", "age_range": (28, 48)},
                ],
                "activities": [],
                "land_tenure": "self",
                "land_use": "cultivation",
                "eligibility": {},
            },
        ]

        gen = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        results = gen.generate_all_farms(test_blueprints)

        for r in results:
            farm = r["group"]
            self.assertTrue(farm.is_group)
            self.assertTrue(farm.is_registrant)
            members = self.env["spp.group.membership"].search([("group", "=", farm.id)])
            self.assertEqual(len(members), 2)
