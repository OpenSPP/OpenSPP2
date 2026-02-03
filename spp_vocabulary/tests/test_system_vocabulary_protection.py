"""System vocabulary protection tests.

Tests that system vocabularies (is_system=True) are properly protected:
- Codes cannot be added to system vocabularies
- Codes cannot be modified beyond allowed fields
- Codes cannot be deleted from system vocabularies
- Allowed fields: active, deprecated, deprecated_date, sequence
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestSystemVocabularyProtection(TransactionCase):
    """Test protection mechanisms for system vocabularies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Create a system vocabulary
        cls.system_vocab = cls.Vocabulary.create(
            {
                "name": "System Protected Vocab",
                "namespace_uri": "urn:test:system-protected",
                "is_system": True,
            }
        )

        # Create a non-system vocabulary for comparison
        cls.user_vocab = cls.Vocabulary.create(
            {
                "name": "User Vocab",
                "namespace_uri": "urn:test:user-protected",
                "is_system": False,
            }
        )

        # Create codes in both vocabularies
        # Use bypass context to create code in system vocabulary during test setup
        # Store only IDs, not records, to avoid context persistence
        system_code_rec = cls.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": cls.system_vocab.id,
                "code": "SYSTEM_CODE",
                "display": "System Code",
            }
        )
        cls.system_code_id = system_code_rec.id

        user_code_rec = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.user_vocab.id,
                "code": "USER_CODE",
                "display": "User Code",
            }
        )
        cls.user_code_id = user_code_rec.id

    def setUp(self):
        """Set up fresh record references for each test."""
        super().setUp()
        # Browse records with fresh environment to avoid context persistence
        self.system_code = self.VocabularyCode.browse(self.system_code_id)
        self.user_code = self.VocabularyCode.browse(self.user_code_id)

    # Test adding codes to system vocabulary

    def test_cannot_add_code_via_get_or_create(self):
        """Test that get_or_create() fails for system vocabularies."""
        with self.assertRaises(UserError) as ctx:
            self.VocabularyCode.get_or_create("urn:test:system-protected", "NEW_CODE", "Should Fail")
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    # Test modifying codes in system vocabulary

    def test_cannot_modify_code_value(self):
        """Test that code value cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"code": "MODIFIED_CODE"})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_display(self):
        """Test that display cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"display": "Modified Display"})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_definition(self):
        """Test that definition cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"definition": "New definition"})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_uri(self):
        """Test that URI cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"uri": "urn:custom:modified#code"})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_is_local(self):
        """Test that is_local cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"is_local": True})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_reference_uri(self):
        """Test that reference_uri cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"reference_uri": "urn:other:code#ref"})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_equivalence(self):
        """Test that equivalence cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"equivalence": "equivalent"})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_modify_parent_id(self):
        """Test that parent_id cannot be changed in system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write({"parent_id": False})
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    # Test allowed field modifications in system vocabulary

    def test_can_modify_active(self):
        """Test that active can be changed in system vocabulary."""
        self.system_code.write({"active": False})
        self.assertFalse(self.system_code.active)
        # Restore for other tests
        self.system_code.write({"active": True})

    def test_can_modify_deprecated(self):
        """Test that deprecated can be changed in system vocabulary."""
        self.system_code.write({"deprecated": True})
        self.assertTrue(self.system_code.deprecated)
        # Restore for other tests
        self.system_code.write({"deprecated": False})

    def test_can_modify_deprecated_date(self):
        """Test that deprecated_date can be changed in system vocabulary."""
        self.system_code.write({"deprecated_date": "2024-01-01"})
        self.assertEqual(str(self.system_code.deprecated_date), "2024-01-01")
        # Clear for other tests
        self.system_code.write({"deprecated_date": False})

    def test_can_modify_sequence(self):
        """Test that sequence can be changed in system vocabulary."""
        original = self.system_code.sequence
        self.system_code.write({"sequence": 99})
        self.assertEqual(self.system_code.sequence, 99)
        # Restore
        self.system_code.write({"sequence": original})

    def test_can_modify_multiple_allowed_fields(self):
        """Test that multiple allowed fields can be changed together."""
        self.system_code.write(
            {
                "active": True,
                "deprecated": True,
                "deprecated_date": "2024-06-15",
                "sequence": 50,
            }
        )
        self.assertTrue(self.system_code.active)
        self.assertTrue(self.system_code.deprecated)
        self.assertEqual(self.system_code.sequence, 50)
        # Restore
        self.system_code.write(
            {
                "deprecated": False,
                "deprecated_date": False,
                "sequence": 10,
            }
        )

    # Test deleting codes from system vocabulary

    def test_cannot_delete_system_code(self):
        """Test that codes cannot be deleted from system vocabulary."""
        # Create a code specifically for deletion test
        # Use bypass context to create code, then browse with fresh environment
        code_rec = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "TO_DELETE_SYS",
                "display": "To Delete System",
            }
        )
        # Browse with fresh environment to avoid context persistence
        code_to_delete = self.VocabularyCode.browse(code_rec.id)

        with self.assertRaises(UserError) as ctx:
            code_to_delete.unlink()
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_cannot_delete_multiple_system_codes(self):
        """Test that multiple codes cannot be deleted from system vocabulary."""
        # Use bypass context to create codes, then browse with fresh environment
        code1_rec = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "BULK_DELETE_1",
                "display": "Bulk Delete 1",
            }
        )
        code2_rec = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "BULK_DELETE_2",
                "display": "Bulk Delete 2",
            }
        )
        # Browse with fresh environment to avoid context persistence
        code1 = self.VocabularyCode.browse(code1_rec.id)
        code2 = self.VocabularyCode.browse(code2_rec.id)

        codes = code1 | code2
        with self.assertRaises(UserError) as ctx:
            codes.unlink()
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    # Test that non-system vocabularies work normally

    def test_user_vocab_code_can_be_modified(self):
        """Test that codes in non-system vocabulary can be fully modified."""
        self.user_code.write(
            {
                "code": "MODIFIED_USER_CODE",
                "display": "Modified User Display",
                "definition": "New definition",
            }
        )
        self.assertEqual(self.user_code.code, "MODIFIED_USER_CODE")
        self.assertEqual(self.user_code.display, "Modified User Display")

    def test_user_vocab_code_can_be_deleted(self):
        """Test that codes in non-system vocabulary can be deleted."""
        code_to_delete = self.VocabularyCode.create(
            {
                "vocabulary_id": self.user_vocab.id,
                "code": "TO_DELETE_USER",
                "display": "To Delete User",
            }
        )
        code_id = code_to_delete.id
        code_to_delete.unlink()
        # Verify deletion
        self.assertFalse(self.VocabularyCode.search([("id", "=", code_id)]))

    def test_user_vocab_get_or_create_works(self):
        """Test that get_or_create() works for non-system vocabularies."""
        result = self.VocabularyCode.get_or_create("urn:test:user-protected", "NEW_USER_CODE", "New User Code Display")
        self.assertTrue(result.id)
        self.assertEqual(result.code, "NEW_USER_CODE")

    # Test mixed allowed and disallowed fields

    def test_cannot_modify_mixed_allowed_disallowed(self):
        """Test that write fails if any disallowed field is included."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write(
                {
                    "active": True,  # allowed
                    "sequence": 5,  # allowed
                    "display": "Modified",  # NOT allowed
                }
            )
        self.assertIn("display", str(ctx.exception))

    # Test error message quality

    def test_error_message_lists_disallowed_fields(self):
        """Test that error message lists the disallowed fields."""
        with self.assertRaises(UserError) as ctx:
            self.system_code.write(
                {
                    "code": "NEW",
                    "display": "New Display",
                }
            )
        error_msg = str(ctx.exception)
        self.assertIn("code", error_msg.lower())
        self.assertIn("display", error_msg.lower())

    # Test local code extensions (ADR-016)

    def test_can_add_local_code_to_system_vocabulary(self):
        """Test that local codes (is_local=True) can be added to system vocabularies.

        ADR-016: Local extensions allow country-specific codes to be added to
        standard vocabularies while maintaining traceability to the original standard.
        """
        local_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "LOCAL_EXTENSION",
                "display": "Local Extension Code",
                "is_local": True,
                "reference_uri": "urn:test:system-protected#SYSTEM_CODE",
                "equivalence": "narrower",
            }
        )
        self.assertTrue(local_code.id)
        self.assertTrue(local_code.is_local)
        self.assertEqual(local_code.vocabulary_id, self.system_vocab)

    def test_cannot_add_non_local_code_to_system_vocabulary(self):
        """Test that non-local codes still cannot be added to system vocabularies."""
        with self.assertRaises(UserError) as ctx:
            self.VocabularyCode.create(
                {
                    "vocabulary_id": self.system_vocab.id,
                    "code": "REGULAR_CODE",
                    "display": "Regular Code",
                    "is_local": False,
                }
            )
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_local_code_requires_is_local_flag(self):
        """Test that omitting is_local still blocks addition to system vocabulary."""
        with self.assertRaises(UserError) as ctx:
            self.VocabularyCode.create(
                {
                    "vocabulary_id": self.system_vocab.id,
                    "code": "NO_FLAG_CODE",
                    "display": "No Flag Code",
                    # is_local not specified, defaults to False
                }
            )
        self.assertIn("system vocabulary", str(ctx.exception).lower())

    def test_local_code_can_be_deleted_from_system_vocabulary(self):
        """Test that local codes can be deleted from system vocabularies."""
        local_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "LOCAL_TO_DELETE",
                "display": "Local To Delete",
                "is_local": True,
            }
        )
        code_id = local_code.id
        local_code.unlink()
        self.assertFalse(self.VocabularyCode.search([("id", "=", code_id)]))

    def test_local_code_can_be_modified_in_system_vocabulary(self):
        """Test that local codes can be fully modified in system vocabularies."""
        local_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "LOCAL_TO_MODIFY",
                "display": "Local To Modify",
                "is_local": True,
            }
        )
        # Local codes should be fully modifiable
        local_code.write(
            {
                "display": "Modified Local Display",
                "definition": "New definition for local code",
            }
        )
        self.assertEqual(local_code.display, "Modified Local Display")

    def test_get_or_create_local_code_system_vocabulary(self):
        """Test that get_or_create() works for local codes in system vocabularies."""
        result = self.VocabularyCode.get_or_create_local(
            "urn:test:system-protected",
            "LOCAL_VIA_API",
            "Local Via API",
            reference_uri="urn:test:system-protected#SYSTEM_CODE",
        )
        self.assertTrue(result.id)
        self.assertTrue(result.is_local)
        self.assertEqual(result.code, "LOCAL_VIA_API")
