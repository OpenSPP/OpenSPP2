# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Phase 7: Bulk membership creation with INSERT ON CONFLICT.

These tests verify that bulk_create_memberships() with skip_duplicates=True
uses raw SQL INSERT ... ON CONFLICT DO NOTHING to silently skip duplicates
instead of raising IntegrityError or doing per-record search() checks.
"""

import uuid

from odoo import fields
from odoo.tests import TransactionCase


class TestBulkProgramMembership(TransactionCase):
    """Test bulk_create_memberships on spp.program.membership."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(10)]
        )

    def test_bulk_create_inserts_all(self):
        """bulk_create_memberships with skip_duplicates inserts all new records."""
        vals_list = [{"partner_id": p.id, "program_id": self.program.id, "state": "draft"} for p in self.partners]
        count = self.env["spp.program.membership"].bulk_create_memberships(vals_list, skip_duplicates=True)
        self.assertEqual(count, 10)
        self.assertEqual(
            self.env["spp.program.membership"].search_count([("program_id", "=", self.program.id)]),
            10,
        )

    def test_bulk_create_skips_duplicates(self):
        """Duplicate (partner_id, program_id) pairs must be silently skipped."""
        # Create first batch
        vals_list = [{"partner_id": p.id, "program_id": self.program.id, "state": "draft"} for p in self.partners[:5]]
        self.env["spp.program.membership"].bulk_create_memberships(vals_list, skip_duplicates=True)

        # Create second batch with overlap
        vals_list_overlap = [
            {"partner_id": p.id, "program_id": self.program.id, "state": "draft"}
            for p in self.partners  # includes first 5 again
        ]
        count = self.env["spp.program.membership"].bulk_create_memberships(vals_list_overlap, skip_duplicates=True)
        # Only 5 new records should be inserted
        self.assertEqual(count, 5)
        self.assertEqual(
            self.env["spp.program.membership"].search_count([("program_id", "=", self.program.id)]),
            10,
        )

    def test_bulk_create_all_duplicates_returns_zero(self):
        """If all records already exist, return 0."""
        vals_list = [{"partner_id": p.id, "program_id": self.program.id, "state": "draft"} for p in self.partners[:3]]
        self.env["spp.program.membership"].bulk_create_memberships(vals_list, skip_duplicates=True)
        count = self.env["spp.program.membership"].bulk_create_memberships(vals_list, skip_duplicates=True)
        self.assertEqual(count, 0)

    def test_bulk_create_empty_list(self):
        """Empty vals_list should return 0."""
        count = self.env["spp.program.membership"].bulk_create_memberships([], skip_duplicates=True)
        self.assertEqual(count, 0)

    def test_bulk_create_without_skip_duplicates_uses_orm(self):
        """Without skip_duplicates, bulk_create_memberships should use the ORM path."""
        vals_list = [{"partner_id": p.id, "program_id": self.program.id, "state": "draft"} for p in self.partners[:3]]
        result = self.env["spp.program.membership"].bulk_create_memberships(vals_list)
        # ORM path returns a recordset
        self.assertEqual(len(result), 3)

    def test_bulk_create_respects_chunk_size(self):
        """With skip_duplicates and chunk_size, should process in chunks."""
        vals_list = [{"partner_id": p.id, "program_id": self.program.id, "state": "draft"} for p in self.partners]
        count = self.env["spp.program.membership"].bulk_create_memberships(
            vals_list, skip_duplicates=True, chunk_size=3
        )
        self.assertEqual(count, 10)


class TestBulkCycleMembership(TransactionCase):
    """Test bulk_create_memberships on spp.cycle.membership."""

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
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(10)]
        )

    def test_bulk_create_inserts_all(self):
        """bulk_create_memberships with skip_duplicates inserts all new records."""
        vals_list = [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "draft"} for p in self.partners]
        count = self.env["spp.cycle.membership"].bulk_create_memberships(vals_list, skip_duplicates=True)
        self.assertEqual(count, 10)

    def test_bulk_create_skips_duplicates(self):
        """Duplicate (partner_id, cycle_id) pairs must be silently skipped."""
        vals_first = [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "draft"} for p in self.partners[:5]]
        self.env["spp.cycle.membership"].bulk_create_memberships(vals_first, skip_duplicates=True)

        vals_overlap = [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "draft"} for p in self.partners]
        count = self.env["spp.cycle.membership"].bulk_create_memberships(vals_overlap, skip_duplicates=True)
        self.assertEqual(count, 5)

    def test_bulk_create_empty_list(self):
        """Empty vals_list should return 0."""
        count = self.env["spp.cycle.membership"].bulk_create_memberships([], skip_duplicates=True)
        self.assertEqual(count, 0)

    def test_bulk_create_without_skip_duplicates_uses_orm(self):
        """Without skip_duplicates, bulk_create_memberships should use the ORM path."""
        vals_list = [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "draft"} for p in self.partners[:3]]
        result = self.env["spp.cycle.membership"].bulk_create_memberships(vals_list)
        self.assertEqual(len(result), 3)


class TestCallerIntegration(TransactionCase):
    """Test that _import_registrants and _add_beneficiaries use bulk_create_memberships."""

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

    def test_add_beneficiaries_skips_duplicates(self):
        """_add_beneficiaries should not raise on duplicate partner IDs."""
        cycle_manager = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": self.program.id,
            }
        )

        partner_ids = self.partners.ids
        # Add beneficiaries twice — second call should not raise
        cycle_manager._add_beneficiaries(self.cycle, partner_ids, "draft")
        cycle_manager._add_beneficiaries(self.cycle, partner_ids, "draft")

        # Should still only have 5 memberships
        count = self.env["spp.cycle.membership"].search_count([("cycle_id", "=", self.cycle.id)])
        self.assertEqual(count, 5)

    def test_import_registrants_skips_duplicates(self):
        """_import_registrants should not raise on duplicate registrants."""
        elig_manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Elig Manager",
                "program_id": self.program.id,
            }
        )

        # Import registrants twice
        elig_manager._import_registrants(self.partners, "draft")
        elig_manager._import_registrants(self.partners, "draft")

        # Should still only have 5 memberships
        count = self.env["spp.program.membership"].search_count([("program_id", "=", self.program.id)])
        self.assertEqual(count, 5)
