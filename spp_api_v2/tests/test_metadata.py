# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Metadata endpoint"""

import json

from .common import ApiV2HttpTestCase


class TestMetadataEndpoint(ApiV2HttpTestCase):
    """Test metadata endpoint"""

    def test_metadata_endpoint_public(self):
        """GET /metadata is public (no authentication required)"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

    def test_metadata_structure(self):
        """Metadata response has required fields"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)

        # Check top-level fields
        self.assertEqual(data["name"], "OpenSPP API")
        self.assertIn("version", data)
        self.assertIn("resources", data)
        self.assertIn("extensions", data)
        self.assertIn("authentication", data)
        self.assertIn("docs", data)

    def test_metadata_version(self):
        """Metadata includes version information"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)

        self.assertIsInstance(data["version"], str)
        # Version should be non-empty
        self.assertTrue(len(data["version"]) > 0)

    def test_metadata_resources(self):
        """Metadata includes core resources"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)

        # Check that core resources are present
        self.assertIn("Individual", data["resources"])
        self.assertIn("Group", data["resources"])
        self.assertIn("Program", data["resources"])
        self.assertIn("ProgramMembership", data["resources"])

    def test_individual_resource_metadata(self):
        """Individual resource has operations and search params"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)
        individual = data["resources"]["Individual"]

        # Check operations
        self.assertIn("operations", individual)
        self.assertIn("read", individual["operations"])
        self.assertIn("search", individual["operations"])
        self.assertIn("create", individual["operations"])
        self.assertIn("update", individual["operations"])
        self.assertIn("patch", individual["operations"])

        # Check search params
        self.assertIn("searchParams", individual)
        search_params = individual["searchParams"]
        self.assertIn("identifier", search_params)
        self.assertIn("name", search_params)
        self.assertIn("birthdate", search_params)
        self.assertIn("gender", search_params)
        self.assertIn("address", search_params)
        self.assertIn("group", search_params)

    def test_group_resource_metadata(self):
        """Group resource has operations and search params"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)
        group = data["resources"]["Group"]

        # Check operations
        self.assertIn("operations", group)
        self.assertIn("read", group["operations"])
        self.assertIn("search", group["operations"])
        self.assertIn("create", group["operations"])
        self.assertIn("update", group["operations"])
        self.assertIn("patch", group["operations"])

        # Check search params
        self.assertIn("searchParams", group)
        search_params = group["searchParams"]
        self.assertIn("identifier", search_params)
        self.assertIn("name", search_params)
        self.assertIn("type", search_params)
        self.assertIn("member", search_params)

    def test_program_resource_metadata(self):
        """Program resource is read-only"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)
        program = data["resources"]["Program"]

        # Program should only have read and search
        self.assertIn("operations", program)
        self.assertIn("read", program["operations"])
        self.assertIn("search", program["operations"])
        self.assertNotIn("create", program["operations"])
        self.assertNotIn("update", program["operations"])

        # Check search params
        self.assertIn("searchParams", program)
        search_params = program["searchParams"]
        self.assertIn("identifier", search_params)
        self.assertIn("name", search_params)
        self.assertIn("status", search_params)
        self.assertIn("type", search_params)
        self.assertIn("targetType", search_params)

    def test_program_membership_resource_metadata(self):
        """ProgramMembership resource has full CRUD operations"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)
        membership = data["resources"]["ProgramMembership"]

        # Check operations
        self.assertIn("operations", membership)
        self.assertIn("read", membership["operations"])
        self.assertIn("search", membership["operations"])
        self.assertIn("create", membership["operations"])
        self.assertIn("update", membership["operations"])

        # Check search params
        self.assertIn("searchParams", membership)
        search_params = membership["searchParams"]
        self.assertIn("beneficiary", search_params)
        self.assertIn("program", search_params)
        self.assertIn("status", search_params)

    def test_metadata_extensions(self):
        """Extensions list is present"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)

        self.assertIn("extensions", data)
        self.assertIsInstance(data["extensions"], list)
        # Extensions may be empty if no extension modules are installed

    def test_metadata_authentication(self):
        """Authentication metadata is present"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)

        self.assertIn("authentication", data)
        auth = data["authentication"]

        self.assertEqual(auth["type"], "oauth2")
        self.assertIn("tokenEndpoint", auth)
        self.assertIn("grantTypes", auth)
        self.assertIn("client_credentials", auth["grantTypes"])

    def test_metadata_docs_url(self):
        """Documentation URL is present"""
        url = "/api/v2/spp/metadata"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)

        self.assertIn("docs", data)
        self.assertEqual(data["docs"], "/api/v2/spp/docs")
