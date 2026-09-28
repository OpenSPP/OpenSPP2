# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Consent-filtered paging neither skips records nor stops early (#554 item M).

When consent filtering hides records, a page is filled from the rows after
them. The next page must start right after the last row actually examined,
and a page cut short by the over-fetch safety limit must still link to the
next page while rows remain.
"""

import json

from odoo.tests.common import BaseCase

from ..utils.pagination import fetch_with_consent
from .common import ApiV2HttpTestCase

NATIONAL_ID = "urn:openspp:vocab:id-type#test_national_id"
HOUSEHOLD_ID = "urn:openspp:vocab:id-type#test_household_id"

# The search services return at most this many rows per query
SERVICE_MAX_ROWS = 100


def _search_over(rows):
    """A search function over a list of rows that caps each query like the services do"""

    def search_function(offset, limit):
        limit = min(limit, SERVICE_MAX_ROWS)
        return rows[offset : offset + limit], len(rows)

    return search_function


class TestFetchWithConsent(BaseCase):
    """utils.pagination.fetch_with_consent"""

    def test_consumed_offset_counts_only_examined_rows(self):
        """The page fills partway through a batch: rows after the last one used are not consumed"""
        rows = list(range(10))
        denied = {1}

        collected, consumed, _total, consent_applied = fetch_with_consent(
            _search_over(rows), lambda row: None if row in denied else row, count=2, offset=0
        )

        self.assertEqual(collected, [0, 2])
        self.assertTrue(consent_applied)
        self.assertEqual(consumed, 3, "The next page must start at row 3, the first row not examined")

    def test_page_larger_than_half_the_service_cap_is_filled(self):
        """count > 50: a batch capped at the service maximum is not mistaken for the end of the data"""
        rows = list(range(500))

        collected, _consumed, _total, _applied = fetch_with_consent(
            _search_over(rows), lambda row: None if row % 2 else row, count=60, offset=0
        )

        self.assertEqual(len(collected), 60)
        self.assertEqual(collected, list(range(0, 120, 2)))

    def test_pages_cover_every_visible_row_exactly_once(self):
        """Following the consumed offset visits every consented row once"""
        rows = list(range(37))
        denied = {1, 2, 5, 11, 12, 13, 20, 36}
        seen = []
        offset = 0

        for _page in range(50):
            collected, offset, total, _applied = fetch_with_consent(
                _search_over(rows), lambda row: None if row in denied else row, count=4, offset=offset
            )
            seen.extend(collected)
            if offset >= total:
                break

        self.assertEqual(seen, [row for row in rows if row not in denied])


class TestConsentPagingAPI(ApiV2HttpTestCase):
    """HTTP: next links of consent-filtered Individual and Group searches"""

    def setUp(self):
        super().setUp()
        self.client = self.create_api_client(
            name="Consent Paging Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "read"},
            ],
        )
        self.token = self.generate_jwt_token(self.client)

    def _consent(self, registrant, resource_type):
        self.create_consent(
            registrant=registrant,
            grantee_partner=self.client.partner_id,
            resource_type=resource_type,
            field_access="all",
        )

    def _page(self, url):
        response = self.url_open(url, headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 200, response.content)
        body = json.loads(response.content)
        return [record["identifier"][0]["value"] for record in body["data"]], body["links"].get("next")

    def test_individual_next_page_does_not_skip(self):
        """B has no consent: page 1 is A, C and page 2 starts at D"""
        for letter in "ABCDE":
            person = self.create_test_individual(name=f"Paging Person {letter}", identifier_value=f"CP-{letter}")
            if letter != "B":
                self._consent(person, "individual")

        page1, next_url = self._page("/api/v2/spp/Individual?name=Paging+Person&_count=2")
        page2, _next = self._page(next_url)

        self.assertEqual(page1, ["CP-A", "CP-C"])
        self.assertEqual(page2, ["CP-D", "CP-E"])

    def test_group_next_page_does_not_skip(self):
        """Group B has no consent: page 1 is A, C and page 2 starts at D"""
        for letter in "ABCDE":
            group = self.create_test_group(name=f"Paging Group {letter}", identifier_value=f"CPG-{letter}")
            if letter != "B":
                self._consent(group, "group")

        page1, next_url = self._page("/api/v2/spp/Group?name=Paging+Group&_count=2")
        page2, _next = self._page(next_url)

        self.assertEqual(page1, ["CPG-A", "CPG-C"])
        self.assertEqual(page2, ["CPG-D", "CPG-E"])

    def test_short_page_keeps_next_while_rows_remain(self):
        """The safety limit cuts the page short: the next link is still given, and leads to E"""
        for letter in "ABCDE":
            person = self.create_test_individual(name=f"Sparse Person {letter}", identifier_value=f"SP-{letter}")
            if letter == "E":
                self._consent(person, "individual")

        page1, next_url = self._page("/api/v2/spp/Individual?name=Sparse+Person&_count=1")
        self.assertEqual(page1, [], "A, B and C are hidden and the 3x safety limit stops the scan")
        self.assertIsNotNone(next_url, "Rows remain, so the client must be told to continue")

        seen = []
        for _page in range(5):
            values, next_url = self._page(next_url)
            seen.extend(values)
            if not next_url:
                break
        self.assertEqual(seen, ["SP-E"])
