# Copyright 2024 OpenSPP.org
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
SPDCI Schema Package

This package provides JSON Schema definitions for SPDCI (Social Protection Data
Connectivity Initiative) API standards and extensions.

The schemas are organized into several categories:
- Core SPDCI schemas (search request/response, message headers)
- Disability Registry (DR) specific schemas
- CRVS (Civil Registration and Vital Statistics) specific schemas
- DCI envelope structure for message wrapping

All schemas are compatible with JSON Schema Draft-07 and can be used with
the jsonschema library for validation.

Example usage:
    from spp_dci_compliance.schemas import SEARCH_REQUEST_SCHEMA, get_schema
    import jsonschema

    # Using direct import
    jsonschema.validate(instance=data, schema=SEARCH_REQUEST_SCHEMA)

    # Using schema registry
    schema = get_schema("search_request")
    jsonschema.validate(instance=data, schema=schema)
"""

from .spdci_schemas import (
    # Core SPDCI Schemas
    SEARCH_REQUEST_SCHEMA,
    SEARCH_RESPONSE_SCHEMA,
    MSG_HEADER_SCHEMA,
    MSG_CALLBACK_HEADER_SCHEMA,
    # Disability Registry (DR) Schemas
    DR_REG_RECORDS_SCHEMA,
    DR_SEARCH_RESPONSE_SCHEMA,
    DR_DISABILITY_STATUS_SCHEMA,
    # CRVS Schemas
    CRVS_REG_RECORDS_SCHEMA,
    CRVS_SEARCH_RESPONSE_SCHEMA,
    CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA,
    CRVS_ON_SEARCH_REQUEST_SCHEMA,
    # DCI Envelope Schema
    DCI_ENVELOPE_SCHEMA,
    # Common Response Schemas
    SUBSCRIBE_RESPONSE_SCHEMA,
    UNSUBSCRIBE_RESPONSE_SCHEMA,
    ON_SEARCH_RESPONSE_SCHEMA,
    # Schema Registry and Helper
    SCHEMA_REGISTRY,
    get_schema,
)

__all__ = [
    # Core SPDCI Schemas
    "SEARCH_REQUEST_SCHEMA",
    "SEARCH_RESPONSE_SCHEMA",
    "MSG_HEADER_SCHEMA",
    "MSG_CALLBACK_HEADER_SCHEMA",
    # Disability Registry (DR) Schemas
    "DR_REG_RECORDS_SCHEMA",
    "DR_SEARCH_RESPONSE_SCHEMA",
    "DR_DISABILITY_STATUS_SCHEMA",
    # CRVS Schemas
    "CRVS_REG_RECORDS_SCHEMA",
    "CRVS_SEARCH_RESPONSE_SCHEMA",
    "CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA",
    "CRVS_ON_SEARCH_REQUEST_SCHEMA",
    # DCI Envelope Schema
    "DCI_ENVELOPE_SCHEMA",
    # Common Response Schemas
    "SUBSCRIBE_RESPONSE_SCHEMA",
    "UNSUBSCRIBE_RESPONSE_SCHEMA",
    "ON_SEARCH_RESPONSE_SCHEMA",
    # Schema Registry and Helper
    "SCHEMA_REGISTRY",
    "get_schema",
]
