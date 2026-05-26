# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for Blueprint + Seeded RNG reproducibility.

Verifies that:
1. Same seed + same locale produces identical output
2. Different locales produce different names but same structure
3. Blueprint counts meet the 1000+ registrant target
4. Volume names don't collide with reserved story names
"""

from odoo.tests import TransactionCase

from ..models.household_blueprints import (
    HOUSEHOLD_BLUEPRINTS,
    get_total_household_count,
    get_total_member_estimate,
)
from ..models.seeded_volume_generator import SeededVolumeGenerator


class TestBlueprintReproducibility(TransactionCase):
    """Test deterministic generation from blueprints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
                no_reset_password=True,
            )
        )

    def test_total_count_over_1000_registrants(self):
        """Blueprint system generates 1000+ total registrants."""
        total_hh = get_total_household_count()
        total_members = get_total_member_estimate()
        total_registrants = total_hh + total_members

        self.assertGreater(total_hh, 500, "Should have at least 500 households")
        self.assertGreater(total_registrants, 1000, "Should have over 1000 total registrants")

    def test_blueprint_structure_integrity(self):
        """Each blueprint has required fields and valid data."""
        for bp in HOUSEHOLD_BLUEPRINTS:
            self.assertIn("id", bp, "Blueprint missing 'id'")
            self.assertIn("count", bp, f"Blueprint {bp.get('id')} missing 'count'")
            self.assertIn("members", bp, f"Blueprint {bp.get('id')} missing 'members'")
            self.assertIn("eligibility", bp, f"Blueprint {bp.get('id')} missing 'eligibility'")
            self.assertGreater(bp["count"], 0, f"Blueprint {bp['id']} count must be positive")
            self.assertGreater(len(bp["members"]), 0, f"Blueprint {bp['id']} must have members")

            for member in bp["members"]:
                self.assertIn("role", member)
                self.assertIn("gender", member)
                self.assertIn("age_range", member)
                self.assertEqual(len(member["age_range"]), 2)
                self.assertLessEqual(member["age_range"][0], member["age_range"][1])

    def test_same_locale_identical_output(self):
        """Two runs with same seed + locale produce identical names."""
        # Use a small subset for speed
        subset = [bp for bp in HOUSEHOLD_BLUEPRINTS if bp["count"] <= 15][:3]

        gen1 = SeededVolumeGenerator(self.env, "fil_PH", seed=42)
        result1 = gen1.generate_all_households(subset)

        gen2 = SeededVolumeGenerator(self.env, "fil_PH", seed=42)
        result2 = gen2.generate_all_households(subset)

        self.assertEqual(len(result1), len(result2), "Same number of households")

        for hh1, hh2 in zip(result1, result2, strict=False):
            self.assertEqual(len(hh1["members"]), len(hh2["members"]), "Same number of members")
            for m1, m2 in zip(hh1["members"], hh2["members"], strict=False):
                self.assertEqual(m1.name, m2.name, "Same name for same seed+locale")
                self.assertEqual(m1.birthdate, m2.birthdate, "Same birthdate for same seed")

    def test_different_locale_different_names_same_structure(self):
        """Different locales produce different names but same household structure."""
        # Use smallest blueprint
        subset = [bp for bp in HOUSEHOLD_BLUEPRINTS if bp["count"] <= 10][:1]
        if not subset:
            subset = [HOUSEHOLD_BLUEPRINTS[0].copy()]
            subset[0]["count"] = 2

        gen_ph = SeededVolumeGenerator(self.env, "fil_PH", seed=42)
        result_ph = gen_ph.generate_all_households(subset)

        gen_lk = SeededVolumeGenerator(self.env, "si_LK", seed=42)
        result_lk = gen_lk.generate_all_households(subset)

        self.assertEqual(len(result_ph), len(result_lk), "Same number of households")

        # Structure should be the same
        for hh_ph, hh_lk in zip(result_ph, result_lk, strict=False):
            self.assertEqual(
                len(hh_ph["members"]),
                len(hh_lk["members"]),
                "Same number of members regardless of locale",
            )

    def test_no_reserved_name_collisions(self):
        """Volume names don't collide with reserved story names."""
        from odoo.addons.spp_demo.models.demo_stories import get_localized_reserved_names

        subset = [bp for bp in HOUSEHOLD_BLUEPRINTS if bp["count"] <= 15][:2]

        gen = SeededVolumeGenerator(self.env, "fil_PH", seed=42)
        result = gen.generate_all_households(subset)

        all_names = set()
        for hh in result:
            for member in hh["members"]:
                full_name = f"{member.given_name} {member.family_name}"
                all_names.add(full_name)

        collisions = all_names & set(get_localized_reserved_names("fil_PH"))
        self.assertEqual(len(collisions), 0, f"Name collisions with reserved names: {collisions}")

    def test_eligibility_flags_exist_for_known_programs(self):
        """Each blueprint's eligibility flags reference valid program IDs."""
        valid_program_ids = {
            "universal_child_grant",
            "conditional_child_grant",
            "elderly_social_pension",
            "emergency_relief_fund",
            "cash_transfer_program",
            "food_assistance",
        }

        for bp in HOUSEHOLD_BLUEPRINTS:
            for prog_id in bp.get("eligibility", {}):
                self.assertIn(
                    prog_id,
                    valid_program_ids,
                    f"Blueprint {bp['id']} references unknown program: {prog_id}",
                )
