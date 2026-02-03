# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for field filter service"""

from odoo.tests.common import TransactionCase

from ..services.field_filter import filter_fields, filter_list


class TestFieldFilter(TransactionCase):
    """Test the field filter utility for sparse fieldsets (_elements parameter)"""

    def setUp(self):
        super().setUp()

        # Create realistic test data like Individual API response
        self.individual_data = {
            "type": "Individual",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#national_id",
                    "value": "IND-001",
                }
            ],
            "name": {
                "family": "Doe",
                "given": ["John", "Michael"],
            },
            "birthDate": "1990-01-01",
            "gender": {
                "coding": [
                    {
                        "system": "urn:iso:std:iso:5218",
                        "code": "1",
                        "display": "Male",
                    }
                ]
            },
            "telecom": [
                {
                    "system": "phone",
                    "value": "+1234567890",
                },
                {
                    "system": "email",
                    "value": "john.doe@example.com",
                },
            ],
            "address": [
                {
                    "use": "home",
                    "city": "Manila",
                    "state": "NCR",
                }
            ],
            "meta": {
                "versionId": "1",
                "lastUpdated": "2024-01-01T00:00:00Z",
            },
        }

        # Group test data
        self.group_data = {
            "type": "Group",
            "identifier": [
                {
                    "system": "urn:openspp:vocab:id-type#household_id",
                    "value": "HH-001",
                }
            ],
            "name": "Doe Household",
            "active": True,
            "member": [
                {
                    "entity": {
                        "reference": "urn:openspp:vocab:id-type#national_id|IND-001",
                        "display": "John Doe",
                    },
                    "role": [
                        {
                            "coding": [
                                {
                                    "system": "urn:openspp:vocab:group-membership-type",
                                    "code": "head",
                                }
                            ]
                        }
                    ],
                }
            ],
        }

    def test_filter_fields_none_returns_all(self):
        """None _elements returns full data unchanged"""
        result = filter_fields(self.individual_data, None)

        self.assertEqual(result, self.individual_data)
        self.assertIn("name", result)
        self.assertIn("birthDate", result)
        self.assertIn("gender", result)
        self.assertIn("telecom", result)
        self.assertIn("address", result)

    def test_filter_fields_basic(self):
        """Simple field selection returns only requested fields"""
        result = filter_fields(self.individual_data, "name,birthDate")

        # Should include type and identifier (always included)
        self.assertIn("type", result)
        self.assertIn("identifier", result)

        # Should include requested fields
        self.assertIn("name", result)
        self.assertIn("birthDate", result)

        # Should NOT include other fields
        self.assertNotIn("gender", result)
        self.assertNotIn("telecom", result)
        self.assertNotIn("address", result)
        self.assertNotIn("meta", result)

    def test_always_includes_type_and_identifier(self):
        """type and identifier fields are ALWAYS included regardless of _elements"""
        result = filter_fields(self.individual_data, "name")

        # Required fields always present
        self.assertIn("type", result)
        self.assertEqual(result["type"], "Individual")
        self.assertIn("identifier", result)
        self.assertEqual(len(result["identifier"]), 1)

        # Requested field present
        self.assertIn("name", result)

        # Other fields not present
        self.assertNotIn("birthDate", result)
        self.assertNotIn("gender", result)

    def test_unknown_fields_ignored(self):
        """Non-existent field names are silently ignored"""
        result = filter_fields(self.individual_data, "name,nonexistent,invalid_field")

        # Should have type, identifier, and name
        self.assertIn("type", result)
        self.assertIn("identifier", result)
        self.assertIn("name", result)

        # Should not error, just ignore unknown fields
        self.assertEqual(len(result), 3)  # type, identifier, name

    def test_nested_dict_field(self):
        """name.family returns only family from name dict"""
        result = filter_fields(self.individual_data, "name.family")

        # Should have type and identifier
        self.assertIn("type", result)
        self.assertIn("identifier", result)

        # Should have name with only family
        self.assertIn("name", result)
        self.assertIsInstance(result["name"], dict)
        self.assertIn("family", result["name"])
        self.assertEqual(result["name"]["family"], "Doe")

        # Should NOT have given
        self.assertNotIn("given", result["name"])

        # Should NOT have other top-level fields
        self.assertNotIn("birthDate", result)
        self.assertNotIn("gender", result)

    def test_nested_list_field(self):
        """telecom.value returns value from each telecom item"""
        result = filter_fields(self.individual_data, "telecom.value")

        # Should have type and identifier
        self.assertIn("type", result)
        self.assertIn("identifier", result)

        # Should have telecom list with only value field
        self.assertIn("telecom", result)
        self.assertIsInstance(result["telecom"], list)
        self.assertEqual(len(result["telecom"]), 2)

        # Each item should only have value
        for item in result["telecom"]:
            self.assertIn("value", item)
            self.assertNotIn("system", item)

        # Values should match original
        values = [item["value"] for item in result["telecom"]]
        self.assertIn("+1234567890", values)
        self.assertIn("john.doe@example.com", values)

    def test_empty_elements_string(self):
        """Empty string handling"""
        result = filter_fields(self.individual_data, "")

        # Empty string should return full data (falsy value)
        self.assertEqual(result, self.individual_data)

    def test_filter_list_basic(self):
        """filter_list applies filter to each item in list"""
        data_list = [
            self.individual_data.copy(),
            self.group_data.copy(),
        ]

        result = filter_list(data_list, "name")

        self.assertEqual(len(result), 2)

        # Each item should have type, identifier, and name only
        for item in result:
            self.assertIn("type", item)
            self.assertIn("identifier", item)
            self.assertIn("name", item)

        # Individual should not have other fields
        self.assertNotIn("birthDate", result[0])
        self.assertNotIn("gender", result[0])

        # Group should not have other fields
        self.assertNotIn("active", result[1])
        self.assertNotIn("member", result[1])

    def test_filter_list_none_returns_all(self):
        """filter_list with None returns unchanged list"""
        data_list = [
            self.individual_data.copy(),
            self.group_data.copy(),
        ]

        result = filter_list(data_list, None)

        self.assertEqual(result, data_list)
        # Verify no filtering occurred
        self.assertEqual(len(result[0]), len(self.individual_data))
        self.assertEqual(len(result[1]), len(self.group_data))

    def test_multiple_fields(self):
        """name,birthDate,gender selection includes multiple fields"""
        result = filter_fields(self.individual_data, "name,birthDate,gender")

        # Required fields
        self.assertIn("type", result)
        self.assertIn("identifier", result)

        # Requested fields
        self.assertIn("name", result)
        self.assertIn("birthDate", result)
        self.assertIn("gender", result)

        # Not requested
        self.assertNotIn("telecom", result)
        self.assertNotIn("address", result)
        self.assertNotIn("meta", result)

    def test_whitespace_handling(self):
        """Spaces around field names are stripped"""
        result = filter_fields(self.individual_data, "name , birthDate , gender")

        # Should work despite extra spaces
        self.assertIn("name", result)
        self.assertIn("birthDate", result)
        self.assertIn("gender", result)

    def test_nested_field_with_list_parent(self):
        """member.entity extracts entity from each member"""
        result = filter_fields(self.group_data, "member.entity")

        self.assertIn("member", result)
        self.assertIsInstance(result["member"], list)
        self.assertEqual(len(result["member"]), 1)

        # Should only have entity field
        self.assertIn("entity", result["member"][0])
        self.assertNotIn("role", result["member"][0])

    def test_nested_field_missing_parent(self):
        """Requesting nested field with missing parent doesn't error"""
        data = {
            "type": "Individual",
            "identifier": [{"system": "test", "value": "123"}],
            "name": {"family": "Doe"},
        }

        # Request nested field that doesn't exist
        result = filter_fields(data, "telecom.value")

        # Should have type and identifier, but not telecom
        self.assertIn("type", result)
        self.assertIn("identifier", result)
        self.assertNotIn("telecom", result)

    def test_deeply_nested_field(self):
        """gender.coding extracts coding from gender"""
        result = filter_fields(self.individual_data, "gender.coding")

        self.assertIn("gender", result)
        self.assertIsInstance(result["gender"], dict)
        self.assertIn("coding", result["gender"])

        # Should only have coding, not other potential gender fields
        self.assertEqual(len(result["gender"]), 1)

    def test_multiple_nested_fields(self):
        """Can select multiple nested fields"""
        result = filter_fields(self.individual_data, "name.family,name.given")

        self.assertIn("name", result)
        self.assertIn("family", result["name"])
        self.assertIn("given", result["name"])

        # Both fields should be present
        self.assertEqual(result["name"]["family"], "Doe")
        self.assertEqual(result["name"]["given"], ["John", "Michael"])

    def test_mix_top_level_and_nested(self):
        """Can mix top-level and nested field selection"""
        result = filter_fields(self.individual_data, "name.family,birthDate,telecom.value")

        # Required fields
        self.assertIn("type", result)
        self.assertIn("identifier", result)

        # Top-level field
        self.assertIn("birthDate", result)
        self.assertEqual(result["birthDate"], "1990-01-01")

        # Nested dict field
        self.assertIn("name", result)
        self.assertIn("family", result["name"])
        self.assertNotIn("given", result["name"])

        # Nested list field
        self.assertIn("telecom", result)
        for item in result["telecom"]:
            self.assertIn("value", item)
            self.assertNotIn("system", item)

    def test_filter_preserves_data_types(self):
        """Filtered data preserves original data types"""
        result = filter_fields(self.individual_data, "name,telecom")

        # name should still be dict
        self.assertIsInstance(result["name"], dict)

        # telecom should still be list
        self.assertIsInstance(result["telecom"], list)

        # identifier should still be list
        self.assertIsInstance(result["identifier"], list)

    def test_empty_list(self):
        """filter_list with empty list returns empty list"""
        result = filter_list([], "name")

        self.assertEqual(result, [])

    def test_filter_list_with_nested_fields(self):
        """filter_list applies nested field filtering"""
        data_list = [
            self.individual_data.copy(),
            {
                "type": "Individual",
                "identifier": [{"system": "test", "value": "IND-002"}],
                "name": {"family": "Smith", "given": ["Jane"]},
                "birthDate": "1995-05-15",
            },
        ]

        result = filter_list(data_list, "name.family")

        self.assertEqual(len(result), 2)

        # Each should have name with only family
        for item in result:
            self.assertIn("name", item)
            self.assertIn("family", item["name"])
            self.assertNotIn("given", item["name"])

        # Check values
        self.assertEqual(result[0]["name"]["family"], "Doe")
        self.assertEqual(result[1]["name"]["family"], "Smith")
