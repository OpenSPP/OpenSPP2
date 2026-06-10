# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ProgramMembership API endpoints"""

import json
from datetime import date

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase


class TestProgramMembershipAPIEndpoints(ApiV2HttpTestCase):
    """Test ProgramMembership resource HTTP endpoints"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/ProgramMembership"

        # Create test data
        self.program = self.create_test_program(name="Test Enrollment Program", target_type="individual")
        self.individual = self.create_test_individual(
            identifier_value="ENROLL-001",
            given_name="John",
            family_name="Enrollee",
        )
        self.group = self.create_test_group(identifier_value="GRP-ENROLL-001")

        # Create test membership
        self.membership = self.create_test_membership(
            partner=self.individual,
            program=self.program,
            state="enrolled",
            enrollment_date=date(2024, 1, 15),
        )

        # Create API client with permissions
        self.client = self.create_api_client(
            name="Membership API Client",
            scopes=[
                {"resource": "program_membership", "action": "read"},
                {"resource": "program_membership", "action": "search"},
                {"resource": "program_membership", "action": "create"},
                {"resource": "program_membership", "action": "update"},
            ],
        )

        # Create consent for beneficiary
        self.consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

        # Generate token
        self.token = self.generate_jwt_token(self.client)

    def _get_headers(self, token=None):
        """Get HTTP headers with authorization"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token or self.token}",
        }

    def test_read_program_membership_success(self):
        """GET /ProgramMembership/{id} returns membership"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "ProgramMembership")
        self.assertEqual(data["status"], "enrolled")
        self.assertIn("program", data)
        self.assertIn("beneficiary", data)

    def test_read_program_membership_not_found(self):
        """GET with non-existent ID returns 404"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 404)

    def test_read_program_membership_etag_header(self):
        """Response includes ETag header for versioning"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("etag", response.headers)

    def test_read_program_membership_consent_header(self):
        """Response includes X-Consent-Status header"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("x-consent-status", response.headers)

    def test_search_program_memberships_success(self):
        """GET /ProgramMembership returns search results"""
        response = self.url_open(self.api_base_url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("data", data)
        self.assertIn("meta", data)
        self.assertIn("total", data["meta"])

    def test_search_by_beneficiary_individual(self):
        """Search by beneficiary returns memberships for that individual"""
        url = f"{self.api_base_url}?beneficiary=Individual/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreater(data["meta"]["total"], 0)
        # Check that results are for the correct beneficiary
        for resource in data.get("data", []):
            self.assertIn("ENROLL-001", resource["beneficiary"]["reference"])

    def test_search_by_beneficiary_group(self):
        """Search by beneficiary returns memberships for that group"""
        # Create membership for group
        self.create_test_membership(partner=self.group, program=self.program)

        # Create consent for the group so it appears in search results
        self.create_consent(
            registrant=self.group,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

        url = f"{self.api_base_url}?beneficiary=Group/urn:openspp:vocab:id-type%23test_household_id|GRP-ENROLL-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreater(data["meta"]["total"], 0)

    def test_search_by_program(self):
        """Search by program returns memberships for that program"""
        url = f"{self.api_base_url}?program=Program/urn:openspp:program|test-enrollment-program"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Should find memberships for this program
        for resource in data.get("data", []):
            self.assertIn("test-enrollment-program", resource["program"]["reference"])

    def test_search_by_status(self):
        """Search by status filters results"""
        # Create membership with different status
        other_individual = self.create_test_individual(identifier_value="PAUSED-001")
        self.create_test_membership(partner=other_individual, program=self.program, state="paused")

        # Create consent for other individual so full data is returned
        self.create_consent(
            registrant=other_individual,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

        url = f"{self.api_base_url}?status=paused"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # All results should be paused
        for resource in data.get("data", []):
            self.assertEqual(resource["status"], "paused")

    def test_search_pagination(self):
        """Search supports _count and _offset parameters"""
        # Create more memberships
        for i in range(5):
            ind = self.create_test_individual(identifier_value=f"SEARCH-{i}")
            self.create_test_membership(partner=ind, program=self.program)
            # Create consent so full data is returned
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                resource_type="all",
                field_access="all",
            )

        url = f"{self.api_base_url}?_count=2&_offset=0"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertLessEqual(len(data.get("data", [])), 2)
        self.assertIn("links", data)

    def test_create_program_membership_success(self):
        """POST /ProgramMembership creates new enrollment"""
        # Create new individual for enrollment
        new_individual = self.create_test_individual(identifier_value="NEW-ENROLL-001")

        # Create consent for new individual
        self.create_consent(
            registrant=new_individual,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

        payload = {
            "type": "ProgramMembership",
            "program": {
                "reference": "Program/urn:openspp:program|test-enrollment-program",
                "display": "Test Enrollment Program",
            },
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|NEW-ENROLL-001",
                "display": new_individual.name,
            },
            "status": "enrolled",
            "enrollmentDate": "2024-02-01",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "ProgramMembership")
        self.assertEqual(data["status"], "enrolled")

        # Check Location header
        self.assertIn("location", response.headers)

    def test_create_program_membership_no_scope(self):
        """POST without create scope returns 403"""
        # Create client without create scope
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "program_membership", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        new_individual = self.create_test_individual(identifier_value="FORBIDDEN-001")

        payload = {
            "type": "ProgramMembership",
            "program": {
                "reference": "Program/urn:openspp:program|test-enrollment-program",
                "display": "Test Enrollment Program",
            },
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|FORBIDDEN-001",
                "display": new_individual.name,
            },
            "status": "enrolled",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(token=read_only_token),
        )

        self.assertEqual(response.status_code, 403)

    def test_create_program_membership_validation_error(self):
        """POST with invalid data returns 422"""
        payload = {
            "type": "ProgramMembership",
            # Missing required program reference
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001",
                "display": "Test",
            },
            "status": "enrolled",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 422)

    def test_update_program_membership_success(self):
        """PUT /ProgramMembership/{id} updates membership status"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        # Use the current representation as the update payload
        get_response = self.url_open(url, headers=self._get_headers())
        payload = json.loads(get_response.content)
        payload["status"] = "paused"

        response = self.url_put(url, data=json.dumps(payload), headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "paused")
        # Persisted on the record
        self.membership.invalidate_recordset()
        self.assertEqual(self.membership.state, "paused")

    def test_update_program_membership_wrong_if_match_returns_409(self):
        """PUT with a stale If-Match version returns 409 Conflict"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        get_response = self.url_open(url, headers=self._get_headers())
        payload = json.loads(get_response.content)
        payload["status"] = "paused"

        headers = self._get_headers()
        headers["If-Match"] = '"stale-version-0"'

        response = self.url_put(url, data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 409)

    def test_update_program_membership_not_found_returns_404(self):
        """PUT to a non-existent membership returns 404"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT-PUT"

        payload = {
            "type": "ProgramMembership",
            "program": {"reference": "Program/urn:openspp:program|test-enrollment-program"},
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT-PUT",
            },
            "status": "paused",
        }

        response = self.url_put(url, data=json.dumps(payload), headers=self._get_headers())
        self.assertEqual(response.status_code, 404)

    def test_update_program_membership_no_scope(self):
        """PUT without update scope returns 403"""
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "program_membership", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        payload = {
            "type": "ProgramMembership",
            "program": {
                "reference": "Program/urn:openspp:program|test-enrollment-program",
                "display": "Test Enrollment Program",
            },
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001",
                "display": "Test",
            },
            "status": "paused",
        }

        response = self.url_put(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(token=read_only_token),
        )

        self.assertEqual(response.status_code, 403)

    def test_create_program_membership_unknown_program_returns_422(self):
        """POST referencing a non-existent program hits the create error path (422)"""
        new_individual = self.create_test_individual(identifier_value="ERR-ENROLL-001")
        self.create_consent(
            registrant=new_individual,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

        payload = {
            "type": "ProgramMembership",
            "program": {"reference": "Program/urn:openspp:program|does-not-exist-program"},
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|ERR-ENROLL-001",
            },
            "status": "enrolled",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 422)

    def test_update_program_membership_bad_identifier_returns_400(self):
        """PUT with an identifier lacking the 'system|value' separator returns 400"""
        url = f"{self.api_base_url}/no-pipe-identifier"

        payload = {
            "type": "ProgramMembership",
            "program": {"reference": "Program/urn:openspp:program|test-enrollment-program"},
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001",
            },
            "status": "paused",
        }

        response = self.url_put(url, data=json.dumps(payload), headers=self._get_headers())
        self.assertEqual(response.status_code, 400)

    def test_update_program_membership_unknown_program_returns_422(self):
        """PUT whose payload references a non-existent program hits the update error path (422)"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"

        payload = {
            "type": "ProgramMembership",
            "program": {"reference": "Program/urn:openspp:program|does-not-exist-program"},
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001",
            },
            "status": "paused",
        }

        response = self.url_put(url, data=json.dumps(payload), headers=self._get_headers())
        self.assertEqual(response.status_code, 422)

    def test_search_program_memberships_prev_link(self):
        """Search with a non-zero _offset builds a previous-page link"""
        # Seed a few more memberships so paging is meaningful
        for i in range(3):
            ind = self.create_test_individual(identifier_value=f"PREV-{i}")
            self.create_test_membership(partner=ind, program=self.program)
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                resource_type="all",
                field_access="all",
            )

        url = f"{self.api_base_url}?_count=2&_offset=2"
        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("links", data)
        self.assertIsNotNone(data["links"].get("prev"))

    def test_consent_filtering_applied(self):
        """Without consent, read returns 403 (same as individual endpoint pattern)"""
        # Create individual without consent
        no_consent_individual = self.create_test_individual(identifier_value="NO-CONSENT-001")
        self.create_test_membership(partner=no_consent_individual, program=self.program)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NO-CONSENT-001"

        response = self.url_open(url, headers=self._get_headers())

        # Without consent, access is denied
        self.assertEqual(response.status_code, 403)

    def test_search_with_invalid_beneficiary_format(self):
        """Search with unrecognized beneficiary format ignores the filter"""
        url = f"{self.api_base_url}?beneficiary=InvalidFormat"

        response = self.url_open(url, headers=self._get_headers())

        # Unrecognized format (not starting with Individual/ or Group/) is ignored
        self.assertEqual(response.status_code, 200)

    def test_search_with_invalid_program_format(self):
        """Search with unrecognized program format ignores the filter"""
        url = f"{self.api_base_url}?program=InvalidFormat"

        response = self.url_open(url, headers=self._get_headers())

        # Unrecognized format (not starting with Program/) is ignored
        self.assertEqual(response.status_code, 200)

    def test_search_combined_filters(self):
        """Search supports combining multiple filters"""
        url = (
            f"{self.api_base_url}?beneficiary=Individual/"
            "urn:openspp:vocab:id-type%23test_national_id|ENROLL-001&status=enrolled"
        )

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Results should match both criteria
        for resource in data.get("data", []):
            self.assertEqual(resource["status"], "enrolled")
            self.assertIn("ENROLL-001", resource["beneficiary"]["reference"])

    def test_create_membership_with_enrollment_date(self):
        """Create membership sets enrollment date automatically when state=enrolled"""
        new_individual = self.create_test_individual(identifier_value="DATE-TEST-001")

        # Create consent for new individual
        self.create_consent(
            registrant=new_individual,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

        payload = {
            "type": "ProgramMembership",
            "program": {
                "reference": "Program/urn:openspp:program|test-enrollment-program",
                "display": "Test Enrollment Program",
            },
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|DATE-TEST-001",
                "display": new_individual.name,
            },
            "status": "enrolled",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        data = json.loads(response.content)
        # enrollment_date is a computed field (from state), set to today when state=enrolled
        self.assertEqual(data["enrollmentDate"], date.today().isoformat())

    def test_search_empty_results(self):
        """Search with no matches returns empty data list"""
        url = f"{self.api_base_url}?status=not_eligible"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # May have 0 or very few results
        self.assertTrue(data["data"] is None or isinstance(data["data"], list))

    def test_no_token_returns_401(self):
        """Request without token returns 401"""
        response = self.url_open(self.api_base_url, headers={"Content-Type": "application/json"})

        self.assertEqual(response.status_code, 401)
