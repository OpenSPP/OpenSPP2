# SPDCI JSON Schemas

This directory contains Python dictionaries representing SPDCI (Social Protection Data
Connectivity Initiative) JSON schemas for compliance validation.

## Overview

The schemas are extracted and converted from:

1. **spdci-api-standards** repository - Official YAML schema definitions
2. **DR-Mockup-Compliance** repository - Disability Registry test schemas
3. **CRVS-Mockup-Compliance** repository - Civil Registration and Vital Statistics test
   schemas

All schemas are JSON Schema Draft-07 compatible and can be used with the `jsonschema`
library.

## Available Schemas

### Core SPDCI Schemas

- **SEARCH_REQUEST_SCHEMA** - Search request structure
- **SEARCH_RESPONSE_SCHEMA** - Search response structure
- **MSG_HEADER_SCHEMA** - Message header for requests
- **MSG_CALLBACK_HEADER_SCHEMA** - Message header for callback responses

### Disability Registry (DR) Schemas

- **DR_REG_RECORDS_SCHEMA** - Individual disability record structure
- **DR_SEARCH_RESPONSE_SCHEMA** - Async search response from DR
- **DR_DISABILITY_STATUS_SCHEMA** - Disability status check response

### CRVS Schemas

- **CRVS_REG_RECORDS_SCHEMA** - Vital events record structure (birth, death, marriage,
  divorce)
- **CRVS_SEARCH_RESPONSE_SCHEMA** - Sync search response from CRVS
- **CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA** - Async search response from CRVS
- **CRVS_ON_SEARCH_REQUEST_SCHEMA** - On-search callback request structure

### Envelope and Common Schemas

- **DCI_ENVELOPE_SCHEMA** - Three-part envelope structure (signature, header, message)
- **SUBSCRIBE_RESPONSE_SCHEMA** - Standard subscribe response
- **UNSUBSCRIBE_RESPONSE_SCHEMA** - Standard unsubscribe response
- **ON_SEARCH_RESPONSE_SCHEMA** - Standard on-search callback response

## Usage Examples

### Basic Import and Validation

```python
from spp_dci_compliance.schemas import SEARCH_REQUEST_SCHEMA
import jsonschema

# Your data to validate
search_request = {
    "transaction_id": "txn-123",
    "search_request": [
        {
            "reference_id": "ref-001",
            "timestamp": "2024-01-01T12:00:00Z",
            "search_criteria": {
                "query_type": "expression",
                "query": {"field": "name", "value": "John"}
            }
        }
    ]
}

# Validate against schema
try:
    jsonschema.validate(instance=search_request, schema=SEARCH_REQUEST_SCHEMA)
    print("Valid!")
except jsonschema.ValidationError as e:
    print(f"Validation error: {e.message}")
```

### Using Schema Registry

```python
from spp_dci_compliance.schemas import get_schema, SCHEMA_REGISTRY

# Get schema by name
search_schema = get_schema("search_request")

# List all available schemas
for schema_name in SCHEMA_REGISTRY.keys():
    print(schema_name)
```

### Validating DCI Envelope

```python
from spp_dci_compliance.schemas import DCI_ENVELOPE_SCHEMA
import jsonschema

# Complete DCI message envelope
envelope = {
    "signature": {
        "signature": "base64_encoded_signature_here"
    },
    "header": {
        "message_id": "msg-123",
        "message_ts": "2024-01-01T12:00:00Z",
        "action": "search",
        "sender_id": "spmis.example.org",
        "total_count": 1
    },
    "message": {
        "transaction_id": "txn-123",
        "search_request": [...]
    }
}

jsonschema.validate(instance=envelope, schema=DCI_ENVELOPE_SCHEMA)
```

### Registry-Specific Validation

```python
from spp_dci_compliance.schemas import DR_REG_RECORDS_SCHEMA, CRVS_REG_RECORDS_SCHEMA

# Validate Disability Registry record
dr_record = {
    "personal_details": {
        "identifier": "DR-12345",
        "name": {
            "first_name": "John",
            "last_name": "Doe"
        },
        "date_of_birth": "1990-01-01",
        "gender": "M"
    },
    "disability_status": "yes",
    "disability_level": "moderate"
}

jsonschema.validate(instance=dr_record, schema=DR_REG_RECORDS_SCHEMA)

# Validate CRVS record
crvs_record = {
    "identifier": {
        "identifier_type": "national_id",
        "identifier_value": "NID-67890"
    },
    "death_date": "2024-01-15T10:30:00Z",
    "death_place": "Hospital ABC"
}

jsonschema.validate(instance=crvs_record, schema=CRVS_REG_RECORDS_SCHEMA)
```

## Schema Structure

### DCI Envelope (Three-Part Structure)

All DCI API communications follow this structure:

```
{
  "signature": {...},  // Message authentication
  "header": {...},     // Routing and protocol info
  "message": {...}     // Actual payload
}
```

### Message Flow

1. **Request** → Uses `MSG_HEADER_SCHEMA`
2. **Response/Callback** → Uses `MSG_CALLBACK_HEADER_SCHEMA`
3. **Payload** → Uses specific schema (SEARCH_REQUEST, SEARCH_RESPONSE, etc.)

## Schema Registry Keys

| Key                          | Schema Constant                   |
| ---------------------------- | --------------------------------- |
| `search_request`             | SEARCH_REQUEST_SCHEMA             |
| `search_response`            | SEARCH_RESPONSE_SCHEMA            |
| `msg_header`                 | MSG_HEADER_SCHEMA                 |
| `msg_callback_header`        | MSG_CALLBACK_HEADER_SCHEMA        |
| `dr_reg_records`             | DR_REG_RECORDS_SCHEMA             |
| `dr_search_response`         | DR_SEARCH_RESPONSE_SCHEMA         |
| `dr_disability_status`       | DR_DISABILITY_STATUS_SCHEMA       |
| `crvs_reg_records`           | CRVS_REG_RECORDS_SCHEMA           |
| `crvs_search_response`       | CRVS_SEARCH_RESPONSE_SCHEMA       |
| `crvs_async_search_response` | CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA |
| `crvs_on_search_request`     | CRVS_ON_SEARCH_REQUEST_SCHEMA     |
| `dci_envelope`               | DCI_ENVELOPE_SCHEMA               |
| `subscribe_response`         | SUBSCRIBE_RESPONSE_SCHEMA         |
| `unsubscribe_response`       | UNSUBSCRIBE_RESPONSE_SCHEMA       |
| `on_search_response`         | ON_SEARCH_RESPONSE_SCHEMA         |

## Development Notes

- All schemas use JSON Schema Draft-07 specification
- Schemas have been flattened (no external `$ref` references)
- Common types (DateTime, TransactionId, etc.) are inlined
- Schemas preserve original SPDCI descriptions and examples
- Python dictionaries use native types (True/False instead of true/false)

## Testing

To verify schemas are working:

```python
from spp_dci_compliance.schemas import SCHEMA_REGISTRY

# Check all schemas are loaded
assert len(SCHEMA_REGISTRY) == 15
print(f"Loaded {len(SCHEMA_REGISTRY)} schemas successfully")
```

## References

- [SPDCI API Standards](https://github.com/spdci/api-standards)
- [JSON Schema Draft-07](https://json-schema.org/draft-07/schema)
- [Python jsonschema library](https://python-jsonschema.readthedocs.io/)
