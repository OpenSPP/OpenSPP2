# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Phase 6: ID-based keyset pagination.

These tests verify that async job dispatch uses ID-range batching (via NTILE)
instead of OFFSET-based pagination. OFFSET N causes PostgreSQL to scan N rows
then discard them, making later batches O(N) slower.
"""

import uuid
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase


class TestComputeIdRanges(TransactionCase):
    """Test the compute_id_ranges helper function."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})

    def _create_memberships(self, count):
        """Create program memberships and return their IDs sorted."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(count)]
        )
        memberships = self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )
        return sorted(memberships.ids)

    def test_compute_id_ranges_returns_covering_ranges(self):
        """All records must be covered by exactly one range."""
        from ..models.managers.pagination_utils import (
            compute_id_ranges,
        )

        ids = self._create_memberships(10)
        ranges = compute_id_ranges(
            self.env.cr,
            "spp_program_membership",
            "program_id = %s AND state IN %s",
            (self.program.id, tuple(["draft"])),
            batch_size=3,
        )
        # Every original ID should fall within exactly one range
        covered = set()
        for min_id, max_id in ranges:
            covered.update(i for i in ids if min_id <= i <= max_id)
        self.assertEqual(covered, set(ids), "All IDs must be covered by ranges")

    def test_compute_id_ranges_batch_count(self):
        """Number of ranges should be ceil(total / batch_size)."""
        from ..models.managers.pagination_utils import (
            compute_id_ranges,
        )

        self._create_memberships(10)
        ranges = compute_id_ranges(
            self.env.cr,
            "spp_program_membership",
            "program_id = %s AND state IN %s",
            (self.program.id, tuple(["draft"])),
            batch_size=3,
        )
        # 10 records / batch_size 3 = ceil(10/3) = 4 ranges
        self.assertEqual(len(ranges), 4)

    def test_compute_id_ranges_single_batch(self):
        """When total <= batch_size, return a single range."""
        from ..models.managers.pagination_utils import (
            compute_id_ranges,
        )

        ids = self._create_memberships(3)
        ranges = compute_id_ranges(
            self.env.cr,
            "spp_program_membership",
            "program_id = %s AND state IN %s",
            (self.program.id, tuple(["draft"])),
            batch_size=10,
        )
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0], (min(ids), max(ids)))

    def test_compute_id_ranges_empty_table(self):
        """Empty result set should return empty list."""
        from ..models.managers.pagination_utils import (
            compute_id_ranges,
        )

        ranges = compute_id_ranges(
            self.env.cr,
            "spp_program_membership",
            "program_id = %s AND state IN %s",
            (self.program.id, tuple(["draft"])),
            batch_size=10,
        )
        self.assertEqual(ranges, [])

    def test_compute_id_ranges_no_overlap(self):
        """Ranges must not overlap (each ID in exactly one range)."""
        from ..models.managers.pagination_utils import (
            compute_id_ranges,
        )

        self._create_memberships(20)
        ranges = compute_id_ranges(
            self.env.cr,
            "spp_program_membership",
            "program_id = %s AND state IN %s",
            (self.program.id, tuple(["draft"])),
            batch_size=5,
        )
        for i in range(len(ranges) - 1):
            self.assertLess(
                ranges[i][1],
                ranges[i + 1][0],
                f"Range {i} max_id must be less than range {i + 1} min_id",
            )


class TestGetBeneficiariesIdRange(TransactionCase):
    """Test min_id/max_id support in get_beneficiaries()."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(10)]
        )
        self.memberships = self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )
        self.sorted_ids = sorted(self.memberships.ids)

        # Also create a cycle for cycle-level tests
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.cycle_memberships = self.env["spp.cycle.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "cycle_id": self.cycle.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )
        self.cycle_sorted_ids = sorted(self.cycle_memberships.ids)

    def test_program_get_beneficiaries_with_id_range(self):
        """get_beneficiaries with min_id/max_id returns only records in range."""
        mid = self.sorted_ids[4]  # 5th record
        end = self.sorted_ids[7]  # 8th record
        result = self.program.get_beneficiaries(state="draft", min_id=mid, max_id=end)
        result_ids = sorted(result.ids)
        expected = [i for i in self.sorted_ids if mid <= i <= end]
        self.assertEqual(result_ids, expected)

    def test_program_get_beneficiaries_id_range_no_offset(self):
        """min_id/max_id should not use offset internally."""
        # If offset were used, we'd get wrong results
        result = self.program.get_beneficiaries(
            state="draft",
            min_id=self.sorted_ids[0],
            max_id=self.sorted_ids[-1],
        )
        self.assertEqual(len(result), 10)

    def test_cycle_get_beneficiaries_with_id_range(self):
        """Cycle get_beneficiaries with min_id/max_id returns only records in range."""
        mid = self.cycle_sorted_ids[3]
        end = self.cycle_sorted_ids[6]
        result = self.cycle.get_beneficiaries(state="draft", min_id=mid, max_id=end)
        result_ids = sorted(result.ids)
        expected = [i for i in self.cycle_sorted_ids if mid <= i <= end]
        self.assertEqual(result_ids, expected)


class TestAsyncDispatchUsesIdRanges(TransactionCase):
    """Verify async dispatch methods use ID ranges, not OFFSET."""

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

    def test_enroll_eligible_async_uses_compute_id_ranges(self):
        """_enroll_eligible_registrants_async must use compute_id_ranges for dispatch."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(10)]
        )
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )

        manager = self.env["spp.program.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
            }
        )

        # Verify compute_id_ranges is called by the async method
        with patch(
            "odoo.addons.spp_programs.models.managers.program_manager.compute_id_ranges",
            wraps=None,
            return_value=[(1, 5), (6, 10)],
        ) as mock_ranges:
            # Also patch delayable to avoid actual job creation
            with patch.object(type(manager), "delayable", return_value=manager):
                try:
                    manager._enroll_eligible_registrants_async(["draft"], 10)
                except Exception:  # pylint: disable=except-pass
                    pass

            mock_ranges.assert_called_once()
            call_args = mock_ranges.call_args
            # Verify it was called with the right table
            self.assertEqual(call_args[0][1], "spp_program_membership")

    def test_enroll_eligible_registrants_accepts_id_range(self):
        """_enroll_eligible_registrants must accept min_id/max_id params."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        memberships = self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )
        sorted_ids = sorted(memberships.ids)

        manager = self.env["spp.program.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
            }
        )

        # Create a simple eligibility manager that passes everyone through
        elig_manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Elig Manager",
                "program_id": self.program.id,
            }
        )
        self.env["spp.eligibility.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"spp.program.membership.manager.default,{elig_manager.id}",
            }
        )

        # Call with min_id/max_id - should only process records in range
        mid = sorted_ids[1]
        end = sorted_ids[3]
        manager._enroll_eligible_registrants(["draft"], min_id=mid, max_id=end)
        # Should have enrolled records in range
        in_range = [i for i in sorted_ids if mid <= i <= end]
        enrolled = self.env["spp.program.membership"].browse(in_range).filtered(lambda m: m.state == "enrolled")
        self.assertEqual(len(enrolled), len(in_range))

    def test_check_eligibility_accepts_id_range(self):
        """_check_eligibility must accept min_id/max_id params."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        cycle_memberships = self.env["spp.cycle.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "cycle_id": self.cycle.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )
        sorted_ids = sorted(cycle_memberships.ids)

        # Create eligibility manager
        elig_manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Elig Manager",
                "program_id": self.program.id,
            }
        )
        self.env["spp.eligibility.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"spp.program.membership.manager.default,{elig_manager.id}",
            }
        )

        cycle_manager = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": self.program.id,
            }
        )

        # Call with min_id/max_id
        mid = sorted_ids[1]
        end = sorted_ids[3]
        count = cycle_manager._check_eligibility(self.cycle, min_id=mid, max_id=end)
        # Should have processed only records in range
        in_range = [i for i in sorted_ids if mid <= i <= end]
        self.assertEqual(count, len(in_range))

    def test_prepare_entitlements_accepts_id_range(self):
        """_prepare_entitlements must accept min_id/max_id params."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        self.env["spp.cycle.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "cycle_id": self.cycle.id,
                    "state": "enrolled",
                }
                for p in partners
            ]
        )

        cycle_manager = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": self.program.id,
            }
        )

        # Verify the method accepts min_id/max_id without TypeError.
        # UserError is expected since no entitlement manager is configured.
        from odoo.exceptions import UserError

        try:
            cycle_manager._prepare_entitlements(
                self.cycle,
                min_id=0,
                max_id=999999999,
            )
        except TypeError as e:
            if "min_id" in str(e) or "max_id" in str(e):
                self.fail("_prepare_entitlements must accept min_id/max_id params")
        except UserError:
            pass  # Expected: no entitlement manager configured

    def test_check_eligibility_async_uses_compute_id_ranges(self):
        """_check_eligibility_async must use compute_id_ranges for dispatch."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        self.env["spp.cycle.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "cycle_id": self.cycle.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )

        cycle_manager = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": self.program.id,
            }
        )

        with patch(
            "odoo.addons.spp_programs.models.managers.cycle_manager_base.compute_id_ranges",
            return_value=[(1, 3), (4, 6)],
        ) as mock_ranges:
            with patch.object(type(cycle_manager), "delayable", return_value=cycle_manager):
                try:
                    cycle_manager._check_eligibility_async(self.cycle, 5)
                except Exception:  # pylint: disable=except-pass
                    pass

            mock_ranges.assert_called_once()
            self.assertEqual(mock_ranges.call_args[0][1], "spp_cycle_membership")

    def test_prepare_entitlements_async_uses_compute_id_ranges(self):
        """_prepare_entitlements_async must use compute_id_ranges for dispatch."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        self.env["spp.cycle.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "cycle_id": self.cycle.id,
                    "state": "enrolled",
                }
                for p in partners
            ]
        )

        cycle_manager = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": self.program.id,
            }
        )

        with patch(
            "odoo.addons.spp_programs.models.managers.cycle_manager_base.compute_id_ranges",
            return_value=[(1, 3), (4, 6)],
        ) as mock_ranges:
            with patch.object(type(cycle_manager), "delayable", return_value=cycle_manager):
                try:
                    cycle_manager._prepare_entitlements_async(self.cycle, 5)
                except Exception:  # pylint: disable=except-pass
                    pass

            mock_ranges.assert_called_once()
            self.assertEqual(mock_ranges.call_args[0][1], "spp_cycle_membership")

    def test_enroll_eligible_async_handles_string_state(self):
        """_enroll_eligible_registrants_async must handle string state arg."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )

        manager = self.env["spp.program.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
            }
        )

        # Pass a string instead of list — the isinstance branch should convert it
        with patch(
            "odoo.addons.spp_programs.models.managers.program_manager.compute_id_ranges",
            return_value=[(1, 5)],
        ) as mock_ranges:
            with patch.object(type(manager), "delayable", return_value=manager):
                try:
                    manager._enroll_eligible_registrants_async("draft", 5)
                except Exception:  # pylint: disable=except-pass
                    pass

            mock_ranges.assert_called_once()
            # Verify the states param was converted from string to tuple
            call_params = mock_ranges.call_args[0][3]
            self.assertIsInstance(call_params[1], tuple)

    def test_enroll_eligible_async_handles_none_state(self):
        """_enroll_eligible_registrants_async must handle state=None.

        The UI "Enroll Eligible" button calls enroll_eligible_registrants() with no
        argument. When the program has >= MIN_ROW_JOB_QUEUE beneficiaries, the async
        path runs with state=None — it must not crash on `tuple(None)`.
        """
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)]
        )
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": p.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
                for p in partners
            ]
        )

        manager = self.env["spp.program.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
            }
        )

        with patch(
            "odoo.addons.spp_programs.models.managers.program_manager.compute_id_ranges",
            return_value=[(1, 5)],
        ) as mock_ranges:
            with patch.object(type(manager), "delayable", return_value=manager):
                try:
                    manager._enroll_eligible_registrants_async(None, 5)
                except TypeError as e:
                    self.fail(f"async dispatch must accept state=None, got TypeError: {e}")
                except Exception:  # pylint: disable=except-pass
                    pass

            mock_ranges.assert_called_once()
            # When states is None, the where clause must omit "state IN %s" and
            # params must contain only the program id (no states tuple).
            where_clause = mock_ranges.call_args[0][2]
            call_params = mock_ranges.call_args[0][3]
            self.assertNotIn("state IN", where_clause)
            self.assertEqual(call_params, (self.program.id,))
