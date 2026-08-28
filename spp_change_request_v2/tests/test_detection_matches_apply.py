# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Conflict/duplicate detection must judge "changed" exactly as apply does.

The change set is derived from the detail-versus-registrant difference, and it
has to agree with the comparison the apply strategy makes. It did not: detection
compared through ``_normalize_field_value``, which lowercases and strips
strings, and it ignored transform expressions entirely, while apply compares raw
and applies the transform first. So a case- or whitespace-only edit was
invisible to detection yet still written to the registrant, and a transform
could make a differing value identical -- or the reverse -- with only apply
aware of it.

Both sides now go through the strategy's ``mapping_changes_value``. Note this is
only about *whether* a field changed; similarity scoring stays deliberately
case-insensitive, since fuzzy matching is its purpose.
"""

from odoo.tests import tagged

from .common import CRTestCase


@tagged("post_install", "-at_install")
class TestDetectionMatchesApply(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.Partner.create(
            {
                "name": "Detect Apply Registrant",
                "given_name": "John",
                "family_name": "Fam",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _make_type(self, code, transform=None):
        mapping = {"source_field": "given_name", "target_field": "given_name"}
        if transform:
            mapping["transform"] = "expression"
            mapping["transform_expression"] = transform
        return self.CRType.create(
            {
                "code": code,
                "name": code,
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "use_dynamic_approval": True,
                "enable_duplicate_detection": True,
                "apply_mapping_ids": [(0, 0, mapping)],
            }
        )

    def _cr(self, cr_type, detail_vals):
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        cr.get_detail().write(dict(detail_vals, field_to_modify="given_name"))
        return cr

    def test_case_only_edit_is_seen_as_a_change(self):
        """It is written to the registrant, so detection must see it."""
        cr_type = self._make_type("detect_apply_case")
        cr = self._cr(cr_type, {"given_name": "  john  "})
        self.assertEqual(
            cr._proposed_changed_fields(),
            {"given_name"},
            "a value apply would write must count as a proposed change",
        )

    def test_detection_and_apply_agree_after_the_edit_lands(self):
        cr_type = self._make_type("detect_apply_agree")
        cr = self._cr(cr_type, {"given_name": "  john  "})
        self.env["spp.cr.strategy.field_mapping"].apply(cr)
        self.assertEqual(self.registrant.given_name, "  john  ")
        # Now the registrant holds it, so nothing is proposed any more.
        self.assertEqual(cr._proposed_changed_fields(), set())

    def test_identical_value_is_not_a_change(self):
        cr_type = self._make_type("detect_apply_same")
        cr = self._cr(cr_type, {"given_name": self.registrant.given_name})
        self.assertEqual(cr._proposed_changed_fields(), set())

    def test_transform_detection_agrees_with_apply(self):
        """Whatever a transform does, detection and apply must reach the same verdict.

        Transform expressions do not currently evaluate at all: Odoo 19's
        ``safe_eval`` takes no ``nocopy`` argument, so ``_eval_expression``
        raises, logs a warning and returns the value untransformed. Rather than
        pin either outcome, this asserts the invariant that matters -- the
        derived change set agrees with whether apply actually wrote anything --
        which holds both before and after that is corrected.
        """
        cr_type = self._make_type("detect_apply_tf_agree", transform="value + '-x'")
        cr = self._cr(cr_type, {"given_name": "Jane"})
        changed = cr._proposed_changed_fields()
        before = self.registrant.given_name
        self.env["spp.cr.strategy.field_mapping"].apply(cr)
        after = self.registrant.given_name
        self.assertEqual(
            bool(changed),
            before != after,
            "detection must agree with whether apply wrote something",
        )

    # ------------------------------------------------------------------
    # Deriving the change set once per run must not change the outcome
    # ------------------------------------------------------------------

    def test_passing_the_change_set_matches_deriving_it(self):
        cr_type = self._make_type("detect_apply_memo")
        config = self.env["spp.cr.duplicate.config"].create(
            {
                "name": "detect_apply_memo config",
                "cr_type_id": cr_type.id,
                "time_window_hours": 24,
                "similarity_threshold": 70.0,
            }
        )
        cr_type.duplicate_detection_config_id = config
        first = self._cr(cr_type, {"given_name": "Changed"})
        second = self._cr(cr_type, {"given_name": "Changed"})
        derived = second._calculate_similarity(first, config)
        passed_in = second._calculate_similarity(first, config, my_changed=second._proposed_changed_fields())
        self.assertEqual(derived, passed_in)
        self.assertEqual(derived, 100.0)
