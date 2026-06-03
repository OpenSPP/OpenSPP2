# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Compliance Tests - Social Registry Sync Search.

Tests compliance with DCI protocol requirements for Social Registry
synchronous search endpoints.
"""

import logging
from datetime import datetime

from odoo.addons.spp_dci.schemas.search import SearchRequest, SearchResponse

from .common import DCIComplianceCommon

_logger = logging.getLogger(__name__)


class TestSRSyncSearchCompliance(DCIComplianceCommon):
    """DCI compliance tests for Social Registry sync search endpoint.

    Tests verify that the /registry/social/sync/search endpoint:
    - Returns HTTP 200 status for valid requests
    - Returns correct Content-Type header
    - Responds within 15 seconds
    - Returns responses conforming to DCI schema
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data for compliance tests."""
        super().setUpClass()

        # Import search service
        from odoo.addons.spp_dci_server_social.services.search_service import (
            DCISocialSearchService,
        )

        cls.SearchService = DCISocialSearchService

        # Ensure test user has registry viewer permissions
        registry_viewer_group = cls.env.ref("spp_registry.group_registry_viewer")
        cls.env.user.sudo().write({"group_ids": [(4, registry_viewer_group.id)]})

        # Always create test individual in code to ensure the registry ID
        # uses the correct vocabulary code (cls.id_type_uin). The XML data
        # references spp_dci.id_type_uin (spp.id.type model) which may be
        # incompatible with spp.registry.id.id_type_id (Many2one to
        # spp.vocabulary.code), causing search by namespace_uri to fail.
        cls.test_individual = cls.Partner.create(
            {
                "name": "Test Individual 847951632",
                "is_registrant": True,
                "is_group": False,
                "given_name": "John",
                "family_name": "Doe",
            }
        )
        cls.IdRecord.create(
            {
                "partner_id": cls.test_individual.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "847951632",
            }
        )

    def test_01_response_status_200_on_valid_request(self):
        """Test that valid search request returns success status.

        Verifies:
        - SearchResponse is returned (not HTTP error)
        - Response status is 'succ' for successful search
        """
        # Build search request for test individual
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
            page_size=10,
            page_number=1,
        )

        # Execute search via service
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)

        # This should not raise an exception
        response = service.execute_search(request)

        # Verify response is valid
        self.assertIsNotNone(response, "Response should not be None")
        self.assertIsInstance(response, SearchResponse, "Response should be SearchResponse")
        self.assertEqual(
            response.transaction_id,
            request_payload["transaction_id"],
            "Response transaction_id should match request",
        )
        self.assertGreater(
            len(response.search_response),
            0,
            "Response should contain at least one search result",
        )

        # Check first response item status
        response_item = response.search_response[0]
        self.assertEqual(
            response_item.status,
            "succ",
            f"Expected success status, got: {response_item.status}. Reason: {response_item.status_reason_message}",
        )

    def test_02_response_content_type_header(self):
        """Test that response contains proper content type.

        Verifies:
        - Response can be serialized to JSON (implicit Content-Type: application/json)
        - Response structure matches DCI SearchResponse schema
        """
        # Build search request
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Verify response can be serialized to JSON (validates structure)
        response_dict = response.model_dump(by_alias=True, exclude_none=True)
        self.assertIsInstance(response_dict, dict, "Response should be serializable to dict")
        self.assertIn("transaction_id", response_dict, "Response should have transaction_id")
        self.assertIn("search_response", response_dict, "Response should have search_response")

        # Verify JSON serialization works (implicit Content-Type test)
        import json

        try:
            json_str = json.dumps(response_dict, default=str)
            self.assertIsInstance(json_str, str, "Response should be JSON-serializable")
        except (TypeError, ValueError) as e:
            self.fail(f"Response failed JSON serialization: {e}")

    def test_03_response_time_under_15_seconds(self):
        """Test that search response time is under 15 seconds.

        Verifies:
        - Synchronous search completes within acceptable time limit
        - Response time meets DCI performance requirements
        """
        # Record start time
        start_time = datetime.utcnow()

        # Build search request
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Verify response is valid
        self.assertIsNotNone(response, "Response should not be None")

        # Check response time
        self.assert_response_time_acceptable(start_time, max_seconds=15)

    def test_04_response_schema_validation(self):
        """Test that response conforms to DCI SearchResponse schema.

        Verifies:
        - Response structure matches SearchResponse Pydantic schema
        - All required fields are present
        - Field types are correct
        - Nested objects (Person, pagination) conform to their schemas
        """
        # Build search request
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
            page_size=10,
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate response object (Pydantic validation)
        self.assertIsInstance(response, SearchResponse, "Response should be SearchResponse")

        # Validate response structure
        self.assert_valid_search_response(response.model_dump())

        # Get first response item
        response_item = response.search_response[0]
        response_item_dict = response_item.model_dump(by_alias=True, exclude_none=True)

        # Validate success status and data presence
        self.assert_search_response_success(response_item_dict)

        # Validate records are present
        self.assert_search_response_has_records(response_item_dict, min_count=1)

        # Validate pagination
        self.assert_pagination_valid(response_item_dict)

        # Validate Person schema
        person = response_item_dict["data"]["reg_records"][0]
        self.assert_person_schema_valid(person)

    def test_05_search_by_identifier_returns_correct_record(self):
        """Test that searching by identifier returns the correct person.

        Verifies:
        - idtype-value query correctly filters by identifier
        - Returned record matches the searched identifier
        - Only matching records are returned
        """
        # Build search request for specific identifier
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate response
        self.assertEqual(len(response.search_response), 1, "Should have one search response item")
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ", "Search should succeed")

        # Check that returned record has the correct identifier
        self.assertIsNotNone(response_item.data, "Response data should not be None")
        records = response_item.data.reg_records
        self.assertGreater(len(records), 0, "Should return at least one record")

        # Verify identifier in first record
        record = records[0]
        record_dict = record.model_dump() if hasattr(record, "model_dump") else record
        identifiers = record_dict.get("identifier", [])
        self.assertGreater(len(identifiers), 0, "Record should have at least one identifier")

        # Check that one of the identifiers matches our search
        found_match = False
        for identifier in identifiers:
            if (
                identifier.get("identifier_type") == "urn:dci:id:uin"
                and identifier.get("identifier_value") == "847951632"
            ):
                found_match = True
                break

        self.assertTrue(
            found_match,
            f"Record should contain identifier urn:dci:id:uin:847951632. Found identifiers: {identifiers}",
        )

    def test_06_pagination_works_correctly(self):
        """Test that pagination parameters are respected.

        Verifies:
        - page_size limits number of results returned
        - page_number correctly offsets results
        - total_count reflects actual number of matching records
        """
        # Build search request with pagination
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
            page_size=5,
            page_number=1,
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate pagination in response
        response_item = response.search_response[0]
        self.assertIsNotNone(response_item.pagination, "Response should have pagination")
        pagination = response_item.pagination

        self.assertEqual(pagination.page_size, 5, "page_size should match request")
        self.assertEqual(pagination.page_number, 1, "page_number should match request")
        self.assertIsNotNone(pagination.total_count, "total_count should be present")
        self.assertGreaterEqual(pagination.total_count, 0, "total_count should be non-negative")

        # Verify number of records doesn't exceed page_size
        if response_item.data:
            records = response_item.data.reg_records
            self.assertLessEqual(
                len(records),
                pagination.page_size,
                f"Number of records ({len(records)}) should not exceed page_size ({pagination.page_size})",
            )

    def test_07_search_nonexistent_identifier_returns_empty(self):
        """Test that searching for nonexistent identifier returns empty result.

        Verifies:
        - Search for non-matching identifier returns success status
        - No records are returned in reg_records
        - total_count is zero
        """
        # Build search request for nonexistent identifier
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="999999999",  # Nonexistent
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate response
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ", "Search should succeed even with no results")

        # Check that no records are returned
        self.assertIsNotNone(response_item.data, "Response data should not be None")
        records = response_item.data.reg_records
        self.assertEqual(len(records), 0, "Should return zero records for nonexistent identifier")

        # Check pagination total_count is zero
        self.assertIsNotNone(response_item.pagination, "Response should have pagination")
        self.assertEqual(
            response_item.pagination.total_count,
            0,
            "total_count should be zero for no results",
        )

    def test_08_expression_query_by_name(self):
        """Test searching by expression query (e.g., by name).

        Verifies:
        - Expression queries work correctly
        - Can search by attributes other than identifier
        - Returns matching records
        """
        # Build expression query for given name
        conditions = [
            {"attribute": "given_name", "operator": "=", "value": "John"},
        ]
        request_payload = self.build_expression_search_request(
            conditions=conditions,
            page_size=10,
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate response
        response_item = response.search_response[0]
        self.assertEqual(
            response_item.status,
            "succ",
            f"Expression search should succeed. Error: {response_item.status_reason_message}",
        )

        # Should return at least one record
        self.assertIsNotNone(response_item.data, "Response data should not be None")
        records = response_item.data.reg_records
        self.assertGreater(len(records), 0, "Should return at least one record with given_name=John")

    def test_09_invalid_registry_type_returns_error(self):
        """Test that invalid registry type returns rejection status.

        Verifies:
        - Invalid reg_type is detected
        - Response status is 'rjct' (rejected)
        - Appropriate error message is provided
        """
        # Build search request with invalid registry type
        request_payload = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632",
            reg_type="INVALID_REGISTRY",  # Invalid
        )

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate response indicates rejection
        response_item = response.search_response[0]
        self.assertEqual(
            response_item.status,
            "rjct",
            "Search with invalid registry type should be rejected",
        )
        self.assertIsNotNone(
            response_item.status_reason_code,
            "Rejected response should have status_reason_code",
        )
        self.assertIsNotNone(
            response_item.status_reason_message,
            "Rejected response should have status_reason_message",
        )

    def test_10_multiple_search_requests_in_batch(self):
        """Test that multiple search requests in one transaction work.

        Verifies:
        - Batch search requests are supported
        - Each request is processed independently
        - Each has its own response item
        """
        # Build batch search request with two searches
        transaction_id = f"txn-batch-{datetime.utcnow().timestamp()}"

        request_payload = {
            "transaction_id": transaction_id,
            "search_request": [
                {
                    "reference_id": "ref-001",
                    "timestamp": datetime.utcnow().isoformat(),
                    "search_criteria": {
                        "version": "1.0.0",
                        "reg_type": "SOCIAL_REGISTRY",
                        "query_type": "idtype-value",
                        "query": {"type": "urn:dci:id:uin", "value": "847951632"},
                        "pagination": {"page_size": 10, "page_number": 1},
                    },
                    "locale": "en",
                },
                {
                    "reference_id": "ref-002",
                    "timestamp": datetime.utcnow().isoformat(),
                    "search_criteria": {
                        "version": "1.0.0",
                        "reg_type": "SOCIAL_REGISTRY",
                        "query_type": "idtype-value",
                        "query": {"type": "urn:dci:id:uin", "value": "999999999"},  # Nonexistent
                        "pagination": {"page_size": 10, "page_number": 1},
                    },
                    "locale": "en",
                },
            ],
        }

        # Execute search
        service = self.SearchService(self.env)
        request = SearchRequest(**request_payload)
        response = service.execute_search(request)

        # Validate response has two items
        self.assertEqual(
            len(response.search_response),
            2,
            "Batch request should return two response items",
        )

        # Check both responses
        response_item_1 = response.search_response[0]
        response_item_2 = response.search_response[1]

        self.assertEqual(response_item_1.reference_id, "ref-001", "First response reference_id")
        self.assertEqual(response_item_2.reference_id, "ref-002", "Second response reference_id")

        # First should succeed with results
        self.assertEqual(response_item_1.status, "succ", "First search should succeed")

        # Second should succeed but with zero results
        self.assertEqual(response_item_2.status, "succ", "Second search should succeed")
        self.assertEqual(
            len(response_item_2.data.reg_records) if response_item_2.data else 0,
            0,
            "Second search should return no records",
        )
