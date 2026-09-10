# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: duplicate detection must not be defeatable by a padded change set.

The proposed change set is derived from the detail-vs-registrant diff, never
from the requester-writable ``selected_field_name`` / ``field_to_modify`` -- that
independence is what makes a mislabelled request still detectable, and these
tests guard it.

Comparison used to require the two derived sets to be *equal*. Since a
dynamic-approval type applies only the routed field, a requester could pad their
request with a throwaway edit to another mapped field, make the sets unequal and
drop similarity to zero, while apply discarded the padding -- so the evasion was
free. Similarity is now scored over the fields both requests propose to change,
proportionally, so padding is ignored and a mostly identical request no longer
collapses to zero when one shared field differs.
"""

from odoo.tests import tagged

from .common import CRTestCase


@tagged("post_install", "-at_install")
class TestDuplicateDetectionScope(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.Partner.create(
            {
                "name": "Dup Scope Registrant",
                "given_name": "Orig",
                "family_name": "OrigFam",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _make_type(self, code, dynamic):
        cr_type = self.CRType.create(
            {
                "code": code,
                "name": code,
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "use_dynamic_approval": dynamic,
                "enable_duplicate_detection": True,
                "apply_mapping_ids": [
                    (0, 0, {"source_field": "given_name", "target_field": "given_name"}),
                    (0, 0, {"source_field": "family_name", "target_field": "family_name"}),
                ],
            }
        )
        config = self.env["spp.cr.duplicate.config"].create(
            {
                "name": f"{code} config",
                "cr_type_id": cr_type.id,
                "time_window_hours": 24,
                "similarity_threshold": 70.0,
            }
        )
        cr_type.duplicate_detection_config_id = config
        return cr_type, config

    def _make_cr(self, cr_type, detail_vals, selected="given_name"):
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        detail = cr.get_detail()
        vals = dict(detail_vals)
        if cr_type.use_dynamic_approval:
            vals["field_to_modify"] = selected
        detail.write(vals)
        return cr

    # ------------------------------------------------------------------
    # Padding a change set must not clear the check
    # ------------------------------------------------------------------

    def test_identical_dynamic_requests_are_detected(self):
        """Control: without a decoy, the duplicate is caught."""
        cr_type, _ = self._make_type("dup_scope_dyn_control", True)
        self._make_cr(cr_type, {"given_name": "NewName"})
        second = self._make_cr(cr_type, {"given_name": "NewName"})
        result = second._detect_duplicates()
        self.assertTrue(result["has_duplicates"])
        self.assertEqual(result["max_similarity"], 100.0)

    def test_detection_is_not_derived_from_the_writable_label(self):
        """The change set must come from the real diff, not the routing label."""
        cr_type, _ = self._make_type("dup_scope_label", True)
        cr = self._make_cr(cr_type, {"given_name": "NewName"}, selected="family_name")
        self.assertEqual(
            cr._proposed_changed_fields(),
            {"given_name"},
            "change set must follow the detail-vs-registrant diff, not field_to_modify",
        )

    def test_decoy_edit_cannot_defeat_duplicate_detection(self):
        """An edit to a mapped field apply discards must not clear the check."""
        cr_type, _ = self._make_type("dup_scope_dyn_decoy", True)
        self._make_cr(cr_type, {"given_name": "NewName"})
        attacker = self._make_cr(cr_type, {"given_name": "NewName", "family_name": "Decoy"})

        # The decoy is a real diff, so it legitimately appears in the change
        # set -- the set is derived from the data, not from what apply writes.
        self.assertEqual(attacker._proposed_changed_fields(), {"given_name", "family_name"})

        # But apply discards it, so it buys the requester nothing ...
        strategy = self.env["spp.cr.strategy.field_mapping"]
        applied = sorted(m.source_field for m in strategy._effective_mappings(attacker))
        self.assertEqual(applied, ["given_name"], "apply scope is not the single routed field")

        # ... and it must not stop the duplicate being flagged.
        result = attacker._detect_duplicates()
        self.assertTrue(
            result["has_duplicates"],
            "a discarded decoy edit defeated duplicate detection",
        )

    def test_routing_a_different_field_is_not_a_duplicate(self):
        """Two requests changing genuinely different fields are not duplicates."""
        cr_type, _ = self._make_type("dup_scope_dyn_distinct", True)
        self._make_cr(cr_type, {"given_name": "NewName"}, selected="given_name")
        other = self._make_cr(cr_type, {"family_name": "OtherFam"}, selected="family_name")
        self.assertFalse(other._detect_duplicates()["has_duplicates"])

    # ------------------------------------------------------------------
    # Scoring: proportional, not all-or-nothing
    # ------------------------------------------------------------------

    def test_partial_match_scores_proportionally(self):
        """One of two changed fields identical scores ~50, not 0."""
        cr_type, config = self._make_type("dup_scope_partial", True)
        first = self._make_cr(cr_type, {"given_name": "Same", "family_name": "AAAA"})
        second = self._make_cr(cr_type, {"given_name": "Same", "family_name": "ZZZZ"})
        self.assertEqual(first._proposed_changed_fields(), {"given_name", "family_name"})
        similarity = second._calculate_similarity(first, config)
        self.assertAlmostEqual(similarity, 50.0, places=1)

    def test_full_match_still_scores_100(self):
        cr_type, config = self._make_type("dup_scope_full", True)
        first = self._make_cr(cr_type, {"given_name": "Same", "family_name": "Same2"})
        second = self._make_cr(cr_type, {"given_name": "Same", "family_name": "Same2"})
        self.assertEqual(second._calculate_similarity(first, config), 100.0)
