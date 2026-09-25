# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Search filters fail closed (#554 item H).

A filter the API cannot apply must never widen the result: malformed input
is a 400, and a well-formed value naming nothing (unknown group, role,
gender, member) matches nothing. Multi-condition filters on one2many
relations must hold on the *same* related row.
"""

import json
from datetime import timedelta

from odoo import fields

from ..services import search_service
from ..services.search_service import SearchService
from .common import ApiV2HttpTestCase, ApiV2TestCase

NATIONAL_ID = "urn:openspp:vocab:id-type#test_national_id"
HOUSEHOLD_ID = "urn:openspp:vocab:id-type#test_household_id"


class TestSearchFiltersFailClosed(ApiV2TestCase):
    """SearchService: malformed filters raise, unresolvable filters match nothing"""

    def setUp(self):
        super().setUp()
        self.service = SearchService(self.env)
        self.ind1 = self.create_test_individual(identifier_value="FC-IND-001", gender_id=self.gender_female.id)
        self.ind2 = self.create_test_individual(identifier_value="FC-IND-002", gender_id=self.gender_male.id)
        self.group_g = self.create_test_group(name="Group G", identifier_value="FC-HH-G")
        self.group_h = self.create_test_group(name="Group H", identifier_value="FC-HH-H")

    def _add_member(self, group, individual, ended=False, role=None):
        vals = {"group": group.id, "individual": individual.id}
        if ended:
            vals["start_date"] = fields.Datetime.now() - timedelta(days=30)
            vals["ended_date"] = fields.Datetime.now() - timedelta(days=1)
        if role:
            vals["membership_type_ids"] = [(4, role.id)]
        return self.env["spp.group.membership"].create(vals)

    def _assert_invalid(self, params, search=None):
        search = search or self.service.search_individuals
        with self.assertRaises(search_service.InvalidSearchParam):
            search(params)

    # --- malformed input raises -------------------------------------------

    def test_malformed_identifier_raises(self):
        self._assert_invalid({"identifier": "NO-SEPARATOR"})
        self._assert_invalid({"identifier": "NO-SEPARATOR"}, self.service.search_groups)

    def test_malformed_birthdate_raises(self):
        self._assert_invalid({"birthdate": "not-a-date"})
        self._assert_invalid({"birthdate": "ge"})

    def test_malformed_last_updated_raises(self):
        self._assert_invalid({"_lastUpdated": "yesterday"})

    def test_malformed_gender_raises(self):
        self._assert_invalid({"gender": "female"})

    def test_malformed_group_raises(self):
        self._assert_invalid({"group": "NO-SEPARATOR"})

    def test_malformed_member_raises(self):
        self._assert_invalid({"member": f"{NATIONAL_ID}|FC-IND-001"}, self.service.search_groups)
        self._assert_invalid({"member": "Individual/NO-SEPARATOR"}, self.service.search_groups)

    # --- unresolvable input matches nothing -------------------------------

    def test_unknown_group_matches_nothing(self):
        """The reported bug: an unknown group returned every individual"""
        records, total = self.service.search_individuals({"group": f"{HOUSEHOLD_ID}|DOES-NOT-EXIST"})

        self.assertEqual(total, 0)
        self.assertFalse(records)

    def test_group_identifier_of_an_individual_matches_nothing(self):
        """An identifier that resolves to an individual, not a group, is not a group"""
        records, total = self.service.search_individuals({"group": f"{NATIONAL_ID}|FC-IND-001"})

        self.assertEqual(total, 0)
        self.assertFalse(records)

    def test_unknown_gender_matches_nothing(self):
        records, total = self.service.search_individuals({"gender": "urn:iso:std:iso:5218|no-such-code"})

        self.assertEqual(total, 0)
        self.assertFalse(records)

    def test_unknown_membership_role_matches_nothing(self):
        self._add_member(self.group_g, self.ind1, role=self.relationship_head)

        records, total = self.service.search_individuals({"membership-role": "no-such-role"})

        self.assertEqual(total, 0)
        self.assertFalse(records)

    def test_unknown_member_matches_nothing(self):
        """An unknown member returned every group"""
        records, total = self.service.search_groups({"member": f"Individual/{NATIONAL_ID}|DOES-NOT-EXIST"})

        self.assertEqual(total, 0)
        self.assertFalse(records)

    # --- multi-condition filters hold on the same row ---------------------

    def test_group_filter_ignores_ended_membership_when_active_elsewhere(self):
        """Removed from G but active in H: not a member of G"""
        self._add_member(self.group_g, self.ind1, ended=True)
        self._add_member(self.group_h, self.ind1)
        self._add_member(self.group_g, self.ind2)  # positive control: a current member of G

        records, _total = self.service.search_individuals({"group": f"{HOUSEHOLD_ID}|FC-HH-G"})

        self.assertNotIn(self.ind1, records)
        self.assertIn(self.ind2, records)

    def test_membership_role_must_be_on_an_active_membership(self):
        """Head of G (ended) and plain member of H (active): not a current head"""
        self._add_member(self.group_g, self.ind1, ended=True, role=self.relationship_head)
        self._add_member(self.group_h, self.ind1)
        self._add_member(self.group_h, self.ind2, role=self.relationship_head)  # positive control: a current head

        records, _total = self.service.search_individuals({"membership-role": "head"})

        self.assertNotIn(self.ind1, records)
        self.assertIn(self.ind2, records)

    def test_identifier_system_and_value_must_be_on_the_same_id(self):
        """System from one ID and value from another is not a match"""
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.ind1.id,
                "id_type_id": self.id_type_household.id,
                "value": "FC-OTHER-VALUE",
                "status": "valid",
            }
        )

        records, total = self.service.search_individuals({"identifier": f"{NATIONAL_ID}|FC-OTHER-VALUE"})

        self.assertEqual(total, 0)
        self.assertFalse(records)

    def test_member_filter_ignores_ended_memberships(self):
        """A group the individual has left is not listed for ?member="""
        self._add_member(self.group_g, self.ind2, ended=True)
        self._add_member(self.group_h, self.ind2)

        records, _total = self.service.search_groups({"member": f"Individual/{NATIONAL_ID}|FC-IND-002"})

        self.assertNotIn(self.group_g, records)
        self.assertIn(self.group_h, records)


class TestSearchFiltersFailClosedAPI(ApiV2HttpTestCase):
    """HTTP: malformed filters are 400, unresolvable filters return nothing"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(identifier_value="FC-API-IND-001")
        self.group = self.create_test_group(name="FC API Group", identifier_value="FC-API-HH-001")
        self.client = self.create_api_client(
            name="Fail Closed Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "read"},
            ],
        )
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )
        self.create_consent(
            registrant=self.group,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )
        self.token = self.generate_jwt_token(self.client)

    def _get(self, url):
        return self.url_open(
            url,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
        )

    def _assert_empty(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        data = json.loads(response.content)
        self.assertEqual(data["meta"]["total"], 0)
        self.assertFalse(data.get("data"))

    def test_individual_unknown_group_returns_nothing(self):
        self._assert_empty(
            self._get("/api/v2/spp/Individual?group=urn:openspp:vocab:id-type%23test_household_id%7CDOES-NOT-EXIST")
        )

    def test_individual_malformed_group_is_400(self):
        response = self._get("/api/v2/spp/Individual?group=NO-SEPARATOR")

        self.assertEqual(response.status_code, 400, response.text)

    def test_individual_malformed_identifier_is_400(self):
        response = self._get("/api/v2/spp/Individual?identifier=NO-SEPARATOR")

        self.assertEqual(response.status_code, 400, response.text)

    def test_individual_malformed_birthdate_is_400(self):
        response = self._get("/api/v2/spp/Individual?birthdate=not-a-date")

        self.assertEqual(response.status_code, 400, response.text)

    def test_individual_malformed_gender_is_400(self):
        response = self._get("/api/v2/spp/Individual?gender=female")

        self.assertEqual(response.status_code, 400, response.text)

    def test_individual_malformed_last_updated_is_400(self):
        response = self._get("/api/v2/spp/Individual?_lastUpdated=yesterday")

        self.assertEqual(response.status_code, 400, response.text)

    def test_group_malformed_member_is_400(self):
        response = self._get("/api/v2/spp/Group?member=NO-SEPARATOR")

        self.assertEqual(response.status_code, 400, response.text)

    def test_group_unknown_member_returns_nothing(self):
        self._assert_empty(
            self._get(
                "/api/v2/spp/Group?member=Individual/urn:openspp:vocab:id-type%23test_national_id%7CDOES-NOT-EXIST"
            )
        )

    def test_group_malformed_identifier_is_400(self):
        response = self._get("/api/v2/spp/Group?identifier=NO-SEPARATOR")

        self.assertEqual(response.status_code, 400, response.text)
