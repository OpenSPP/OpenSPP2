# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Consent-filtered paging neither skips records nor stops early (#554 item M).

When consent filtering hides records, a page is filled from the rows after
them. The next page must start right after the last row actually examined,
and a page cut short by the over-fetch safety limit must still link to the
next page while rows remain.
"""

import json

from odoo.tests.common import BaseCase

from ..utils import pagination
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


class TestPageTotalAndNext(BaseCase):
    """utils.pagination.page_total_and_next"""

    def test_consent_client_total_is_the_page_size(self):
        """Hidden rows are never counted, even when none were met in this window"""
        total, next_offset = pagination.page_total_and_next(
            returned=1, count=1, offset=0, db_offset_consumed=1, raw_total=6, consent_filtered=True
        )
        self.assertEqual(total, 1)
        self.assertEqual(next_offset, 1)

    def test_consent_client_past_the_end(self):
        """Past the end: nothing returned, total 0, no next, whatever the raw count"""
        total, next_offset = pagination.page_total_and_next(
            returned=0, count=1, offset=1, db_offset_consumed=1, raw_total=1, consent_filtered=True
        )
        self.assertEqual(total, 0)
        self.assertIsNone(next_offset)

    def test_consent_client_next_until_the_scan_ends(self):
        """A short page links on while rows remain, and not once the scan reached the end"""
        self.assertEqual(
            pagination.page_total_and_next(
                returned=0, count=1, offset=0, db_offset_consumed=3, raw_total=5, consent_filtered=True
            )[1],
            3,
        )
        self.assertIsNone(
            pagination.page_total_and_next(
                returned=1, count=1, offset=3, db_offset_consumed=5, raw_total=5, consent_filtered=True
            )[1]
        )

    def test_legal_basis_client_unchanged(self):
        """Without consent filtering: the real total, next while pages are full"""
        self.assertEqual(
            pagination.page_total_and_next(
                returned=2, count=2, offset=0, db_offset_consumed=2, raw_total=7, consent_filtered=False
            ),
            (7, 2),
        )
        self.assertEqual(
            pagination.page_total_and_next(
                returned=1, count=2, offset=6, db_offset_consumed=7, raw_total=7, consent_filtered=False
            ),
            (7, None),
        )


class TestConsentTotalNotLeakedAPI(ApiV2HttpTestCase):
    """HTTP: the total never counts records the client has no consent for"""

    def setUp(self):
        super().setUp()
        scopes = [
            {"resource": "individual", "action": "read"},
            {"resource": "group", "action": "read"},
        ]
        self.consent_client = self.create_api_client(name="Total Consent Client", scopes=scopes)
        self.consent_token = self.generate_jwt_token(self.consent_client)
        self.legal_client = self.create_api_client(
            name="Total Legal Client", scopes=scopes, require_consent=False, legal_basis="public_task"
        )
        self.legal_token = self.generate_jwt_token(self.legal_client)

    def _body(self, url, token):
        response = self.url_open(url, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def _assert_nothing(self, body):
        self.assertEqual(body["data"], [])
        self.assertEqual(body["meta"]["total"], 0)
        self.assertIsNone(body["links"].get("next"))

    def test_individual_hidden_match_past_the_end_is_not_counted(self):
        """identifier= of a registrant without consent, _offset=1: same answer as an unknown identifier"""
        self.create_test_individual(name="Hidden Total", identifier_value="HT-IND-1")

        hidden = self._body(
            f"/api/v2/spp/Individual?identifier={NATIONAL_ID.replace('#', '%23')}|HT-IND-1&_count=1&_offset=1",
            self.consent_token,
        )
        unknown = self._body(
            f"/api/v2/spp/Individual?identifier={NATIONAL_ID.replace('#', '%23')}|HT-NOBODY&_count=1&_offset=1",
            self.consent_token,
        )

        self._assert_nothing(hidden)
        self._assert_nothing(unknown)

    def test_group_hidden_match_past_the_end_is_not_counted(self):
        """identifier= of a group without consent, _offset=1: same answer as an unknown identifier"""
        self.create_test_group(name="Hidden Total Group", identifier_value="HT-GRP-1")

        hidden = self._body(
            f"/api/v2/spp/Group?identifier={HOUSEHOLD_ID.replace('#', '%23')}|HT-GRP-1&_count=1&_offset=1",
            self.consent_token,
        )

        self._assert_nothing(hidden)

    def test_page_filled_before_hidden_rows_does_not_count_them(self):
        """A is consented and fills the page; the hidden B, C, D after it are not in the total"""
        for letter in "ABCD":
            person = self.create_test_individual(name=f"Filled First {letter}", identifier_value=f"FF-{letter}")
            if letter == "A":
                self.create_consent(
                    registrant=person,
                    grantee_partner=self.consent_client.partner_id,
                    resource_type="individual",
                    field_access="all",
                )

        body = self._body("/api/v2/spp/Individual?name=Filled+First&_count=1", self.consent_token)

        self.assertEqual([r["identifier"][0]["value"] for r in body["data"]], ["FF-A"])
        self.assertEqual(body["meta"]["total"], 1)

    def test_legal_basis_client_gets_the_real_total(self):
        """A client that isn't consent-filtered still gets the exact total"""
        for letter in "ABC":
            self.create_test_individual(name=f"Legal Total {letter}", identifier_value=f"LT-{letter}")

        body = self._body("/api/v2/spp/Individual?name=Legal+Total&_count=1", self.legal_token)

        self.assertEqual(body["meta"]["total"], 3)
        self.assertIsNotNone(body["links"].get("next"))


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
        page2, last_next = self._page(next_url)

        self.assertEqual(page1, ["CP-A", "CP-C"])
        self.assertEqual(page2, ["CP-D", "CP-E"])
        self.assertIsNone(last_next, "E is the last row: no link to an empty page")

    def test_group_next_page_does_not_skip(self):
        """Group B has no consent: page 1 is A, C and page 2 starts at D"""
        for letter in "ABCDE":
            group = self.create_test_group(name=f"Paging Group {letter}", identifier_value=f"CPG-{letter}")
            if letter != "B":
                self._consent(group, "group")

        page1, next_url = self._page("/api/v2/spp/Group?name=Paging+Group&_count=2")
        page2, last_next = self._page(next_url)

        self.assertEqual(page1, ["CPG-A", "CPG-C"])
        self.assertEqual(page2, ["CPG-D", "CPG-E"])
        self.assertIsNone(last_next, "E is the last row: no link to an empty page")

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
        pages = 1
        for _page in range(5):
            values, next_url = self._page(next_url)
            pages += 1
            seen.extend(values)
            if not next_url:
                break
        self.assertEqual(seen, ["SP-E"])
        self.assertIsNone(next_url)
        self.assertEqual(pages, 2, "Page 2 scans D and E and ends the scan: no third, empty page")
