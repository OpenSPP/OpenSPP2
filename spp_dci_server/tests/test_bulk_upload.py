# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI bulk upload functionality."""

import json
import logging

from odoo.tests import tagged

from odoo.addons.spp_dci_server.routers.bulk_upload import (
    BulkUploadError,
    _identifiers_to_search_requests,
    _parse_csv_file,
    _parse_json_file,
)

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestBulkUploadParsers:
    """Test cases for bulk upload file parsers.

    These are pure Python tests that don't require Odoo environment.
    """

    def test_parse_json_identifiers_array(self):
        """Test parsing JSON with identifiers array format."""
        content = json.dumps(
            {
                "identifiers": [
                    {"type": "urn:gov:id:national", "value": "12345"},
                    {"type": "urn:gov:id:national", "value": "12346"},
                ]
            }
        ).encode()

        result = _parse_json_file(content)

        assert len(result) == 2
        assert result[0]["search_criteria"]["query"]["query_params"]["identifier_value"] == "12345"
        assert result[1]["search_criteria"]["query"]["query_params"]["identifier_value"] == "12346"

    def test_parse_json_search_request_format(self):
        """Test parsing JSON with full search_request format."""
        content = json.dumps(
            {
                "search_request": [
                    {
                        "reference_id": "ref-001",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "search_criteria": {
                            "reg_type": "SOCIAL_REGISTRY",
                            "query_type": "namedQuery",
                            "query": {"query_name": "identifier"},
                        },
                    }
                ]
            }
        ).encode()

        result = _parse_json_file(content)

        assert len(result) == 1
        assert result[0]["reference_id"] == "ref-001"

    def test_parse_json_full_envelope(self):
        """Test parsing JSON with full DCI envelope format."""
        content = json.dumps(
            {
                "header": {"action": "search"},
                "message": {
                    "transaction_id": "txn-001",
                    "search_request": [
                        {
                            "reference_id": "ref-001",
                            "timestamp": "2024-01-01T00:00:00Z",
                            "search_criteria": {"query_type": "namedQuery"},
                        }
                    ],
                },
            }
        ).encode()

        result = _parse_json_file(content)

        assert len(result) == 1
        assert result[0]["reference_id"] == "ref-001"

    def test_parse_json_direct_array(self):
        """Test parsing JSON with direct array of identifiers."""
        content = json.dumps(
            [
                {"type": "urn:gov:id:national", "value": "12345"},
                {"type": "urn:gov:id:national", "value": "12346"},
            ]
        ).encode()

        result = _parse_json_file(content)

        assert len(result) == 2

    def test_parse_json_invalid_format(self):
        """Test that invalid JSON format raises error."""
        content = b'{"invalid": "structure"}'

        try:
            _parse_json_file(content)
            raise AssertionError("Should have raised BulkUploadError")
        except BulkUploadError as e:
            assert e.code == "err.file.format_invalid"

    def test_parse_json_invalid_syntax(self):
        """Test that invalid JSON syntax raises error."""
        content = b"not valid json"

        try:
            _parse_json_file(content)
            raise AssertionError("Should have raised BulkUploadError")
        except BulkUploadError as e:
            assert e.code == "err.file.parse_error"

    def test_parse_csv_standard_format(self):
        """Test parsing CSV with standard headers."""
        content = b"""identifier_type,identifier_value,reg_type
urn:gov:id:national,12345,SOCIAL_REGISTRY
urn:gov:id:national,12346,SOCIAL_REGISTRY"""

        result = _parse_csv_file(content)

        assert len(result) == 2
        assert result[0]["search_criteria"]["query"]["query_params"]["identifier_type"] == "urn:gov:id:national"
        assert result[0]["search_criteria"]["query"]["query_params"]["identifier_value"] == "12345"

    def test_parse_csv_camel_case_headers(self):
        """Test parsing CSV with camelCase headers."""
        content = b"""identifierType,identifierValue,regType
urn:gov:id:national,12345,SOCIAL_REGISTRY"""

        result = _parse_csv_file(content)

        assert len(result) == 1
        assert result[0]["search_criteria"]["query"]["query_params"]["identifier_value"] == "12345"

    def test_parse_csv_short_headers(self):
        """Test parsing CSV with short headers (type, value)."""
        content = b"""type,value
urn:gov:id:national,12345"""

        result = _parse_csv_file(content)

        assert len(result) == 1
        assert result[0]["search_criteria"]["query"]["query_params"]["identifier_value"] == "12345"

    def test_parse_csv_empty_file(self):
        """Test that empty CSV raises error."""
        content = b"""identifier_type,identifier_value,reg_type"""

        try:
            _parse_csv_file(content)
            raise AssertionError("Should have raised BulkUploadError")
        except BulkUploadError as e:
            assert e.code == "err.file.empty"

    def test_parse_csv_skips_incomplete_rows(self):
        """Test that rows with missing values are skipped."""
        content = b"""identifier_type,identifier_value,reg_type
urn:gov:id:national,12345,SOCIAL_REGISTRY
,12346,SOCIAL_REGISTRY
urn:gov:id:national,,SOCIAL_REGISTRY
urn:gov:id:national,12347,SOCIAL_REGISTRY"""

        result = _parse_csv_file(content)

        # Should only get 2 valid rows
        assert len(result) == 2

    def test_identifiers_to_search_requests(self):
        """Test conversion of identifier objects to search requests."""
        identifiers = [
            {"type": "urn:gov:id:national", "value": "12345"},
            {"type": "urn:gov:id:national", "value": "12346", "reg_type": "DR"},
        ]

        result = _identifiers_to_search_requests(identifiers)

        assert len(result) == 2
        assert result[0]["reference_id"] == "bulk-000000"
        assert result[1]["reference_id"] == "bulk-000001"
        assert result[0]["search_criteria"]["reg_type"] == "SOCIAL_REGISTRY"  # Default
        assert result[1]["search_criteria"]["reg_type"] == "DR"

    def test_identifiers_namespace_format(self):
        """Test identifiers with 'namespace' instead of 'type'."""
        identifiers = [
            {"namespace": "urn:gov:id:national", "value": "12345"},
        ]

        result = _identifiers_to_search_requests(identifiers)

        assert len(result) == 1
        assert result[0]["search_criteria"]["query"]["query_params"]["identifier_type"] == "urn:gov:id:national"
