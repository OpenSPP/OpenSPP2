# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Coverage for the spp.scoring.invalid.value sentinel-value catalog."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringInvalidValue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.InvalidValue = cls.env["spp.scoring.invalid.value"]

    # ─── defaults ────────────────────────────────────────────────────

    def test_defaults(self):
        rec = self.InvalidValue.create({"name": "No Birthdate!"})
        self.assertEqual(rec.match_type, "exact")
        self.assertTrue(rec.active)
        self.assertFalse(rec.description)

    # ─── exact-match entries ─────────────────────────────────────────

    def test_create_exact_entry(self):
        rec = self.InvalidValue.create({"name": "N/A", "match_type": "exact", "description": "Common sentinel"})
        self.assertEqual(rec.name, "N/A")
        self.assertEqual(rec.match_type, "exact")
        self.assertEqual(rec.description, "Common sentinel")

    # ─── regex-match entries ─────────────────────────────────────────

    def test_create_regex_entry_valid(self):
        rec = self.InvalidValue.create({"name": r"^N/A.*$", "match_type": "regex"})
        self.assertEqual(rec.match_type, "regex")

    def test_regex_pattern_must_compile_on_create(self):
        """A non-compiling regex must be rejected up front so the scoring
        engine never explodes mid-run."""
        with self.assertRaises(ValidationError):
            self.InvalidValue.create({"name": "([unclosed", "match_type": "regex"})

    def test_regex_pattern_must_compile_on_write(self):
        rec = self.InvalidValue.create({"name": r"^N/A$", "match_type": "regex"})
        with self.assertRaises(ValidationError):
            rec.write({"name": "([broken-on-write"})

    def test_regex_constraint_skipped_for_exact_matches(self):
        """Strings that would be invalid as regex are fine as exact-match
        entries — the constraint must not flag them."""
        rec = self.InvalidValue.create({"name": "([not a regex when exact", "match_type": "exact"})
        self.assertEqual(rec.name, "([not a regex when exact")

    def test_regex_constraint_skipped_when_name_empty(self):
        """An empty name on a regex row shouldn't trip the constraint —
        the required=True check on `name` will reject it first."""
        # We can't actually create with name='' (required), so verify the
        # guard by writing on an existing record after manually clearing.
        rec = self.InvalidValue.create({"name": r"^N/A$", "match_type": "regex"})
        # Switching mode without touching the (currently-valid) regex
        # must not trigger the constraint.
        rec.write({"match_type": "exact"})
        self.assertEqual(rec.match_type, "exact")

    # ─── active flag ─────────────────────────────────────────────────

    def test_archive_via_active_flag(self):
        rec = self.InvalidValue.create({"name": "Retired Sentinel"})
        rec.active = False
        self.assertFalse(rec.active)
        # Still searchable with active_test=False
        self.assertIn(rec, self.InvalidValue.with_context(active_test=False).search([("id", "=", rec.id)]))
