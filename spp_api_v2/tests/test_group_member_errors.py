# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Member operations map the service's errors to a status by type, not by text.

The service raises its messages through ``_()``, so their text follows the
user's language; a status decided by matching English text changes with it.
"""

import json
from unittest.mock import patch

from ..services.group_service import AlreadyMemberError, GroupService, NotMemberError
from .common import ApiV2HttpTestCase

GROUP_PATH = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-ERR"
MEMBER_REF = "Individual/urn:openspp:vocab:id-type#test_national_id|IND-ERR-MEMBER"
OUTSIDER_ID = "urn:openspp:vocab:id-type%23test_national_id|IND-ERR-OUTSIDER"


class TestGroupMemberErrors(ApiV2HttpTestCase):
    def setUp(self):
        super().setUp()
        self.member = self.create_test_individual(name="Member", identifier_value="IND-ERR-MEMBER")
        self.outsider = self.create_test_individual(name="Outsider", identifier_value="IND-ERR-OUTSIDER")
        self.group = self.create_test_group(
            name="Error Household", identifier_value="HH-ERR", members=[(self.member, None)]
        )
        client = self.create_api_client(
            name="Member Errors Client",
            scopes=[{"resource": "group", "action": "read"}, {"resource": "group", "action": "update"}],
            require_consent=False,
            legal_basis="public_task",
        )
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.generate_jwt_token(client)}",
        }

    def _post(self, path, payload):
        return self.url_open(path, data=json.dumps(payload), headers=self.headers)

    def _patch(self, path, payload):
        return self.url_patch(path, data=json.dumps(payload), headers=self.headers)

    # --- service raises the dedicated errors ------------------------------

    def test_service_raises_already_member(self):
        with self.assertRaises(AlreadyMemberError):
            GroupService(self.env).add_member(self.group, self.member)

    def test_service_raises_not_member_on_update_and_remove(self):
        service = GroupService(self.env)
        with self.assertRaises(NotMemberError):
            service.update_member(self.group, self.outsider)
        with self.assertRaises(NotMemberError):
            service.remove_member(self.group, self.outsider)

    # --- the status does not depend on the message's language -------------

    def test_add_existing_member_is_409_whatever_the_language(self):
        with patch.object(GroupService, "add_member", side_effect=AlreadyMemberError("Déjà membre de ce groupe")):
            response = self._post(f"{GROUP_PATH}/$add-member", {"entity": {"reference": MEMBER_REF}})

        self.assertEqual(response.status_code, 409, response.text)

    def test_update_non_member_is_404_whatever_the_language(self):
        with patch.object(GroupService, "update_member", side_effect=NotMemberError("Pas membre de ce groupe")):
            response = self._patch(f"{GROUP_PATH}/member/{OUTSIDER_ID}", {"startDate": "2024-01-15"})

        self.assertEqual(response.status_code, 404, response.text)

    def test_remove_non_member_is_404_whatever_the_language(self):
        with patch.object(GroupService, "remove_member", side_effect=NotMemberError("Pas membre de ce groupe")):
            response = self._post(
                f"{GROUP_PATH}/$remove-member",
                {"entity": {"reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-ERR-OUTSIDER"}},
            )

        self.assertEqual(response.status_code, 404, response.text)
