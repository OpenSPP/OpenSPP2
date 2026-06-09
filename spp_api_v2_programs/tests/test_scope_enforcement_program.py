# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Scope enforcement tests for the Program Membership endpoints.

Moved out of spp_api_v2 together with the program API (OP#1081).
"""

import json

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase


class TestScopeEnforcementProgramMembership(ApiV2HttpTestCase):
    """Test scope enforcement on Program Membership endpoints"""

    def setUp(self):
        super().setUp()
        # Create test data
        self.program = self.create_test_program(name="Test Program", target_type="individual")
        self.individual = self.create_test_individual(identifier_value="SCOPE-PM-001")

        # Create test membership
        self.membership = self.create_test_membership(
            partner=self.individual,
            program=self.program,
            state="enrolled",
        )

        # Base URL for program membership
        self.pm_url = "/api/v2/spp/ProgramMembership"
        self.pm_id_url = f"{self.pm_url}/urn:openspp:vocab:id-type%23test_national_id|SCOPE-PM-001"

    def _make_client_without_scope(self, excluded_resource, excluded_action):
        """Create a client that has all scopes EXCEPT the specified one"""
        scopes = []
        # Give it a different resource scope to prove it's not resource-agnostic
        other_resource = "individual" if excluded_resource == "program_membership" else "program_membership"
        scopes.append({"resource": other_resource, "action": "all"})
        client = self.create_api_client(
            name=f"No {excluded_resource}:{excluded_action}",
            scopes=scopes,
            require_consent=False,
        )
        return client, self.generate_jwt_token(client)

    def test_program_membership_create_requires_scope(self):
        """POST /ProgramMembership returns 403 without program_membership:create scope"""
        client, token = self._make_client_without_scope("program_membership", "create")

        # Create new individual for enrollment
        self.create_test_individual(identifier_value="SCOPE-PM-NEW")

        payload = {
            "resourceType": "ProgramMembership",
            "status": "enrolled",
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|SCOPE-PM-NEW",
            },
            "program": {
                "reference": "Program/urn:openspp:program|test-program",
            },
        }

        response = self.url_open(
            self.pm_url,
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

    def test_program_membership_update_requires_scope(self):
        """PUT /ProgramMembership/{id} returns 403 without program_membership:update scope"""
        client, token = self._make_client_without_scope("program_membership", "update")

        payload = {
            "resourceType": "ProgramMembership",
            "status": "paused",
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|SCOPE-PM-001",
            },
            "program": {
                "reference": "Program/urn:openspp:program|test-program",
            },
        }

        response = self.url_put(
            self.pm_id_url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Missing required scope", data["detail"])
        self.assertIn("program_membership:update", data["detail"])

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
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|SCOPE-PM-001",
            },
            "program": {
                "reference": "Program/urn:openspp:program|test-program",
            },
        }

        response = self.url_open(
            self.pm_url,
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
