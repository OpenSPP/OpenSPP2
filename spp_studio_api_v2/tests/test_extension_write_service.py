# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ExtensionWriteService."""

from odoo.tests.common import TransactionCase


class TestExtensionWriteService(TransactionCase):
    """Test cases for ExtensionWriteService."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test vocabulary
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": "Test Vocab",
                "namespace_uri": "urn:test:vocab",
            }
        )
        cls.vocab.flush_recordset()  # Ensure vocabulary is stored first

        cls.vocab_code = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "test_code",
                "display": "Test Code",
                # namespace_uri is a stored related field from vocabulary_id
            }
        )
        # Ensure related field is computed and stored
        cls.vocab_code.flush_recordset()
        # Force recomputation of stored related field
        cls.env.add_to_compute(
            cls.env["spp.vocabulary.code"]._fields["namespace_uri"],
            cls.vocab_code,
        )
        cls.env.flush_all()

        # Create test extension
        module = cls.env["ir.module.module"].search([("name", "=", "spp_studio_api_v2")], limit=1)
        if not module:
            module = cls.env["ir.module.module"].search([("state", "=", "installed")], limit=1)

        cls.extension = cls.env["spp.api.extension"].create(
            {
                "name": "Test Extension",
                "url": "urn:test:extension",
                "module_id": module.id,
                "applies_to": "individual",
                "active": True,
            }
        )

    def test_odoo_to_api_name_conversion(self):
        """Test field name conversion from Odoo to API format."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Test conversions
        self.assertEqual(service._odoo_to_api_name("x_farm_size"), "farmSize")
        self.assertEqual(service._odoo_to_api_name("x_primary_crop_id"), "primaryCrop")
        self.assertEqual(service._odoo_to_api_name("farm_size"), "farmSize")
        self.assertEqual(service._odoo_to_api_name("simple"), "simple")

    def test_convert_codeable_concept_to_many2one(self):
        """Test conversion of CodeableConcept to Many2one ID."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Create a mock field record
        field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "res.partner"),
                ("name", "=", "gender_id"),
            ],
            limit=1,
        )

        if not field:
            self.skipTest("gender_id field not found")

        # Test CodeableConcept conversion
        # Use vocabulary's namespace_uri directly (related field might have caching issues)
        api_value = {
            "coding": [
                {
                    "system": self.vocab.namespace_uri,
                    "code": self.vocab_code.code,
                    "display": self.vocab_code.display,
                }
            ],
            "text": self.vocab_code.display,
        }

        result = service._convert_many2one(field, api_value)
        self.assertEqual(result, self.vocab_code.id)

    def test_convert_primitives(self):
        """Test conversion of primitive values."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Mock field records for different types
        class MockField:
            def __init__(self, ttype, relation=None):
                self.ttype = ttype
                self.relation = relation

        # Test integer
        result = service._convert_to_odoo(MockField("integer"), 42)
        self.assertEqual(result, 42)

        # Test float
        result = service._convert_to_odoo(MockField("float"), 3.14)
        self.assertEqual(result, 3.14)

        # Test boolean
        result = service._convert_to_odoo(MockField("boolean"), True)
        self.assertTrue(result)

        # Test char
        result = service._convert_to_odoo(MockField("char"), "test")
        self.assertEqual(result, "test")

        # Test date (ISO string)
        result = service._convert_to_odoo(MockField("date"), "2024-01-15")
        self.assertEqual(result, "2024-01-15")

    def test_parse_empty_extension_data(self):
        """Test parsing empty extension data."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        result = service.parse_extension_data({}, "individual")
        self.assertEqual(result, {})

        result = service.parse_extension_data(None, "individual")
        self.assertEqual(result, {})

    def test_find_extension_by_url(self):
        """Test finding extension by URL."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Find by exact URL
        ext = service._find_extension("urn:test:extension", "individual")
        self.assertEqual(ext.id, self.extension.id)

        # Find by key (last part of URL)
        ext = service._find_extension("extension", "individual")
        self.assertEqual(ext.id, self.extension.id)


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE COERCION ATTACK TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtensionWriteServiceTypeCoercion(TransactionCase):
    """Test type coercion edge cases and attack vectors."""

    def test_convert_integer_overflow(self):
        """Test rejection of very large numbers exceeding PostgreSQL int4 range."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype):
                self.ttype = ttype

        # Test very large integer - should be rejected (out of PostgreSQL int4 range)
        large_int = 9999999999999999
        result = service._convert_to_odoo(MockField("integer"), large_int)
        self.assertIsNone(result)

        # Test value at upper boundary (valid)
        result = service._convert_to_odoo(MockField("integer"), 2147483647)
        self.assertEqual(result, 2147483647)

        # Test value at lower boundary (valid)
        result = service._convert_to_odoo(MockField("integer"), -2147483648)
        self.assertEqual(result, -2147483648)

        # Test value just over upper boundary (invalid)
        result = service._convert_to_odoo(MockField("integer"), 2147483648)
        self.assertIsNone(result)

    def test_convert_integer_string_nan(self):
        """Test rejection of NaN string for integer."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype):
                self.ttype = ttype

        # "NaN" string should be rejected (returns None for invalid conversion)
        result = service._convert_to_odoo(MockField("integer"), "NaN")
        self.assertIsNone(result)

    def test_convert_float_infinity(self):
        """Test rejection of infinity for float (non-finite values not allowed)."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype):
                self.ttype = ttype

        # Python float('inf') should be rejected (non-finite)
        result = service._convert_to_odoo(MockField("float"), float("inf"))
        self.assertIsNone(result)

    def test_convert_float_negative_infinity(self):
        """Test rejection of negative infinity for float (non-finite values not allowed)."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype):
                self.ttype = ttype

        # Python float('-inf') should be rejected (non-finite)
        result = service._convert_to_odoo(MockField("float"), float("-inf"))
        self.assertIsNone(result)

    def test_convert_float_nan(self):
        """Test rejection of NaN for float."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype):
                self.ttype = ttype

        # NaN should be rejected (non-finite)
        result = service._convert_to_odoo(MockField("float"), float("nan"))
        self.assertIsNone(result)

    def test_convert_boolean_from_string(self):
        """Test boolean conversion from string values."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype):
                self.ttype = ttype

        # String "false" should be parsed as False (not truthy non-empty string)
        result = service._convert_to_odoo(MockField("boolean"), "false")
        self.assertFalse(result)

        # String "true" should be True
        result = service._convert_to_odoo(MockField("boolean"), "true")
        self.assertTrue(result)

        # String "True" (capitalized) should be True
        result = service._convert_to_odoo(MockField("boolean"), "True")
        self.assertTrue(result)

        # String "1" should be True
        result = service._convert_to_odoo(MockField("boolean"), "1")
        self.assertTrue(result)

        # String "yes" should be True
        result = service._convert_to_odoo(MockField("boolean"), "yes")
        self.assertTrue(result)

        # String "0" should be False
        result = service._convert_to_odoo(MockField("boolean"), "0")
        self.assertFalse(result)

        # String "no" should be False
        result = service._convert_to_odoo(MockField("boolean"), "no")
        self.assertFalse(result)

        # Empty string is falsy
        result = service._convert_to_odoo(MockField("boolean"), "")
        self.assertFalse(result)

        # Zero is falsy
        result = service._convert_to_odoo(MockField("boolean"), 0)
        self.assertFalse(result)

        # Python bool True
        result = service._convert_to_odoo(MockField("boolean"), True)
        self.assertTrue(result)


# ═══════════════════════════════════════════════════════════════════════════════
# MALFORMED INPUT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtensionWriteServiceMalformedInput(TransactionCase):
    """Test handling of malformed input data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test vocabulary
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": "Test Vocab Malformed",
                "namespace_uri": "urn:test:vocab:malformed",
            }
        )
        cls.vocab_code = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "test_code",
                "display": "Test Code",
                # namespace_uri is a related field from vocabulary_id
            }
        )
        # Ensure related field is computed and stored
        cls.vocab_code.flush_recordset()
        # Invalidate cache and reload to ensure related field is available
        cls.env.invalidate_all()
        cls.vocab_code = cls.env["spp.vocabulary.code"].browse(cls.vocab_code.id)

    def test_codeable_concept_empty_coding(self):
        """Test CodeableConcept with empty coding array."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype, relation=None):
                self.ttype = ttype
                self.relation = relation

        api_value = {
            "coding": [],
            "text": "Some Text",
        }

        result = service._convert_many2one(MockField("many2one"), api_value)
        self.assertFalse(result)

    def test_codeable_concept_missing_system(self):
        """Test CodeableConcept with missing system field."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype, relation=None):
                self.ttype = ttype
                self.relation = relation

        api_value = {
            "coding": [
                {
                    "code": "test_code",
                    "display": "Test Code",
                }
            ],
        }

        result = service._convert_many2one(MockField("many2one"), api_value)
        self.assertFalse(result)

    def test_codeable_concept_missing_code(self):
        """Test CodeableConcept with missing code field."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        class MockField:
            def __init__(self, ttype, relation=None):
                self.ttype = ttype
                self.relation = relation

        api_value = {
            "coding": [
                {
                    "system": "urn:test:vocab",
                    "display": "Test Code",
                }
            ],
        }

        result = service._convert_many2one(MockField("many2one"), api_value)
        self.assertFalse(result)

    def test_deeply_nested_extension_data(self):
        """Test handling of deeply nested extension data."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Create deeply nested dict (should not cause recursion issues)
        deeply_nested = {"level1": {"level2": {"level3": {"level4": "value"}}}}

        # Should handle gracefully without errors
        result = service.parse_extension_data(deeply_nested, "individual")
        # Should return empty dict since no valid extension found
        self.assertEqual(result, {})


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtensionWriteServiceSecurity(TransactionCase):
    """Test security aspects of extension write service."""

    def test_blocked_model_lookup(self):
        """Test that lookup on sensitive models returns None."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Attempt to find record in res.users (sensitive model)
        # This should be blocked or return None gracefully
        result = service._find_by_display("res.users", "admin")

        # Should either return None or empty recordset
        if result:
            self.assertFalse(result.exists())
        else:
            self.assertIsNone(result)

    def test_safe_model_lookup(self):
        """Test that lookup on safe models works correctly."""
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)

        # Create a vocabulary code (namespace_uri is a related field from vocabulary_id)
        vocab = self.env["spp.vocabulary"].create(
            {
                "name": "Test Safe Vocab",
                "namespace_uri": "urn:test:safe",
            }
        )
        code = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "safe_code",
                "display": "Safe Code",
                # Don't pass namespace_uri - it's computed from vocabulary_id
            }
        )
        # Ensure related field is computed and stored
        code.flush_recordset()

        # Find the code
        result = service._find_vocabulary_code("urn:test:safe", "safe_code")

        self.assertIsNotNone(result, "Should find the vocabulary code")
        self.assertEqual(result.id, code.id)
