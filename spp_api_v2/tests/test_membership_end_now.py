# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Ending a membership "now" takes effect immediately (#554 item G).

The stored ``is_ended``/``status`` computes compare ``ended_date`` with
``fields.Datetime.now()``, which has whole-second precision. An end date
written with microseconds (``datetime.now()``) is a fraction of a second
in the future at compute time, so the row was stored as still active and
only corrected later by the repair cron.
"""

import json

from ..services.group_service import GroupService
from .common import ApiV2HttpTestCase, ApiV2TestCase

HOUSEHOLD_ID = "urn:openspp:vocab:id-type#test_household_id"


def _stored_end_state(env, membership):
    """ended_date, is_ended, status as stored in the database (not the cache)"""
    env.flush_all()
    env.cr.execute(
        "SELECT ended_date, is_ended, status FROM spp_group_membership WHERE id = %s",
        (membership.id,),
    )
    return env.cr.fetchone()


class TestMembershipEndNow(ApiV2TestCase):
    """GroupService operations that end memberships at the current time"""

    def setUp(self):
        super().setUp()
        self.service = GroupService(self.env)
        self.head = self.create_test_individual(name="End Head", identifier_value="END-IND-HEAD")
        self.member_a = self.create_test_individual(name="End A", identifier_value="END-IND-A")
        self.member_b = self.create_test_individual(name="End B", identifier_value="END-IND-B")

    def _membership(self, group, individual):
        return self.env["spp.group.membership"].search(
            [("group", "=", group.id), ("individual", "=", individual.id)], limit=1
        )

    def _assert_ended_now(self, membership):
        ended_date, is_ended, status = _stored_end_state(self.env, membership)
        self.assertTrue(ended_date)
        self.assertEqual(ended_date.microsecond, 0, "ended_date must use the ORM's second precision")
        self.assertTrue(is_ended, "stored is_ended must be true without waiting for the repair cron")
        self.assertEqual(status, "inactive")

    def test_remove_member_ends_membership_immediately(self):
        group = self.create_test_group(
            name="End Remove",
            identifier_value="END-HH-REMOVE",
            members=[(self.head, self.relationship_head), (self.member_a, None)],
        )

        response = self.service.remove_member(group, self.member_a)

        self.assertEqual(response["status"], "inactive")
        self._assert_ended_now(self._membership(group, self.member_a))

    def test_merge_ends_source_memberships_immediately(self):
        source = self.create_test_group(
            name="End Merge Source",
            identifier_value="END-HH-MERGE-SRC",
            members=[(self.member_a, None), (self.member_b, None)],
        )
        target = self.create_test_group(
            name="End Merge Target",
            identifier_value="END-HH-MERGE-TGT",
            members=[(self.head, self.relationship_head)],
        )
        source_memberships = source.group_membership_ids

        self.service.merge_groups(source, target)

        for membership in source_memberships:
            self._assert_ended_now(membership)

    def test_split_ends_moved_memberships_immediately(self):
        source = self.create_test_group(
            name="End Split Source",
            identifier_value="END-HH-SPLIT-SRC",
            members=[(self.head, self.relationship_head), (self.member_a, None), (self.member_b, None)],
        )
        moved = self._membership(source, self.member_a)

        self.service.split_group(
            source,
            new_identifiers=[{"system": HOUSEHOLD_ID, "value": "END-HH-SPLIT-NEW"}],
            members_to_move=[self.member_a],
        )

        self._assert_ended_now(moved)
        self.assertFalse(_stored_end_state(self.env, self._membership(source, self.member_b))[1])


class TestRemoveMemberEndNowAPI(ApiV2HttpTestCase):
    """$remove-member without endedDate: the response and searches agree at once"""

    def setUp(self):
        super().setUp()
        self.head = self.create_test_individual(name="API End Head", identifier_value="END-API-HEAD")
        self.leaver = self.create_test_individual(name="API End Leaver", identifier_value="END-API-LEAVER")
        self.group = self.create_test_group(
            name="API End Household",
            identifier_value="END-API-HH",
            members=[(self.head, self.relationship_head), (self.leaver, None)],
        )
        self.client = self.create_api_client(
            name="End Now Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "update"},
            ],
        )
        for registrant in (self.head, self.leaver, self.group):
            self.create_consent(
                registrant=registrant,
                grantee_partner=self.client.partner_id,
                resource_type="all",
                field_access="all",
            )
        self.token = self.generate_jwt_token(self.client)

    def _headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"}

    def test_remove_member_is_effective_immediately(self):
        response = self.url_open(
            "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|END-API-HH/$remove-member",
            data=json.dumps(
                {"entity": {"reference": "Individual/urn:openspp:vocab:id-type#test_national_id|END-API-LEAVER"}}
            ),
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "inactive")
        self.assertIn("endedDate", response.json())

        search = self.url_open(
            "/api/v2/spp/Individual?group=urn:openspp:vocab:id-type%23test_household_id%7CEND-API-HH",
            headers=self._headers(),
        )
        self.assertEqual(search.status_code, 200, search.text)
        values = {resource["identifier"][0]["value"] for resource in search.json().get("data") or []}
        self.assertIn("END-API-HEAD", values)
        self.assertNotIn("END-API-LEAVER", values)
