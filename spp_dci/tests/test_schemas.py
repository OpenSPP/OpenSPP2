"""Tests for Pydantic schemas."""

import unittest
from datetime import date, datetime

from pydantic import ValidationError

from ..schemas import (
    Address,
    DCICallbackHeader,
    DCIEnvelope,
    DCIMessageHeader,
    GeoCoordinates,
    GeoLocation,
    Group,
    Identifier,
    Member,
    Name,
    Pagination,
    PaginationRequest,
    Person,
    Place,
    RequestStatus,
    SearchCriteria,
    SearchRequest,
    SearchRequestItem,
    SearchResponse,
    SearchResponseData,
    SearchResponseItem,
    SearchSort,
)


class TestCommonSchemas(unittest.TestCase):
    """Test common schema types."""

    def test_identifier_schema(self):
        """Test Identifier schema."""
        identifier = Identifier(
            identifier_type="UIN",
            identifier_value="123456789",
        )
        self.assertEqual(identifier.identifier_type, "UIN")
        self.assertEqual(identifier.identifier_value, "123456789")

        # Test serialization
        data = identifier.model_dump()
        self.assertEqual(data["identifier_type"], "UIN")
        self.assertEqual(data["identifier_value"], "123456789")

    def test_name_schema(self):
        """Test Name schema."""
        name = Name(
            given_name="John",
            surname="Doe",
            second_name="Michael",
            prefix="Mr.",
            suffix="Jr.",
        )
        self.assertEqual(name.given_name, "John")
        self.assertEqual(name.surname, "Doe")
        self.assertEqual(name.second_name, "Michael")
        self.assertEqual(name.prefix, "Mr.")
        self.assertEqual(name.suffix, "Jr.")

        # Test with minimal fields
        name_min = Name(given_name="Jane")
        self.assertEqual(name_min.given_name, "Jane")
        self.assertIsNone(name_min.surname)

    def test_address_schema(self):
        """Test Address schema."""
        address = Address(
            address_line_1="123 Main Street",
            address_line_2="Apt 4B",
            locality="Springfield",
            region_code="IL",
            postal_code="62701",
            country_code="US",
        )
        self.assertEqual(address.address_line_1, "123 Main Street")
        self.assertEqual(address.locality, "Springfield")
        self.assertEqual(address.country_code, "US")

    def test_geo_location_schema(self):
        """Test GeoLocation and GeoCoordinates schemas."""
        coords = GeoCoordinates(
            latitude=40.7128,
            longitude=-74.0060,
        )
        self.assertEqual(coords.latitude, 40.7128)
        self.assertEqual(coords.longitude, -74.0060)

        # Test in address context
        address = Address(
            address_line_1="123 Main St",
            geo_location=GeoLocation(),
        )
        self.assertIsNotNone(address.geo_location)

    def test_place_schema(self):
        """Test Place schema with hierarchy."""
        # Create nested places
        country = Place(name="United States")
        state = Place(
            name="Illinois",
            contained_in_place=country,
        )
        city = Place(
            name="Springfield",
            contained_in_place=state,
            geo=GeoCoordinates(latitude=39.7817, longitude=-89.6501),
        )

        self.assertEqual(city.name, "Springfield")
        self.assertEqual(city.contained_in_place.name, "Illinois")
        self.assertEqual(city.contained_in_place.contained_in_place.name, "United States")


class TestPersonSchema(unittest.TestCase):
    """Test Person schema."""

    def test_person_schema_minimal(self):
        """Test Person with minimal required fields."""
        person = Person(
            identifier=[
                Identifier(
                    identifier_type="UIN",
                    identifier_value="123456789",
                )
            ],
        )
        self.assertEqual(len(person.identifier), 1)
        self.assertEqual(person.identifier[0].identifier_type, "UIN")
        self.assertEqual(person.type_, "Person")

    def test_person_schema_complete(self):
        """Test Person with all fields populated."""
        person = Person(
            identifier=[
                Identifier(identifier_type="UIN", identifier_value="123456789"),
                Identifier(identifier_type="BRN", identifier_value="BRN-001"),
            ],
            name=Name(
                given_name="John",
                surname="Doe",
                second_name="Michael",
            ),
            sex="male",
            birth_date=date(1990, 1, 15),
            address=[
                Address(
                    address_line_1="123 Main St",
                    locality="Springfield",
                    country_code="US",
                )
            ],
            phone_number=["+12125551234"],
            email=["john.doe@example.com"],
            registration_date=datetime(2024, 1, 1, 10, 0, 0),
            last_updated=datetime(2024, 12, 3, 15, 30, 0),
        )

        # Verify all fields
        self.assertEqual(len(person.identifier), 2)
        self.assertEqual(person.name.given_name, "John")
        self.assertEqual(person.sex, "male")
        self.assertEqual(person.birth_date, date(1990, 1, 15))
        self.assertEqual(len(person.address), 1)
        self.assertEqual(len(person.phone_number), 1)
        self.assertEqual(len(person.email), 1)

    def test_person_serialization(self):
        """Test Person model serialization."""
        person = Person(
            identifier=[
                Identifier(identifier_type="UIN", identifier_value="123456789"),
            ],
            name=Name(given_name="John", surname="Doe"),
        )

        # Serialize to dict
        data = person.model_dump()
        self.assertEqual(data["@type"], "Person")
        self.assertEqual(len(data["identifier"]), 1)
        self.assertEqual(data["name"]["given_name"], "John")

        # Serialize to JSON mode (excludes None values)
        json_data = person.model_dump(mode="json", exclude_none=True)
        self.assertNotIn("sex", json_data)
        self.assertNotIn("birth_date", json_data)


class TestGroupSchema(unittest.TestCase):
    """Test Group schema."""

    def test_group_schema(self):
        """Test Group with members."""
        group = Group(
            group_identifier=[
                Identifier(identifier_type="GID", identifier_value="GRP-001"),
            ],
            group_type="Household",
            member_list=[
                Member(
                    member_identifier=[
                        Identifier(identifier_type="UIN", identifier_value="111"),
                    ],
                    demographic_info=Person(
                        identifier=[
                            Identifier(identifier_type="UIN", identifier_value="111"),
                        ],
                    ),
                ),
                Member(
                    member_identifier=[
                        Identifier(identifier_type="UIN", identifier_value="222"),
                    ],
                    demographic_info=Person(
                        identifier=[
                            Identifier(identifier_type="UIN", identifier_value="222"),
                        ],
                    ),
                ),
            ],
        )

        self.assertEqual(group.group_type, "Household")
        self.assertEqual(len(group.member_list), 2)
        self.assertEqual(group.member_list[0].member_identifier[0].identifier_value, "111")
        self.assertEqual(group.member_list[1].member_identifier[0].identifier_value, "222")


class TestSearchSchemas(unittest.TestCase):
    """Test search-related schemas."""

    def test_pagination_request_schema(self):
        """Test PaginationRequest schema."""
        pagination = PaginationRequest(
            page_size=10,
            page_number=1,
        )
        self.assertEqual(pagination.page_size, 10)
        self.assertEqual(pagination.page_number, 1)

        # Test validation - page_size must be > 0
        with self.assertRaises(ValidationError):
            PaginationRequest(page_size=0, page_number=1)

    def test_pagination_response_schema(self):
        """Test Pagination response schema."""
        pagination = Pagination(
            page_size=10,
            page_number=1,
            total_count=100,
        )
        self.assertEqual(pagination.page_size, 10)
        self.assertEqual(pagination.page_number, 1)
        self.assertEqual(pagination.total_count, 100)

    def test_search_sort_schema(self):
        """Test SearchSort schema."""
        sort = SearchSort(
            attribute_name="name",
            sort_order="asc",
        )
        self.assertEqual(sort.attribute_name, "name")
        self.assertEqual(sort.sort_order, "asc")

        # Test descending
        sort_desc = SearchSort(
            attribute_name="date",
            sort_order="desc",
        )
        self.assertEqual(sort_desc.sort_order, "desc")

    def test_search_criteria_schema(self):
        """Test SearchCriteria schema."""
        search_criteria = SearchCriteria(
            version="1.0.0",
            reg_type="SOCIAL_REGISTRY",
            query_type="idtype-value",
            query={
                "type": "UIN",
                "value": "123456789",
            },
            pagination=PaginationRequest(page_size=10, page_number=1),
            sort=[
                SearchSort(attribute_name="name", sort_order="asc"),
            ],
        )

        self.assertEqual(search_criteria.reg_type, "SOCIAL_REGISTRY")
        self.assertEqual(search_criteria.query_type, "idtype-value")
        self.assertEqual(search_criteria.query["type"], "UIN")
        self.assertIsNotNone(search_criteria.pagination)
        self.assertEqual(len(search_criteria.sort), 1)

    def test_search_request_schema(self):
        """Test SearchRequest schema."""
        search_request = SearchRequest(
            transaction_id="txn-123456",
            search_request=[
                SearchRequestItem(
                    reference_id="ref-001",
                    timestamp=datetime.now(),
                    search_criteria=SearchCriteria(
                        reg_type="SOCIAL_REGISTRY",
                        query_type="idtype-value",
                        query={"type": "UIN", "value": "123456789"},
                    ),
                    locale="en",
                )
            ],
        )

        self.assertEqual(search_request.transaction_id, "txn-123456")
        self.assertEqual(len(search_request.search_request), 1)
        self.assertEqual(search_request.search_request[0].reference_id, "ref-001")
        self.assertEqual(search_request.search_request[0].locale, "en")

    def test_search_response_schema(self):
        """Test SearchResponse schema."""
        search_response = SearchResponse(
            transaction_id="txn-123456",
            correlation_id="corr-789",
            search_response=[
                SearchResponseItem(
                    reference_id="ref-001",
                    timestamp=datetime.now(),
                    status="succ",
                    data=SearchResponseData(
                        reg_type="SOCIAL_REGISTRY",
                        reg_record_type="PERSON",
                        reg_records=[
                            {
                                "identifier": [
                                    {
                                        "identifier_type": "UIN",
                                        "identifier_value": "123456789",
                                    }
                                ],
                                "name": {"given_name": "John", "surname": "Doe"},
                            }
                        ],
                    ),
                    pagination=Pagination(
                        page_size=10,
                        page_number=1,
                        total_count=1,
                    ),
                )
            ],
        )

        self.assertEqual(search_response.transaction_id, "txn-123456")
        self.assertEqual(len(search_response.search_response), 1)
        self.assertEqual(search_response.search_response[0].status, "succ")
        self.assertIsNotNone(search_response.search_response[0].data)


class TestEnvelopeSchemas(unittest.TestCase):
    """Test envelope schemas."""

    def test_message_header_schema(self):
        """Test DCIMessageHeader schema."""
        header = DCIMessageHeader(
            version="1.0.0",
            message_id="msg-123456",
            message_ts=datetime.now(),
            action="search",
            sender_id="sender-org",
            sender_uri="https://sender.example.org/callback",
            receiver_id="receiver-org",
            total_count=1,
            is_msg_encrypted=False,
            meta={"custom_field": "value"},
        )

        self.assertEqual(header.version, "1.0.0")
        self.assertEqual(header.action, "search")
        self.assertEqual(header.sender_id, "sender-org")
        self.assertEqual(header.receiver_id, "receiver-org")
        self.assertFalse(header.is_msg_encrypted)
        self.assertEqual(header.meta["custom_field"], "value")

    def test_callback_header_schema(self):
        """Test DCICallbackHeader schema."""
        header = DCICallbackHeader(
            version="1.0.0",
            message_id="msg-123456",
            message_ts=datetime.now(),
            action="on-search",
            sender_id="sender-org",
            receiver_id="receiver-org",
            status=RequestStatus.SUCCESS,
            total_count=1,
            completed_count=1,
        )

        self.assertEqual(header.action, "on-search")
        self.assertEqual(header.status, RequestStatus.SUCCESS)
        self.assertEqual(header.completed_count, 1)

        # Test with error status
        error_header = DCICallbackHeader(
            version="1.0.0",
            message_id="msg-error",
            message_ts=datetime.now(),
            action="on-search",
            sender_id="sender-org",
            receiver_id="receiver-org",
            status=RequestStatus.REJECTED,
            status_reason_code="ERR_NOT_FOUND",
            status_reason_message="Record not found",
            total_count=1,
            completed_count=1,
        )

        self.assertEqual(error_header.status, RequestStatus.REJECTED)
        self.assertEqual(error_header.status_reason_code, "ERR_NOT_FOUND")
        self.assertEqual(error_header.status_reason_message, "Record not found")

    def test_envelope_schema(self):
        """Test DCIEnvelope schema."""
        envelope = DCIEnvelope(
            signature='namespace="dci", kidId="sender|key1|ed25519", signature="abcd1234"',
            header=DCIMessageHeader(
                message_id="msg-123",
                message_ts=datetime.now(),
                action="search",
                sender_id="sender-org",
                receiver_id="receiver-org",
            ),
            message={
                "transaction_id": "txn-456",
                "search_request": [],
            },
        )

        self.assertIn("namespace=", envelope.signature)
        self.assertEqual(envelope.header.action, "search")
        self.assertEqual(envelope.message["transaction_id"], "txn-456")

    def test_envelope_with_callback_header(self):
        """Test DCIEnvelope with callback header."""
        envelope = DCIEnvelope(
            signature='namespace="dci", kidId="sender|key1|ed25519", signature="abcd1234"',
            header=DCICallbackHeader(
                message_id="msg-123",
                message_ts=datetime.now(),
                action="on-search",
                sender_id="sender-org",
                receiver_id="receiver-org",
                status=RequestStatus.SUCCESS,
            ),
            message={
                "transaction_id": "txn-456",
                "search_response": [],
            },
        )

        self.assertEqual(envelope.header.action, "on-search")
        self.assertEqual(envelope.header.status, RequestStatus.SUCCESS)

    def test_schema_serialization(self):
        """Test comprehensive schema serialization."""
        # Create complete envelope
        envelope = DCIEnvelope(
            signature='namespace="dci", signature="test"',
            header=DCIMessageHeader(
                message_id="msg-123",
                message_ts=datetime(2024, 12, 3, 10, 0, 0),
                action="search",
                sender_id="sender",
                receiver_id="receiver",
            ),
            message=SearchRequest(
                transaction_id="txn-456",
                search_request=[
                    SearchRequestItem(
                        reference_id="ref-001",
                        timestamp=datetime(2024, 12, 3, 10, 0, 0),
                        search_criteria=SearchCriteria(
                            reg_type="SOCIAL_REGISTRY",
                            query_type="idtype-value",
                            query={"type": "UIN", "value": "123"},
                        ),
                    )
                ],
            ).model_dump(),
        )

        # Serialize to dict
        data = envelope.model_dump()
        self.assertIn("signature", data)
        self.assertIn("header", data)
        self.assertIn("message", data)

        # Serialize to JSON mode
        json_data = envelope.model_dump(mode="json")
        self.assertIsInstance(json_data["header"]["message_ts"], str)
