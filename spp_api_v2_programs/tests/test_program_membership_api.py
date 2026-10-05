# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ProgramMembership API endpoints"""

import json
from datetime import date
from unittest.mock import patch

from odoo.tools import mute_logger

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase

from ..services.program_membership_service import ProgramMembershipService

NATIONAL_ID = "urn:openspp:vocab:id-type#test_national_id"


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

    def _get_rejected(self, url):
        """GET a request the API answers with an error, without the error log it writes"""
        with mute_logger("odoo.http", "odoo.addons.spp_api_v2_programs.routers.program_membership"):
            return self.url_open(url, headers=self._get_headers())

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

    def _no_consent_required_token(self):
        """Token for a client with a legal basis (no consent needed), to test 404 behaviour

        Consent-requiring clients get 403 for an unknown beneficiary to prevent
        enumeration, as on the Individual endpoints.
        """
        client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[
                {"resource": "program_membership", "action": "read"},
                {"resource": "program_membership", "action": "update"},
            ],
            require_consent=False,
            legal_basis="public_interest",
        )
        return self.generate_jwt_token(client)

    def test_read_program_membership_not_found(self):
        """GET with non-existent ID returns 404 (for non-consent-requiring clients)"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT"

        response = self.url_open(url, headers=self._get_headers(token=self._no_consent_required_token()))

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
        """PUT to a non-existent membership returns 404 (for non-consent-requiring clients)"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT-PUT"
        token = self._no_consent_required_token()

        payload = {
            "type": "ProgramMembership",
            "program": {"reference": "Program/urn:openspp:program|test-enrollment-program"},
            "beneficiary": {
                "reference": "Individual/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT-PUT",
            },
            "status": "paused",
        }

        response = self.url_put(url, data=json.dumps(payload), headers=self._get_headers(token=token))
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
        """Search with unrecognized beneficiary format returns 400 instead of every membership"""
        url = f"{self.api_base_url}?beneficiary=InvalidFormat"

        response = self._get_rejected(url)

        # Unrecognized format (not starting with Individual/ or Group/) is rejected
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid beneficiary", json.loads(response.content)["detail"])

    def test_search_with_invalid_program_format(self):
        """Search with unrecognized program format returns 400 instead of every membership"""
        url = f"{self.api_base_url}?program=InvalidFormat"

        response = self._get_rejected(url)

        # Unrecognized format (not starting with Program/) is rejected
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid program", json.loads(response.content)["detail"])

    def test_search_with_beneficiary_missing_value_separator(self):
        """A beneficiary reference without system|value returns 400"""
        url = f"{self.api_base_url}?beneficiary=Individual/ENROLL-001"

        response = self._get_rejected(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid beneficiary", json.loads(response.content)["detail"])

    def test_search_with_program_missing_value_separator(self):
        """A program reference without system|value returns 400"""
        url = f"{self.api_base_url}?program=Program/test-enrollment-program"

        response = self._get_rejected(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid program", json.loads(response.content)["detail"])

    def test_search_with_unknown_beneficiary_is_empty(self):
        """A well-formed reference that matches nobody still returns an empty page"""
        url = f"{self.api_base_url}?beneficiary=Individual/urn:openspp:vocab:id-type%23test_national_id|NOBODY"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], [])

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

    def _duplicate_payload(self):
        return {
            "type": "ProgramMembership",
            "program": {"reference": "Program/urn:openspp:program|test-enrollment-program"},
            "beneficiary": {"reference": "Individual/urn:openspp:vocab:id-type#test_national_id|ENROLL-001"},
            "status": "enrolled",
        }

    def _assert_no_database_internals(self, detail):
        for leaked in ("duplicate key", "Key (", "partner_id", "program_id", "constraint"):
            self.assertNotIn(leaked, detail)

    def test_create_duplicate_membership_returns_409(self):
        """POST for a beneficiary already in the program returns 409 without database internals"""
        with mute_logger("odoo.http"):
            response = self.url_open(
                self.api_base_url,
                data=json.dumps(self._duplicate_payload()),
                headers=self._get_headers(),
            )

        self.assertEqual(response.status_code, 409)
        detail = json.loads(response.content)["detail"]
        self.assertIn("already a member", detail)
        self._assert_no_database_internals(detail)

    def test_create_duplicate_membership_race_returns_409(self):
        """When the pre-check misses (concurrent create), the database constraint still answers 409"""
        with (
            patch.object(ProgramMembershipService, "_find_existing_membership", return_value=None) as pre_check,
            mute_logger("odoo.sql_db", "odoo.http", "odoo.addons.spp_api_v2_programs.routers.program_membership"),
        ):
            response = self.url_open(
                self.api_base_url,
                data=json.dumps(self._duplicate_payload()),
                headers=self._get_headers(),
            )

        pre_check.assert_called_once()
        self.assertEqual(response.status_code, 409)
        detail = json.loads(response.content)["detail"]
        self.assertIn("already a member", detail)
        self._assert_no_database_internals(detail)
        # The transaction is still usable after the violation, and no second row was written
        self.env.invalidate_all()
        self.assertEqual(
            self.env["spp.program.membership"].search_count(
                [("partner_id", "=", self.individual.id), ("program_id", "=", self.program.id)]
            ),
            1,
        )

    def test_create_other_unique_violation_is_not_reported_as_duplicate(self):
        """A unique violation on another table during create is a generic error, not 'already a member'"""
        new_individual = self.create_test_individual(identifier_value="OTHER-UNIQUE-001")
        payload = self._duplicate_payload()
        payload["beneficiary"]["reference"] = "Individual/urn:openspp:vocab:id-type#test_national_id|OTHER-UNIQUE-001"
        membership_model = type(self.env["spp.program.membership"])

        def violate_another_constraint(*args, **kwargs):
            # Duplicate an existing system parameter key: a real UniqueViolation on ir_config_parameter
            self.env.cr.execute(
                "INSERT INTO ir_config_parameter (key, value) SELECT key, value FROM ir_config_parameter LIMIT 1"
            )

        with (
            patch.object(membership_model, "create", side_effect=violate_another_constraint),
            mute_logger("odoo.sql_db", "odoo.http", "odoo.addons.spp_api_v2_programs.routers.program_membership"),
        ):
            response = self.url_open(self.api_base_url, data=json.dumps(payload), headers=self._get_headers())

        self.assertEqual(response.status_code, 422)
        self.assertEqual(json.loads(response.content)["detail"], "Failed to create program membership")
        self.env.invalidate_all()
        self.assertFalse(self.env["spp.program.membership"].search([("partner_id", "=", new_individual.id)]))

    def test_create_unexpected_error_hides_exception_text(self):
        """An unexpected create error returns a generic 422 and is only logged"""
        self.create_test_individual(identifier_value="HIDE-ERR-001")
        payload = self._duplicate_payload()
        payload["beneficiary"]["reference"] = "Individual/urn:openspp:vocab:id-type#test_national_id|HIDE-ERR-001"

        with (
            patch.object(ProgramMembershipService, "create", side_effect=RuntimeError("internal detail 4242")),
            mute_logger("odoo.http"),
            self.assertLogs("odoo.addons.spp_api_v2_programs.routers.program_membership", "ERROR") as logs,
        ):
            response = self.url_open(self.api_base_url, data=json.dumps(payload), headers=self._get_headers())

        self.assertEqual(response.status_code, 422)
        self.assertEqual(json.loads(response.content)["detail"], "Failed to create program membership")
        self.assertIn("internal detail 4242", "\n".join(logs.output))

    def test_update_unexpected_error_hides_exception_text(self):
        """An unexpected PUT error returns a generic 422 and is only logged"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|ENROLL-001"
        payload = json.loads(self.url_open(url, headers=self._get_headers()).content)
        payload["status"] = "paused"

        with (
            patch.object(ProgramMembershipService, "update", side_effect=RuntimeError("internal detail 4343")),
            mute_logger("odoo.http"),
            self.assertLogs("odoo.addons.spp_api_v2_programs.routers.program_membership", "ERROR") as logs,
        ):
            response = self.url_put(url, data=json.dumps(payload), headers=self._get_headers())

        self.assertEqual(response.status_code, 422)
        self.assertEqual(json.loads(response.content)["detail"], "Failed to update program membership")
        self.assertIn("internal detail 4343", "\n".join(logs.output))

    def test_search_unexpected_error_hides_exception_text(self):
        """An unexpected search error returns a generic error and is only logged"""
        with (
            patch.object(ProgramMembershipService, "search", side_effect=RuntimeError("internal detail 4545")),
            mute_logger("odoo.http"),
            self.assertLogs("odoo.addons.spp_api_v2_programs.routers.program_membership", "ERROR") as logs,
        ):
            response = self.url_open(self.api_base_url, headers=self._get_headers())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.content)["detail"], "Failed to search program memberships")
        self.assertIn("internal detail 4545", "\n".join(logs.output))

    def test_search_huge_offset_is_rejected(self):
        """An _offset beyond what the database accepts is a validation error, not a database error text"""
        response = self._get_rejected(f"{self.api_base_url}?_offset=99999999999999999999")

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("bigint", response.text)
        self.assertNotIn("LINE", response.text)


class TestProgramMembershipPagingAPI(ApiV2HttpTestCase):
    """GET /ProgramMembership next links: followable, consent-aware, and no leaked total"""

    PROGRAM_REF = "Program/urn:openspp:program|paging-program"

    def setUp(self):
        super().setUp()
        self.program = self.create_test_program(name="Paging Program", target_type="individual")
        self.other_program = self.create_test_program(name="Other Paging Program", target_type="individual")
        self.client = self.create_api_client(
            name="Membership Paging Client",
            scopes=[
                {"resource": "program_membership", "action": "read"},
                {"resource": "program_membership", "action": "search"},
            ],
        )
        self.token = self.generate_jwt_token(self.client)

    def _consent(self, partner):
        self.create_consent(
            registrant=partner,
            grantee_partner=self.client.partner_id,
            resource_type="all",
            field_access="all",
        )

    def _enroll(self, value, program, consented=True):
        partner = self.env["res.partner"].search([("reg_ids.value", "=", value)], limit=1)
        if not partner:
            partner = self.create_test_individual(identifier_value=value)
            if consented:
                self._consent(partner)
        self.create_test_membership(partner=partner, program=program, state="enrolled")
        return partner

    def _get(self, url):
        response = self.url_open(url, headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def test_next_link_keeps_the_beneficiary_filter(self):
        """The '#' in the beneficiary's identifier type is encoded, so following next stays on that beneficiary"""
        self._enroll("PAGE-TWO-PROGRAMS", self.program)
        self._enroll("PAGE-TWO-PROGRAMS", self.other_program)
        self._enroll("PAGE-SOMEONE-ELSE", self.program)

        first = self._get(
            f"/api/v2/spp/ProgramMembership?beneficiary=Individual/{NATIONAL_ID.replace('#', '%23')}|PAGE-TWO-PROGRAMS"
            "&_count=1"
        )
        self.assertIn("%23", first["links"]["self"])
        second = self._get(first["links"]["next"])

        references = {m["beneficiary"]["reference"] for m in first["data"] + second["data"]}
        programs = {m["program"]["reference"] for m in first["data"] + second["data"]}
        self.assertEqual(references, {f"Individual/{NATIONAL_ID}|PAGE-TWO-PROGRAMS"})
        self.assertEqual(len(programs), 2)

    def test_consent_filtered_pages_cover_every_visible_membership_once(self):
        """Following next visits each consented member exactly once and then stops"""
        visible = set()
        for number in range(1, 7):
            value = f"PAGE-MEMBER-{number}"
            self._enroll(value, self.program, consented=number not in (2, 5))
            if number not in (2, 5):
                visible.add(f"Individual/{NATIONAL_ID}|{value}")

        seen = []
        url = f"/api/v2/spp/ProgramMembership?program={self.PROGRAM_REF.replace('|', '%7C')}&_count=2"
        for _page in range(10):
            body = self._get(url)
            seen.extend(m["beneficiary"]["reference"] for m in body["data"])
            url = body["links"].get("next")
            if not url:
                break

        self.assertIsNone(url)
        self.assertEqual(sorted(seen), sorted(visible))

    def test_hidden_beneficiary_past_the_end_is_not_counted(self):
        """beneficiary= of someone without consent, _offset=1: no data, total 0, no next"""
        self._enroll("PAGE-HIDDEN", self.program, consented=False)

        body = self._get(
            f"/api/v2/spp/ProgramMembership?beneficiary=Individual/{NATIONAL_ID.replace('#', '%23')}|PAGE-HIDDEN"
            "&_count=1&_offset=1"
        )

        self.assertEqual(body["data"], [])
        self.assertEqual(body["meta"]["total"], 0)
        self.assertIsNone(body["links"].get("next"))
