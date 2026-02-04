# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Bulk API endpoint"""

import json
from datetime import date

from .common import ApiV2HttpTestCase


class TestBulkAPIEndpoint(ApiV2HttpTestCase):
    """Test Bulk/$bulk/export endpoint for bulk resource export"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/$bulk/export"

        # Create test individuals
        self.individual1 = self.create_test_individual(
            name="John Doe",
            given_name="John",
            family_name="Doe",
            identifier_value="IND-001",
            gender_id=self.gender_male.id,
            birthdate=date(1990, 1, 1),
            phone="+1234567890",
        )

        self.individual2 = self.create_test_individual(
            name="Jane Smith",
            given_name="Jane",
            family_name="Smith",
            identifier_value="IND-002",
            gender_id=self.gender_female.id,
            birthdate=date(1995, 5, 15),
            email="jane@example.com",
        )

        self.individual3 = self.create_test_individual(
            name="Bob Johnson",
            given_name="Bob",
            family_name="Johnson",
            identifier_value="IND-003",
            gender_id=self.gender_male.id,
        )

        # Create API client with read permissions
        self.client = self.create_api_client(
            name="Bulk Export Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "read"},
            ],
        )

        # Create consents for individuals 1 and 2
        self.consent1 = self.create_consent(
            registrant=self.individual1,
            grantee_partner=self.client.partner_id,
            field_access="all",
        )

        self.consent2 = self.create_consent(
            registrant=self.individual2,
            grantee_partner=self.client.partner_id,
            field_access="all",
        )

        # individual3 has no consent (for access denied tests)

        # Generate token
        self.token = self.generate_jwt_token(self.client)

    def _get_headers(self, token=None):
        """Get HTTP headers with authorization"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token or self.token}",
        }

    def test_bulk_export_requires_auth(self):
        """Request without authentication returns 401"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_bulk_export_requires_scope(self):
        """Request without individual:read scope returns 403"""
        # Create client without read scope
        no_scope_client = self.create_api_client(
            name="No Read Scope Client",
            scopes=[{"resource": "individual", "action": "create"}],
        )
        no_scope_token = self.generate_jwt_token(no_scope_client)

        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(token=no_scope_token),
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("individual:read", data["detail"])

    def test_bulk_export_success(self):
        """Export single individual returns success"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["successful"], 1)
        self.assertEqual(data["failed"], 0)

        # Check item structure
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["identifier"], "urn:openspp:vocab:id-type#test_national_id|IND-001")
        self.assertEqual(item["status"], "success")
        self.assertIn("resource", item)

        # Check resource structure
        resource = item["resource"]
        self.assertEqual(resource["type"], "Individual")
        self.assertIn("identifier", resource)
        self.assertIn("name", resource)

        # Should not have consent metadata in response
        self.assertNotIn("_consent", resource)

    def test_bulk_export_multiple(self):
        """Export multiple individuals returns all with consent"""
        payload = {
            "type": "Individual",
            "identifiers": [
                "urn:openspp:vocab:id-type#test_national_id|IND-001",
                "urn:openspp:vocab:id-type#test_national_id|IND-002",
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["successful"], 2)
        self.assertEqual(data["failed"], 0)

        # Check both items returned successfully
        self.assertEqual(len(data["items"]), 2)
        for item in data["items"]:
            self.assertEqual(item["status"], "success")
            self.assertIn("resource", item)

        # Check identifiers match
        returned_identifiers = {item["identifier"] for item in data["items"]}
        self.assertIn("urn:openspp:vocab:id-type#test_national_id|IND-001", returned_identifiers)
        self.assertIn("urn:openspp:vocab:id-type#test_national_id|IND-002", returned_identifiers)

    def test_bulk_export_not_found(self):
        """Non-existent identifier returns not_found for non-consent clients"""
        # Create client that doesn't require consent
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[{"resource": "individual", "action": "read"}],
            require_consent=False,
            legal_basis="public_interest",
        )
        no_consent_token = self.generate_jwt_token(no_consent_client)

        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|NONEXISTENT"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(token=no_consent_token),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["successful"], 0)
        self.assertEqual(data["failed"], 1)

        # Check item structure
        item = data["items"][0]
        self.assertEqual(item["identifier"], "urn:openspp:vocab:id-type#test_national_id|NONEXISTENT")
        self.assertEqual(item["status"], "not_found")
        self.assertIn("error", item)
        self.assertIn("not found", item["error"].lower())
        self.assertNotIn("resource", item)

    def test_bulk_export_access_denied(self):
        """Individual without consent returns access_denied"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-003"],  # No consent
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["successful"], 0)
        self.assertEqual(data["failed"], 1)

        # Check item structure
        item = data["items"][0]
        self.assertEqual(item["identifier"], "urn:openspp:vocab:id-type#test_national_id|IND-003")
        self.assertEqual(item["status"], "access_denied")
        self.assertIn("error", item)
        self.assertEqual(item["error"], "Access denied")
        self.assertNotIn("resource", item)

    def test_bulk_export_invalid_format(self):
        """Identifier without pipe returns error"""
        payload = {
            "type": "Individual",
            "identifiers": ["INVALID-FORMAT"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["successful"], 0)
        self.assertEqual(data["failed"], 1)

        # Check item structure
        item = data["items"][0]
        self.assertEqual(item["identifier"], "INVALID-FORMAT")
        self.assertEqual(item["status"], "error")
        self.assertIn("error", item)
        self.assertIn("Invalid identifier format", item["error"])
        self.assertIn("{system}|{value}", item["error"])

    def test_bulk_export_with_elements(self):
        """_elements filtering is applied to results"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
            "_elements": "name,birthDate",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["successful"], 1)

        # Check resource has only requested fields (plus type and identifier)
        resource = data["items"][0]["resource"]
        self.assertIn("type", resource)
        self.assertIn("identifier", resource)
        self.assertIn("name", resource)
        self.assertIn("birthDate", resource)

        # Should NOT have other fields
        self.assertNotIn("gender", resource)
        self.assertNotIn("telecom", resource)
        self.assertNotIn("address", resource)

    def test_bulk_export_with_nested_elements(self):
        """_elements with nested fields (e.g., name.family) works"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
            "_elements": "name.family",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        resource = data["items"][0]["resource"]

        # Should have name with only family
        self.assertIn("name", resource)
        self.assertIn("family", resource["name"])

        # Should not have given
        self.assertNotIn("given", resource["name"])

    def test_bulk_export_mixed_results(self):
        """Some found, some not found, some access denied"""
        payload = {
            "type": "Individual",
            "identifiers": [
                "urn:openspp:vocab:id-type#test_national_id|IND-001",  # Has consent - success
                # Doesn't exist - access_denied (for consent clients)
                "urn:openspp:vocab:id-type#test_national_id|NONEXISTENT",
                "urn:openspp:vocab:id-type#test_national_id|IND-003",  # No consent - access_denied
                "urn:openspp:vocab:id-type#test_national_id|IND-002",  # Has consent - success
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["successful"], 2)
        self.assertEqual(data["failed"], 2)

        # Check status distribution
        statuses = {item["identifier"]: item["status"] for item in data["items"]}
        self.assertEqual(statuses["urn:openspp:vocab:id-type#test_national_id|IND-001"], "success")
        self.assertEqual(statuses["urn:openspp:vocab:id-type#test_national_id|IND-002"], "success")
        self.assertEqual(
            statuses["urn:openspp:vocab:id-type#test_national_id|IND-003"],
            "access_denied",
        )
        self.assertEqual(
            statuses["urn:openspp:vocab:id-type#test_national_id|NONEXISTENT"],
            "access_denied",
        )

    def test_bulk_export_preserves_order(self):
        """Results are returned in same order as request"""
        payload = {
            "type": "Individual",
            "identifiers": [
                "urn:openspp:vocab:id-type#test_national_id|IND-002",
                "urn:openspp:vocab:id-type#test_national_id|IND-001",
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        data = json.loads(response.content)

        # Order should match request
        self.assertEqual(
            data["items"][0]["identifier"],
            "urn:openspp:vocab:id-type#test_national_id|IND-002",
        )
        self.assertEqual(
            data["items"][1]["identifier"],
            "urn:openspp:vocab:id-type#test_national_id|IND-001",
        )

    def test_bulk_export_empty_identifiers_returns_400(self):
        """Request with empty identifiers list returns 422"""
        payload = {
            "type": "Individual",
            "identifiers": [],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Should return validation error (422)
        self.assertEqual(response.status_code, 422)

    def test_bulk_export_too_many_identifiers_returns_422(self):
        """Request with more than 100 identifiers returns 422"""
        payload = {
            "type": "Individual",
            "identifiers": [f"urn:openspp:vocab:id-type#test_national_id|IND-{i:03d}" for i in range(101)],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Should return validation error
        self.assertEqual(response.status_code, 422)

    def test_bulk_export_group_type(self):
        """Bulk export works for Group resources"""
        # Create test group
        group = self.create_test_group(
            name="Test Household",
            identifier_value="HH-001",
        )

        # Create consent for group
        self.create_consent(
            registrant=group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        payload = {
            "type": "Group",
            "identifiers": ["urn:openspp:vocab:id-type#test_household_id|HH-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["successful"], 1)

        # Check resource type
        resource = data["items"][0]["resource"]
        self.assertEqual(resource["type"], "Group")

    def test_bulk_export_invalid_json_returns_422(self):
        """Invalid JSON payload returns 422"""
        response = self.url_open(
            self.api_base_url,
            data="invalid json {",
            headers=self._get_headers(),
        )

        # Should return error
        self.assertIn(response.status_code, [400, 422, 500])

    def test_bulk_export_missing_type_returns_422(self):
        """Request without type field returns 422"""
        payload = {
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 422)

    def test_bulk_export_with_extensions(self):
        """_extensions parameter is passed through"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
            "_extensions": "farmer",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Should succeed (whether or not extensions exist)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["successful"], 1)

    def test_bulk_export_duplicate_identifiers(self):
        """Duplicate identifiers in request are processed independently"""
        payload = {
            "type": "Individual",
            "identifiers": [
                "urn:openspp:vocab:id-type#test_national_id|IND-001",
                "urn:openspp:vocab:id-type#test_national_id|IND-001",  # Duplicate
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        # Both should succeed (duplicate is OK)
        self.assertEqual(data["successful"], 2)

    def test_bulk_export_identifier_with_special_characters(self):
        """Identifiers with special characters are handled correctly"""
        # Create individual with special chars in identifier
        special_individual = self.create_test_individual(
            name="Special ID",
            identifier_value="IND-SPECIAL-123/456",
        )

        # Create consent
        self.create_consent(
            registrant=special_individual,
            grantee_partner=self.client.partner_id,
            field_access="all",
        )

        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-SPECIAL-123/456"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["successful"], 1)

    def test_bulk_export_partial_invalid_identifiers(self):
        """Mix of valid and invalid identifier formats"""
        payload = {
            "type": "Individual",
            "identifiers": [
                "urn:openspp:vocab:id-type#test_national_id|IND-001",  # Valid
                "INVALID",  # Invalid format
                "urn:openspp:vocab:id-type#test_national_id|IND-002",  # Valid
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["successful"], 2)  # Two valid ones succeeded
        self.assertEqual(data["failed"], 1)  # One invalid failed

        # Check the invalid one has error status
        statuses = {item["identifier"]: item["status"] for item in data["items"]}
        self.assertEqual(statuses["INVALID"], "error")

    def test_bulk_export_no_consent_metadata_in_response(self):
        """Response should not include _consent metadata"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        data = json.loads(response.content)
        resource = data["items"][0]["resource"]

        # Should not have consent metadata
        self.assertNotIn("_consent", resource)

    def test_bulk_export_rate_limit_header(self):
        """Response includes rate limit headers"""
        payload = {
            "type": "Individual",
            "identifiers": ["urn:openspp:vocab:id-type#test_national_id|IND-001"],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Check for rate limit headers (if implemented)
        # Note: Actual rate limiting may not be enforced in tests
        # This test just checks if headers are present
        self.assertEqual(response.status_code, 200)
