# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Program API endpoints"""

import json

from .common import ApiV2HttpTestCase


class TestProgramAPIEndpoints(ApiV2HttpTestCase):
    """Test Program resource HTTP endpoints"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/Program"

        # Create test programs
        self.program = self.create_test_program(
            name="Cash Transfer Program",
            target_type="group",
            state="active",
            description="Monthly cash transfers for vulnerable households",
        )

        # Create API client with read permissions
        self.client = self.create_api_client(
            name="Program API Client",
            scopes=[
                {"resource": "program", "action": "read"},
                {"resource": "program", "action": "search"},
            ],
        )

        # Generate token
        self.token = self.generate_jwt_token(self.client)

    def _get_headers(self, token=None):
        """Get HTTP headers with authorization"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token or self.token}",
        }

    def test_read_program_success(self):
        """GET /Program/{id} returns program"""
        url = f"{self.api_base_url}/urn:openspp:program|cash-transfer-program"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Program")
        self.assertNotIn("id", data, "Database ID must not be exposed")
        self.assertEqual(data["name"], "Cash Transfer Program")
        self.assertEqual(data["targetType"], "group")
        self.assertTrue(data["active"])

    def test_read_program_not_found(self):
        """GET with non-existent ID returns 404"""
        url = f"{self.api_base_url}/urn:openspp:program|nonexistent"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 404)

    def test_read_program_invalid_identifier_format(self):
        """GET with invalid identifier format returns 400"""
        url = f"{self.api_base_url}/invalid-format"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)

    def test_read_program_etag_header(self):
        """Response includes ETag header for versioning"""
        url = f"{self.api_base_url}/urn:openspp:program|cash-transfer-program"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("etag", response.headers)

    def test_read_program_no_token(self):
        """Request without token returns 401"""
        url = f"{self.api_base_url}/urn:openspp:program|cash-transfer-program"

        response = self.url_open(url, headers={"Content-Type": "application/json"})

        self.assertEqual(response.status_code, 401)

    def test_search_programs_success(self):
        """GET /Program returns search results"""
        response = self.url_open(self.api_base_url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("meta", data)
        self.assertIn("total", data["meta"])
        self.assertIn("data", data)

    def test_search_by_name(self):
        """Search with name parameter filters results"""
        url = f"{self.api_base_url}?name=Cash"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreater(data["meta"]["total"], 0)
        # Check that results contain the search term
        for resource in data.get("data", []):
            self.assertIn("Cash", resource["name"])

    def test_search_by_status_active(self):
        """Search by status=active returns only active programs"""
        # Create ended program
        self.create_test_program(name="Ended Program", state="ended", active=False)

        url = f"{self.api_base_url}?status=active"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # All results should be active
        for resource in data.get("data", []):
            self.assertTrue(resource["active"])

    def test_search_by_status_ended(self):
        """Search by status=ended returns only ended programs"""
        # Create ended program
        from datetime import date

        self.create_test_program(
            name="Ended Program",
            state="ended",
            active=False,
            date_ended=date(2023, 12, 31),
        )

        url = f"{self.api_base_url}?status=ended"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreater(data["meta"]["total"], 0)

    def test_search_by_target_type(self):
        """Search by targetType filters results"""
        # Create individual-targeted program
        self.create_test_program(name="Individual Program", target_type="individual")

        url = f"{self.api_base_url}?targetType=individual"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # All results should target individuals
        for resource in data.get("data", []):
            self.assertEqual(resource["targetType"], "individual")

    def test_search_pagination(self):
        """Search supports _count and _offset parameters"""
        # Create multiple programs
        for i in range(5):
            self.create_test_program(name=f"Program {i}")

        url = f"{self.api_base_url}?_count=2&_offset=0"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertLessEqual(len(data.get("data", [])), 2)

        # Pagination links are in 'links' field, not meta
        self.assertIn("links", data)
        self.assertIn("self", data["links"])

    def test_search_bundle_has_pagination_links(self):
        """Search result includes next/prev links"""
        # Create more programs for pagination
        for i in range(5):
            self.create_test_program(name=f"Pagination Test {i}")

        url = f"{self.api_base_url}?_count=2&_offset=2"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        self.assertIn("links", data)
        self.assertIn("self", data["links"])
        # Should have next or previous link
        self.assertTrue(data["links"].get("next") or data["links"].get("prev"))

    def test_programs_are_read_only_no_post(self):
        """POST /Program is not allowed (programs are read-only)"""
        payload = {
            "resourceType": "Program",
            "identifier": [{"system": "urn:openspp:program", "value": "new-program"}],
            "name": "New Program",
            "targetType": "individual",
            "active": True,
            "type": {
                "coding": [
                    {
                        "system": "urn:openspp:vocab:program-type",
                        "code": "cash-transfer",
                    }
                ]
            },
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Should not allow POST (405 or 404)
        self.assertIn(response.status_code, [404, 405])

    def test_programs_are_read_only_no_put(self):
        """PUT /Program/{id} is not allowed (programs are read-only)"""
        url = f"{self.api_base_url}/urn:openspp:program|cash-transfer-program"

        payload = {
            "resourceType": "Program",
            "identifier": [{"system": "urn:openspp:program", "value": "cash-transfer-program"}],
            "name": "Updated Program Name",
            "targetType": "group",
            "active": True,
            "type": {
                "coding": [
                    {
                        "system": "urn:openspp:vocab:program-type",
                        "code": "cash-transfer",
                    }
                ]
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # Should not allow PUT (405 or 404)
        self.assertIn(response.status_code, [404, 405])

    def test_programs_are_read_only_no_delete(self):
        """DELETE /Program/{id} is not allowed (programs are read-only)"""
        # The program router only defines GET endpoints.
        # A DELETE request to a GET-only route returns 405 Method Not Allowed.
        # url_open doesn't support DELETE directly, so we verify that only
        # GET endpoints are registered on the program router.
        from ..routers.program import program_router

        methods = set()
        for route in program_router.routes:
            methods.update(getattr(route, "methods", set()))
        self.assertNotIn("DELETE", methods, "Program router must not allow DELETE")

    def test_search_with_multiple_filters(self):
        """Search supports combining multiple parameters"""
        url = f"{self.api_base_url}?status=active&targetType=group&name=Cash"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Results should match all criteria
        for resource in data.get("data", []):
            self.assertTrue(resource["active"])
            self.assertEqual(resource["targetType"], "group")
            self.assertIn("Cash", resource["name"])

    def test_search_empty_results(self):
        """Search with no matches returns empty data list"""
        url = f"{self.api_base_url}?name=NonexistentProgramName"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["meta"]["total"], 0)
        self.assertTrue(data["data"] is None or len(data["data"]) == 0)

    def test_search_default_pagination(self):
        """Search uses default pagination when not specified"""
        response = self.url_open(self.api_base_url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Default page size should be 20 or less
        if data.get("data"):
            self.assertLessEqual(len(data["data"]), 20)

    def test_read_program_metadata(self):
        """Read program includes complete metadata"""
        url = f"{self.api_base_url}/urn:openspp:program|cash-transfer-program"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        self.assertIn("meta", data)
        self.assertIn("versionId", data["meta"])
        self.assertIn("lastUpdated", data["meta"])

    def test_search_results_have_metadata(self):
        """Search results include metadata"""
        response = self.url_open(self.api_base_url, headers=self._get_headers())

        data = json.loads(response.content)

        # Verify search metadata is present
        self.assertIn("meta", data)
        self.assertIn("total", data["meta"])

        # Verify data contains resources directly
        if data.get("data"):
            for resource in data["data"]:
                self.assertIn("type", resource)
                self.assertEqual(resource["type"], "Program")
