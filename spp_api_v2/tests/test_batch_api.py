# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Batch API endpoint"""

import json

from .common import ApiV2HttpTestCase


class TestBatchAPIEndpoint(ApiV2HttpTestCase):
    """Test Batch/$batch endpoint for transaction and batch operations"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/$batch"

        # Create API client with all permissions
        self.client = self.create_api_client(
            name="Batch Test Client",
            scopes=[
                {"resource": "individual", "action": "create"},
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "update"},
                {"resource": "individual", "action": "delete"},
                {"resource": "group", "action": "create"},
                {"resource": "group", "action": "read"},
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

    def test_post_batch_with_transaction_type(self):
        """POST /$batch with transaction type processes atomically"""
        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": "urn:uuid:individual-1",
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "BATCH-TXN-001",
                            }
                        ],
                        "name": {"given": "Transaction", "family": "Test"},
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "transaction-response")
        self.assertEqual(len(data["entry"]), 1)
        self.assertEqual(data["entry"][0]["response"]["status"], "201 Created")

        # Verify individual was created
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "BATCH-TXN-001")])
        self.assertTrue(partner)

    def test_post_batch_with_batch_type(self):
        """POST /$batch with batch type processes independently"""
        payload = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "fullUrl": "urn:uuid:individual-1",
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "BATCH-BCH-001",
                            }
                        ],
                        "name": {"given": "Batch", "family": "Test"},
                    },
                },
                {
                    "fullUrl": "urn:uuid:individual-2",
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "BATCH-BCH-002",
                            }
                        ],
                        "name": {"given": "Another", "family": "Test"},
                    },
                },
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["type"], "batch-response")
        self.assertEqual(len(data["entry"]), 2)

    def test_transaction_response_format_correct(self):
        """Transaction response format includes status, location, etag"""
        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "RESP-FORMAT-001",
                            }
                        ],
                        "name": {"given": "Response", "family": "Format"},
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        data = json.loads(response.content)
        entry_response = data["entry"][0]["response"]

        self.assertIn("status", entry_response)
        self.assertIn("location", entry_response)
        self.assertIn("etag", entry_response)
        self.assertIn("resource", data["entry"][0])

    def test_placeholder_uuid_resolved_in_response(self):
        """Placeholder UUIDs are resolved to actual identifiers"""
        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": "urn:uuid:ind-placeholder",
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "PLACEHOLDER-001",
                            }
                        ],
                        "name": {"given": "Placeholder", "family": "Test"},
                    },
                },
                {
                    "fullUrl": "urn:uuid:group-placeholder",
                    "request": {"method": "POST", "url": "Group"},
                    "resource": {
                        "type": "Group",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_household_id",
                                "value": "PLACEHOLDER-GRP",
                            }
                        ],
                        "name": "Placeholder Group",
                        "member": [
                            {
                                "entity": {
                                    "reference": "urn:uuid:ind-placeholder",
                                    "display": "Placeholder Test",
                                }
                            }
                        ],
                    },
                },
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data["entry"]), 2)

        # Both should succeed
        self.assertEqual(data["entry"][0]["response"]["status"], "201 Created")
        self.assertEqual(data["entry"][1]["response"]["status"], "201 Created")

    def test_authentication_required(self):
        """Request without authentication returns 401"""
        payload = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_bundle_type_returns_400(self):
        """Invalid bundle type returns 400"""
        payload = {
            "resourceType": "Bundle",
            "type": "invalid-type",
            "entry": [],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        # FastAPI/Pydantic validation returns 422 for invalid enum values
        self.assertIn(response.status_code, [400, 422])

    def test_empty_bundle_returns_400(self):
        """Bundle with no entries returns 400"""
        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 400)

    def test_transaction_rolls_back_on_failure(self):
        """Transaction with failure rolls back all changes"""
        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "ROLLBACK-001",
                            }
                        ],
                        "name": {"given": "Valid", "family": "Entry"},
                    },
                },
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        # Missing required identifier - will fail
                        "name": {"given": "Invalid", "family": "Entry"},
                    },
                },
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 422)

        # Verify first entry was NOT created (rolled back)
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "ROLLBACK-001")])
        self.assertFalse(partner)

    def test_batch_continues_on_partial_failure(self):
        """Batch continues processing even when some entries fail"""
        payload = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "PARTIAL-001",
                            }
                        ],
                        "name": {"given": "Valid", "family": "Entry"},
                    },
                },
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        # Missing identifier - will fail
                        "name": {"given": "Invalid", "family": "Entry"},
                    },
                },
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "PARTIAL-003",
                            }
                        ],
                        "name": {"given": "Another", "family": "Valid"},
                    },
                },
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data["entry"]), 3)

        # First entry should succeed
        self.assertEqual(data["entry"][0]["response"]["status"], "201 Created")

        # Second entry should fail (missing identifier causes error)
        failed_status = data["entry"][1]["response"]["status"]
        self.assertTrue(
            "422" in failed_status or "400" in failed_status or "500" in failed_status,
            f"Expected error status code, got: {failed_status}",
        )

        # Third entry should succeed
        self.assertEqual(data["entry"][2]["response"]["status"], "201 Created")

        # Verify successful entries were created
        partner1 = self.env["res.partner"].search([("reg_ids.value", "=", "PARTIAL-001")])
        partner3 = self.env["res.partner"].search([("reg_ids.value", "=", "PARTIAL-003")])
        self.assertTrue(partner1)
        self.assertTrue(partner3)

    def test_transaction_with_get_operation(self):
        """Transaction bundle can include GET operations"""
        # Create individual first
        self.create_test_individual(identifier_value="GET-IN-TXN")

        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "GET",
                        "url": "Individual/urn:openspp:vocab:id-type#test_national_id|GET-IN-TXN",
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["entry"][0]["response"]["status"], "200 OK")
        self.assertIn("resource", data["entry"][0])

    def test_transaction_with_put_operation(self):
        """Transaction bundle can include PUT operations"""
        # Create individual first
        individual = self.create_test_individual(identifier_value="PUT-IN-TXN", given_name="Original")

        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "PUT",
                        "url": "Individual/urn:openspp:vocab:id-type#test_national_id|PUT-IN-TXN",
                    },
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "PUT-IN-TXN",
                            }
                        ],
                        "name": {"given": "Updated", "family": "Name"},
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["entry"][0]["response"]["status"], "200 OK")

        # Verify update
        individual.invalidate_recordset()
        self.assertEqual(individual.given_name, "Updated")

    def test_transaction_with_delete_operation(self):
        """Transaction bundle can include DELETE operations"""
        # Create individual first
        individual = self.create_test_individual(identifier_value="DELETE-IN-TXN")

        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "DELETE",
                        "url": "Individual/urn:openspp:vocab:id-type#test_national_id|DELETE-IN-TXN",
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["entry"][0]["response"]["status"], "204 No Content")

        # Verify soft delete
        individual.invalidate_recordset()
        self.assertFalse(individual.active)

    def test_batch_with_mixed_operations(self):
        """Batch can include mixed operation types"""
        # Create individual for GET
        self.create_test_individual(identifier_value="MIXED-EXISTING")

        payload = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "MIXED-NEW",
                            }
                        ],
                        "name": {"given": "New", "family": "Individual"},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "Individual/urn:openspp:vocab:id-type#test_national_id|MIXED-EXISTING",
                    },
                },
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data["entry"]), 2)
        self.assertEqual(data["entry"][0]["response"]["status"], "201 Created")
        self.assertEqual(data["entry"][1]["response"]["status"], "200 OK")

    def test_error_response_includes_operation_outcome(self):
        """Error responses include OperationOutcome"""
        payload = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        # Missing required identifier
                        "name": {"given": "Error", "family": "Test"},
                    },
                }
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        data = json.loads(response.content)
        entry_resource = data["entry"][0]["resource"]

        self.assertEqual(entry_resource["resourceType"], "OperationOutcome")
        self.assertIn("issue", entry_resource)
        self.assertGreater(len(entry_resource["issue"]), 0)

    def test_invalid_json_returns_400(self):
        """Invalid JSON payload returns 400"""
        response = self.url_open(
            self.api_base_url,
            data="invalid json {",
            headers=self._get_headers(),
        )

        # Should return error (400 or 422)
        self.assertIn(response.status_code, [400, 422, 500])

    def test_batch_processes_multiple_resources(self):
        """Batch can process multiple different resource types"""
        # Create individual for group membership
        self.create_test_individual(identifier_value="MULTI-MEMBER")

        payload = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "fullUrl": "urn:uuid:ind-1",
                    "request": {"method": "POST", "url": "Individual"},
                    "resource": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_national_id",
                                "value": "MULTI-IND",
                            }
                        ],
                        "name": {"given": "Multi", "family": "Individual"},
                    },
                },
                {
                    "request": {"method": "POST", "url": "Group"},
                    "resource": {
                        "type": "Group",
                        "identifier": [
                            {
                                "system": "urn:openspp:vocab:id-type#test_household_id",
                                "value": "MULTI-GRP",
                            }
                        ],
                        "name": "Multi Group",
                    },
                },
            ],
        }

        response = self.url_open(
            self.api_base_url,
            data=json.dumps(payload),
            headers=self._get_headers(),
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data["entry"]), 2)
        self.assertEqual(data["entry"][0]["response"]["status"], "201 Created")
        self.assertEqual(data["entry"][1]["response"]["status"], "201 Created")
