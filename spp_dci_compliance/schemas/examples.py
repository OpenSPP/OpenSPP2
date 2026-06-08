# Copyright 2024 OpenSPP.org
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
SPDCI Schema Usage Examples

This module demonstrates how to use the SPDCI schemas for validation.
These examples can be used as templates for creating valid DCI messages.
"""

import logging

_logger = logging.getLogger(__name__)

# Example 1: Valid Search Request
EXAMPLE_SEARCH_REQUEST = {
    "transaction_id": "txn-2024-001",
    "search_request": [
        {
            "reference_id": "ref-001",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "search_criteria": {
                "version": "1.0.0",
                "reg_type": "ns:org:RegistryType:Disability",
                "reg_record_type": "spdci-extensions-dci:Member",
                "query_type": "expression",
                "query": {
                    "field": "personal_details.identifier",
                    "operator": "eq",
                    "value": "ID-12345",
                },
                "pagination": {"page_size": 100, "page_number": 1},
            },
            "locale": "eng",
        }
    ],
}

# Example 2: Valid Search Response
EXAMPLE_SEARCH_RESPONSE = {
    "transaction_id": "txn-2024-001",
    "correlation_id": "corr-2024-001",
    "search_response": [
        {
            "reference_id": "ref-001",
            "timestamp": "2024-01-15T10:30:05+00:00",
            "status": "succ",
            "data": {
                "version": "1.0.0",
                "reg_type": "ns:org:RegistryType:Disability",
                "reg_record_type": "spdci-extensions-dci:Member",
                "reg_records": {
                    "personal_details": {
                        "identifier": "ID-12345",
                        "name": {"first_name": "John", "last_name": "Doe"},
                        "date_of_birth": "1990-01-01",
                        "gender": "M",
                    },
                    "disability_status": "yes",
                    "disability_level": "moderate",
                },
            },
            "pagination": {"page_size": 100, "page_number": 1, "total_count": 1},
            "locale": "eng",
        }
    ],
}

# Example 3: Valid Message Header
EXAMPLE_MSG_HEADER = {
    "version": "1.0.0",
    "message_id": "msg-2024-001",
    "message_ts": "2024-01-15T10:30:00+00:00",
    "action": "search",
    "sender_id": "spmis.example.org",
    "sender_uri": "https://spmis.example.org/dci/callback/on-search",
    "receiver_id": "dr.example.org",
    "total_count": 1,
    "is_msg_encrypted": False,
    "meta": {"request_origin": "web_portal", "user_role": "case_worker"},
}

# Example 4: Valid Message Callback Header
EXAMPLE_MSG_CALLBACK_HEADER = {
    "version": "1.0.0",
    "message_id": "msg-2024-001-response",
    "message_ts": "2024-01-15T10:30:05+00:00",
    "action": "on-search",
    "status": "succ",
    "total_count": 1,
    "completed_count": 1,
    "sender_id": "dr.example.org",
    "receiver_id": "spmis.example.org",
    "is_msg_encrypted": False,
}

# Example 5: Valid DR Registry Record
EXAMPLE_DR_REG_RECORD = {
    "personal_details": {
        "identifier": "DR-2024-12345",
        "name": {"first_name": "Jane", "last_name": "Smith"},
        "date_of_birth": "1985-06-15",
        "gender": "F",
    },
    "disability_status": "yes",
    "disability_level": "severe",
    "disability_details": [
        {
            "impairment_type": "visual",
            "impairment_level": "severe",
            "impairment_cause": "congenital",
            "age_on_set": "birth",
        }
    ],
    "disability_support": [
        {
            "human_assistance": {
                "frequency": "daily",
                "type": "personal_care",
                "support_status": "receiving",
            }
        }
    ],
    "transport_requirement": "wheelchair_accessible",
    "housing_type": "adapted",
    "programs_enrollments": [{"programme_name": "Disability Support Grant", "programme_identifier": "DSG-001"}],
    "registration_date": "2024-01-01T00:00:00+00:00",
    "last_updated": "2024-01-15T10:00:00+00:00",
}

# Example 6: Valid DR Search Response
EXAMPLE_DR_SEARCH_RESPONSE = {
    "message": {
        "transaction_id": 2024001,
        "correlation_id": "corr-2024-001",
        "search_response": [
            {
                "reference_id": "ref-001",
                "timestamp": "2024-01-15T10:30:05+00:00",
                "status": "succ",
                "status_reason_code": "",
                "status_reason_message": "Search completed successfully",
                "data": {
                    "version": "1.0.0",
                    "reg_type": "disability",
                    "reg_event_type": "query",
                    "reg_record_type": "member",
                    "reg_records": [EXAMPLE_DR_REG_RECORD],
                },
            }
        ],
        "pagination": {"page_size": 100, "page_number": 1, "total_count": 1},
        "locale": "eng",
    }
}

# Example 7: Valid DR Disability Status Response
EXAMPLE_DR_DISABILITY_STATUS = {
    "message": {
        "transaction_id": 2024002,
        "correlation_id": "corr-2024-002",
        "disabled_response": [
            {
                "reference_id": "ref-002",
                "timestamp": "2024-01-15T11:00:00+00:00",
                "status": "succ",
                "status_reason_message": "Status retrieved successfully",
                "disabled_status": "yes",
            }
        ],
    }
}

# Example 8: Valid CRVS Registry Record
EXAMPLE_CRVS_REG_RECORD = {
    "identifier": {"identifier_type": "death_certificate", "identifier_value": "DC-2024-001"},
    "death_date": "2024-01-10T08:30:00+00:00",
    "death_place": "General Hospital",
    "address": {
        "address_line1": "123 Main Street",
        "address_line2": "Apt 4B",
        "locality": "Central District",
        "sub_region_code": "CD-01",
        "region_code": "R-01",
        "postal_code": "12345",
        "country_code": "XX",
    },
    "marital_status": "married",
    "marriage_date": "2010-05-20T00:00:00+00:00",
}

# Example 9: Valid DCI Envelope
EXAMPLE_DCI_ENVELOPE = {
    "signature": {"signature": "base64_encoded_signature_would_go_here=="},
    "header": EXAMPLE_MSG_HEADER,
    "message": EXAMPLE_SEARCH_REQUEST,
}

# Example 10: Valid Subscribe Response
EXAMPLE_SUBSCRIBE_RESPONSE = {
    "message": {
        "ack_status": "ACK",
        "timestamp": "2024-01-15T10:30:00+00:00",
        "error": {},
        "correlation_id": "corr-2024-003",
    }
}


def validate_examples():
    """
    Validate all examples against their schemas.
    Requires jsonschema library to be installed.
    """
    try:
        import jsonschema

        from . import (
            CRVS_REG_RECORDS_SCHEMA,
            DCI_ENVELOPE_SCHEMA,
            DR_DISABILITY_STATUS_SCHEMA,
            DR_REG_RECORDS_SCHEMA,
            DR_SEARCH_RESPONSE_SCHEMA,
            MSG_CALLBACK_HEADER_SCHEMA,
            MSG_HEADER_SCHEMA,
            SEARCH_REQUEST_SCHEMA,
            SEARCH_RESPONSE_SCHEMA,
            SUBSCRIBE_RESPONSE_SCHEMA,
        )

        examples = [
            ("Search Request", EXAMPLE_SEARCH_REQUEST, SEARCH_REQUEST_SCHEMA),
            ("Search Response", EXAMPLE_SEARCH_RESPONSE, SEARCH_RESPONSE_SCHEMA),
            ("Message Header", EXAMPLE_MSG_HEADER, MSG_HEADER_SCHEMA),
            ("Message Callback Header", EXAMPLE_MSG_CALLBACK_HEADER, MSG_CALLBACK_HEADER_SCHEMA),
            ("DR Registry Record", EXAMPLE_DR_REG_RECORD, DR_REG_RECORDS_SCHEMA),
            ("DR Search Response", EXAMPLE_DR_SEARCH_RESPONSE, DR_SEARCH_RESPONSE_SCHEMA),
            ("DR Disability Status", EXAMPLE_DR_DISABILITY_STATUS, DR_DISABILITY_STATUS_SCHEMA),
            ("CRVS Registry Record", EXAMPLE_CRVS_REG_RECORD, CRVS_REG_RECORDS_SCHEMA),
            ("DCI Envelope", EXAMPLE_DCI_ENVELOPE, DCI_ENVELOPE_SCHEMA),
            ("Subscribe Response", EXAMPLE_SUBSCRIBE_RESPONSE, SUBSCRIBE_RESPONSE_SCHEMA),
        ]

        _logger.info("Validating examples against schemas...")
        for name, example, schema in examples:
            try:
                jsonschema.validate(instance=example, schema=schema)
                _logger.info("%s is valid", name)
            except jsonschema.ValidationError as e:
                _logger.error("%s validation failed: %s", name, e.message)

        _logger.info("All examples validated!")
        return True

    except ImportError:
        _logger.error("jsonschema library not installed. Install with: pip install jsonschema")
        return False


if __name__ == "__main__":
    validate_examples()
