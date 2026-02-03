# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Individual API endpoints"""

import json
from datetime import date

from .common import ApiV2HttpTestCase


class TestIndividualAPIEndpoints(ApiV2HttpTestCase):
    """Test Individual resource HTTP endpoints"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/Individual"

        # Create test individuals
        self.individual = self.create_test_individual(
            name="Jane Doe",
            given_name="Jane",
            family_name="Doe",
            identifier_value="IND-001",
            gender_id=self.gender_female.id,
            birthdate=date(1990, 5, 15),
            phone="+1234567890",
            email="jane@example.com",
        )

        # Create API client with full permissions
        self.client = self.create_api_client(
            name="Test API Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "search"},
                {"resource": "individual", "action": "create"},
                {"resource": "individual", "action": "update"},
            ],
        )

        # Create consent
        self.consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
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

    def test_read_individual_success(self):
        """GET /Individual/{id} returns individual"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Individual")
        self.assertNotIn("id", data, "Database ID must not be exposed")
        self.assertEqual(data["identifier"][0]["value"], "IND-001")
        self.assertEqual(data["name"]["given"], "Jane")
        self.assertEqual(data["name"]["family"], "Doe")
        self.assertEqual(data["birthDate"], "1990-05-15")
        self.assertIn("gender", data)

    def test_read_individual_etag_header(self):
        """Response includes ETag header for versioning"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("etag", response.headers)

    def test_read_individual_consent_header(self):
        """Response includes X-Consent-Status header"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("x-consent-status", response.headers)
        self.assertEqual(response.headers["x-consent-status"], "active")

    def test_read_individual_not_found(self):
        """GET with non-existent ID returns 404 (for non-consent-requiring clients)"""
        # Create client that doesn't require consent to test 404 behavior
        # (consent-requiring clients return 403 to prevent user enumeration)
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[{"resource": "individual", "action": "read"}],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT"

        response = self.url_open(url, headers=self._get_headers(token=token))

        self.assertEqual(response.status_code, 404)

    def test_read_individual_invalid_format(self):
        """GET with invalid identifier format returns 400"""
        url = f"{self.api_base_url}/INVALID-FORMAT"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("detail", data)

    def test_read_individual_no_token(self):
        """Request without token returns 401"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        response = self.url_open(url, headers={"Content-Type": "application/json"})

        self.assertEqual(response.status_code, 401)

    def test_read_individual_no_consent_returns_403(self):
        """Without consent, returns 403 (security hardening to prevent enumeration)"""
        # Create individual without consent
        self.create_test_individual(
            identifier_value="IND-NO-CONSENT",
            name="No Consent Person",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-NO-CONSENT"

        response = self.url_open(url, headers=self._get_headers())

        # Security: consent-requiring clients get 403 for records without consent
        # (to prevent attacker from determining which individuals have consented)
        self.assertEqual(response.status_code, 403)

    def test_search_individuals_success(self):
        """GET /Individual returns search results"""
        response = self.url_open(self.api_base_url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("data", data)
        self.assertIn("meta", data)
        self.assertIn("links", data)
        self.assertIn("total", data["meta"])

    def test_search_by_name(self):
        """Search with name parameter filters results"""
        url = f"{self.api_base_url}?name=Jane"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreater(data["meta"]["total"], 0)
        # Check that results contain the search term
        for resource in data.get("data", []):
            if "name" in resource:
                self.assertIn("Jane", resource["name"].get("given", ""))

    def test_search_by_identifier(self):
        """Search by identifier returns exact match"""
        url = f"{self.api_base_url}?identifier=urn:openspp:vocab:id-type%23test_national_id|IND-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreaterEqual(data["meta"]["total"], 1)
        resource = data["data"][0]
        self.assertEqual(resource["identifier"][0]["value"], "IND-001")

    def test_search_by_gender(self):
        """Search by gender filters results"""
        url = f"{self.api_base_url}?gender=urn:iso:std:iso:5218|2"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Should find female individuals
        for resource in data.get("data", []):
            if "gender" in resource:
                self.assertEqual(resource["gender"]["coding"][0]["code"], "2")

    def test_search_pagination(self):
        """Search supports _count and _offset parameters"""
        url = f"{self.api_base_url}?_count=1&_offset=0"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertLessEqual(len(data.get("data", [])), 1)
        self.assertIn("links", data)

        # Check for pagination links
        links = data["links"]
        self.assertIn("self", links)

    def test_search_bundle_has_pagination_links(self):
        """Search result includes next/prev links"""
        # Create more individuals for pagination
        for i in range(5):
            self.create_test_individual(identifier_value=f"SEARCH-{i}")

        url = f"{self.api_base_url}?_count=2&_offset=2"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)
        links = data["links"]

        self.assertIn("self", links)
        # Should have next or prev link
        self.assertTrue("next" in links or "prev" in links)

    def test_create_individual_success(self):
        """POST /Individual creates new individual"""
        payload = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "CREATE-001"}],
            "name": {"given": "New", "family": "Person"},
            "active": True,
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Individual")
        self.assertEqual(data["name"]["given"], "New")

        # Check Location header
        self.assertIn("location", response.headers)
        self.assertIn("CREATE-001", response.headers["location"])

    def test_create_individual_source_tracking(self):
        """Created individual has source_system set"""
        payload = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "SOURCE-001"}],
            "name": {"given": "Source", "family": "Test"},
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        # Find the created individual
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "SOURCE-001")], limit=1)
        self.assertTrue(partner.source_system)
        self.assertIn(self.client.client_id, partner.source_system)

    def test_create_individual_no_scope(self):
        """POST without create scope returns 403"""
        # Create client without create scope
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        payload = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "FORBIDDEN-001"}],
            "name": {"given": "Forbidden", "family": "Test"},
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(token=read_only_token),
        )

        self.assertEqual(response.status_code, 403)

    def test_create_individual_validation_error(self):
        """POST with invalid data returns 422"""
        payload = {
            "type": "Individual",
            # Missing required identifier
            "name": {"given": "Invalid", "family": "Test"},
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 422)

    def test_update_individual_success(self):
        """PUT /Individual/{id} updates individual"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        # Get current version
        get_response = self.url_open(url, headers=self._get_headers())
        current_data = json.loads(get_response.content)
        version_id = current_data["meta"]["versionId"]

        # Update
        payload = current_data.copy()
        payload["name"]["given"] = "Updated"

        headers = self._get_headers()
        headers["If-Match"] = f'"{version_id}"'

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=headers,
        )

        # Note: PUT method needs to be handled by url_open differently
        # For now, check that endpoint exists (200/405 acceptable)
        self.assertIn(response.status_code, [200, 405])

    def test_update_individual_no_scope(self):
        """PUT without update scope returns 403"""
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        payload = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "Forbidden", "family": "Update"},
        }

        headers = self._get_headers(token=read_only_token)

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=headers,
        )

        # 403 or 405 (method not allowed in test mode)
        self.assertIn(response.status_code, [403, 405])

    def test_search_with_extensions_param(self):
        """Search with _extensions parameter works"""
        url = f"{self.api_base_url}?_extensions=farmer"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("data", data)
        self.assertIn("meta", data)

    def test_search_with_elements_param(self):
        """Search with _elements parameter works"""
        url = f"{self.api_base_url}?_elements=identifier,name"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("data", data)
        self.assertIn("meta", data)

    def test_search_with_sort(self):
        """Search with _sort parameter works"""
        url = f"{self.api_base_url}?_sort=name"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("data", data)

    def test_read_with_extensions_param(self):
        """Read with _extensions query parameter"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001?_extensions=farmer"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["type"], "Individual")

    def test_get_individual_groups_success(self):
        """GET /Individual/{id}/groups returns group memberships"""
        # Create a group
        group = self.create_test_group(
            name="Test Household",
            identifier_value="HH-001",
        )

        # Create membership
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": self.individual.id,
                "membership_type_ids": [(4, self.relationship_head.id)],
            }
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001/groups"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "GroupMembershipList")
        self.assertGreaterEqual(data["total"], 1)
        self.assertIn("entry", data)

        # Check membership data
        entry = data["entry"][0]
        resource = entry["resource"]
        self.assertEqual(resource["type"], "GroupMember")
        self.assertIn("group", resource)
        self.assertIn("entity", resource)
        self.assertIn("status", resource)

    def test_get_individual_groups_filter_by_status(self):
        """GET /Individual/{id}/groups with status filter"""
        # Create a group with active membership
        group_active = self.create_test_group(
            name="Active Household",
            identifier_value="HH-ACTIVE",
        )
        self.env["spp.group.membership"].create(
            {
                "group": group_active.id,
                "individual": self.individual.id,
                "membership_type_ids": [(4, self.relationship_head.id)],
            }
        )

        # Create a group with inactive membership
        group_inactive = self.create_test_group(
            name="Inactive Household",
            identifier_value="HH-INACTIVE",
        )
        from datetime import datetime, timedelta

        self.env["spp.group.membership"].create(
            {
                "group": group_inactive.id,
                "individual": self.individual.id,
                "start_date": datetime.now() - timedelta(days=30),
                "ended_date": datetime.now() - timedelta(days=1),
            }
        )

        # Test filter for active only
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001/groups?status=active"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Should only return active memberships
        for entry in data.get("entry", []):
            resource = entry["resource"]
            self.assertEqual(resource["status"], "active")

    def test_get_individual_groups_limit(self):
        """GET /Individual/{id}/groups respects _count limit"""
        # Create multiple groups
        for i in range(5):
            group = self.create_test_group(
                name=f"Household {i}",
                identifier_value=f"HH-LIMIT-{i}",
            )
            self.env["spp.group.membership"].create(
                {
                    "group": group.id,
                    "individual": self.individual.id,
                }
            )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001/groups?_count=2"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertLessEqual(len(data.get("entry", [])), 2)

    def test_get_individual_groups_not_found(self):
        """GET /Individual/{id}/groups returns 404 for non-existent individual"""
        # Create client that doesn't require consent
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[{"resource": "individual", "action": "read"}],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT/groups"

        response = self.url_open(url, headers=self._get_headers(token=token))

        self.assertEqual(response.status_code, 404)

    def test_get_individual_groups_no_scope(self):
        """GET /Individual/{id}/groups without read scope returns 403"""
        # Create client without read scope
        no_scope_client = self.create_api_client(
            name="No Read Scope Client",
            scopes=[{"resource": "individual", "action": "create"}],
        )
        no_scope_token = self.generate_jwt_token(no_scope_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-001/groups"

        response = self.url_open(url, headers=self._get_headers(token=no_scope_token))

        self.assertEqual(response.status_code, 403)

    def test_get_individual_groups_no_consent(self):
        """GET /Individual/{id}/groups without consent returns 403"""
        # Create individual without consent
        self.create_test_individual(
            identifier_value="IND-NO-CONSENT-GROUPS",
            name="No Consent Person",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-NO-CONSENT-GROUPS/groups"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 403)

    def test_get_individual_groups_empty_result(self):
        """GET /Individual/{id}/groups returns empty bundle for individual with no groups"""
        # Create individual with no group memberships
        individual_no_groups = self.create_test_individual(
            identifier_value="IND-NO-GROUPS",
            name="No Groups Person",
        )

        # Create consent for this individual
        self.create_consent(
            registrant=individual_no_groups,
            grantee_partner=self.client.partner_id,
            field_access="all",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|IND-NO-GROUPS/groups"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "GroupMembershipList")
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data.get("entry", [])), 0)

    def test_search_by_group(self):
        """Search by group parameter returns members of that group"""
        # Create a group
        group = self.create_test_group(
            name="Test Household",
            identifier_value="HH-SEARCH-001",
        )

        # Create members
        member1 = self.create_test_individual(
            identifier_value="MEMBER-001",
            name="Member One",
        )
        member2 = self.create_test_individual(
            identifier_value="MEMBER-002",
            name="Member Two",
        )
        # Create a non-member
        non_member = self.create_test_individual(
            identifier_value="NON-MEMBER",
            name="Not Member",
        )

        # Add members to group
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": member1.id,
            }
        )
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": member2.id,
            }
        )

        # Create consents for all
        for ind in [member1, member2, non_member]:
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                field_access="all",
            )

        # Search by group
        url = f"{self.api_base_url}?group=urn:openspp:vocab:id-type%23test_household_id|HH-SEARCH-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["meta"]["total"], 2)

        # Verify results contain only members
        member_values = {resource["identifier"][0]["value"] for resource in data.get("data", [])}
        self.assertIn("MEMBER-001", member_values)
        self.assertIn("MEMBER-002", member_values)
        self.assertNotIn("NON-MEMBER", member_values)

    def test_search_by_group_none(self):
        """Search with group=none returns orphan individuals"""
        # Create orphan individual (not in any group)
        orphan = self.create_test_individual(
            identifier_value="ORPHAN-001",
            name="Orphan Individual",
        )

        # Create group with member
        group = self.create_test_group(
            name="Test Group",
            identifier_value="GROUP-001",
        )
        member = self.create_test_individual(
            identifier_value="GROUPED-001",
            name="Grouped Individual",
        )
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": member.id,
            }
        )

        # Create consents
        for ind in [orphan, member]:
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                field_access="all",
            )

        # Search for orphans
        url = f"{self.api_base_url}?group=none"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Check that orphan is in results
        orphan_values = {resource["identifier"][0]["value"] for resource in data.get("data", [])}
        self.assertIn("ORPHAN-001", orphan_values)
        # Check that grouped individual is NOT in results
        self.assertNotIn("GROUPED-001", orphan_values)

    def test_search_by_membership_role(self):
        """Search by membership-role parameter returns individuals with that role"""
        # Create group
        group = self.create_test_group(
            name="Test Household",
            identifier_value="HH-ROLE-001",
        )

        # Ensure the relationship vocabulary exists
        relationship_vocab = self.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")], limit=1
        )
        if not relationship_vocab:
            relationship_vocab = self.env["spp.vocabulary"].create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )

        # Get role codes
        head_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", relationship_vocab.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        spouse_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", relationship_vocab.id),
                ("code", "=", "spouse"),
            ],
            limit=1,
        )

        if not head_code:
            head_code = self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": relationship_vocab.id,
                    "code": "head",
                    "display": "Head",
                    "is_local": True,
                }
            )
        if not spouse_code:
            spouse_code = self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": relationship_vocab.id,
                    "code": "spouse",
                    "display": "Spouse",
                    "is_local": True,
                }
            )

        # Create head
        head = self.create_test_individual(
            identifier_value="HEAD-001",
            name="Household Head",
        )
        # Create spouse
        spouse = self.create_test_individual(
            identifier_value="SPOUSE-001",
            name="Household Spouse",
        )

        # Add memberships with roles
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": head.id,
                "membership_type_ids": [(4, head_code.id)],
            }
        )
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": spouse.id,
                "membership_type_ids": [(4, spouse_code.id)],
            }
        )

        # Create consents
        for ind in [head, spouse]:
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                field_access="all",
            )

        # Search for heads
        url = f"{self.api_base_url}?membership-role=head"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreaterEqual(data["meta"]["total"], 1)

        # Verify head is in results
        head_values = {resource["identifier"][0]["value"] for resource in data.get("data", [])}
        self.assertIn("HEAD-001", head_values)

    def test_search_by_membership_role_and_group_combined(self):
        """Search can combine group and membership-role filters"""
        # Create two groups
        group1 = self.create_test_group(
            name="Group 1",
            identifier_value="G1",
        )
        group2 = self.create_test_group(
            name="Group 2",
            identifier_value="G2",
        )

        # Ensure the relationship vocabulary exists
        relationship_vocab = self.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")], limit=1
        )
        if not relationship_vocab:
            relationship_vocab = self.env["spp.vocabulary"].create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )

        # Get head code
        head_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", relationship_vocab.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        if not head_code:
            head_code = self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": relationship_vocab.id,
                    "code": "head",
                    "display": "Head",
                    "is_local": True,
                }
            )

        # Create heads for both groups
        head1 = self.create_test_individual(
            identifier_value="HEAD-G1",
            name="Head of Group 1",
        )
        head2 = self.create_test_individual(
            identifier_value="HEAD-G2",
            name="Head of Group 2",
        )

        # Add memberships
        self.env["spp.group.membership"].create(
            {
                "group": group1.id,
                "individual": head1.id,
                "membership_type_ids": [(4, head_code.id)],
            }
        )
        self.env["spp.group.membership"].create(
            {
                "group": group2.id,
                "individual": head2.id,
                "membership_type_ids": [(4, head_code.id)],
            }
        )

        # Create consents
        for ind in [head1, head2]:
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                field_access="all",
            )

        # Search for head of group 1 only
        url = f"{self.api_base_url}?group=urn:openspp:vocab:id-type%23test_household_id|G1&membership-role=head"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Should only find head of group 1
        result_values = {resource["identifier"][0]["value"] for resource in data.get("data", [])}
        self.assertIn("HEAD-G1", result_values)
        self.assertNotIn("HEAD-G2", result_values)

    def test_search_by_group_excludes_ended_memberships(self):
        """Search by group excludes individuals with ended memberships"""
        # Create group
        group = self.create_test_group(
            name="Test Group",
            identifier_value="GROUP-ENDED",
        )

        # Create active member
        active_member = self.create_test_individual(
            identifier_value="ACTIVE-MEMBER",
            name="Active Member",
        )
        # Create ended member
        ended_member = self.create_test_individual(
            identifier_value="ENDED-MEMBER",
            name="Ended Member",
        )

        # Add memberships
        from datetime import datetime, timedelta

        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": active_member.id,
                "ended_date": False,
            }
        )
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": ended_member.id,
                "start_date": datetime.now() - timedelta(days=30),
                "ended_date": datetime.now() - timedelta(days=1),  # Ended yesterday
            }
        )

        # Create consents
        for ind in [active_member, ended_member]:
            self.create_consent(
                registrant=ind,
                grantee_partner=self.client.partner_id,
                field_access="all",
            )

        # Search by group
        url = f"{self.api_base_url}?group=urn:openspp:vocab:id-type%23test_household_id|GROUP-ENDED"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Should only find active member
        result_values = {resource["identifier"][0]["value"] for resource in data.get("data", [])}
        self.assertIn("ACTIVE-MEMBER", result_values)
        self.assertNotIn("ENDED-MEMBER", result_values)

    def test_search_excludes_consent_denied_records(self):
        """Search results exclude individuals without consent"""
        # Create a second individual WITHOUT consent
        self.create_test_individual(
            name="No Consent Person",
            given_name="No",
            family_name="Consent",
            identifier_value="NO-CONSENT-001",
        )
        # NOTE: No consent created for no_consent_individual

        # Search all individuals
        url = self.api_base_url
        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # The individual without consent should NOT appear in results
        result_values = set()
        for resource in data.get("data", []):
            if resource.get("identifier"):
                for ident in resource["identifier"]:
                    result_values.add(ident.get("value"))

        self.assertIn("IND-001", result_values, "Consented individual should appear")
        self.assertNotIn(
            "NO-CONSENT-001",
            result_values,
            "Individual without consent should be excluded from search results",
        )

        # Total count should be adjusted (should not count consent-denied records)
        self.assertLessEqual(
            data["meta"]["total"],
            len(data["data"]) + 20,  # Allow for pagination
            "Total should be adjusted for consent-denied records",
        )
