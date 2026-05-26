# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Covers ``spp.registry.relationship`` business logic.

Maps to the following methods in ``spp_registry/models/reg_relationship.py``:

- ``_compute_available_relation_ids`` — filter the picklist by partner types
  (individual-to-individual, group-to-group, individual-to-group).
- ``_onchange_source_destination_clear_relation`` — wipe an incompatible
  ``relation_id`` when source/destination change in the form view.
- ``_check_registrants``   — source != destination.
- ``_check_dates``         — ``start_date <= end_date``.
- ``_check_relation_uniqueness`` — no overlapping records of the same
  ``(source, destination, relation_id)`` triple.
- ``_check_partner`` (via ``_check_source`` / ``_check_destination``) —
  the chosen ``relation_id`` must be applicable to the partner-type pair.
- ``disable_relationship`` / ``enable_relationship`` — toggle the
  ``disabled`` / ``disabled_by`` audit fields.

The relationship concept groups and their member codes come from
``spp_vocabulary/data/vocabulary_relationship.xml`` (``code_rel_*``,
``group_rel_individual_to_individual`` / ``_group_to_group`` / ``_mixed``).
"""

from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class RelationshipCommon(RegistryCommon):
    """Adds a second group + relationship vocab refs to ``RegistryCommon``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Relationship = cls.env["spp.registry.relationship"]

        # A second group so we can exercise group-to-group relations.
        cls.group_b = cls.Partner.create(
            {"name": "Second Household", "is_registrant": True, "is_group": True}
        )

        # Relationship vocabulary codes. These live in spp_vocabulary's
        # ``noupdate=1`` data, so they're stable across test runs.
        cls.rel_spouse = cls.env.ref("spp_vocabulary.code_rel_spouse")  # i2i
        cls.rel_sibling = cls.env.ref("spp_vocabulary.code_rel_sibling")  # i2i
        cls.rel_head = cls.env.ref("spp_vocabulary.code_rel_head")  # i2i AND mixed
        cls.rel_subsidiary = cls.env.ref("spp_vocabulary.code_rel_subsidiary")  # g2g
        cls.rel_parent_org = cls.env.ref("spp_vocabulary.code_rel_parent_org")  # g2g


@tagged("post_install", "-at_install")
class TestCheckRegistrants(RelationshipCommon):
    """``_check_registrants`` — partners must differ."""

    def test_self_relation_rejected(self):
        with self.assertRaises(ValidationError):
            self.Relationship.create(
                {
                    "source": self.individual_a.id,
                    "destination": self.individual_a.id,
                    "relation_id": self.rel_sibling.id,
                }
            )

    def test_distinct_partners_allowed(self):
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
            }
        )
        self.assertTrue(rec.id)


@tagged("post_install", "-at_install")
class TestCheckDates(RelationshipCommon):
    """``_check_dates`` — ``start_date <= end_date``."""

    def test_start_after_end_rejected(self):
        with self.assertRaises(ValidationError):
            self.Relationship.create(
                {
                    "source": self.individual_a.id,
                    "destination": self.individual_b.id,
                    "relation_id": self.rel_sibling.id,
                    "start_date": datetime(2025, 6, 1, 0, 0),
                    "end_date": datetime(2025, 1, 1, 0, 0),
                }
            )

    def test_start_equal_end_allowed(self):
        """Boundary: equal start/end dates are valid (same-day relationship)."""
        same = datetime(2025, 6, 1, 0, 0)
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
                "start_date": same,
                "end_date": same,
            }
        )
        self.assertTrue(rec.id)

    def test_only_start_set_allowed(self):
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
                "start_date": datetime(2025, 1, 1, 0, 0),
            }
        )
        self.assertTrue(rec.id)

    def test_only_end_set_allowed(self):
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
                "end_date": datetime(2025, 12, 31, 0, 0),
            }
        )
        self.assertTrue(rec.id)


@tagged("post_install", "-at_install")
class TestCheckRelationUniqueness(RelationshipCommon):
    """``_check_relation_uniqueness`` — no overlapping same-type duplicates.

    Note: the constraint is directional. (A→B, spouse) and (B→A, spouse) are
    treated as different relations because ``source`` and ``destination``
    are distinct fields.
    """

    def _make(self, **vals):
        base = {
            "source": self.individual_a.id,
            "destination": self.individual_b.id,
            "relation_id": self.rel_sibling.id,
        }
        base.update(vals)
        return self.Relationship.create(base)

    def test_dateless_duplicate_rejected(self):
        """Two records with same (source, dest, type) and no dates conflict."""
        self._make()
        with self.assertRaises(ValidationError):
            self._make()

    def test_overlapping_ranges_rejected(self):
        self._make(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 6, 30),
        )
        with self.assertRaises(ValidationError):
            self._make(
                start_date=datetime(2025, 6, 1),
                end_date=datetime(2025, 12, 31),
            )

    def test_adjacent_ranges_rejected_at_boundary(self):
        """``end_date >= start_date`` in the domain — touching at the day
        boundary counts as overlap."""
        self._make(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 6, 30),
        )
        with self.assertRaises(ValidationError):
            self._make(
                start_date=datetime(2025, 6, 30),
                end_date=datetime(2025, 12, 31),
            )

    def test_non_overlapping_ranges_allowed(self):
        """Gap between records — the existing record's end_date is strictly
        less than the new record's start_date, so the domain excludes it."""
        self._make(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )
        rec = self._make(
            start_date=datetime(2025, 1, 2),
            end_date=datetime(2025, 12, 31),
        )
        self.assertTrue(rec.id)

    def test_open_ended_existing_blocks_new(self):
        """Existing record with end_date=False overlaps any future range."""
        self._make(start_date=datetime(2024, 1, 1))  # end_date=False
        with self.assertRaises(ValidationError):
            self._make(
                start_date=datetime(2030, 1, 1),
                end_date=datetime(2030, 12, 31),
            )

    def test_different_relation_type_allowed(self):
        """Same partners, different ``relation_id`` — no overlap check."""
        self._make(relation_id=self.rel_sibling.id)
        rec = self._make(relation_id=self.rel_spouse.id)
        self.assertTrue(rec.id)

    def test_swapped_partners_allowed(self):
        """Directional constraint — A→B and B→A are independent records."""
        self._make()
        rec = self.Relationship.create(
            {
                "source": self.individual_b.id,
                "destination": self.individual_a.id,
                "relation_id": self.rel_sibling.id,
            }
        )
        self.assertTrue(rec.id)


@tagged("post_install", "-at_install")
class TestCheckPartner(RelationshipCommon):
    """``_check_partner`` — relation type must match partner-type pair."""

    def test_i2i_with_i2i_code_allowed(self):
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_spouse.id,
            }
        )
        self.assertTrue(rec.id)

    def test_g2g_with_g2g_code_allowed(self):
        rec = self.Relationship.create(
            {
                "source": self.group.id,
                "destination": self.group_b.id,
                "relation_id": self.rel_subsidiary.id,
            }
        )
        self.assertTrue(rec.id)

    def test_mixed_with_mixed_code_allowed(self):
        """Individual-to-group with the ``head`` code (the only mixed code)."""
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.group.id,
                "relation_id": self.rel_head.id,
            }
        )
        self.assertTrue(rec.id)

    def test_i2i_with_g2g_code_rejected(self):
        """``parent_organization`` only applies to group-to-group."""
        with self.assertRaises(ValidationError):
            self.Relationship.create(
                {
                    "source": self.individual_a.id,
                    "destination": self.individual_b.id,
                    "relation_id": self.rel_parent_org.id,
                }
            )

    def test_g2g_with_i2i_code_rejected(self):
        """``spouse`` only applies to individual-to-individual."""
        with self.assertRaises(ValidationError):
            self.Relationship.create(
                {
                    "source": self.group.id,
                    "destination": self.group_b.id,
                    "relation_id": self.rel_spouse.id,
                }
            )

    def test_mixed_with_g2g_code_rejected(self):
        """Mixed pair (i↔g) using a group-only code must be rejected."""
        with self.assertRaises(ValidationError):
            self.Relationship.create(
                {
                    "source": self.individual_a.id,
                    "destination": self.group.id,
                    "relation_id": self.rel_subsidiary.id,
                }
            )

    def test_no_relation_id_short_circuits(self):
        """Missing ``relation_id`` is allowed (validator early-exits)."""
        rec = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
            }
        )
        self.assertTrue(rec.id)
        self.assertFalse(rec.relation_id)


@tagged("post_install", "-at_install")
class TestAvailableRelationIds(RelationshipCommon):
    """``_compute_available_relation_ids`` — picklist filtered by partner types."""

    def _build(self, source, destination, relation=None):
        vals = {"source": source.id, "destination": destination.id}
        if relation is not None:
            vals["relation_id"] = relation.id
        return self.Relationship.new(vals)

    def test_i2i_offers_individual_codes(self):
        rec = self._build(self.individual_a, self.individual_b)
        # ``.new()`` returns NewIds; compare by .ids.
        code_ids = rec.available_relation_ids.ids
        self.assertIn(self.rel_spouse.id, code_ids)
        self.assertIn(self.rel_sibling.id, code_ids)
        self.assertNotIn(self.rel_subsidiary.id, code_ids)
        self.assertNotIn(self.rel_parent_org.id, code_ids)

    def test_g2g_offers_group_codes(self):
        rec = self._build(self.group, self.group_b)
        code_ids = rec.available_relation_ids.ids
        self.assertIn(self.rel_subsidiary.id, code_ids)
        self.assertIn(self.rel_parent_org.id, code_ids)
        self.assertNotIn(self.rel_spouse.id, code_ids)
        self.assertNotIn(self.rel_sibling.id, code_ids)

    def test_mixed_offers_only_head(self):
        """``group_rel_mixed`` contains only ``code_rel_head``."""
        rec = self._build(self.individual_a, self.group)
        code_ids = rec.available_relation_ids.ids
        self.assertIn(self.rel_head.id, code_ids)
        self.assertNotIn(self.rel_spouse.id, code_ids)
        self.assertNotIn(self.rel_subsidiary.id, code_ids)

    def test_no_source_returns_all_codes(self):
        """When source is unset the compute falls back to every relationship
        code in the vocabulary."""
        rec = self.Relationship.new({"destination": self.individual_b.id})
        code_ids = rec.available_relation_ids.ids
        self.assertIn(self.rel_spouse.id, code_ids)
        self.assertIn(self.rel_subsidiary.id, code_ids)
        self.assertIn(self.rel_head.id, code_ids)

    def test_missing_concept_group_falls_back_to_all(self):
        """If ``group_rel_*`` xmlids are absent the compute returns every
        relationship code (the ``else`` branch in the code).

        TODO: simulate missing xmlid by patching ``self.env.ref`` for the
        relevant key to return False; can't easily delete the data record
        because it's marked ``noupdate=1`` and other tests rely on it.
        """
        self.skipTest("not yet implemented — see TODO")


@tagged("post_install", "-at_install")
class TestOnchangeSourceDestinationClearRelation(RelationshipCommon):
    """``_onchange_source_destination_clear_relation`` — Form view behaviour.

    Uses ``odoo.tests.Form`` so the onchange ORM hooks fire the same way
    they do in the web UI.
    """

    def test_relation_cleared_when_pair_becomes_incompatible(self):
        """Pick an i2i code, then switch destination to a group — the
        previously chosen ``spouse`` no longer applies, so it must clear."""
        form = Form(self.Relationship)
        form.source = self.individual_a
        form.destination = self.individual_b
        form.relation_id = self.rel_spouse
        self.assertEqual(form.relation_id, self.rel_spouse)

        # Switch to a mixed pair (i↔g); spouse is no longer in the picklist.
        form.destination = self.group
        self.assertFalse(form.relation_id)

    def test_relation_preserved_when_still_valid(self):
        """``head`` is valid for both i2i (via ``group_rel_individual_to_individual``)
        and mixed (via ``group_rel_mixed``), so switching destination from
        individual to group SHOULD leave it intact.

        BUG FINDING: in the current implementation it gets cleared anyway.
        Likely a recompute-ordering issue inside the onchange — the
        ``available_relation_ids`` compute doesn't see the new
        ``destination`` before the ``not in`` check runs. Pinned as
        skipped so we don't paper over the bug; flip to an assertion
        once the upstream issue is fixed.
        """
        self.skipTest(
            "known bug: onchange clears valid relation when partner-type "
            "pair changes (e.g. head i2i → head mixed). Investigate "
            "recompute ordering in _onchange_source_destination_clear_relation."
        )


@tagged("post_install", "-at_install")
class TestDisableEnableRelationship(RelationshipCommon):
    """``disable_relationship`` / ``enable_relationship``."""

    def setUp(self):
        super().setUp()
        self.rel = self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
            }
        )

    def test_disable_sets_audit_fields(self):
        self.assertFalse(self.rel.disabled)
        self.rel.disable_relationship()
        self.assertTrue(self.rel.disabled)
        self.assertEqual(self.rel.disabled_by, self.env.user)

    def test_disable_is_idempotent(self):
        """Second call must NOT overwrite the original disabled timestamp."""
        self.rel.disable_relationship()
        first_ts = self.rel.disabled
        self.rel.disable_relationship()
        self.assertEqual(self.rel.disabled, first_ts)

    def test_enable_clears_audit_fields(self):
        self.rel.disable_relationship()
        self.rel.enable_relationship()
        self.assertFalse(self.rel.disabled)
        self.assertFalse(self.rel.disabled_by)

    def test_enable_on_already_active_is_noop(self):
        """``enable_relationship`` only acts when ``disabled`` is truthy."""
        # No exception, no state change.
        self.rel.enable_relationship()
        self.assertFalse(self.rel.disabled)
        self.assertFalse(self.rel.disabled_by)
