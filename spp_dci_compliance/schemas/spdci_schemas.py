# Copyright 2024 OpenSPP.org
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
SPDCI JSON Schema Definitions

This module contains Python dictionaries representing SPDCI API standard schemas
for use in compliance validation. These schemas are derived from:
- spdci-api-standards repository (YAML schemas)
- DR-Mockup-Compliance repository (JavaScript test schemas)
- CRVS-Mockup-Compliance repository (JavaScript test schemas)

All schemas are JSON Schema Draft-07 compatible and can be used with the
jsonschema library for validation.
"""

# ============================================================================
# SPDCI Core Schemas (from spdci-api-standards)
# ============================================================================

SEARCH_REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": (
        "1. Functional registry specific extension to search.\n"
        "2. Additional checks using conditional expressions is possible.\n"
        "3. Allows Country/Registry specific implementation extensions using key/value pairs."
    ),
    "properties": {
        "transaction_id": {
            "type": "string",
            "maxLength": 99,
            "description": (
                "1. transaction_id set by txn initiating system (i.e sender) to co-relate all "
                "related requests in the context of a business transaction.\n"
                "2. transaction_id should be same across processing systems/service end points.\n"
                "3. transaction_id uniqueness is ensured by txn initiating system (i.e sender)"
            ),
            "example": "0123456789",
        },
        "search_request": {
            "type": "array",
            "description": (
                "1. Batch requests enable multiple individual requests with respective consent/authorize codes"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "reference_id": {
                        "type": "string",
                        "description": "Unique reference_id set by txn initiating system for each request in a batch",
                        "example": "12345678901234567890",
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": (
                            "1. All dates and timestamps are represented in ISO 8601 format "
                            "including timezone - e.g 2022-12-04T17:20:07-04:00."
                        ),
                    },
                    "search_criteria": {
                        "type": "object",
                        "properties": {
                            "version": {"type": "string", "default": "1.0.0"},
                            "reg_type": {
                                "type": "string",
                                "description": (
                                    "Registry type values defined as per implementation context. "
                                    "Usually a list of enum values of all possible queryable functional registries"
                                ),
                                "example": "ns:org:RegistryType:Social",
                            },
                            "reg_record_type": {
                                "type": "string",
                                "description": (
                                    "Registry record type values defined as per implementation context. "
                                    "Usually a list of enum values of all possible queryable result sets"
                                ),
                                "example": "spdci-extensions-dci:Member",
                            },
                            "query_type": {
                                "type": "string",
                                "description": (
                                    "1. Query format allow multiple ways to search registry\n"
                                    "2. Templatized query expressions with placeholder for conditional values"
                                ),
                                "enum": ["idtype-value", "expression", "predicate", "graphql"],
                                "example": "expression",
                            },
                            "query": {
                                "description": (
                                    "1. Implementing systems can define schemas.\n"
                                    "2. Based on context, pre defined named queries can also help as part of ExpTemplate construct.\n"
                                    "3. ExpressionWithConditionList is simple generic search query construct to solve for majority of search conditions."
                                ),
                                "oneOf": [
                                    {"type": "object"},  # ExpTemplate or other query types
                                    {"type": "object"},  # IdentifierTypeValue
                                    {"type": "object"},  # ExpPredicateWithConditionList
                                ],
                            },
                            "sort": {
                                "type": "array",
                                "items": {"type": "object"},  # SearchSort items
                            },
                            "pagination": {
                                "type": "object",
                                "description": "Pagination definition, count starts with 1",
                                "properties": {
                                    "page_size": {"type": "number", "format": "int32", "example": 2000},
                                    "page_number": {
                                        "type": "number",
                                        "format": "int32",
                                        "default": 1,
                                        "example": 5,
                                    },
                                },
                                "required": ["page_size"],
                            },
                            "consent": {
                                "type": "object",
                                "description": "Consent information",
                            },
                            "authorize": {
                                "type": "object",
                                "description": "Authorization information",
                            },
                        },
                        "required": ["query_type", "query"],
                    },
                    "locale": {
                        "type": "string",
                        "description": "indicates language code. SPDCI Connect supports country codes as per ISO 639.3 standard",
                        "pattern": "^[a-z]{3,3}$",
                        "example": "en",
                    },
                },
                "required": ["reference_id", "timestamp", "search_criteria"],
            },
        },
    },
    "required": ["transaction_id", "search_request"],
}

SEARCH_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Response to search request. Multiple responses for each page can be pushed to the caller as an implementation!",
    "properties": {
        "transaction_id": {
            "type": "string",
            "maxLength": 99,
            "description": (
                "1. transaction_id set by txn initiating system (i.e sender) to co-relate all "
                "related requests in the context of a business transaction.\n"
                "2. transaction_id should be same across processing systems/service end points.\n"
                "3. transaction_id uniqueness is ensured by txn initiating system (i.e sender)"
            ),
            "example": "0123456789",
        },
        "correlation_id": {
            "type": "string",
            "maxLength": 99,
            "description": (
                "1. correlation_id acknowledged by end txn processing system (i.e receiver) to co-relate all "
                "related requests in the context of a business transaction.\n"
                "2. correlation_id uniqueness is ensured by txn processing system (i.e receiver)"
            ),
            "example": "9876543210",
        },
        "search_response": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reference_id": {
                        "type": "string",
                        "description": "Unique reference_id set by txn initiating system for each request in a batch",
                        "example": "12345678901234567890",
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": (
                            "1. All dates and timestamps are represented in ISO 8601 format "
                            "including timezone - e.g 2022-12-04T17:20:07-04:00."
                        ),
                    },
                    "status": {
                        "type": "string",
                        "description": "Request status: rcvd (Received), pdng (Pending), succ (Success), rjct (Rejected)",
                        "enum": ["rcvd", "pdng", "succ", "rjct"],
                    },
                    "status_reason_code": {
                        "type": "string",
                        "description": "Identity verification request status reason codes",
                        "enum": [
                            "rjct.reference_id.invalid",
                            "rjct.reference_id.duplicate",
                            "rjct.timestamp.invalid",
                            "rjct.search_criteria.invalid",
                            "rjct.filter.invalid",
                            "rjct.sort.invalid",
                            "rjct.pagination.invalid",
                            "rjct.search.too_many_records_found",
                        ],
                    },
                    "status_reason_message": {
                        "type": "string",
                        "maxLength": 999,
                        "description": "Status reason code message. Helps actionable messaging for systems/end users",
                    },
                    "data": {
                        "type": "object",
                        "description": "Search result record as an outcome of search/subscribe action",
                        "properties": {
                            "version": {"type": "string", "default": "1.0.0"},
                            "reg_type": {
                                "type": "string",
                                "description": (
                                    "Registry type values defined as per implementation context. "
                                    "Usually a list of enum values of all possible queryable functional registries"
                                ),
                                "example": "ns:org:RegistryType:Social",
                            },
                            "reg_record_type": {
                                "type": "string",
                                "description": (
                                    "Registry record type values defined as per implementation context. "
                                    "Usually a list of enum values of all possible queryable result sets"
                                ),
                                "example": "spdci-extensions-dci:Member",
                            },
                            "reg_records": {
                                "type": "object",
                                "description": 'The "person" object contains fields expected in response of search',
                            },
                        },
                        "required": ["reg_record_type", "reg_records"],
                    },
                    "pagination": {
                        "type": "object",
                        "description": "Pagination definition, count starts with 1",
                        "properties": {
                            "page_size": {"type": "number", "format": "int32", "example": 2000},
                            "page_number": {"type": "number", "format": "int32", "example": 5},
                            "total_count": {"type": "number", "format": "int32", "example": 24250},
                        },
                        "required": ["page_size", "page_number", "total_count"],
                    },
                    "locale": {
                        "type": "string",
                        "description": "indicates language code. SPDCI Connect supports country codes as per ISO 639.3 standard",
                        "pattern": "^[a-z]{3,3}$",
                        "example": "en",
                    },
                },
                "required": ["reference_id", "timestamp", "status"],
            },
        },
    },
    "required": ["transaction_id", "correlation_id", "search_response"],
}

MSG_HEADER_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Message header",
    "properties": {
        "version": {
            "type": "string",
            "default": "1.0.0",
            "description": "Messaging protocol specification version being used",
        },
        "message_id": {
            "type": "string",
            "example": "123",
            "description": (
                "1. Unique message id to communicate between sender and receiver systems to reliable deliver "
                "the message over any transport layer i.e https, pub/sub, sftp etc.,\n"
                "2. The scope of message_id end with successful ack of the message by the receiver.\n"
                "3. To relay the message between hops, underlying relying parties may consider to store and "
                "forward the message with integrity, ie Signature intact."
            ),
        },
        "message_ts": {
            "type": "string",
            "format": "date-time",
            "description": (
                "1. All dates and timestamps are represented in ISO 8601 format "
                "including timezone - e.g 2022-12-04T17:20:07-04:00."
            ),
        },
        "action": {
            "type": "string",
            "description": (
                "spdci Connect specific action. Usually verb from the URI. Helps in sync, async, "
                "store/fwd processing. Helps to identify payload type in message property."
            ),
        },
        "sender_id": {
            "type": "string",
            "example": "spmis.example.org",
            "description": (
                "1. sender_id registered with the receiving system or gateway.\n"
                "2. Used for authorization, encryption, digital sign verification, etc.,"
            ),
        },
        "sender_uri": {
            "type": "string",
            "format": "uri",
            "example": "https://spmis.example.org/{namespace}/callback/on-search",
            "description": (
                "1. sender url to accept callbacks. Applicable only for async communications and if response ack_status is ACK.\n"
                "2. Default uri is assumed to be configured on the gateway as part of sender/receiver onboarding.\n"
                "3. For SFTP based communications, this shall be set to server/folder details."
            ),
        },
        "receiver_id": {
            "type": "string",
            "example": "registry.example.org",
            "description": "receiver id registered with the calling system. Used for authorization, encryption, digital sign verification, etc., functions.",
        },
        "total_count": {
            "type": "integer",
            "example": 21800,
            "description": "Total no of requests present in the message request",
        },
        "is_msg_encrypted": {
            "type": "boolean",
            "default": False,
            "description": "Is message encrypted?",
        },
        "meta": {
            "type": "object",
            "description": (
                "Additional meta info defined as per implementation context. "
                "Usually unencrypted list of name/value, tags, etc., to provide additional info to intermediary entities. "
                "The information SHOULD be privacy preserving"
            ),
        },
    },
    "required": ["message_id", "message_ts", "action", "sender_id", "total_count"],
}

MSG_CALLBACK_HEADER_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Message header for callback responses",
    "properties": {
        "version": {
            "type": "string",
            "default": "1.0.0",
            "description": "Messaging protocol specification version being used",
        },
        "message_id": {
            "type": "string",
            "example": "789",
            "description": (
                "1. Unique message id to communicate between sender and receiver systems to reliable deliver "
                "the message over any transport layer i.e https, pub/sub, sftp etc.,\n"
                "2. The scope of message_id end with successful ack of the message by the receiver.\n"
                "3. To relay the message between hops, underlying relying parties may consider to store and "
                "forward the message with integrity, ie Signature intact."
            ),
        },
        "message_ts": {
            "type": "string",
            "format": "date-time",
            "description": (
                "1. All dates and timestamps are represented in ISO 8601 format "
                "including timezone - e.g 2022-12-04T17:20:07-04:00."
            ),
        },
        "action": {
            "type": "string",
            "description": "SPDCI Connect specific action. Usually verb from the URI should go here to help store and fwd kind of processing requirements.",
        },
        "status": {
            "type": "string",
            "description": "Request status: rcvd (Received), pdng (Pending), succ (Success), rjct (Rejected)",
            "enum": ["rcvd", "pdng", "succ", "rjct"],
        },
        "status_reason_code": {
            "type": "string",
            "description": "Message header related common status reason codes",
            "enum": [
                "rjct.version.invalid",
                "rjct.message_id.duplicate",
                "rjct.message_ts.invalid",
                "rjct.action.invalid",
                "rjct.action.not_supported",
                "rjct.total_count.invalid",
                "rjct.total_count.limit_exceeded",
                "rjct.errors.too_many",
            ],
        },
        "status_reason_message": {
            "type": "string",
            "maxLength": 999,
            "description": "Status reason code message, if any, Helps actionable messaging for system/end users",
        },
        "total_count": {
            "type": "integer",
            "example": 21800,
            "description": "Total no of requests present in the message request",
        },
        "completed_count": {
            "type": "integer",
            "example": 50,
            "description": "No of requests in completed state. Complete includes success and error requests due to functional errors",
        },
        "sender_id": {
            "type": "string",
            "example": "registry.example.org",
            "description": (
                "1. sender_id registered with the receiving system or gateway.\n"
                "2. Used for authorization, encryption, digital sign verification, etc.,"
            ),
        },
        "receiver_id": {
            "type": "string",
            "example": "spmis.example.org",
            "description": "receiver id registered with the calling system. Used for authorization, encryption, digital sign verification, etc., functions.",
        },
        "is_msg_encrypted": {
            "type": "boolean",
            "default": False,
            "description": "Is message encrypted?",
        },
        "meta": {
            "type": "object",
            "description": (
                "Additional meta info defined as per implementation context. "
                "Usually unencrypted list of name/value, tags, etc., to provide additional info to intermediary entities. "
                "The information SHOULD be privacy preserving"
            ),
        },
    },
    "required": ["message_id", "message_ts", "action", "status"],
}

# ============================================================================
# Disability Registry (DR) Schemas (from DR-Mockup-Compliance)
# ============================================================================

DR_REG_RECORDS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Disability Registry record schema for individual disability information",
    "properties": {
        "personal_details": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "name": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                    },
                },
                "date_of_birth": {"type": "string", "format": "date"},
                "gender": {"type": "string"},
            },
        },
        "disability_status": {"type": "string"},
        "disability_level": {"type": "string"},
        "disability_details": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "impairment_type": {"type": "string"},
                    "impairment_level": {"type": "string"},
                    "impairment_cause": {"type": "string"},
                    "age_on_set": {"type": "string"},
                },
            },
        },
        "disability_support": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "human_assistance": {
                        "type": "object",
                        "properties": {
                            "frequency": {"type": "string"},
                            "type": {"type": "string"},
                            "support_status": {"type": "string"},
                        },
                    },
                },
            },
        },
        "transport_requirement": {"type": "string"},
        "housing_type": {"type": "string"},
        "programs_enrollments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "programme_name": {"type": "string"},
                    "programme_identifier": {"type": "string"},
                },
            },
        },
        "registration_date": {"type": "string", "format": "date-time"},
        "last_updated": {"type": "string", "format": "date-time"},
    },
}

DR_SEARCH_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Disability Registry async search response schema",
    "properties": {
        "message": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string", "maxLength": 99},
                "correlation_id": {"type": "string"},
                "search_response": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference_id": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "status": {"type": "string"},
                            "status_reason_code": {"type": "string"},
                            "status_reason_message": {"type": "string"},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "version": {"type": "string"},
                                    "reg_type": {"type": "string"},
                                    "reg_event_type": {"type": "string"},
                                    "reg_record_type": {"type": "string"},
                                    "reg_records": {
                                        "type": "array",
                                        "items": DR_REG_RECORDS_SCHEMA,
                                    },
                                },
                            },
                        },
                    },
                },
                "pagination": {
                    "type": "object",
                    "properties": {
                        "page_size": {"type": "integer"},
                        "page_number": {"type": "integer"},
                        "total_count": {"type": "integer"},
                    },
                },
                "locale": {"type": "string"},
            },
        },
    },
    "required": ["message"],
}

DR_DISABILITY_STATUS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Disability Registry get-disability-status response schema",
    "properties": {
        "message": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string", "maxLength": 99},
                "correlation_id": {"type": "string"},
                "disabled_response": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference_id": {"type": "string"},
                            "timestamp": {"type": "string", "format": "date-time"},
                            "status": {"type": "string"},
                            "status_reason_message": {"type": "string"},
                            "disabled_status": {"type": "string", "enum": ["yes", "no"]},
                        },
                    },
                },
            },
        },
    },
}

# ============================================================================
# CRVS (Civil Registration and Vital Statistics) Schemas
# ============================================================================

CRVS_REG_RECORDS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "CRVS registry record schema for vital events (birth, death, marriage, divorce)",
    "properties": {
        "identifier": {
            "type": "object",
            "properties": {
                "identifier_type": {"type": "string"},
                "identifier_value": {"type": "string"},
            },
        },
        "death_date": {"type": "string", "format": "date-time"},
        "death_place": {"type": "string"},
        "address": {
            "type": "object",
            "properties": {
                "address_line1": {"type": "string"},
                "address_line2": {"type": "string"},
                "locality": {"type": "string"},
                "sub_region_code": {"type": "string"},
                "region_code": {"type": "string"},
                "postal_code": {"type": "string"},
                "country_code": {"type": "string"},
                "geo_location": {
                    "type": "object",
                    "properties": {
                        "plus_code": {
                            "type": "object",
                            "properties": {
                                "global_code": {"type": "string"},
                                "geometry": {
                                    "type": "object",
                                    "properties": {
                                        "bounds": {
                                            "type": "object",
                                            "properties": {
                                                "northeast": {
                                                    "type": "object",
                                                    "properties": {
                                                        "latitude": {"type": "number"},
                                                        "longitude": {"type": "number"},
                                                    },
                                                },
                                                "southwest": {
                                                    "type": "object",
                                                    "properties": {
                                                        "latitude": {"type": "number"},
                                                        "longitude": {"type": "number"},
                                                    },
                                                },
                                            },
                                        },
                                        "location": {
                                            "type": "object",
                                            "properties": {
                                                "@id": {"type": "string"},
                                                "@type": {"type": "string"},
                                                "latitude": {"type": "number"},
                                                "longitude": {"type": "number"},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "marital_status": {"type": "string"},
        "marriage_date": {"type": "string", "format": "date-time"},
        "divorce_date": {"type": "string", "format": "date-time"},
        "parent1_identifier": {
            "type": "object",
            "properties": {
                "identifier_type": {"type": "string"},
                "identifier_value": {"type": "string"},
            },
        },
        "parent2_identifier": {
            "type": "object",
            "properties": {
                "identifier_type": {"type": "string"},
                "identifier_value": {"type": "string"},
            },
        },
    },
}

CRVS_SEARCH_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "CRVS sync search response schema",
    "properties": {
        "transaction_id": {"type": "string", "maxLength": 99},
        "correlation_id": {"type": "string"},
        "txnstatus_response": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string", "maxLength": 99},
                "correlation_id": {"type": "string"},
                "search_response": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference_id": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "status": {"type": "string"},
                            "status_reason_code": {"type": "string"},
                            "status_reason_message": {"type": "string"},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "version": {"type": "string"},
                                    "reg_type": {"type": "string"},
                                    "reg_event_type": {"type": "string"},
                                    "reg_record_type": {"type": "string"},
                                    "reg_records": {"type": "array"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}

CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "CRVS async search response schema",
    "properties": {
        "transaction_id": {"type": "string", "maxLength": 99},
        "correlation_id": {"type": "string"},
        "search_response": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["status", "message"],
        },
    },
    "required": ["transaction_id", "correlation_id", "search_response"],
}

CRVS_ON_SEARCH_REQUEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "description": "CRVS on-search callback request schema",
    "properties": {
        "message": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string", "maxLength": 99},
                "correlation_id": {"type": "string"},
                "search_response": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference_id": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "status": {"type": "string", "enum": ["rcvd", "processed", "failed"]},
                            "status_reason_code": {"type": "string"},
                            "status_reason_message": {"type": "string"},
                            "data": {"type": "object"},
                            "pagination": {"type": "object"},
                            "locale": {"type": "string", "enum": ["en", "fr", "ar"]},
                        },
                    },
                },
            },
            "required": ["transaction_id", "correlation_id", "search_response"],
        },
    },
    "required": ["message"],
}

# ============================================================================
# DCI Envelope Schema (Three-Part Structure)
# ============================================================================

DCI_ENVELOPE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": (
        "DCI envelope structure with three parts: signature, header, and message. "
        "This is the top-level structure for all DCI API communications."
    ),
    "properties": {
        "signature": {
            "type": "object",
            "description": "Digital signature for message authentication and integrity",
            "properties": {
                "signature": {
                    "type": "string",
                    "description": "Base64 encoded signature of the message payload",
                },
            },
            "required": ["signature"],
        },
        "header": {
            "type": "object",
            "description": "Message header containing routing and protocol information",
            "oneOf": [MSG_HEADER_SCHEMA, MSG_CALLBACK_HEADER_SCHEMA],
        },
        "message": {
            "type": "object",
            "description": "The actual message payload (search request, search response, etc.)",
            "oneOf": [
                SEARCH_REQUEST_SCHEMA,
                SEARCH_RESPONSE_SCHEMA,
                DR_SEARCH_RESPONSE_SCHEMA,
                DR_DISABILITY_STATUS_SCHEMA,
                CRVS_SEARCH_RESPONSE_SCHEMA,
                CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA,
                CRVS_ON_SEARCH_REQUEST_SCHEMA,
            ],
        },
    },
    "required": ["signature", "header", "message"],
}

# ============================================================================
# Additional Response Schemas (from mockup compliance tests)
# ============================================================================

SUBSCRIBE_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Standard subscribe response schema",
    "properties": {
        "message": {
            "type": "object",
            "properties": {
                "ack_status": {"type": "string"},
                "timestamp": {"type": "string"},
                "error": {"type": "object"},
                "correlation_id": {"type": "string"},
            },
            "required": ["ack_status", "timestamp", "error", "correlation_id"],
            "additionalProperties": False,
        },
    },
    "required": ["message"],
}

UNSUBSCRIBE_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Standard unsubscribe response schema",
    "properties": {
        "message": {
            "type": "object",
            "properties": {
                "ack_status": {"type": "string"},
                "timestamp": {"type": "string"},
                "error": {"type": "object"},
                "correlation_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
}

ON_SEARCH_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "description": "Standard on-search callback response schema",
    "properties": {
        "message": {
            "type": "object",
            "properties": {
                "ack_status": {"type": "string"},
                "timestamp": {"type": "string"},
                "error": {"type": "object"},
                "correlation_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "required": ["message"],
}

# ============================================================================
# Schema Registry
# ============================================================================

SCHEMA_REGISTRY = {
    # Core SPDCI schemas
    "search_request": SEARCH_REQUEST_SCHEMA,
    "search_response": SEARCH_RESPONSE_SCHEMA,
    "msg_header": MSG_HEADER_SCHEMA,
    "msg_callback_header": MSG_CALLBACK_HEADER_SCHEMA,
    # DR schemas
    "dr_reg_records": DR_REG_RECORDS_SCHEMA,
    "dr_search_response": DR_SEARCH_RESPONSE_SCHEMA,
    "dr_disability_status": DR_DISABILITY_STATUS_SCHEMA,
    # CRVS schemas
    "crvs_reg_records": CRVS_REG_RECORDS_SCHEMA,
    "crvs_search_response": CRVS_SEARCH_RESPONSE_SCHEMA,
    "crvs_async_search_response": CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA,
    "crvs_on_search_request": CRVS_ON_SEARCH_REQUEST_SCHEMA,
    # Envelope and common schemas
    "dci_envelope": DCI_ENVELOPE_SCHEMA,
    "subscribe_response": SUBSCRIBE_RESPONSE_SCHEMA,
    "unsubscribe_response": UNSUBSCRIBE_RESPONSE_SCHEMA,
    "on_search_response": ON_SEARCH_RESPONSE_SCHEMA,
}


def get_schema(schema_name):
    """
    Retrieve a schema by name from the schema registry.

    Args:
        schema_name: Name of the schema to retrieve

    Returns:
        dict: The JSON schema dictionary

    Raises:
        KeyError: If schema_name is not found in the registry
    """
    return SCHEMA_REGISTRY[schema_name]
