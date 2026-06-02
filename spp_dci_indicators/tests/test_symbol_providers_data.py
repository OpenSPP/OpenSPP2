# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Populated-cache tests for DCI symbol providers.

test_symbol_providers.py covers initialisation, lazy-loading, default
values and the no-data-source paths. This module exercises the
populated-cache branches: when a real DR/CRVS/IBR cache record exists
for the partner, the provider must surface its data through the CEL
symbol properties and methods.
"""

import json
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.spp_dci_indicators.symbols.dci_symbols import (
    CRVSSymbolProvider,
    DRSymbolProvider,
    IBRSymbolProvider,
    SRSymbolProvider,
)


@tagged("post_install", "-at_install")
class TestSymbolProvidersPopulated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Populated Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

    # --- DR populated ---------------------------------------------------------

    def test_dr_surfaces_synced_disability_record(self):
        """A synced disability.status record must surface through the DR
        symbol. Regression: the provider previously filtered
        state in ['active','draft'] but the model only has
        synced/stale/error, so disability data never loaded."""
        self.env["spp.dci.disability.status"].create(
            {
                "partner_id": self.partner.id,
                "has_disability": True,
                "disability_types": json.dumps(["Vision", "Mobility"]),
                "functional_scores": json.dumps({"Vision": 3, "Mobility": 4}),
                "assessment_date": date(2024, 1, 15),
                "state": "synced",
            }
        )

        provider = DRSymbolProvider(self.env, self.partner)
        self.assertTrue(provider.has_disability)
        self.assertEqual(sorted(provider.types), ["Mobility", "Vision"])
        self.assertTrue(provider.assessed)
        self.assertEqual(provider.severity("Vision"), 3)
        self.assertEqual(provider.severity("Mobility"), 4)
        # Unknown type defaults to 1 (no difficulty)
        self.assertEqual(provider.severity("Hearing"), 1)
        self.assertTrue(provider.has_type("Vision"))
        self.assertFalse(provider.has_type("Hearing"))

    def test_dr_stale_record_still_surfaces(self):
        """Stale cached data is still the last-known value and should
        surface (only 'error' records are excluded)."""
        self.env["spp.dci.disability.status"].create(
            {
                "partner_id": self.partner.id,
                "has_disability": True,
                "disability_types": json.dumps(["Hearing"]),
                "state": "stale",
            }
        )
        provider = DRSymbolProvider(self.env, self.partner)
        self.assertTrue(provider.has_disability)
        self.assertEqual(provider.types, ["Hearing"])

    # --- CRVS populated -------------------------------------------------------

    def _crvs_event(self, event_type, state="processed"):
        return self.env["spp.dci.crvs.event"].create(
            {
                "event_type": event_type,
                "person_id": self.partner.id,
                "event_date": date(2024, 1, 1),
                "state": state,
            }
        )

    def test_crvs_birth_event_marks_birth_verified(self):
        self._crvs_event("birth")
        provider = CRVSSymbolProvider(self.env, self.partner)
        self.assertTrue(provider.birth_verified)
        self.assertTrue(provider.is_alive)
        self.assertTrue(provider.has_event("birth"))
        self.assertFalse(provider.has_event("death"))

    def test_crvs_death_event_marks_not_alive(self):
        self._crvs_event("death")
        provider = CRVSSymbolProvider(self.env, self.partner)
        self.assertFalse(provider.is_alive)
        self.assertTrue(provider.has_event("death"))

    def test_crvs_marriage_without_divorce_is_married(self):
        self._crvs_event("marriage")
        provider = CRVSSymbolProvider(self.env, self.partner)
        self.assertTrue(provider.is_married)

    def test_crvs_divorce_overrides_marriage(self):
        self._crvs_event("marriage")
        self._crvs_event("divorce")
        provider = CRVSSymbolProvider(self.env, self.partner)
        self.assertFalse(provider.is_married)

    def test_crvs_unprocessed_event_ignored(self):
        """Only 'processed' events count; a received event must not surface."""
        self._crvs_event("birth", state="received")
        provider = CRVSSymbolProvider(self.env, self.partner)
        self.assertFalse(provider.birth_verified)

    # --- IBR populated --------------------------------------------------------

    def _dup_check(self, result, matched_programs=None, state="completed"):
        vals = {
            "partner_id": self.partner.id,
            "identifier_type": "UIN",
            "identifier_value": "DUP-001",
            "result": result,
            "state": state,
        }
        if matched_programs is not None:
            vals["matched_programs"] = matched_programs
        return self.env["spp.dci.duplication.check"].create(vals)

    def test_ibr_confirmed_match_has_duplicate(self):
        self._dup_check(
            "confirmed_match",
            matched_programs="Cash Transfer\nFood Assistance",
        )
        provider = IBRSymbolProvider(self.env, self.partner)
        self.assertTrue(provider.has_duplicate)
        self.assertIsNotNone(provider.last_check_date)
        self.assertEqual(
            sorted(provider.matched_programs),
            ["Cash Transfer", "Food Assistance"],
        )
        # Case-insensitive partial match
        self.assertTrue(provider.is_enrolled("cash transfer"))
        self.assertTrue(provider.is_enrolled("food"))
        self.assertFalse(provider.is_enrolled("Pension"))

    def test_ibr_no_match_has_no_duplicate(self):
        self._dup_check("no_match")
        provider = IBRSymbolProvider(self.env, self.partner)
        self.assertFalse(provider.has_duplicate)
        self.assertEqual(provider.matched_programs, [])

    def test_ibr_possible_match_counts_as_duplicate(self):
        self._dup_check("possible_match")
        provider = IBRSymbolProvider(self.env, self.partner)
        self.assertTrue(provider.has_duplicate)

    def test_ibr_ignores_incomplete_checks(self):
        """A ready/checking record must not surface as a completed result."""
        self._dup_check("confirmed_match", state="ready")
        provider = IBRSymbolProvider(self.env, self.partner)
        self.assertFalse(provider.has_duplicate)

    # --- SR not-installed branch ---------------------------------------------

    def test_sr_defaults_when_model_not_installed(self):
        """spp_dci_indicators does not depend on spp_dci_client_sr, so the
        sr.record model is absent; the provider returns safe defaults."""
        provider = SRSymbolProvider(self.env, self.partner)
        self.assertFalse(provider.is_registered)
        self.assertEqual(provider.program_count, 0)
        self.assertEqual(provider.enrolled_programs, [])
        self.assertIsNone(provider.household_id)
        self.assertEqual(provider.household_size, 0)
        self.assertFalse(provider.is_head_of_household)
        self.assertFalse(provider.is_enrolled("anything"))
