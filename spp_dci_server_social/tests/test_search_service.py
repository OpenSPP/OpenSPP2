# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Social Registry Search Service."""

import logging
from datetime import UTC, datetime
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from odoo.addons.spp_dci.schemas.search import (
    PaginationRequest,
    SearchCriteria,
    SearchRequest,
    SearchRequestItem,
)

from ..services.search_service import DCISocialSearchService
from .common import DCISocialServerCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestDCISocialSearchService(DCISocialServerCommon):
    """Test cases for DCI Social Registry Search Service."""

    def setUp(self):
        """Set up test environment before each test."""
        super().setUp()
        # Create service instance
        self.search_service = DCISocialSearchService(self.env, sender_registry=self.test_sender)

    def test_service_initialization(self):
        """Test service initializes correctly."""
        service = DCISocialSearchService(self.env)
        self.assertIsNotNone(service.env)
        self.assertIsNone(service.sender)

        service_with_sender = DCISocialSearchService(self.env, sender_registry=self.test_sender)
        self.assertEqual(service_with_sender.sender, self.test_sender)

    def test_set_sender(self):
        """Test setting sender after initialization."""
        service = DCISocialSearchService(self.env)
        self.assertIsNone(service.sender)

        service.set_sender(self.test_sender)
        self.assertEqual(service.sender, self.test_sender)

    def test_search_by_identifier_success(self):
        """Test searching by identifier type and value."""
        # Create search request
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-001"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-001",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-001",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify response
        self.assertEqual(response.transaction_id, "test-txn-001")
        self.assertEqual(len(response.search_response), 1)

        response_item = response.search_response[0]
        self.assertEqual(response_item.reference_id, "test-ref-001")
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        self.assertEqual(response_item.data.reg_type, "SOCIAL_REGISTRY")
        self.assertEqual(response_item.data.reg_record_type, "PERSON")
        self.assertEqual(len(response_item.data.reg_records), 1)

        # Verify pagination
        self.assertIsNotNone(response_item.pagination)
        self.assertEqual(response_item.pagination.total_count, 1)

    def test_search_by_identifier_not_found(self):
        """Test searching by identifier that doesn't exist."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NON-EXISTENT"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-002",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-002",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify response - should succeed with empty results
        self.assertEqual(len(response.search_response), 1)
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        self.assertEqual(len(response_item.data.reg_records), 0)
        self.assertEqual(response_item.pagination.total_count, 0)

    def test_search_by_expression_name(self):
        """Test searching by name using expression query."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="expression",
            query={
                "seq": [
                    {"attribute": "family_name", "operator": "=", "value": "Doe"},
                ]
            },
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-003",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-003",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify response - should find both Doe individuals
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        self.assertEqual(len(response_item.data.reg_records), 2)
        self.assertEqual(response_item.pagination.total_count, 2)

    def test_search_by_expression_multiple_conditions(self):
        """Test searching with multiple conditions in expression."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="expression",
            query={
                "seq": [
                    {"attribute": "family_name", "operator": "=", "value": "Doe"},
                    {"attribute": "given_name", "operator": "=", "value": "John"},
                ]
            },
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-004",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-004",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify response - should find only John Doe
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertEqual(len(response_item.data.reg_records), 1)

        # Verify it's John Doe
        record = response_item.data.reg_records[0]
        self.assertEqual(record["name"]["given_name"], "John")
        self.assertEqual(record["name"]["surname"], "Doe")

    def test_search_by_expression_city(self):
        """Test searching by city/locality."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="expression",
            query={
                "seq": [
                    {"attribute": "city", "operator": "=", "value": "Test City"},
                ]
            },
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-005",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-005",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify response - should find both individuals plus the
        # household, all of which the fixture places in "Test City".
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertEqual(len(response_item.data.reg_records), 3)

    def test_search_group(self):
        """Test searching for groups/households."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "HH-001"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-006",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-006",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify response
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        self.assertEqual(response_item.data.reg_record_type, "GROUP")
        self.assertEqual(len(response_item.data.reg_records), 1)

        # Verify group has members
        group_record = response_item.data.reg_records[0]
        self.assertIn("member_list", group_record)
        self.assertEqual(group_record["group_size"], 2)

    def test_search_pagination(self):
        """Test pagination in search results."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="expression",
            query={"seq": []},  # Empty query to match all registrants
            pagination=PaginationRequest(page_size=2, page_number=1),
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-007",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-007",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify pagination
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertEqual(response_item.pagination.page_size, 2)
        self.assertEqual(response_item.pagination.page_number, 1)
        self.assertLessEqual(len(response_item.data.reg_records), 2)
        self.assertGreaterEqual(response_item.pagination.total_count, 3)  # At least our 3 individuals

    def test_search_pagination_second_page(self):
        """Test retrieving second page of results."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="expression",
            query={"seq": []},  # Empty query to match all registrants
            pagination=PaginationRequest(page_size=2, page_number=2),
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-008",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-008",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify pagination
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertEqual(response_item.pagination.page_number, 2)

    def test_search_invalid_registry_type(self):
        """Test rejection of invalid registry type."""
        criteria = SearchCriteria(
            reg_type="CIVIL_REGISTRY",  # Invalid for social registry
            reg_event_type="BIRTH",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-001"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-009",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-009",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify error response
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "rjct")
        self.assertEqual(response_item.status_reason_code, "rjct.search_criteria.invalid")
        self.assertIn("SOCIAL_REGISTRY", response_item.status_reason_message)

    def test_search_predicate_simple_expression(self):
        """Test predicate query with simple CEL expression."""
        # Search for individuals with family_name == "Doe"
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="predicate",
            query="r.family_name == 'Doe'",
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-010",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-010",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify successful response
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        # Should find both John Doe and Jane Doe
        self.assertEqual(len(response_item.data.reg_records), 2)

    def test_search_predicate_compound_expression(self):
        """Test predicate query with compound CEL expression using && operator."""
        # Search for individuals with family_name == "Doe" AND given_name == "John"
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="predicate",
            query="r.family_name == 'Doe' && r.given_name == 'John'",
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-010a",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-010a",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify successful response
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        # Should find only John Doe
        self.assertEqual(len(response_item.data.reg_records), 1)
        self.assertEqual(response_item.data.reg_records[0]["name"]["given_name"], "John")

    def test_search_predicate_as_dict_expression(self):
        """Test predicate query with expression provided as dict."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="predicate",
            query={"expression": "r.city == 'Test City'"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-010b",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-010b",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify successful response - should find individuals in Test City
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        self.assertEqual(len(response_item.data.reg_records), 2)

    def test_search_predicate_invalid_expression(self):
        """Test that invalid predicate expression returns proper error."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="predicate",
            query="invalid_syntax((",
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-010c",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-010c",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify error response with sanitized message
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "rjct")
        self.assertEqual(response_item.status_reason_code, "rjct.filter.invalid")

    def test_search_predicate_empty_expression(self):
        """Test predicate query with empty expression returns all registrants."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="predicate",
            query="",
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-010d",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-010d",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Empty expression should succeed with all registrants
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")
        self.assertIsNotNone(response_item.data)
        # Should return at least our test individuals
        self.assertGreaterEqual(response_item.pagination.total_count, 3)

    def test_search_cursor_pagination(self):
        """Test cursor-based pagination for efficient large dataset traversal."""
        # First request without cursor
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            # query_type="namedQuery" is not implemented by the service;
            # an empty expression matches every registrant and is a fair
            # stand-in for "give me all results" while exercising cursor
            # pagination.
            query_type="expression",
            query={"seq": []},
            pagination=PaginationRequest(page_size=1, page_number=1),
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-cursor-1",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-cursor-1",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)
        response_item = response.search_response[0]

        self.assertEqual(response_item.status, "succ")
        self.assertEqual(len(response_item.data.reg_records), 1)

        # Should have next_cursor since there are more records
        if response_item.pagination.total_count > 1:
            self.assertIsNotNone(response_item.pagination.next_cursor)

            # Second request with cursor
            criteria_with_cursor = SearchCriteria(
                reg_type="SOCIAL_REGISTRY",
                reg_event_type="ACTIVE",
                query_type="expression",
                query={"seq": []},
                pagination=PaginationRequest(
                    page_size=1,
                    page_number=1,
                    cursor=response_item.pagination.next_cursor,
                ),
            )

            search_req_2 = SearchRequestItem(
                reference_id="test-ref-cursor-2",
                timestamp=datetime.now(UTC),
                search_criteria=criteria_with_cursor,
            )

            request_2 = SearchRequest(
                transaction_id="test-txn-cursor-2",
                search_request=[search_req_2],
            )

            response_2 = self.search_service.execute_search(request_2)
            response_item_2 = response_2.search_response[0]

            self.assertEqual(response_item_2.status, "succ")
            self.assertEqual(len(response_item_2.data.reg_records), 1)

            # Should be a different record than the first page
            first_record_id = response_item.data.reg_records[0].get("identifier", [{}])[0].get("identifier_value")
            second_record_id = response_item_2.data.reg_records[0].get("identifier", [{}])[0].get("identifier_value")
            self.assertNotEqual(first_record_id, second_record_id)

    def test_search_cursor_encode_decode(self):
        """Test cursor encoding and decoding round-trip."""
        # Test encoding
        cursor = self.search_service._encode_cursor(12345)
        self.assertIsNotNone(cursor)
        self.assertIsInstance(cursor, str)

        # Test decoding
        decoded_id = self.search_service._decode_cursor(cursor)
        self.assertEqual(decoded_id, 12345)

    def test_search_cursor_invalid(self):
        """Test that invalid cursor falls back to page_number pagination."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            # query_type="namedQuery" is not implemented by the service;
            # an empty expression matches every registrant and is a fair
            # stand-in for "give me all results" while exercising cursor
            # pagination.
            query_type="expression",
            query={"seq": []},
            pagination=PaginationRequest(
                page_size=10,
                page_number=1,
                cursor="invalid_cursor_string",
            ),
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-invalid-cursor",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-invalid-cursor",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        # Should not raise, just fallback to page_number
        response = self.search_service.execute_search(request)
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "succ")

    def test_search_query_type_graphql_not_supported(self):
        """Test that GraphQL query type is rejected with proper error."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="graphql",
            query={"query": "{ registrant { name } }"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-011",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-011",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify error response with sanitized message
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "rjct")
        self.assertEqual(response_item.status_reason_code, "rjct.filter.invalid")
        self.assertEqual(response_item.status_reason_message, "The search query format is invalid")

    def test_search_without_permission(self):
        """Test that search without registry viewer permission is denied.

        Use a fresh internal user (not the test superuser) because
        ``has_group`` returns True for superuser regardless of the
        actual group memberships, which would silently mask the check.
        """
        plain_user = self.env["res.users"].create(
            {
                "name": "DCI Search Plain User",
                "login": "dci_plain_user@example.test",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-001"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-012",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-012",
            search_request=[search_req],
        )

        plain_env = self.env(user=plain_user.id)
        self.assertFalse(
            plain_env.user.has_group("spp_registry.group_registry_viewer"),
            "fixture mistake: plain_user should not have registry_viewer",
        )
        service = DCISocialSearchService(plain_env, sender_registry=self.test_sender)
        with self.assertRaises(AccessError) as context:
            service.execute_search(request)

        error_msg = str(context.exception)
        self.assertIn("permission", error_msg.lower())
        self.assertIn("Social Registry", error_msg)

    def test_search_error_handling_sanitized(self):
        """Test that internal errors return sanitized messages."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-001"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-013",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-013",
            search_request=[search_req],
        )

        # Mock search to raise an exception. In Odoo 19 recordsets are
        # immutable so patch.object on the recordset raises read-only;
        # patch the model class via type(...) instead.
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})
        partner_cls = type(self.search_service.env["res.partner"])
        with patch.object(partner_cls, "search", side_effect=Exception("Internal error")):
            response = self.search_service.execute_search(request)

        # Verify error response with sanitized message
        response_item = response.search_response[0]
        self.assertEqual(response_item.status, "rjct")
        self.assertEqual(response_item.status_reason_code, "rjct.search_criteria.invalid")
        # Should use generic error message, not expose internal error
        self.assertEqual(response_item.status_reason_message, "An error occurred while processing your request")
        self.assertNotIn("Internal error", response_item.status_reason_message)

    def test_search_multiple_items(self):
        """Test processing multiple search items in one request."""
        # Create multiple search items
        criteria_1 = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-001"},
        )

        criteria_2 = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-002"},
        )

        search_req_1 = SearchRequestItem(
            reference_id="test-ref-014-1",
            timestamp=datetime.now(UTC),
            search_criteria=criteria_1,
        )

        search_req_2 = SearchRequestItem(
            reference_id="test-ref-014-2",
            timestamp=datetime.now(UTC),
            search_criteria=criteria_2,
        )

        request = SearchRequest(
            transaction_id="test-txn-014",
            search_request=[search_req_1, search_req_2],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify both responses
        self.assertEqual(len(response.search_response), 2)
        self.assertEqual(response.search_response[0].reference_id, "test-ref-014-1")
        self.assertEqual(response.search_response[0].status, "succ")
        self.assertEqual(response.search_response[1].reference_id, "test-ref-014-2")
        self.assertEqual(response.search_response[1].status, "succ")

    def test_to_dci_person_conversion(self):
        """Test conversion of partner to DCI Person schema."""
        person = self.search_service._to_dci_person(self.individual_1)

        # Verify Person fields
        self.assertIsNotNone(person.identifier)
        self.assertEqual(len(person.identifier), 1)
        self.assertEqual(person.identifier[0].identifier_value, "NAT-001")

        self.assertIsNotNone(person.name)
        self.assertEqual(person.name.given_name, "John")
        self.assertEqual(person.name.surname, "Doe")

        self.assertEqual(person.sex, "male")
        self.assertIsNotNone(person.birth_date)

        self.assertIsNotNone(person.address)
        self.assertEqual(len(person.address), 1)
        self.assertEqual(person.address[0].address_line_1, "123 Main St")
        self.assertEqual(person.address[0].locality, "Test City")

        self.assertIsNotNone(person.phone_number)
        self.assertIn("+1234567890", person.phone_number)

        self.assertIsNotNone(person.email)
        self.assertIn("john.doe@example.com", person.email)

    def test_to_dci_person_missing_identifier(self):
        """Test that conversion fails for partner without identifier."""
        # Create individual without identifier
        individual_no_id = self._create_test_individual(
            {
                "family_name": "NoID",
                "given_name": "Test",
            },
            identifier_value=None,
        )

        # Should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            self.search_service._to_dci_person(individual_no_id)

        error_msg = str(context.exception)
        self.assertIn("no valid identifiers", error_msg.lower())

    def test_to_dci_group_conversion(self):
        """Test conversion of partner to DCI Group schema."""
        group = self.search_service._to_dci_group(self.group_1)

        # Verify Group fields
        self.assertIsNotNone(group.group_identifier)
        self.assertEqual(len(group.group_identifier), 1)
        self.assertEqual(group.group_identifier[0].identifier_value, "HH-001")

        self.assertEqual(group.group_type, "Household")

        self.assertIsNotNone(group.address)
        self.assertEqual(len(group.address), 1)

        self.assertIsNotNone(group.member_list)
        self.assertEqual(group.group_size, 2)
        self.assertEqual(len(group.member_list), 2)

    def test_map_gender_with_vocabulary(self):
        """Test gender mapping with vocabulary codes."""
        # Test male
        sex = self.search_service._map_gender(self.individual_1)
        self.assertEqual(sex, "male")

        # Test female
        sex = self.search_service._map_gender(self.individual_2)
        self.assertEqual(sex, "female")

    def test_apply_consent_filter_no_consent_model(self):
        """Test consent filter when consent model is not available."""
        # Mock consent adapter to return None
        self.search_service._consent_adapter = None

        # Mock env to not have consent model
        with patch.object(self.search_service.env, "__contains__", return_value=False):
            domain = [("is_registrant", "=", True)]
            result = self.search_service._apply_consent_filter(domain)

            # Should return unchanged domain
            self.assertEqual(result, domain)

    def test_build_domain_idtype_value(self):
        """Test building Odoo domain from idtype-value query."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": "urn:test:id:type", "value": "TEST-001"},
        )

        domain = self.search_service._build_domain(criteria)

        # Verify domain structure
        self.assertIn(("is_registrant", "=", True), domain)
        self.assertIn(("reg_ids.id_type_id.namespace_uri", "=", "urn:test:id:type"), domain)
        self.assertIn(("reg_ids.value", "=", "TEST-001"), domain)

    def test_build_domain_expression(self):
        """Test building Odoo domain from expression query."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="expression",
            query={
                "seq": [
                    {"attribute": "given_name", "operator": "=", "value": "John"},
                    {"attribute": "family_name", "operator": "=", "value": "Doe"},
                ]
            },
        )

        domain = self.search_service._build_domain(criteria)

        # Verify domain structure
        self.assertIn(("is_registrant", "=", True), domain)
        self.assertIn(("given_name", "=", "John"), domain)
        self.assertIn(("family_name", "=", "Doe"), domain)

    def test_build_domain_unknown_query_type(self):
        """Test that unknown query type raises error."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="unknown_type",
            query={},
        )

        with self.assertRaises(ValueError) as context:
            self.search_service._build_domain(criteria)

        error_msg = str(context.exception)
        self.assertIn("Unknown query_type", error_msg)

    def test_condition_to_domain_attribute_mapping(self):
        """Test attribute name mapping in condition_to_domain."""
        # Test various attribute mappings
        test_cases = [
            ("given_name", "=", "John", ("given_name", "=", "John")),
            ("surname", "=", "Doe", ("family_name", "=", "Doe")),
            ("family_name", "=", "Doe", ("family_name", "=", "Doe")),
            ("birth_date", "=", "2000-01-01", ("birthdate", "=", "2000-01-01")),
            ("sex", "=", "male", ("gender", "=", "male")),
            ("city", "=", "Test", ("city", "=", "Test")),
            ("locality", "=", "Test", ("city", "=", "Test")),
        ]

        for attr, op, val, expected in test_cases:
            with self.subTest(attribute=attr):
                result = self.search_service._condition_to_domain(attr, op, val)
                self.assertEqual(result, expected)

    def test_condition_to_domain_operator_mapping(self):
        """Test operator mapping in condition_to_domain."""
        test_cases = [
            ("=", "="),
            ("==", "="),
            (">", ">"),
            ("<", "<"),
            (">=", ">="),
            ("<=", "<="),
            ("in", "in"),
            ("contains", "ilike"),
            ("like", "ilike"),
        ]

        for dci_op, odoo_op in test_cases:
            with self.subTest(operator=dci_op):
                result = self.search_service._condition_to_domain("name", dci_op, "test")
                self.assertEqual(result[1], odoo_op)

    def test_parse_expression_with_or(self):
        """Test parsing expression with OR logic."""
        expression = {
            "seq": [{"attribute": "family_name", "operator": "=", "value": "Doe"}],
            "or": [{"seq": [{"attribute": "family_name", "operator": "=", "value": "Smith"}]}],
        }

        domain = self.search_service._parse_expression(expression)

        # Verify domain has OR operator
        self.assertIn(("family_name", "=", "Doe"), domain)
        self.assertIn("|", domain)
        self.assertIn(("family_name", "=", "Smith"), domain)

    def test_response_correlation_id_generated(self):
        """Test that correlation_id is generated for response."""
        criteria = SearchCriteria(
            reg_type="SOCIAL_REGISTRY",
            reg_event_type="ACTIVE",
            query_type="idtype-value",
            query={"type": self.test_id_type.namespace_uri, "value": "NAT-001"},
        )

        search_req = SearchRequestItem(
            reference_id="test-ref-015",
            timestamp=datetime.now(UTC),
            search_criteria=criteria,
        )

        request = SearchRequest(
            transaction_id="test-txn-015",
            search_request=[search_req],
        )

        # Execute search with registry viewer permissions
        self.env.user.write({"group_ids": [(4, self.env.ref("spp_registry.group_registry_viewer").id)]})

        response = self.search_service.execute_search(request)

        # Verify correlation_id is present and is a valid UUID
        self.assertIsNotNone(response.correlation_id)
        # UUID format check (basic)
        self.assertRegex(
            response.correlation_id,
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        )
