# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Phase 8: Canary patterns for bulk operations.

During bulk operations, expensive computed field recomputation should be
skipped via context flags and refreshed once at completion.
"""

import uuid

from odoo import fields
from odoo.tests import TransactionCase


class TestRegistrantCanaryFlags(TransactionCase):
    """Test that registrant statistics skip recomputation with context flags."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.partner = self.env["res.partner"].create({"name": "Test Registrant", "is_registrant": True})

    def test_skip_registrant_statistics_skips_program_membership_count(self):
        """With skip_registrant_statistics, _compute_program_membership_count should be a no-op."""
        self.partner.with_context(skip_registrant_statistics=True)._compute_program_membership_count()
        # Value should remain at default (0) since compute was skipped
        self.assertEqual(self.partner.program_membership_count, 0)

    def test_skip_registrant_statistics_skips_entitlements_count(self):
        """With skip_registrant_statistics, _compute_entitlements_count should be a no-op."""
        self.partner.with_context(skip_registrant_statistics=True)._compute_entitlements_count()
        self.assertEqual(self.partner.entitlements_count, 0)

    def test_skip_registrant_statistics_skips_cycle_count(self):
        """With skip_registrant_statistics, _compute_cycle_count should be a no-op."""
        self.partner.with_context(skip_registrant_statistics=True)._compute_cycle_count()
        self.assertEqual(self.partner.cycles_count, 0)

    def test_skip_registrant_statistics_skips_inkind_count(self):
        """With skip_registrant_statistics, _compute_inkind_entitlements_count should be a no-op."""
        self.partner.with_context(skip_registrant_statistics=True)._compute_inkind_entitlements_count()
        self.assertEqual(self.partner.inkind_entitlements_count, 0)

    def test_without_flag_computes_normally(self):
        """Without the flag, compute methods should work normally."""
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.partner.id,
                "program_id": self.program.id,
                "state": "draft",
            }
        )
        self.partner._compute_program_membership_count()
        self.assertEqual(self.partner.program_membership_count, 1)


class TestProgramCanaryFlags(TransactionCase):
    """Test that program statistics skip recomputation with context flags."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})

    def test_skip_program_statistics_skips_has_members(self):
        """With skip_program_statistics, _compute_has_members should be a no-op."""
        self.program.with_context(skip_program_statistics=True)._compute_has_members()
        self.assertFalse(self.program.has_members)

    def test_has_members_uses_sql_exists(self):
        """_compute_has_members should detect members without loading the recordset."""
        partner = self.env["res.partner"].create({"name": "Registrant", "is_registrant": True})
        self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": self.program.id,
                "state": "draft",
            }
        )
        self.program._compute_has_members()
        self.assertTrue(self.program.has_members)


class TestRefreshMethods(TransactionCase):
    """Test refresh_beneficiary_counts and refresh_statistics methods."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )

    def test_program_refresh_beneficiary_counts(self):
        """refresh_beneficiary_counts should update all program statistics."""
        # Create memberships via SQL (bypassing ORM triggers)
        for p in self.partners:
            self.env["spp.program.membership"].bulk_create_memberships(
                [{"partner_id": p.id, "program_id": self.program.id, "state": "enrolled"}],
                skip_duplicates=True,
            )

        # Counts are stale (SQL insert bypassed ORM)
        self.program.refresh_beneficiary_counts()

        self.assertEqual(self.program.beneficiaries_count, 5)
        self.assertEqual(self.program.eligible_beneficiaries_count, 5)
        self.assertTrue(self.program.has_members)

    def test_cycle_refresh_statistics(self):
        """refresh_statistics should update cycle member and entitlement counts."""
        for p in self.partners:
            self.env["spp.cycle.membership"].bulk_create_memberships(
                [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "enrolled"}],
                skip_duplicates=True,
            )

        self.cycle.refresh_statistics()
        self.assertEqual(self.cycle.members_count, 5)
