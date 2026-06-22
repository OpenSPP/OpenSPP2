# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for DCI Compliance tests."""

import uuid
from datetime import datetime

from odoo.tests import TransactionCase


class DCIComplianceCommon(TransactionCase):
    """Base test class for DCI compliance testing.

    Provides helper methods to build DCI envelopes, search requests,
    and common assertions for DCI responses.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()

        # Models
        cls.Partner = cls.env["res.partner"]
        cls.IdRecord = cls.env["spp.registry.id"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Get or create UIN identifier type vocabulary
        # The search service matches on reg_ids.id_type_id.namespace_uri which is
        # the vocabulary's namespace_uri (related field on spp.vocabulary.code).
        # For DCI search to work, the vocabulary namespace must match the DCI
        # identifier type URI used in the search request.
        id_type_vocab = cls.Vocabulary.search([("namespace_uri", "=", "urn:dci:id:uin")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.Vocabulary.create(
                {
                    "name": "DCI UIN ID Type",
                    "namespace_uri": "urn:dci:id:uin",
                }
            )

        # Get or create UIN vocabulary code
        cls.id_type_uin = cls.VocabularyCode.search(
            [
                ("vocabulary_id", "=", id_type_vocab.id),
                ("code", "=", "uin"),
            ],
            limit=1,
        )
        if not cls.id_type_uin:
            cls.id_type_uin = cls.VocabularyCode.create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "uin",
                    "display": "Unique Identification Number",
                    "is_local": True,
                    "target_type": "individual",
                }
            )

        # Test data now references spp_dci.id_type_uin directly in XML
        # No migration needed

        # Test sender/receiver IDs
        cls.test_sender_id = "test.client.dci"
        cls.test_receiver_id = "openspp.registry.social"

    def build_search_request(
        self,
        identifier_type="urn:dci:id:uin",
        identifier_value=None,
        query_type="idtype-value",
        reg_type="SOCIAL_REGISTRY",
        page_size=20,
        page_number=1,
        transaction_id=None,
        reference_id=None,
    ):
        """Build a DCI SearchRequest payload.

        Args:
            identifier_type: Identifier type URI (default: urn:dci:id:uin)
            identifier_value: Identifier value to search for
            query_type: Query type (default: idtype-value)
            reg_type: Registry type (default: SOCIAL_REGISTRY)
            page_size: Results per page (default: 20)
            page_number: Page number (default: 1)
            transaction_id: Transaction ID (auto-generated if None)
            reference_id: Reference ID (auto-generated if None)

        Returns:
            dict: DCI SearchRequest payload
        """
        if transaction_id is None:
            transaction_id = f"txn-{uuid.uuid4()}"
        if reference_id is None:
            reference_id = f"ref-{uuid.uuid4()}"

        query = {"type": identifier_type, "value": identifier_value}

        return {
            "transaction_id": transaction_id,
            "search_request": [
                {
                    "reference_id": reference_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "search_criteria": {
                        "version": "1.0.0",
                        "reg_type": reg_type,
                        "query_type": query_type,
                        "query": query,
                        "pagination": {"page_size": page_size, "page_number": page_number},
                    },
                    "locale": "en",
                }
            ],
        }

    def build_expression_search_request(
        self,
        conditions,
        reg_type="SOCIAL_REGISTRY",
        page_size=20,
        page_number=1,
        transaction_id=None,
        reference_id=None,
    ):
        """Build a DCI SearchRequest with expression query.

        Args:
            conditions: List of condition dicts with 'attribute', 'operator', 'value'
            reg_type: Registry type (default: SOCIAL_REGISTRY)
            page_size: Results per page (default: 20)
            page_number: Page number (default: 1)
            transaction_id: Transaction ID (auto-generated if None)
            reference_id: Reference ID (auto-generated if None)

        Returns:
            dict: DCI SearchRequest payload with expression query
        """
        if transaction_id is None:
            transaction_id = f"txn-{uuid.uuid4()}"
        if reference_id is None:
            reference_id = f"ref-{uuid.uuid4()}"

        query = {"seq": conditions}

        return {
            "transaction_id": transaction_id,
            "search_request": [
                {
                    "reference_id": reference_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "search_criteria": {
                        "version": "1.0.0",
                        "reg_type": reg_type,
                        "query_type": "expression",
                        "query": query,
                        "pagination": {"page_size": page_size, "page_number": page_number},
                    },
                    "locale": "en",
                }
            ],
        }

    def build_dci_envelope(self, message, action="search"):
        """Build a DCI envelope with header and message.

        Args:
            message: Message payload (SearchRequest, etc.)
            action: DCI action (default: search)

        Returns:
            dict: DCI envelope with signature, header, and message
        """
        header = {
            "version": "1.0.0",
            "message_id": f"msg-{uuid.uuid4()}",
            "message_ts": datetime.utcnow().isoformat(),
            "action": action,
            "sender_id": self.test_sender_id,
            "sender_uri": f"https://{self.test_sender_id}/callback",
            "receiver_id": self.test_receiver_id,
            "total_count": 1,
            "is_msg_encrypted": False,
        }

        return {
            "signature": "test-signature-stub",
            "header": header,
            "message": message,
        }

    def assert_valid_search_response(self, response):
        """Assert that a SearchResponse is valid and well-formed.

        Args:
            response: SearchResponse dict

        Raises:
            AssertionError: If response is not valid
        """
        self.assertIn("transaction_id", response, "Response must have transaction_id")
        self.assertIn("search_response", response, "Response must have search_response")
        self.assertIsInstance(response["search_response"], list, "search_response must be a list")
        self.assertGreater(len(response["search_response"]), 0, "search_response must not be empty")

    def assert_search_response_success(self, response_item):
        """Assert that a SearchResponseItem indicates success.

        Args:
            response_item: SearchResponseItem dict

        Raises:
            AssertionError: If response item is not successful
        """
        self.assertIn("status", response_item, "Response item must have status")
        self.assertEqual(
            response_item["status"],
            "succ",
            f"Expected status 'succ', got '{response_item.get('status')}'",
        )
        self.assertIn("data", response_item, "Successful response must have data")
        self.assertIsNotNone(response_item["data"], "Successful response data must not be None")

    def assert_search_response_has_records(self, response_item, min_count=1):
        """Assert that a SearchResponseItem has records.

        Args:
            response_item: SearchResponseItem dict
            min_count: Minimum number of records expected (default: 1)

        Raises:
            AssertionError: If response item does not have enough records
        """
        self.assert_search_response_success(response_item)
        data = response_item["data"]
        self.assertIn("reg_records", data, "Response data must have reg_records")
        self.assertIsInstance(data["reg_records"], list, "reg_records must be a list")
        self.assertGreaterEqual(
            len(data["reg_records"]),
            min_count,
            f"Expected at least {min_count} records, got {len(data['reg_records'])}",
        )

    def assert_pagination_valid(self, response_item):
        """Assert that pagination information is valid.

        Args:
            response_item: SearchResponseItem dict

        Raises:
            AssertionError: If pagination is not valid
        """
        self.assertIn("pagination", response_item, "Response must have pagination")
        pagination = response_item["pagination"]
        self.assertIn("page_size", pagination, "Pagination must have page_size")
        self.assertIn("page_number", pagination, "Pagination must have page_number")
        self.assertIn("total_count", pagination, "Pagination must have total_count")
        self.assertGreater(pagination["page_size"], 0, "page_size must be positive")
        self.assertGreater(pagination["page_number"], 0, "page_number must be positive")
        self.assertGreaterEqual(pagination["total_count"], 0, "total_count must be non-negative")

    def assert_person_schema_valid(self, person):
        """Assert that a Person record conforms to DCI schema.

        Args:
            person: Person dict

        Raises:
            AssertionError: If person does not conform to schema
        """
        self.assertIn("identifier", person, "Person must have identifier")
        self.assertIsInstance(person["identifier"], list, "identifier must be a list")
        self.assertGreater(len(person["identifier"]), 0, "Person must have at least one identifier")

        # Check first identifier
        identifier = person["identifier"][0]
        self.assertIn("identifier_type", identifier, "Identifier must have identifier_type")
        self.assertIn("identifier_value", identifier, "Identifier must have identifier_value")

    def assert_group_schema_valid(self, group):
        """Assert that a Group record conforms to DCI schema.

        Args:
            group: Group dict

        Raises:
            AssertionError: If group does not conform to schema
        """
        self.assertIn("group_identifier", group, "Group must have group_identifier")
        self.assertIsInstance(group["group_identifier"], list, "group_identifier must be a list")

    def assert_response_time_acceptable(self, start_time, max_seconds=15):
        """Assert that response time is within acceptable limits.

        Args:
            start_time: datetime when request started
            max_seconds: Maximum acceptable response time in seconds (default: 15)

        Raises:
            AssertionError: If response time exceeds max_seconds
        """
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        self.assertLess(
            elapsed,
            max_seconds,
            f"Response time {elapsed:.2f}s exceeds limit of {max_seconds}s",
        )

    def validate_json_schema(self, data, schema):
        """Validate data against a JSON schema.

        Args:
            data: Data to validate
            schema: JSON schema dict

        Raises:
            AssertionError: If data does not conform to schema
        """
        try:
            import jsonschema

            jsonschema.validate(instance=data, schema=schema)
        except ImportError:
            self.skipTest("jsonschema package not available")
        except jsonschema.ValidationError as e:
            self.fail(f"JSON schema validation failed: {e}")
