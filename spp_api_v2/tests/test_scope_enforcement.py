# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for API scope enforcement on all endpoints.

Verifies that every protected endpoint properly enforces scope checks.
If scope checks are missing (like the issue fixed in commit 2df2df77c),
these tests will catch it by failing with unexpected 200/404 instead of 403.
"""

import json

from .common import ApiV2HttpTestCase


class TestScopeEnforcementIndividual(ApiV2HttpTestCase):
    """Test scope enforcement on Individual endpoints"""

    def setUp(self):
        super().setUp()
        # Create test data
        self.individual = self.create_test_individual(identifier_value="SCOPE-IND-001")
        # Base URL for individual
        self.ind_url = "/api/v2/spp/Individual"
        self.ind_id_url = f"{self.ind_url}/urn:openspp:vocab:id-type%23test_national_id|SCOPE-IND-001"

    def _make_client_without_scope(self, excluded_resource, excluded_action):
        """Create a client that has all scopes EXCEPT the specified one"""
        scopes = []
        # Give it a different resource scope to prove it's not resource-agnostic
        other_resource = "group" if excluded_resource == "individual" else "individual"
        scopes.append({"resource": other_resource, "action": "all"})
        client = self.create_api_client(
            name=f"No {excluded_resource}:{excluded_action}",
            scopes=scopes,
            require_consent=False,
        )
        return client, self.generate_jwt_token(client)

    def test_individual_read_requires_scope(self):
        """GET /Individual/{id} returns 403 without individual:read scope"""
        client, token = self._make_client_without_scope("individual", "read")

        response = self.url_open(
            self.ind_id_url,
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:read", data["detail"])

    def test_individual_search_requires_scope(self):
        """GET /Individual returns 403 without individual:read scope"""
        client, token = self._make_client_without_scope("individual", "read")

        response = self.url_open(
            self.ind_url,
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:read", data["detail"])

    def test_individual_create_requires_scope(self):
        """POST /Individual returns 403 without individual:create scope"""
        client, token = self._make_client_without_scope("individual", "create")

        payload = {
            "resourceType": "Individual",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "NO-CREATE-SCOPE",
                }
            ],
            "name": {"given": "Test", "family": "NoCreate"},
        }

        response = self.url_open(
            self.ind_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:create", data["detail"])

    def test_individual_update_requires_scope(self):
        """PUT /Individual/{id} returns 403 without individual:update scope"""
        client, token = self._make_client_without_scope("individual", "update")

        payload = {
            "resourceType": "Individual",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "SCOPE-IND-001",
                }
            ],
            "name": {"given": "Updated", "family": "Name"},
        }

        response = self.url_put(
            self.ind_id_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:update", data["detail"])

    def test_individual_patch_requires_scope(self):
        """PATCH /Individual/{id} returns 403 without individual:update scope"""
        client, token = self._make_client_without_scope("individual", "update")

        payload = {
            "name": {"given": "Patched"},
        }

        response = self.url_patch(
            self.ind_id_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:update", data["detail"])

    def test_individual_groups_requires_scope(self):
        """GET /Individual/{id}/groups returns 403 without individual:read scope"""
        client, token = self._make_client_without_scope("individual", "read")

        response = self.url_open(
            f"{self.ind_id_url}/groups",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:read", data["detail"])


class TestScopeEnforcementGroup(ApiV2HttpTestCase):
    """Test scope enforcement on Group endpoints"""

    def setUp(self):
        super().setUp()
        # Create test data
        self.individual1 = self.create_test_individual(identifier_value="SCOPE-MEMBER-001")
        self.individual2 = self.create_test_individual(identifier_value="SCOPE-MEMBER-002")
        self.group = self.create_test_group(
            identifier_value="SCOPE-GRP-001",
            members=[
                (self.individual1, self.relationship_head),
                (self.individual2, None),
            ],
        )
        # Base URL for group
        self.grp_url = "/api/v2/spp/Group"
        self.grp_id_url = f"{self.grp_url}/urn:openspp:vocab:id-type%23test_household_id|SCOPE-GRP-001"

    def _make_client_without_scope(self, excluded_resource, excluded_action):
        """Create a client that has all scopes EXCEPT the specified one"""
        scopes = []
        # Give it a different resource scope to prove it's not resource-agnostic
        other_resource = "individual" if excluded_resource == "group" else "group"
        scopes.append({"resource": other_resource, "action": "all"})
        client = self.create_api_client(
            name=f"No {excluded_resource}:{excluded_action}",
            scopes=scopes,
            require_consent=False,
        )
        return client, self.generate_jwt_token(client)

    def test_group_read_requires_scope(self):
        """GET /Group/{id} returns 403 without group:read scope"""
        client, token = self._make_client_without_scope("group", "read")

        response = self.url_open(
            self.grp_id_url,
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:read", data["detail"])

    def test_group_search_requires_scope(self):
        """GET /Group returns 403 without group:read scope"""
        client, token = self._make_client_without_scope("group", "read")

        response = self.url_open(
            self.grp_url,
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:read", data["detail"])

    def test_group_create_requires_scope(self):
        """POST /Group returns 403 without group:create scope"""
        client, token = self._make_client_without_scope("group", "create")

        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "NO-CREATE-SCOPE",
                }
            ],
            "name": "Test Group No Create",
            "type": "Group",
        }

        response = self.url_open(
            self.grp_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:create", data["detail"])

    def test_group_update_requires_scope(self):
        """PUT /Group/{id} returns 403 without group:update scope"""
        client, token = self._make_client_without_scope("group", "update")

        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "SCOPE-GRP-001",
                }
            ],
            "name": "Updated Group Name",
            "type": "Group",
        }

        response = self.url_put(
            self.grp_id_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])

    def test_group_patch_requires_scope(self):
        """PATCH /Group/{id} returns 403 without group:update scope"""
        client, token = self._make_client_without_scope("group", "update")

        payload = {
            "name": "Patched Group Name",
        }

        response = self.url_patch(
            self.grp_id_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])

    def test_group_add_member_requires_scope(self):
        """POST /Group/{id}/$add-member returns 403 without group:update scope"""
        client, token = self._make_client_without_scope("group", "update")

        # Create a new individual to add
        self.create_test_individual(identifier_value="SCOPE-NEW-MEMBER")

        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|SCOPE-NEW-MEMBER",
            },
        }

        response = self.url_open(
            f"{self.grp_id_url}/$add-member",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])

    def test_group_remove_member_requires_scope(self):
        """POST /Group/{id}/$remove-member returns 403 without group:update scope"""
        client, token = self._make_client_without_scope("group", "update")

        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|SCOPE-MEMBER-001",
            },
        }

        response = self.url_open(
            f"{self.grp_id_url}/$remove-member",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])

    def test_group_update_member_requires_scope(self):
        """PATCH /Group/{id}/member/{member_id} returns 403 without group:update scope"""
        client, token = self._make_client_without_scope("group", "update")

        member_id_url = "urn:openspp:vocab:id-type%23test_national_id|SCOPE-MEMBER-001"

        payload = {
            "role": {
                "coding": [
                    {
                        "system": "urn:openspp:vocab:group-membership-type",
                        "code": "spouse",
                        "display": "Spouse",
                    }
                ]
            },
        }

        response = self.url_patch(
            f"{self.grp_id_url}/member/{member_id_url}",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])

    def test_group_merge_requires_scope(self):
        """POST /Group/$merge returns 403 without group:update scope"""
        client, token = self._make_client_without_scope("group", "update")

        # Create a second group
        self.create_test_group(identifier_value="SCOPE-GRP-002")

        payload = {
            "sourceGroup": {
                "reference": "Group/urn:openspp:vocab:id-type#test_household_id|SCOPE-GRP-002",
            },
            "targetGroup": {
                "reference": "Group/urn:openspp:vocab:id-type#test_household_id|SCOPE-GRP-001",
            },
        }

        response = self.url_open(
            f"{self.grp_url}/$merge",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])

    def test_group_split_requires_both_scopes(self):
        """POST /Group/{id}/$split returns 403 without both group:create and group:update scopes"""
        # Test 1: Has create but not update
        client_no_update = self.create_api_client(
            name="Has create, no update",
            scopes=[{"resource": "group", "action": "create"}],
            require_consent=False,
        )
        token_no_update = self.generate_jwt_token(client_no_update)

        payload = {
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|SCOPE-MEMBER-001",
                }
            ],
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "SCOPE-SPLIT-NEW",
                }
            ],
        }

        response = self.url_open(
            f"{self.grp_id_url}/$split",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token_no_update}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scopes", data["detail"])

        # Test 2: Has update but not create
        client_no_create = self.create_api_client(
            name="Has update, no create",
            scopes=[{"resource": "group", "action": "update"}],
            require_consent=False,
        )
        token_no_create = self.generate_jwt_token(client_no_create)

        response = self.url_open(
            f"{self.grp_id_url}/$split",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token_no_create}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scopes", data["detail"])

    def test_group_membership_history_requires_scope(self):
        """GET /Group/{id}/membership-history returns 403 without group:read scope"""
        client, token = self._make_client_without_scope("group", "read")

        response = self.url_open(
            f"{self.grp_id_url}/membership-history",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:read", data["detail"])


class TestScopeIsolation(ApiV2HttpTestCase):
    """Test that scopes for one resource don't grant access to another"""

    def setUp(self):
        super().setUp()
        # Create test data for all resource types
        self.individual = self.create_test_individual(identifier_value="ISOLATION-IND-001")
        self.group = self.create_test_group(identifier_value="ISOLATION-GRP-001")
        self.program = self.create_test_program(name="Isolation Test Program")
        self.membership = self.create_test_membership(
            partner=self.individual,
            program=self.program,
        )

    def test_individual_scope_does_not_grant_group_access(self):
        """individual:read scope does not grant access to group endpoints"""
        # Create client with only individual:read scope
        client = self.create_api_client(
            name="Individual Only Client",
            scopes=[{"resource": "individual", "action": "read"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to access group endpoint
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|ISOLATION-GRP-001"
        response = self.url_open(url, headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:read", data["detail"])

    def test_group_scope_does_not_grant_individual_access(self):
        """group:read scope does not grant access to individual endpoints"""
        # Create client with only group:read scope
        client = self.create_api_client(
            name="Group Only Client",
            scopes=[{"resource": "group", "action": "read"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to access individual endpoint
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|ISOLATION-IND-001"
        response = self.url_open(url, headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:read", data["detail"])

    def test_individual_scope_does_not_grant_program_membership_access(self):
        """individual:create scope does not grant access to program_membership endpoints"""
        # Create client with only individual:create scope
        client = self.create_api_client(
            name="Individual Create Only Client",
            scopes=[{"resource": "individual", "action": "create"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to create program membership
        payload = {
            "resourceType": "ProgramMembership",
            "status": "enrolled",
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|ISOLATION-IND-001",
            },
            "program": {
                "reference": "Program/urn:openspp:program|isolation-test-program",
            },
        }

        response = self.url_open(
            "/api/v2/spp/ProgramMembership",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("program_membership:create", data["detail"])

    def test_read_scope_does_not_grant_create_access(self):
        """individual:read scope does not grant create access"""
        # Create client with only individual:read scope
        client = self.create_api_client(
            name="Individual Read Only Client",
            scopes=[{"resource": "individual", "action": "read"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to create individual
        payload = {
            "resourceType": "Individual",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "READ-SCOPE-CREATE-ATTEMPT",
                }
            ],
            "name": {"given": "Test", "family": "ReadScope"},
        }

        response = self.url_open(
            "/api/v2/spp/Individual",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:create", data["detail"])

    def test_create_scope_does_not_grant_update_access(self):
        """individual:create scope does not grant update access"""
        # Create client with only individual:create scope
        client = self.create_api_client(
            name="Individual Create Only Client",
            scopes=[{"resource": "individual", "action": "create"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to update individual
        payload = {
            "resourceType": "Individual",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "ISOLATION-IND-001",
                }
            ],
            "name": {"given": "Updated", "family": "Name"},
        }

        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|ISOLATION-IND-001"
        response = self.url_put(
            url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("individual:update", data["detail"])

    def test_group_read_scope_does_not_grant_create_access(self):
        """group:read scope does not grant create access"""
        # Create client with only group:read scope
        client = self.create_api_client(
            name="Group Read Only Client",
            scopes=[{"resource": "group", "action": "read"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to create group
        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "READ-SCOPE-CREATE-GROUP",
                }
            ],
            "name": "Test Group Creation with Read Scope",
            "type": "Group",
        }

        response = self.url_open(
            "/api/v2/spp/Group",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:create", data["detail"])

    def test_group_create_scope_does_not_grant_update_access(self):
        """group:create scope does not grant update access"""
        # Create client with only group:create scope
        client = self.create_api_client(
            name="Group Create Only Client",
            scopes=[{"resource": "group", "action": "create"}],
            require_consent=False,
        )
        token = self.generate_jwt_token(client)

        # Try to update group
        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "ISOLATION-GRP-001",
                }
            ],
            "name": "Updated Group Name",
            "type": "Group",
        }

        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|ISOLATION-GRP-001"
        response = self.url_put(
            url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("group:update", data["detail"])
