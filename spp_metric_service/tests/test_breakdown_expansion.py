# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for BreakdownService group-to-member expansion."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBreakdownExpansion(TransactionCase):
    """Test that BreakdownService expands groups to members for individual-level dimensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.breakdown = cls.env["spp.metrics.breakdown"]
        cls.dim_model = cls.env["spp.demographic.dimension"]

        # Create a dimension that applies to individuals only
        cls.gender_dim = cls.dim_model.search([("name", "=", "gender")], limit=1)
        if not cls.gender_dim:
            cls.gender_dim = cls.dim_model.create(
                {
                    "name": "gender",
                    "label": "Gender",
                    "dimension_type": "field",
                    "field_path": "gender_id.code",
                    "applies_to": "individuals",
                    "default_value": "unknown",
                }
            )
        else:
            # Ensure applies_to is set for this test
            cls.gender_dim.applies_to = "individuals"

        # Create a dimension that applies to all
        cls.type_dim = cls.dim_model.search([("name", "=", "registrant_type")], limit=1)
        if not cls.type_dim:
            cls.type_dim = cls.dim_model.create(
                {
                    "name": "registrant_type",
                    "label": "Registrant Type",
                    "dimension_type": "field",
                    "field_path": "is_group",
                    "applies_to": "all",
                    "default_value": "unknown",
                }
            )

        # Create a group with two individual members
        cls.group = cls.env["res.partner"].create(
            {
                "name": "Expansion Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.member1 = cls.env["res.partner"].create(
            {
                "name": "Member 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.member2 = cls.env["res.partner"].create(
            {
                "name": "Member 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create memberships
        cls.env["spp.group.membership"].create({"group": cls.group.id, "individual": cls.member1.id})
        cls.env["spp.group.membership"].create({"group": cls.group.id, "individual": cls.member2.id})

    def test_expansion_with_individual_dimension(self):
        """Passing group IDs with individual-level dimensions expands to members."""
        result = self.breakdown.compute_breakdown([self.group.id], ["gender"])

        # Should have breakdown entries (from the 2 members, not the 1 group)
        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, 2, "Should count 2 individual members, not 1 group")

    def test_no_expansion_with_all_dimension(self):
        """Passing group IDs with applies_to='all' dimensions does NOT expand."""
        result = self.breakdown.compute_breakdown([self.group.id], ["registrant_type"])

        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, 1, "Should count 1 group record without expansion")

    def test_mixed_group_and_individual_ids(self):
        """Mixed group + individual IDs: groups expand, individuals pass through."""
        result = self.breakdown.compute_breakdown(
            [self.group.id, self.member1.id],
            ["gender"],
        )

        # group expands to member1 + member2, plus member1 directly = 3 IDs
        # but member1 appears twice, so after dedup = 2 unique individuals
        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, 2, "Duplicates from expansion should be deduplicated")

    def test_empty_group_no_phantom_entries(self):
        """Group with no active members produces no entries."""
        empty_group = self.env["res.partner"].create(
            {
                "name": "Empty Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        result = self.breakdown.compute_breakdown([empty_group.id], ["gender"])
        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, 0, "Empty group should produce no breakdown entries")

    def test_existing_tests_unaffected(self):
        """Empty group_by still returns empty dict."""
        result = self.breakdown.compute_breakdown([self.group.id], [])
        self.assertEqual(result, {})

    def test_individual_ids_with_individual_dimension(self):
        """Passing individual IDs with individual-level dimensions works without expansion."""
        result = self.breakdown.compute_breakdown(
            [self.member1.id, self.member2.id],
            ["gender"],
        )
        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, 2, "Individual IDs should pass through without expansion")
