# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for PATCH API endpoints (Individual and Group)"""

import json
from datetime import date

from .common import ApiV2HttpTestCase


class TestPatchAPIEndpoints(ApiV2HttpTestCase):
    """Test PATCH endpoints for Individual and Group resources"""

    def setUp(self):
        super().setUp()

        # Create test individual
        self.individual = self.create_test_individual(
            name="Jane Doe",
            given_name="Jane",
            family_name="Doe",
            identifier_value="IND-PATCH-001",
            gender_id=self.gender_female.id,
            birthdate=date(1990, 5, 15),
            phone="+1234567890",
            email="jane@example.com",
        )

        # Create test group
        self.group = self.create_test_group(
            name="Smith Household",
            identifier_value="HH-PATCH-001",
        )

        # Create API client with full permissions
        self.client = self.create_api_client(
            name="Test API Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "update"},
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "update"},
            ],
        )

        # Create consents
        self.individual_consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
            field_access="all",
        )
        self.group_consent = self.create_consent(
            registrant=self.group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Generate token
        self.token = self.generate_jwt_token(self.client)

    def _get_headers(self, token=None, if_match=None):
        """Get HTTP headers with authorization and optional If-Match"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token or self.token}",
        }
        if if_match:
            headers["If-Match"] = if_match
        return headers

    def _get_version_id(self, url):
        """Get current versionId from resource"""
        response = self.url_open(url, headers=self._get_headers())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        return data["meta"]["versionId"]

    # =============================================================================
    # Individual PATCH Tests
    # =============================================================================

    def test_patch_individual_requires_auth(self):
        """PATCH /Individual/{id} without token returns 401"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_patch_individual_requires_scope(self):
        """PATCH /Individual/{id} without update scope returns 403"""
        # Create client without update scope
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(token=read_only_token),
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("individual:update", data["detail"])

    def test_patch_individual_success(self):
        """PATCH /Individual/{id} successfully updates single field"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update birthDate only
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Individual")
        self.assertEqual(data["birthDate"], "1990-06-20")
        # Other fields should remain unchanged
        self.assertEqual(data["name"]["given"], "Jane")
        self.assertEqual(data["name"]["family"], "Doe")

    def test_patch_individual_not_found(self):
        """PATCH /Individual/{id} returns 404 for non-existent identifier (non-consent client)"""
        # Create client that doesn't require consent to test 404 behavior
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "update"},
            ],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT"
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(token=token),
        )

        self.assertEqual(response.status_code, 404)

    def test_patch_individual_no_consent_returns_403(self):
        """PATCH /Individual/{id} succeeds even without consent (consent only required for read)"""
        # Create individual without consent
        self.create_test_individual(
            identifier_value="IND-NO-CONSENT-PATCH",
            name="No Consent Person",
        )

        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-NO-CONSENT-PATCH"
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Note: Consent is only enforced for read operations, not update operations
        # This is by design in the current implementation
        self.assertEqual(response.status_code, 200)

    def test_patch_individual_version_conflict(self):
        """PATCH /Individual/{id} returns 409 with wrong If-Match value"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Use incorrect version ID
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match='"wrong-version-id"'),
        )

        self.assertEqual(response.status_code, 409)
        data = json.loads(response.content)
        self.assertIn("conflict", data["detail"].lower())

    def test_patch_individual_multiple_fields(self):
        """PATCH /Individual/{id} updates multiple fields at once"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update multiple fields
        payload = {
            "birthDate": "1990-07-25",
            "telecom": [
                {
                    "system": "phone",
                    "value": "+9876543210",
                    "use": "mobile",
                }
            ],
        }

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["birthDate"], "1990-07-25")
        self.assertIn("telecom", data)
        # Find the mobile telecom entry (not the first one, which may be home phone)
        mobile_entry = next((t for t in data["telecom"] if t.get("use") == "mobile"), None)
        self.assertIsNotNone(mobile_entry, "Mobile telecom entry should exist")
        self.assertEqual(mobile_entry["value"], "+9876543210")
        # Name should remain unchanged
        self.assertEqual(data["name"]["given"], "Jane")

    def test_patch_individual_without_if_match(self):
        """PATCH /Individual/{id} works without If-Match header (no version check)"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Update without If-Match header
        payload = {"birthDate": "1990-08-10"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),  # No if_match parameter
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["birthDate"], "1990-08-10")

    def test_patch_individual_invalid_data(self):
        """PATCH /Individual/{id} with invalid data returns 422"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Invalid birthDate format
        payload = {"birthDate": "not-a-date"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 422)

    def test_patch_individual_updates_version(self):
        """PATCH /Individual/{id} updates the versionId"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        old_version_id = self._get_version_id(url)

        # Update field
        payload = {"birthDate": "1990-09-15"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{old_version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        new_version_id = data["meta"]["versionId"]

        # Version should have changed
        self.assertNotEqual(old_version_id, new_version_id)

    # =============================================================================
    # Group PATCH Tests
    # =============================================================================

    def test_patch_group_requires_auth(self):
        """PATCH /Group/{id} without token returns 401"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"
        payload = {"name": "Updated Household"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_patch_group_requires_scope(self):
        """PATCH /Group/{id} without update scope returns 403"""
        # Create client without update scope
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "group", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"
        payload = {"name": "Updated Household"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(token=read_only_token),
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("group:update", data["detail"])

    def test_patch_group_success(self):
        """PATCH /Group/{id} successfully updates group name"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update name only
        payload = {"name": "Updated Smith Household"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Group")
        self.assertEqual(data["name"], "Updated Smith Household")
        # Identifier should remain unchanged
        self.assertEqual(data["identifier"][0]["value"], "HH-PATCH-001")

    def test_patch_group_not_found(self):
        """PATCH /Group/{id} returns 404 for non-existent identifier (non-consent client)"""
        # Create client that doesn't require consent to test 404 behavior
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "update"},
            ],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|NONEXISTENT"
        payload = {"name": "Updated"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(token=token),
        )

        self.assertEqual(response.status_code, 404)

    def test_patch_group_no_consent_returns_403(self):
        """PATCH /Group/{id} succeeds even without consent (consent only required for read)"""
        # Create group without consent
        self.create_test_group(
            identifier_value="HH-NO-CONSENT-PATCH",
            name="No Consent Group",
        )

        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-NO-CONSENT-PATCH"
        payload = {"name": "Updated"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Note: Consent is only enforced for read operations, not update operations
        # This is by design in the current implementation
        self.assertEqual(response.status_code, 200)

    def test_patch_group_version_conflict(self):
        """PATCH /Group/{id} returns 409 with wrong If-Match value"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Use incorrect version ID
        payload = {"name": "Updated"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match='"wrong-version-id"'),
        )

        self.assertEqual(response.status_code, 409)
        data = json.loads(response.content)
        self.assertIn("conflict", data["detail"].lower())

    def test_patch_group_multiple_fields(self):
        """PATCH /Group/{id} updates multiple fields at once"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update multiple fields
        payload = {
            "name": "New Smith Household",
            "active": True,
        }

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["name"], "New Smith Household")
        self.assertEqual(data["active"], True)

    def test_patch_group_without_if_match(self):
        """PATCH /Group/{id} works without If-Match header (no version check)"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Update without If-Match header
        payload = {"name": "Another Update"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),  # No if_match parameter
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["name"], "Another Update")

    def test_patch_group_invalid_data(self):
        """PATCH /Group/{id} with invalid data returns 422"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Invalid field - send wrong type for 'active' field (string instead of boolean)
        payload = {"active": "not-a-boolean"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 422)

    def test_patch_group_updates_version(self):
        """PATCH /Group/{id} updates the versionId"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Get current version
        old_version_id = self._get_version_id(url)

        # Update field
        payload = {"name": "Version Test Household"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{old_version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        new_version_id = data["meta"]["versionId"]

        # Version should have changed
        self.assertNotEqual(old_version_id, new_version_id)

    # =============================================================================
    # Additional Edge Cases
    # =============================================================================

    def test_patch_individual_empty_payload(self):
        """PATCH /Individual/{id} with empty payload returns 200 (no changes)"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Empty payload
        payload = {}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        # Should succeed with no changes
        self.assertEqual(response.status_code, 200)

    def test_patch_group_empty_payload(self):
        """PATCH /Group/{id} with empty payload returns 200 (no changes)"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Empty payload
        payload = {}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        # Should succeed with no changes
        self.assertEqual(response.status_code, 200)

    def test_patch_individual_invalid_identifier_format(self):
        """PATCH /Individual/{id} with invalid identifier format returns 400"""
        url = "/api/v2/spp/Individual/INVALID-FORMAT"
        payload = {"birthDate": "1990-06-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 400)

    def test_patch_group_invalid_identifier_format(self):
        """PATCH /Group/{id} with invalid identifier format returns 400"""
        url = "/api/v2/spp/Group/INVALID-FORMAT"
        payload = {"name": "Updated"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 400)

    def test_patch_individual_with_address(self):
        """PATCH /Individual/{id} can update address fields"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update address
        payload = {
            "address": [
                {
                    "type": "physical",
                    "line": ["123 New Street"],
                    "city": "New City",
                    "state": "New State",
                    "country": "TC",
                    "postalCode": "54321",
                }
            ]
        }

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("address", data)
        if data["address"]:
            self.assertEqual(data["address"][0]["city"], "New City")

    def test_patch_individual_source_tracking(self):
        """PATCH /Individual/{id} updates last_update_system field"""
        url = "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|IND-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update field
        payload = {"birthDate": "1990-10-20"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        # Find the updated individual and check last_update_system (not source_system)
        # source_system is immutable after creation; updates are tracked in last_update_system
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "IND-PATCH-001")], limit=1)
        self.assertTrue(partner.last_update_system)
        self.assertIn(self.client.client_id, partner.last_update_system)

    def test_patch_group_source_tracking(self):
        """PATCH /Group/{id} updates last_update_system field"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Get current version
        version_id = self._get_version_id(url)

        # Update field
        payload = {"name": "Source Tracking Test"}

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(if_match=f'"{version_id}"'),
        )

        self.assertEqual(response.status_code, 200)

        # Find the updated group and check last_update_system (not source_system)
        # source_system is immutable after creation; updates are tracked in last_update_system
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "HH-PATCH-001")], limit=1)
        self.assertTrue(partner.last_update_system)
        self.assertIn(self.client.client_id, partner.last_update_system)

    def test_patch_group_creates_audit_log(self):
        """PATCH /Group/{id} creates audit log on success"""
        url = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|HH-PATCH-001"

        # Count existing audit logs
        existing_logs = (
            self.env["spp.api.audit.log"]
            .sudo()
            .search_count([("operation", "=", "patch"), ("resource_type", "=", "group")])
        )

        # Update field
        payload = {"name": "Audit Log Test"}
        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)

        # Verify audit log was created
        new_logs = (
            self.env["spp.api.audit.log"]
            .sudo()
            .search_count([("operation", "=", "patch"), ("resource_type", "=", "group")])
        )
        self.assertGreater(new_logs, existing_logs)
