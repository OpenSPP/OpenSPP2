# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Every reference the API returns can be followed back (#554 item F).

References must carry the identifier type's full code URI
(``id_type_id.uri``, e.g. ``urn:openspp:vocab:id-type#test_national_id``),
the value lookups match on — not the vocabulary namespace alone.
"""

import json
from urllib.parse import quote

from .common import ApiV2HttpTestCase

GROUP_PATH = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|REF-HH-001"


class TestReferencesResolvable(ApiV2HttpTestCase):
    """Follow Individual/Group references from each response that returns them"""

    def setUp(self):
        super().setUp()
        self.member = self.create_test_individual(name="Ref Member", identifier_value="REF-IND-001")
        self.newcomer = self.create_test_individual(name="Ref Newcomer", identifier_value="REF-IND-002")
        self.group = self.create_test_group(
            name="Ref Household",
            identifier_value="REF-HH-001",
            members=[(self.member, self.relationship_head)],
        )
        self.client = self.create_api_client(
            name="Reference Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "update"},
            ],
        )
        for registrant in (self.member, self.newcomer, self.group):
            self.create_consent(
                registrant=registrant,
                grantee_partner=self.client.partner_id,
                resource_type="all",
                field_access="all",
            )
        self.token = self.generate_jwt_token(self.client)

    def _headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"}

    def _get(self, path):
        return self.url_open(path, headers=self._headers())

    def _post(self, path, payload):
        return self.url_open(path, data=json.dumps(payload), headers=self._headers())

    def _assert_followable(self, reference, expected_value):
        """GET the referenced resource and check it is the one named"""
        resource_type, identifier = reference.split("/", 1)
        response = self._get(f"/api/v2/spp/{resource_type}/{quote(identifier, safe=':|')}")
        self.assertEqual(response.status_code, 200, f"{reference} → {response.status_code} {response.text}")
        values = {ident["value"] for ident in response.json()["identifier"]}
        self.assertIn(expected_value, values)

    def test_group_member_entity_reference(self):
        """GET /Group/{id}: member[].entity.reference"""
        response = self._get(GROUP_PATH)
        self.assertEqual(response.status_code, 200, response.text)

        members = response.json()["member"]
        self.assertTrue(members)
        for member in members:
            self._assert_followable(member["entity"]["reference"], "REF-IND-001")

    def test_add_member_response_references(self):
        """POST $add-member: group and entity references in the response"""
        response = self._post(
            f"{GROUP_PATH}/$add-member",
            {"entity": {"reference": "Individual/urn:openspp:vocab:id-type#test_national_id|REF-IND-002"}},
        )
        self.assertIn(response.status_code, (200, 201), response.text)
        data = response.json()

        self._assert_followable(data["group"]["reference"], "REF-HH-001")
        self._assert_followable(data["entity"]["reference"], "REF-IND-002")

    def test_remove_member_response_references(self):
        """POST $remove-member: group and entity references in the response"""
        response = self._post(
            f"{GROUP_PATH}/$remove-member",
            {"entity": {"reference": "Individual/urn:openspp:vocab:id-type#test_national_id|REF-IND-001"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        self._assert_followable(data["group"]["reference"], "REF-HH-001")
        self._assert_followable(data["entity"]["reference"], "REF-IND-001")

    def test_membership_history_member_reference(self):
        """GET membership-history: data[].member.reference"""
        response = self._get(f"{GROUP_PATH}/membership-history")
        self.assertEqual(response.status_code, 200, response.text)

        entries = response.json()["data"]
        self.assertTrue(entries)
        for entry in entries:
            self._assert_followable(entry["member"]["reference"], "REF-IND-001")

    def test_individual_group_membership_reference(self):
        """GET /Individual/{id}: groupMembership[].group.reference"""
        response = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|REF-IND-001")
        self.assertEqual(response.status_code, 200, response.text)

        memberships = response.json()["groupMembership"]
        self.assertTrue(memberships)
        for membership in memberships:
            self._assert_followable(membership["group"]["reference"], "REF-HH-001")

    def _add_removed_id(self, partner, value):
        """Give the registrant a newer, soft-removed ID (it sorts first in reg_ids)"""
        self.env["spp.registry.id"].create(
            {
                "partner_id": partner.id,
                "id_type_id": self.id_type_household.id,
                "value": value,
                "status": "invalid",
            }
        )

    def test_references_use_a_live_id_not_a_removed_one(self):
        """A soft-removed ID no longer resolves, so references must not be built from it"""
        self._add_removed_id(self.member, "REF-REMOVED-IND")
        removed_group_type = self.env["spp.vocabulary.code"].search(
            [("uri", "=", "urn:openspp:vocab:id-type#test_national_id")], limit=1
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.group.id,
                "id_type_id": removed_group_type.id,
                "value": "REF-REMOVED-HH",
                "status": "invalid",
            }
        )

        group_response = self._get(GROUP_PATH)
        self.assertEqual(group_response.status_code, 200, group_response.text)
        for member in group_response.json()["member"]:
            self._assert_followable(member["entity"]["reference"], "REF-IND-001")

        individual_response = self._get(
            "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|REF-IND-001"
        )
        self.assertEqual(individual_response.status_code, 200, individual_response.text)
        for membership in individual_response.json()["groupMembership"]:
            self._assert_followable(membership["group"]["reference"], "REF-HH-001")
