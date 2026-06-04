# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for SPDCI schema definitions and example payloads.

Covers schemas/__init__.py, schemas/spdci_schemas.py, and schemas/examples.py.
"""

from odoo.tests import TransactionCase


class TestSpdciSchemas(TransactionCase):
    """Verify that all schema constants are importable and structurally sound."""

    def test_import_all_public_names(self):
        """The __init__.py re-exports every schema constant and get_schema()."""
        from odoo.addons.spp_dci_compliance.schemas import (
            CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA,
            CRVS_ON_SEARCH_REQUEST_SCHEMA,
            CRVS_REG_RECORDS_SCHEMA,
            CRVS_SEARCH_RESPONSE_SCHEMA,
            DCI_ENVELOPE_SCHEMA,
            DR_DISABILITY_STATUS_SCHEMA,
            DR_REG_RECORDS_SCHEMA,
            DR_SEARCH_RESPONSE_SCHEMA,
            MSG_CALLBACK_HEADER_SCHEMA,
            MSG_HEADER_SCHEMA,
            ON_SEARCH_RESPONSE_SCHEMA,
            SCHEMA_REGISTRY,
            SEARCH_REQUEST_SCHEMA,
            SEARCH_RESPONSE_SCHEMA,
            SUBSCRIBE_RESPONSE_SCHEMA,
            UNSUBSCRIBE_RESPONSE_SCHEMA,
            get_schema,
        )

        # All objects must be dicts or callables — none should be None.
        for name, obj in [
            ("SEARCH_REQUEST_SCHEMA", SEARCH_REQUEST_SCHEMA),
            ("SEARCH_RESPONSE_SCHEMA", SEARCH_RESPONSE_SCHEMA),
            ("MSG_HEADER_SCHEMA", MSG_HEADER_SCHEMA),
            ("MSG_CALLBACK_HEADER_SCHEMA", MSG_CALLBACK_HEADER_SCHEMA),
            ("DR_REG_RECORDS_SCHEMA", DR_REG_RECORDS_SCHEMA),
            ("DR_SEARCH_RESPONSE_SCHEMA", DR_SEARCH_RESPONSE_SCHEMA),
            ("DR_DISABILITY_STATUS_SCHEMA", DR_DISABILITY_STATUS_SCHEMA),
            ("CRVS_REG_RECORDS_SCHEMA", CRVS_REG_RECORDS_SCHEMA),
            ("CRVS_SEARCH_RESPONSE_SCHEMA", CRVS_SEARCH_RESPONSE_SCHEMA),
            ("CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA", CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA),
            ("CRVS_ON_SEARCH_REQUEST_SCHEMA", CRVS_ON_SEARCH_REQUEST_SCHEMA),
            ("DCI_ENVELOPE_SCHEMA", DCI_ENVELOPE_SCHEMA),
            ("SUBSCRIBE_RESPONSE_SCHEMA", SUBSCRIBE_RESPONSE_SCHEMA),
            ("UNSUBSCRIBE_RESPONSE_SCHEMA", UNSUBSCRIBE_RESPONSE_SCHEMA),
            ("ON_SEARCH_RESPONSE_SCHEMA", ON_SEARCH_RESPONSE_SCHEMA),
            ("SCHEMA_REGISTRY", SCHEMA_REGISTRY),
        ]:
            with self.subTest(schema=name):
                self.assertIsInstance(obj, dict, f"{name} must be a dict")
                self.assertGreater(len(obj), 0, f"{name} must not be empty")

        self.assertTrue(callable(get_schema))

    def test_all_schemas_are_dicts_with_type_or_properties(self):
        """Every schema dict must have at least one of 'type', 'properties', or '$schema'."""
        from odoo.addons.spp_dci_compliance.schemas import SCHEMA_REGISTRY

        for name, schema in SCHEMA_REGISTRY.items():
            with self.subTest(schema=name):
                self.assertIsInstance(schema, dict)
                has_structure = any(k in schema for k in ("type", "properties", "$schema", "oneOf", "anyOf"))
                self.assertTrue(has_structure, f"{name} lacks structural keys")

    def test_get_schema_returns_correct_schema(self):
        """get_schema(name) returns the same object as direct import."""
        from odoo.addons.spp_dci_compliance.schemas import SCHEMA_REGISTRY, SEARCH_REQUEST_SCHEMA, get_schema

        result = get_schema("search_request")
        self.assertIs(result, SEARCH_REQUEST_SCHEMA)
        # Every key in the registry must be retrievable.
        for key in SCHEMA_REGISTRY:
            with self.subTest(key=key):
                self.assertIs(get_schema(key), SCHEMA_REGISTRY[key])

    def test_get_schema_raises_for_unknown_name(self):
        """get_schema() raises KeyError for an unregistered schema name."""
        from odoo.addons.spp_dci_compliance.schemas import get_schema

        with self.assertRaises(KeyError):
            get_schema("no_such_schema_xyz")

    def test_search_request_schema_required_fields(self):
        """SEARCH_REQUEST_SCHEMA requires transaction_id and search_request."""
        from odoo.addons.spp_dci_compliance.schemas import SEARCH_REQUEST_SCHEMA

        required = SEARCH_REQUEST_SCHEMA.get("required", [])
        self.assertIn("transaction_id", required)
        self.assertIn("search_request", required)

    def test_search_response_schema_required_fields(self):
        """SEARCH_RESPONSE_SCHEMA requires transaction_id, correlation_id, and search_response."""
        from odoo.addons.spp_dci_compliance.schemas import SEARCH_RESPONSE_SCHEMA

        required = SEARCH_RESPONSE_SCHEMA.get("required", [])
        self.assertIn("transaction_id", required)
        self.assertIn("correlation_id", required)
        self.assertIn("search_response", required)

    def test_msg_header_schema_required_fields(self):
        """MSG_HEADER_SCHEMA requires the mandatory header fields."""
        from odoo.addons.spp_dci_compliance.schemas import MSG_HEADER_SCHEMA

        required = MSG_HEADER_SCHEMA.get("required", [])
        for field in ("message_id", "message_ts", "action", "sender_id", "total_count"):
            self.assertIn(field, required)

    def test_dci_envelope_schema_requires_all_three_parts(self):
        """DCI_ENVELOPE_SCHEMA must require signature, header, and message."""
        from odoo.addons.spp_dci_compliance.schemas import DCI_ENVELOPE_SCHEMA

        required = DCI_ENVELOPE_SCHEMA.get("required", [])
        for part in ("signature", "header", "message"):
            self.assertIn(part, required)

    def test_crvs_async_search_response_required_fields(self):
        """CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA requires the core response fields."""
        from odoo.addons.spp_dci_compliance.schemas import CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA

        required = CRVS_ASYNC_SEARCH_RESPONSE_SCHEMA.get("required", [])
        for field in ("transaction_id", "correlation_id", "search_response"):
            self.assertIn(field, required)

    def test_schema_registry_contains_all_expected_keys(self):
        """SCHEMA_REGISTRY must contain every documented schema name."""
        from odoo.addons.spp_dci_compliance.schemas import SCHEMA_REGISTRY

        expected_keys = {
            "search_request",
            "search_response",
            "msg_header",
            "msg_callback_header",
            "dr_reg_records",
            "dr_search_response",
            "dr_disability_status",
            "crvs_reg_records",
            "crvs_search_response",
            "crvs_async_search_response",
            "crvs_on_search_request",
            "dci_envelope",
            "subscribe_response",
            "unsubscribe_response",
            "on_search_response",
        }
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, SCHEMA_REGISTRY, f"Missing schema key: {key}")


class TestSpdciSchemaExamples(TransactionCase):
    """Verify that example payloads are importable and structurally sound."""

    def test_import_all_example_constants(self):
        """All example constants in examples.py must be importable."""
        from odoo.addons.spp_dci_compliance.schemas.examples import (
            EXAMPLE_CRVS_REG_RECORD,
            EXAMPLE_DCI_ENVELOPE,
            EXAMPLE_DR_DISABILITY_STATUS,
            EXAMPLE_DR_REG_RECORD,
            EXAMPLE_DR_SEARCH_RESPONSE,
            EXAMPLE_MSG_CALLBACK_HEADER,
            EXAMPLE_MSG_HEADER,
            EXAMPLE_SEARCH_REQUEST,
            EXAMPLE_SEARCH_RESPONSE,
            EXAMPLE_SUBSCRIBE_RESPONSE,
        )

        for name, obj in [
            ("EXAMPLE_SEARCH_REQUEST", EXAMPLE_SEARCH_REQUEST),
            ("EXAMPLE_SEARCH_RESPONSE", EXAMPLE_SEARCH_RESPONSE),
            ("EXAMPLE_MSG_HEADER", EXAMPLE_MSG_HEADER),
            ("EXAMPLE_MSG_CALLBACK_HEADER", EXAMPLE_MSG_CALLBACK_HEADER),
            ("EXAMPLE_DR_REG_RECORD", EXAMPLE_DR_REG_RECORD),
            ("EXAMPLE_DR_SEARCH_RESPONSE", EXAMPLE_DR_SEARCH_RESPONSE),
            ("EXAMPLE_DR_DISABILITY_STATUS", EXAMPLE_DR_DISABILITY_STATUS),
            ("EXAMPLE_CRVS_REG_RECORD", EXAMPLE_CRVS_REG_RECORD),
            ("EXAMPLE_DCI_ENVELOPE", EXAMPLE_DCI_ENVELOPE),
            ("EXAMPLE_SUBSCRIBE_RESPONSE", EXAMPLE_SUBSCRIBE_RESPONSE),
        ]:
            with self.subTest(example=name):
                self.assertIsInstance(obj, dict, f"{name} must be a dict")
                self.assertGreater(len(obj), 0, f"{name} must not be empty")

    def test_example_search_request_has_required_fields(self):
        """The example search request must have the required top-level fields."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_SEARCH_REQUEST

        self.assertIn("transaction_id", EXAMPLE_SEARCH_REQUEST)
        self.assertIn("search_request", EXAMPLE_SEARCH_REQUEST)
        self.assertIsInstance(EXAMPLE_SEARCH_REQUEST["search_request"], list)
        self.assertGreater(len(EXAMPLE_SEARCH_REQUEST["search_request"]), 0)

    def test_example_search_response_has_required_fields(self):
        """The example search response must have correlation_id and search_response."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_SEARCH_RESPONSE

        self.assertIn("transaction_id", EXAMPLE_SEARCH_RESPONSE)
        self.assertIn("correlation_id", EXAMPLE_SEARCH_RESPONSE)
        self.assertIn("search_response", EXAMPLE_SEARCH_RESPONSE)

    def test_example_msg_header_has_required_fields(self):
        """The example message header must have all required fields."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_MSG_HEADER

        for field in ("message_id", "message_ts", "action", "sender_id", "total_count"):
            self.assertIn(field, EXAMPLE_MSG_HEADER, f"Missing field: {field}")

    def test_example_dci_envelope_has_three_parts(self):
        """The DCI envelope example must have signature, header, and message."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_DCI_ENVELOPE

        for part in ("signature", "header", "message"):
            self.assertIn(part, EXAMPLE_DCI_ENVELOPE)

    def test_example_dr_reg_record_has_personal_details(self):
        """The DR registry record example must have personal_details."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_DR_REG_RECORD

        self.assertIn("personal_details", EXAMPLE_DR_REG_RECORD)
        self.assertIn("disability_status", EXAMPLE_DR_REG_RECORD)

    def test_example_crvs_reg_record_has_identifier(self):
        """The CRVS registry record example must have an identifier."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_CRVS_REG_RECORD

        self.assertIn("identifier", EXAMPLE_CRVS_REG_RECORD)

    def test_example_subscribe_response_shape(self):
        """The subscribe response example must have the expected ack shape."""
        from odoo.addons.spp_dci_compliance.schemas.examples import EXAMPLE_SUBSCRIBE_RESPONSE

        self.assertIn("message", EXAMPLE_SUBSCRIBE_RESPONSE)
        msg = EXAMPLE_SUBSCRIBE_RESPONSE["message"]
        self.assertIn("ack_status", msg)
        self.assertIn("correlation_id", msg)

    def test_validate_examples_function_is_callable(self):
        """validate_examples() must be callable and return a bool."""
        from odoo.addons.spp_dci_compliance.schemas.examples import validate_examples

        self.assertTrue(callable(validate_examples))
        # Call it - returns True when jsonschema is available, False when not.
        result = validate_examples()
        self.assertIsInstance(result, bool)
