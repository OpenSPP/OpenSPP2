# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for consent-aware pagination utility"""

import unittest

from ..utils.pagination import fetch_with_consent


class TestFetchWithConsent(unittest.TestCase):
    """Test the fetch_with_consent pagination helper"""

    def _make_search_function(self, all_records):
        """Create a search function that simulates DB queries."""

        def search_function(offset, limit):
            total = len(all_records)
            page = all_records[offset : offset + limit]
            return page, total

        return search_function

    def test_no_consent_filtering(self):
        """All records pass consent check - standard pagination"""
        records = list(range(10))

        collected, db_offset, raw_total, consent_applied = fetch_with_consent(
            self._make_search_function(records),
            lambda r: {"id": r},  # All records pass
            count=5,
            offset=0,
        )

        self.assertEqual(len(collected), 5)
        self.assertEqual(raw_total, 10)
        self.assertFalse(consent_applied)

    def test_consent_denials_trigger_overfetch(self):
        """Records denied by consent are skipped, more records are fetched"""
        records = list(range(20))

        # Deny even-numbered records
        def consent_filter(record):
            if record % 2 == 0:
                return None  # Denied
            return {"id": record}

        collected, db_offset, raw_total, consent_applied = fetch_with_consent(
            self._make_search_function(records),
            consent_filter,
            count=5,
            offset=0,
        )

        self.assertEqual(len(collected), 5)
        self.assertTrue(consent_applied)
        # All collected should be odd numbers
        for item in collected:
            self.assertEqual(item["id"] % 2, 1)

    def test_consent_applied_flag_set(self):
        """consent_was_applied is True when any record is denied"""
        records = list(range(5))

        # Deny just one record
        def consent_filter(record):
            if record == 2:
                return None
            return {"id": record}

        _, _, _, consent_applied = fetch_with_consent(
            self._make_search_function(records),
            consent_filter,
            count=5,
            offset=0,
        )

        self.assertTrue(consent_applied)

    def test_fewer_records_than_requested(self):
        """Returns fewer records when DB is exhausted"""
        records = list(range(3))

        collected, _, _, _ = fetch_with_consent(
            self._make_search_function(records),
            lambda r: {"id": r},
            count=10,
            offset=0,
        )

        self.assertEqual(len(collected), 3)

    def test_empty_result(self):
        """Returns empty list when no records exist"""
        collected, _, raw_total, consent_applied = fetch_with_consent(
            self._make_search_function([]),
            lambda r: {"id": r},
            count=10,
            offset=0,
        )

        self.assertEqual(len(collected), 0)
        self.assertEqual(raw_total, 0)
        self.assertFalse(consent_applied)

    def test_offset_is_respected(self):
        """Starting offset is applied correctly"""
        records = list(range(10))

        collected, _, _, _ = fetch_with_consent(
            self._make_search_function(records),
            lambda r: {"id": r},
            count=3,
            offset=5,
        )

        self.assertEqual(len(collected), 3)
        self.assertEqual(collected[0]["id"], 5)
        self.assertEqual(collected[2]["id"], 7)

    def test_safety_limit_prevents_runaway(self):
        """Safety limit prevents infinite fetching when all records are denied"""
        records = list(range(100))

        collected, _, _, consent_applied = fetch_with_consent(
            self._make_search_function(records),
            lambda r: None,  # Deny all
            count=10,
            offset=0,
        )

        self.assertEqual(len(collected), 0)
        self.assertTrue(consent_applied)
