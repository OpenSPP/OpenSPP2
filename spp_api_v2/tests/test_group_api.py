# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Group API endpoints"""

import json

from .common import ApiV2HttpTestCase


class TestGroupAPIEndpoints(ApiV2HttpTestCase):
    """Test Group resource HTTP endpoints"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/Group"

        # Create test individuals for group members
        self.individual1 = self.create_test_individual(
            name="John Smith",
            identifier_value="IND-001",
        )
        self.individual2 = self.create_test_individual(
            name="Jane Smith",
            identifier_value="IND-002",
        )

        # Create test group
        self.group = self.create_test_group(
            name="Smith Household",
            identifier_value="HH-001",
            members=[
                (self.individual1, self.relationship_head),
                (self.individual2, None),
            ],
        )

        # Create API client with full permissions
        self.client = self.create_api_client(
            name="Test API Client",
            scopes=[
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "search"},
                {"resource": "group", "action": "create"},
                {"resource": "group", "action": "update"},
            ],
        )

        # Create consent
        self.consent = self.create_consent(
            registrant=self.group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
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

    def test_read_group_success(self):
        """GET /Group/{id} returns group"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Group")
        self.assertNotIn("id", data, "Database ID must not be exposed")
        self.assertEqual(data["identifier"][0]["value"], "HH-001")
        self.assertEqual(data["name"], "Smith Household")
        self.assertEqual(data["type"], "Group")
        self.assertIn("member", data)
        self.assertEqual(data["quantity"], 2)

    def test_read_group_members_have_references(self):
        """Group members use Individual references"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)
        members = data["member"]

        # Check member references
        for member in members:
            self.assertIn("entity", member)
            self.assertIn("reference", member["entity"])
            self.assertTrue(member["entity"]["reference"].startswith("Individual/"))
            self.assertIn("display", member["entity"])

    def test_read_group_member_with_role(self):
        """Member roles are included"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)
        members = data["member"]

        # Find head of household
        head = None
        for member in members:
            if "role" in member:
                if member["role"]["coding"][0]["code"] == "head":
                    head = member
                    break

        self.assertIsNotNone(head, "Should have head of household")
        # Display text may vary depending on vocabulary data ("Head" or "Head of Household")
        self.assertIn("Head", head["role"]["coding"][0]["display"])

    def test_read_group_not_found(self):
        """GET with non-existent ID returns 404 (for non-consent-requiring clients)"""
        # Create client that doesn't require consent to test 404 behavior
        # (consent-requiring clients return 403 to prevent user enumeration)
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[{"resource": "group", "action": "read"}],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_national_id|NONEXISTENT"

        response = self.url_open(url, headers=self._get_headers(token=token))

        self.assertEqual(response.status_code, 404)

    def test_read_group_no_identifiers_returns_404(self):
        """GET group without valid identifiers returns 404"""
        no_id_group = self.create_test_group(
            name="Will Lose IDs Group",
            identifier_value="WILL-LOSE-GRP-001",
        )

        no_consent_client = self.create_api_client(
            name="No Consent Client For Group 404",
            scopes=[{"resource": "group", "action": "read"}],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        # Delete all registry IDs to simulate missing identifiers
        no_id_group.reg_ids.unlink()

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|WILL-LOSE-GRP-001"
        response = self.url_open(url, headers=self._get_headers(token=token))

        # Partner's identifier was deleted, so lookup by identifier returns 404
        self.assertEqual(response.status_code, 404)

    def test_read_group_invalid_format(self):
        """GET with invalid identifier format returns 400"""
        url = f"{self.api_base_url}/INVALID-FORMAT"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)

    def test_read_group_no_token(self):
        """Request without token returns 401"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers={"Content-Type": "application/json"})

        self.assertEqual(response.status_code, 401)

    def test_read_group_no_consent_returns_403(self):
        """Without consent, returns 403 (security hardening to prevent enumeration)"""
        # Create group without consent
        self.create_test_group(
            identifier_value="HH-NO-CONSENT",
            name="No Consent Group",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-NO-CONSENT"

        response = self.url_open(url, headers=self._get_headers())

        # Security: consent-requiring clients get 403 for records without consent
        # (to prevent attacker from determining which groups have consented)
        self.assertEqual(response.status_code, 403)

    def test_search_groups_success(self):
        """GET /Group returns search results"""
        response = self.url_open(self.api_base_url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("meta", data)
        self.assertIn("total", data["meta"])
        self.assertIn("data", data)

    def test_search_by_name(self):
        """Search with name parameter filters results"""
        url = f"{self.api_base_url}?name=Smith"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreater(data["meta"]["total"], 0)

    def test_search_by_identifier(self):
        """Search by identifier returns exact match"""
        url = f"{self.api_base_url}?identifier=urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertGreaterEqual(data["meta"]["total"], 1)
        resource = data["data"][0]
        self.assertEqual(resource["identifier"][0]["value"], "HH-001")

    def test_search_by_member(self):
        """Search by member reference"""
        url = f"{self.api_base_url}?member=Individual/urn:openspp:vocab:id-type%23test_national_id|IND-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Should find groups with this member
        self.assertGreaterEqual(data["meta"]["total"], 1)

    def test_search_pagination(self):
        """Search supports _count and _offset parameters"""
        url = f"{self.api_base_url}?_count=1&_offset=0"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertLessEqual(len(data.get("data", [])), 1)
        self.assertIn("links", data)

    def test_create_group_success(self):
        """POST /Group creates new group"""
        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-CREATE-001",
                }
            ],
            "name": "New Household",
            "type": "Group",
            "active": True,
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "Group")
        self.assertEqual(data["name"], "New Household")

        # Check Location header
        self.assertIn("location", response.headers)
        self.assertIn("HH-CREATE-001", response.headers["location"])

    def test_create_group_with_members(self):
        """POST /Group with members creates group memberships"""
        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-CREATE-002",
                }
            ],
            "name": "Group with Members",
            "type": "Group",
            "member": [
                {
                    "entity": {
                        "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-001",
                        "display": "John Smith",
                    },
                    "role": {
                        "coding": [
                            {
                                "system": "urn:test:relationship",
                                "code": "head",
                                "display": "Head",
                            }
                        ]
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        # Find the created group
        group = self.env["res.partner"].search([("reg_ids.value", "=", "HH-CREATE-002")], limit=1)
        self.assertTrue(group)

        # Check members were created
        # Note: During group creation, the API creates spp.registry.relationship records
        # The $add-member operation uses spp.group.membership instead
        memberships = self.env["spp.group.membership"].search([("group", "=", group.id)])
        relationships = self.env["spp.registry.relationship"].search([("destination", "=", group.id)])
        # Either memberships or relationships should be created
        self.assertTrue(
            len(memberships) > 0 or len(relationships) > 0,
            "No members or relationships created",
        )

    def test_create_group_source_tracking(self):
        """Created group has source_system set"""
        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-SOURCE-001",
                }
            ],
            "name": "Source Test Group",
            "type": "Group",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        # Find the created group
        group = self.env["res.partner"].search([("reg_ids.value", "=", "HH-SOURCE-001")], limit=1)
        self.assertTrue(group.source_system)
        self.assertIn(self.client.client_id, group.source_system)

    def test_create_group_no_scope(self):
        """POST without create scope returns 403"""
        # Create client without create scope
        read_only_client = self.create_api_client(
            name="Read Only Client",
            scopes=[{"resource": "group", "action": "read"}],
        )
        read_only_token = self.generate_jwt_token(read_only_client)

        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-FORBIDDEN-001",
                }
            ],
            "name": "Forbidden Group",
            "type": "Group",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(token=read_only_token),
        )

        self.assertEqual(response.status_code, 403)

    def test_create_group_validation_error(self):
        """POST with invalid data returns 422"""
        payload = {
            "resourceType": "Group",
            # Missing required identifier
            "name": "Invalid Group",
            "type": "Group",
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 422)

    def test_read_group_etag_header(self):
        """Response includes ETag header for versioning"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("etag", response.headers)

    def test_read_group_consent_header(self):
        """Response includes X-Consent-Status header"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("x-consent-status", response.headers)

    def test_search_with_sort(self):
        """Search with _sort parameter works"""
        url = f"{self.api_base_url}?_sort=name"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("data", data)

    def test_create_group_with_address(self):
        """POST /Group with address creates location"""
        payload = {
            "resourceType": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-CREATE-003",
                }
            ],
            "name": "Group with Address",
            "type": "Group",
            "address": [
                {
                    "type": "physical",
                    "line": ["123 Main St"],
                    "city": "Test City",
                    "state": "Test State",
                    "country": "TC",
                    "postalCode": "12345",
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        data = json.loads(response.content)
        self.assertIn("address", data)
        self.assertEqual(data["address"][0]["city"], "Test City")

    def test_add_member_success(self):
        """POST /Group/{id}/$add-member adds member to group"""
        # Create a new individual to add
        self.create_test_individual(
            name="Bob Smith",
            identifier_value="IND-003",
        )

        # Create a new group without this member
        test_group = self.create_test_group(
            name="New Household",
            identifier_value="HH-002",
        )

        # Create consent for this group
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-002/$add-member"
        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-003",
                "display": "Bob Smith",
            },
            "role": {
                "coding": [
                    {
                        "system": "urn:test:relationship",
                        "code": "head",
                        "display": "Head of Household",
                    }
                ]
            },
            "startDate": "2024-01-15",
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "GroupMember")
        self.assertIn("group", data)
        self.assertIn("HH-002", data["group"]["reference"])
        self.assertIn("entity", data)
        self.assertIn("IND-003", data["entity"]["reference"])
        self.assertEqual(data["status"], "active")
        self.assertIn("role", data)
        self.assertEqual(data["role"]["coding"][0]["code"], "head")

    def test_add_member_already_exists(self):
        """Adding existing member returns 409 Conflict"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$add-member"
        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-001",
                "display": "John Smith",
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 409)

    def test_add_member_invalid_individual(self):
        """Adding non-existent individual returns 404"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$add-member"
        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|NON-EXISTENT",
                "display": "Ghost Person",
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 404)

    def test_add_member_no_permission(self):
        """Adding member without update permission returns 403"""
        # Create client without update permission
        client = self.create_api_client(
            name="Read Only Client",
            scopes=[
                {"resource": "group", "action": "read"},
            ],
        )
        token = self.generate_jwt_token(client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$add-member"
        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-002",
                "display": "Jane Smith",
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(token),
        )

        self.assertEqual(response.status_code, 403)

    def test_remove_member_success(self):
        """POST /Group/{id}/$remove-member removes member from group"""
        # Backdate the membership start_date so we can use a past endedDate
        # (status is computed: inactive when ended_date <= now, and
        # constraint requires ended_date >= start_date)
        membership = self.env["spp.group.membership"].search(
            [("group", "=", self.group.id), ("individual", "=", self.individual2.id)],
            limit=1,
        )
        membership.sudo().write({"start_date": "2024-01-01 00:00:00"})
        self.env.cr.flush()

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$remove-member"
        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-002",
                "display": "Jane Smith",
            },
            "endedDate": "2025-01-01",
            "reason": "Moved to another household",
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "GroupMember")
        self.assertEqual(data["status"], "inactive")
        self.assertIn("endedDate", data)
        self.assertEqual(data["endedDate"], "2025-01-01")

    def test_remove_member_not_a_member(self):
        """Removing non-member returns 404"""
        # Create individual who is not a member
        self.create_test_individual(
            name="Alice Jones",
            identifier_value="IND-999",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$remove-member"
        payload = {
            "entity": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-999",
                "display": "Alice Jones",
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 404)

    def test_update_member_role_success(self):
        """PATCH /Group/{id}/member/{individual_id} updates member role"""
        url = (
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/member/"
            "urn:openspp:vocab:id-type%23test_national_id|IND-002"
        )
        payload = {
            "role": {
                "coding": [
                    {
                        "system": "urn:test:relationship",
                        "code": "head",
                        "display": "Head of Household",
                    }
                ]
            },
        }

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "GroupMember")
        self.assertIn("role", data)
        self.assertEqual(data["role"]["coding"][0]["code"], "head")

    def test_update_member_dates(self):
        """PATCH /Group/{id}/member/{individual_id} updates membership dates"""
        url = (
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/member/"
            "urn:openspp:vocab:id-type%23test_national_id|IND-002"
        )
        payload = {
            "startDate": "2026-01-01",
            "endedDate": "2026-12-31",
        }

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "GroupMember")
        self.assertIn("startDate", data)
        self.assertEqual(data["startDate"], "2026-01-01")
        self.assertIn("endedDate", data)
        self.assertEqual(data["endedDate"], "2026-12-31")

    def test_update_member_not_a_member(self):
        """Updating non-member returns 404"""
        # Create individual who is not a member
        self.create_test_individual(
            name="Charlie Brown",
            identifier_value="IND-888",
        )

        url = (
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/member/"
            "urn:openspp:vocab:id-type%23test_national_id|IND-888"
        )
        payload = {
            "role": {
                "coding": [
                    {
                        "system": "urn:test:relationship",
                        "code": "head",
                        "display": "Head of Household",
                    }
                ]
            },
        }

        response = self.url_patch(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 404)

    def test_split_group_success(self):
        """POST /Group/{id}/$split splits group into two"""
        # Create a group with 4 members
        member1 = self.create_test_individual(
            name="Alice Johnson",
            identifier_value="IND-101",
        )
        member2 = self.create_test_individual(
            name="Bob Johnson",
            identifier_value="IND-102",
        )
        member3 = self.create_test_individual(
            name="Charlie Johnson",
            identifier_value="IND-103",
        )
        member4 = self.create_test_individual(
            name="Diana Johnson",
            identifier_value="IND-104",
        )

        source_group = self.create_test_group(
            name="Johnson Household",
            identifier_value="HH-101",
            members=[
                (member1, self.relationship_head),
                (member2, None),
                (member3, None),
                (member4, None),
            ],
        )

        # Create consent for this group
        self.create_consent(
            registrant=source_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-101/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-102",
                }
            ],
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-103",
                    "display": "Charlie Johnson",
                },
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-104",
                    "display": "Diana Johnson",
                },
            ],
            "newHead": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-103",
                "display": "Charlie Johnson",
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 201)

        # Verify response is the new group
        data = json.loads(response.content)
        self.assertEqual(data["type"], "Group")
        self.assertEqual(data["identifier"][0]["value"], "HH-102")
        self.assertEqual(len(data["member"]), 2)
        self.assertEqual(data["quantity"], 2)

        # Verify Location header
        self.assertIn("Location", response.headers)
        self.assertIn("HH-102", response.headers["Location"])

        # Verify new group has the head
        head_member = next(
            (m for m in data["member"] if "role" in m and m["role"]["coding"][0]["code"] == "head"),
            None,
        )
        self.assertIsNotNone(head_member)
        self.assertIn("IND-103", head_member["entity"]["reference"])

        # Verify source group still has 2 members
        source_response = self.url_open(
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-101",
            headers=self._get_headers(),
        )
        source_data = json.loads(source_response.content)
        self.assertEqual(len(source_data["member"]), 2)
        self.assertEqual(source_data["quantity"], 2)

    def test_split_group_empty_members_to_move(self):
        """Splitting with empty membersToMove returns 400"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-999",
                }
            ],
            "membersToMove": [],
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # FastAPI/Pydantic validation returns 422 for empty list validation
        self.assertIn(response.status_code, [400, 422])

    def test_split_group_member_not_in_source(self):
        """Splitting with member not in source returns 404"""
        # Create individual who is not in the group
        self.create_test_individual(
            name="Outsider Person",
            identifier_value="IND-999",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-998",
                }
            ],
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-999",
                },
            ],
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 404)

    def test_split_group_would_leave_empty(self):
        """Splitting all members returns 409"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-997",
                }
            ],
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-001",
                },
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-002",
                },
            ],
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 409)

    def test_split_group_moving_head(self):
        """Splitting with head being moved returns 409"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-996",
                }
            ],
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-001",  # This is the head
                },
            ],
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 409)

    def test_split_group_new_head_not_in_members_to_move(self):
        """Splitting with newHead not in membersToMove returns 400"""
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-995",
                }
            ],
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-002",
                },
            ],
            "newHead": {
                "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-001",  # Not in membersToMove
            },
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 400)

    def test_split_group_no_permission(self):
        """Splitting without permission returns 403"""
        # Create client without create permission
        limited_client = self.create_api_client(
            name="Limited Client",
            scopes=[
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "update"},  # Has update but not create
            ],
        )
        limited_token = self.generate_jwt_token(limited_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/$split"
        payload = {
            "newGroupIdentifier": [
                {
                    "system": "urn:openspp:vocab:id-type#test_household_id",
                    "value": "HH-994",
                }
            ],
            "membersToMove": [
                {
                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-002",
                },
            ],
        }

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=self._get_headers(limited_token),
        )

        self.assertEqual(response.status_code, 403)

    def test_get_membership_history_success(self):
        """GET /Group/{id}/membership-history returns membership change timeline"""
        # Create a group and track membership changes
        member1 = self.create_test_individual(
            name="Alice History",
            identifier_value="IND-H01",
        )
        member2 = self.create_test_individual(
            name="Bob History",
            identifier_value="IND-H02",
        )

        test_group = self.create_test_group(
            name="History Test Group",
            identifier_value="HH-HISTORY-001",
            members=[
                (member1, self.relationship_head),
            ],
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Add second member
        self.env["spp.group.membership"].create(
            {
                "group": test_group.id,
                "individual": member2.id,
                "start_date": "2024-02-01",
            }
        )

        # Get membership history
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-001/membership-history"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("meta", data)
        self.assertIn("total", data["meta"])
        self.assertIn("data", data)

        # Should have 2 "added" events (one for each member)
        self.assertEqual(data["meta"]["total"], 2)
        self.assertEqual(len(data["data"]), 2)

        # Verify each entry has required fields
        for resource in data["data"]:
            self.assertIn("timestamp", resource)
            self.assertIn("action", resource)
            self.assertIn("member", resource)
            self.assertIn("changedBy", resource)

            # Verify action is valid
            self.assertIn(resource["action"], ["added", "removed", "role_changed"])

            # Verify member reference format
            self.assertTrue(resource["member"]["reference"].startswith("Individual/"))

    def test_get_membership_history_with_removals(self):
        """Membership history includes removal events"""
        member1 = self.create_test_individual(
            name="Charlie History",
            identifier_value="IND-H03",
        )

        test_group = self.create_test_group(
            name="Removal Test Group",
            identifier_value="HH-HISTORY-002",
            members=[
                (member1, None),
            ],
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Remove the member
        membership = self.env["spp.group.membership"].search(
            [
                ("group", "=", test_group.id),
                ("individual", "=", member1.id),
            ],
            limit=1,
        )
        membership.write({"ended_date": "2026-06-01 10:00:00"})

        # Get membership history
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-002/membership-history"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Should have 2 events: "added" and "removed"
        self.assertEqual(data["meta"]["total"], 2)

        # Find the removed event
        removed_event = next((e for e in data["data"] if e["action"] == "removed"), None)
        self.assertIsNotNone(removed_event)
        self.assertIn("timestamp", removed_event)
        self.assertIn("member", removed_event)

    def test_get_membership_history_with_roles(self):
        """Membership history includes role information"""
        member1 = self.create_test_individual(
            name="Diana History",
            identifier_value="IND-H04",
        )

        test_group = self.create_test_group(
            name="Role Test Group",
            identifier_value="HH-HISTORY-003",
            members=[
                (member1, self.relationship_head),
            ],
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Get membership history
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-003/membership-history"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Find the added event for the head
        added_event = next((e for e in data["data"] if e["action"] == "added"), None)
        self.assertIsNotNone(added_event)

        # Should have newRole field with the head role
        if "newRole" in added_event:
            self.assertIn("coding", added_event["newRole"])
            self.assertEqual(added_event["newRole"]["coding"][0]["code"], "head")

    def test_get_membership_history_pagination(self):
        """Membership history supports _count parameter"""
        # Create group with multiple members to generate history
        members = []
        for i in range(5):
            member = self.create_test_individual(
                name=f"Member {i}",
                identifier_value=f"IND-H-{i:02d}",
            )
            members.append((member, None))

        test_group = self.create_test_group(
            name="Pagination Test Group",
            identifier_value="HH-HISTORY-004",
            members=members,
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Request with limit
        url = (
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-004/"
            "membership-history?_count=3"
        )

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Should respect the count parameter
        self.assertLessEqual(len(data["data"]), 3)

    def test_get_membership_history_with_since_filter(self):
        """Membership history supports _since parameter"""
        from datetime import datetime, timedelta

        member1 = self.create_test_individual(
            name="Eve History",
            identifier_value="IND-H05",
        )

        test_group = self.create_test_group(
            name="Since Filter Group",
            identifier_value="HH-HISTORY-005",
            members=[
                (member1, None),
            ],
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Use a future date to filter out all events
        future_date = (datetime.now() + timedelta(days=1)).isoformat()

        url = (
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-005/"
            f"membership-history?_since={future_date}"
        )

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Should have 0 events since all are before the future date
        self.assertEqual(data["meta"]["total"], 0)

    def test_get_membership_history_invalid_since(self):
        """Invalid _since parameter returns 400"""
        test_group = self.create_test_group(
            name="Invalid Since Group",
            identifier_value="HH-HISTORY-006",
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        url = (
            f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-006/"
            "membership-history?_since=invalid-date"
        )

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)

    def test_get_membership_history_group_not_found(self):
        """Membership history for non-existent group returns 404"""
        # Create client that doesn't require consent to test 404 behavior
        no_consent_client = self.create_api_client(
            name="No Consent Required Client",
            scopes=[{"resource": "group", "action": "read"}],
            require_consent=False,
            legal_basis="public_interest",
        )
        token = self.generate_jwt_token(no_consent_client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-NONEXISTENT/membership-history"

        response = self.url_open(url, headers=self._get_headers(token=token))

        self.assertEqual(response.status_code, 404)

    def test_get_membership_history_no_permission(self):
        """Membership history without read permission returns 403"""
        # Create client without read permission
        client = self.create_api_client(
            name="No Read Client",
            scopes=[
                {"resource": "group", "action": "update"},
            ],
        )
        token = self.generate_jwt_token(client)

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-001/membership-history"

        response = self.url_open(url, headers=self._get_headers(token))

        self.assertEqual(response.status_code, 403)

    def test_get_membership_history_no_consent(self):
        """Membership history without consent returns 403"""
        # Create group without consent
        self.create_test_group(
            name="No Consent History Group",
            identifier_value="HH-HISTORY-007",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-007/membership-history"

        response = self.url_open(url, headers=self._get_headers())

        # Security: consent-requiring clients get 403 for records without consent
        self.assertEqual(response.status_code, 403)

    def test_get_membership_history_sorted_descending(self):
        """Membership history is sorted by timestamp descending (most recent first)"""
        import time

        member1 = self.create_test_individual(
            name="Frank History",
            identifier_value="IND-H06",
        )
        member2 = self.create_test_individual(
            name="Grace History",
            identifier_value="IND-H07",
        )

        test_group = self.create_test_group(
            name="Sort Test Group",
            identifier_value="HH-HISTORY-008",
            members=[
                (member1, None),
            ],
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        # Small delay to ensure different timestamps
        time.sleep(0.1)

        # Add second member (should be most recent)
        self.env["spp.group.membership"].create(
            {
                "group": test_group.id,
                "individual": member2.id,
            }
        )

        # Get membership history
        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-008/membership-history"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Verify timestamps are in descending order
        timestamps = [resource["timestamp"] for resource in data["data"]]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        # Most recent event should be the second member added
        most_recent = data["data"][0]
        self.assertIn("IND-H07", most_recent["member"]["reference"])

    def test_get_membership_history_empty_group(self):
        """Membership history for group with no members returns empty list"""
        test_group = self.create_test_group(
            name="Empty History Group",
            identifier_value="HH-HISTORY-009",
        )

        # Create consent
        self.create_consent(
            registrant=test_group,
            grantee_partner=self.client.partner_id,
            resource_type="group",
            field_access="all",
        )

        url = f"{self.api_base_url}/urn:openspp:vocab:id-type%23test_household_id|HH-HISTORY-009/membership-history"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["meta"]["total"], 0)
        self.assertEqual(len(data["data"]), 0)
