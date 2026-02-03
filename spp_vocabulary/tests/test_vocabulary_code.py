from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestVocabularyCode(TransactionCase):
    """Test the spp.vocabulary.code model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Create test vocabularies
        cls.vocab_system = cls.Vocabulary.create(
            {
                "name": "System Vocabulary",
                "namespace_uri": "urn:test:system",
                "is_system": True,
            }
        )

        cls.vocab_user = cls.Vocabulary.create(
            {
                "name": "User Vocabulary",
                "namespace_uri": "urn:test:user",
                "is_system": False,
            }
        )

        cls.vocab_hierarchical = cls.Vocabulary.create(
            {
                "name": "Hierarchical Vocabulary",
                "namespace_uri": "urn:test:hierarchy",
                "is_hierarchical": True,
            }
        )

    def test_create_code(self):
        """Test creating a code and verify all fields are set correctly"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "TEST01",
                "display": "Test Code 01",
                "definition": "A test code for testing",
                "sequence": 5,
            }
        )

        self.assertEqual(code.vocabulary_id, self.vocab_user)
        self.assertEqual(code.namespace_uri, "urn:test:user")
        self.assertEqual(code.code, "TEST01")
        self.assertEqual(code.display, "Test Code 01")
        self.assertEqual(code.definition, "A test code for testing")
        self.assertEqual(code.sequence, 5)
        self.assertTrue(code.active)
        self.assertFalse(code.deprecated)
        self.assertEqual(code.level, 0)

    def test_code_unique_in_vocabulary(self):
        """Test that code must be unique within a vocabulary"""
        # Use a unique code name to avoid conflicts with other tests
        import uuid

        unique_code = f"UNIQUE_{uuid.uuid4().hex[:8]}"

        # Delete any existing code with this code in this vocabulary (shouldn't exist, but be safe)
        existing = self.VocabularyCode.search(
            [
                ("vocabulary_id", "=", self.vocab_user.id),
                ("code", "=", unique_code),
            ]
        )
        if existing:
            existing.unlink()

        # Create first code
        self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": unique_code,
                "display": "First Code",
            }
        )

        # Try to create second code with same code in same vocabulary
        with self.assertRaises(ValidationError):
            self.VocabularyCode.create(
                {
                    "vocabulary_id": self.vocab_user.id,
                    "code": unique_code,
                    "display": "Second Code",
                }
            )

    def test_code_can_duplicate_across_vocabularies(self):
        """Test that same code can exist in different vocabularies"""
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "SHARED",
                "display": "Code in User Vocab",
            }
        )

        # Use install_mode context to create code in system vocabulary
        code2 = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.vocab_system.id,
                "code": "SHARED",
                "display": "Code in System Vocab",
            }
        )

        self.assertNotEqual(code1.id, code2.id)
        self.assertEqual(code1.code, code2.code)
        self.assertNotEqual(code1.namespace_uri, code2.namespace_uri)

    def test_get_code_returns_correct_record(self):
        """Test get_code() method returns the correct code"""
        # Create test code
        created_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "FIND_ME",
                "display": "Findable Code",
            }
        )

        # Use get_code to find it
        found_code = self.VocabularyCode.get_code("urn:test:user", "FIND_ME")

        self.assertEqual(found_code, created_code)
        self.assertEqual(found_code.code, "FIND_ME")
        self.assertEqual(found_code.display, "Findable Code")

    def test_get_code_returns_empty_when_not_found(self):
        """Test get_code() returns empty recordset when code doesn't exist"""
        result = self.VocabularyCode.get_code("urn:test:user", "NONEXISTENT")
        self.assertFalse(result)

    def test_get_code_ignores_inactive(self):
        """Test get_code() only returns active codes"""
        # Create inactive code
        self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "INACTIVE",
                "display": "Inactive Code",
                "active": False,
            }
        )

        # Try to find it with get_code
        result = self.VocabularyCode.get_code("urn:test:user", "INACTIVE")
        self.assertFalse(result)

    def test_get_code_cache(self):
        """Test that get_code() caching works correctly"""
        # Clear cache first
        self.env.registry.clear_cache()

        # Create a code
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "CACHE_TEST",
                "display": "Cache Test",
            }
        )

        # First call should cache the result
        result1 = self.VocabularyCode.get_code("urn:test:user", "CACHE_TEST")
        self.assertEqual(result1, code)

        # Second call should use cache (modify code but get old cached result)
        code.write({"display": "Modified Display"})

        # Cache should be cleared on write
        result2 = self.VocabularyCode.get_code("urn:test:user", "CACHE_TEST")
        self.assertEqual(result2.display, "Modified Display")

    def test_get_or_create_existing(self):
        """Test get_or_create() returns existing code"""
        # Create existing code
        existing = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "EXISTING",
                "display": "Existing Code",
            }
        )

        # Call get_or_create
        result = self.VocabularyCode.get_or_create("urn:test:user", "EXISTING", "Different Display")

        # Should return existing code, not create new one
        self.assertEqual(result, existing)
        self.assertEqual(result.display, "Existing Code")  # Original display unchanged

    def test_get_or_create_new(self):
        """Test get_or_create() creates new code in non-system vocabulary"""
        # Ensure code doesn't exist
        self.assertFalse(
            self.VocabularyCode.search(
                [
                    ("vocabulary_id", "=", self.vocab_user.id),
                    ("code", "=", "NEW_CODE"),
                ]
            )
        )

        # Call get_or_create
        result = self.VocabularyCode.get_or_create("urn:test:user", "NEW_CODE", "New Code Display")

        # Should create new code
        self.assertTrue(result)
        self.assertEqual(result.code, "NEW_CODE")
        self.assertEqual(result.display, "New Code Display")
        self.assertEqual(result.vocabulary_id, self.vocab_user)

    def test_get_or_create_new_without_display(self):
        """Test get_or_create() creates code using code as display if display not provided"""
        result = self.VocabularyCode.get_or_create("urn:test:user", "CODE_AS_DISPLAY")

        self.assertEqual(result.code, "CODE_AS_DISPLAY")
        self.assertEqual(result.display, "CODE_AS_DISPLAY")

    def test_get_or_create_system_vocab_raises(self):
        """Test get_or_create() raises error for system vocabularies"""
        with self.assertRaises(UserError) as ctx:
            self.VocabularyCode.get_or_create("urn:test:system", "NEW_CODE", "Should Fail")

        self.assertIn("system vocabulary", str(ctx.exception))

    def test_get_or_create_nonexistent_vocab_raises(self):
        """Test get_or_create() raises error if vocabulary doesn't exist"""
        with self.assertRaises(UserError) as ctx:
            self.VocabularyCode.get_or_create("urn:test:nonexistent", "CODE", "Display")

        self.assertIn("Vocabulary not found", str(ctx.exception))

    def test_get_or_create_inactive_code_raises(self):
        """Test get_or_create() raises error if code exists but is inactive"""
        # Create inactive code
        self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "INACTIVE_CODE",
                "display": "Inactive",
                "active": False,
            }
        )

        with self.assertRaises(UserError) as ctx:
            self.VocabularyCode.get_or_create("urn:test:user", "INACTIVE_CODE")

        self.assertIn("inactive", str(ctx.exception))

    def test_hierarchy_level_computed(self):
        """Test that level is computed correctly for parent/child relationships"""
        # Create root code (level 0)
        root = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "ROOT",
                "display": "Root Code",
            }
        )
        self.assertEqual(root.level, 0)

        # Create child code (level 1)
        child = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "CHILD",
                "display": "Child Code",
                "parent_id": root.id,
            }
        )
        self.assertEqual(child.level, 1)

        # Create grandchild code (level 2)
        grandchild = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "GRANDCHILD",
                "display": "Grandchild Code",
                "parent_id": child.id,
            }
        )
        self.assertEqual(grandchild.level, 2)

    def test_hierarchy_parent_relationship(self):
        """Test parent-child relationships work correctly"""
        parent = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "PARENT",
                "display": "Parent",
            }
        )

        child1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "CHILD1",
                "display": "Child 1",
                "parent_id": parent.id,
            }
        )

        child2 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "CHILD2",
                "display": "Child 2",
                "parent_id": parent.id,
            }
        )

        # Verify parent relationship
        self.assertEqual(child1.parent_id, parent)
        self.assertEqual(child2.parent_id, parent)

        # Verify children relationship
        self.assertIn(child1, parent.child_ids)
        self.assertIn(child2, parent.child_ids)
        self.assertEqual(len(parent.child_ids), 2)

    def test_name_get(self):
        """Test that name_get returns format 'Display (code)'"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "TEST",
                "display": "Test Display",
            }
        )

        name_get_result = code.name_get()
        self.assertEqual(len(name_get_result), 1)
        self.assertEqual(name_get_result[0][0], code.id)
        self.assertEqual(name_get_result[0][1], "Test Display (TEST)")

    def test_name_get_multiple_records(self):
        """Test name_get with multiple records"""
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "CODE1",
                "display": "First",
            }
        )
        code2 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "CODE2",
                "display": "Second",
            }
        )

        codes = code1 | code2
        name_get_result = codes.name_get()

        self.assertEqual(len(name_get_result), 2)
        self.assertEqual(name_get_result[0][1], "First (CODE1)")
        self.assertEqual(name_get_result[1][1], "Second (CODE2)")

    def test_deprecated_code(self):
        """Test deprecated code fields"""
        replacement = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "NEW",
                "display": "New Code",
            }
        )

        deprecated_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "OLD",
                "display": "Old Code",
                "deprecated": True,
                "deprecated_date": "2024-01-01",
                "replaced_by_id": replacement.id,
            }
        )

        self.assertTrue(deprecated_code.deprecated)
        self.assertEqual(str(deprecated_code.deprecated_date), "2024-01-01")
        self.assertEqual(deprecated_code.replaced_by_id, replacement)

    def test_default_sequence(self):
        """Test that default sequence is 10"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "SEQ",
                "display": "Sequence Test",
            }
        )
        self.assertEqual(code.sequence, 10)

    def test_namespace_uri_stored(self):
        """Test that namespace_uri is stored from related field"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "NS",
                "display": "Namespace Test",
            }
        )

        # namespace_uri should be stored
        self.assertEqual(code.namespace_uri, self.vocab_user.namespace_uri)
        self.assertEqual(code.namespace_uri, "urn:test:user")

    def test_cache_cleared_on_create(self):
        """Test that cache is cleared when creating codes"""
        # Clear cache
        self.env.registry.clear_cache()

        # Create and retrieve code to populate cache
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "CACHE1",
                "display": "Cache 1",
            }
        )
        result1 = self.VocabularyCode.get_code("urn:test:user", "CACHE1")
        self.assertEqual(result1, code1)

        # Create new code (should clear cache)
        self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "CACHE2",
                "display": "Cache 2",
            }
        )

        # Should still find first code
        result2 = self.VocabularyCode.get_code("urn:test:user", "CACHE1")
        self.assertEqual(result2, code1)

    def test_cache_cleared_on_unlink(self):
        """Test that cache is cleared when deleting codes"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "DELETE_ME",
                "display": "To Delete",
            }
        )

        # Verify code exists
        result = self.VocabularyCode.get_code("urn:test:user", "DELETE_ME")
        self.assertEqual(result, code)

        # Delete code
        code.unlink()

        # Should not find deleted code
        result = self.VocabularyCode.get_code("urn:test:user", "DELETE_ME")
        self.assertFalse(result)

    def test_level_recomputed_when_parent_changes(self):
        """Test that level is recomputed when parent hierarchy changes"""
        root = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "ROOT",
                "display": "Root",
            }
        )

        child = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "CHILD",
                "display": "Child",
                "parent_id": root.id,
            }
        )

        movable = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_hierarchical.id,
                "code": "MOVABLE",
                "display": "Movable",
            }
        )

        # Initially at level 0
        self.assertEqual(movable.level, 0)

        # Move under child (should become level 2)
        movable.write({"parent_id": child.id})
        self.assertEqual(movable.level, 2)

        # Move under root (should become level 1)
        movable.write({"parent_id": root.id})
        self.assertEqual(movable.level, 1)

        # Remove parent (should become level 0)
        movable.write({"parent_id": False})
        self.assertEqual(movable.level, 0)

    # ADR-016: Code URI Tests

    def test_uri_computed_on_create(self):
        """Test that URI is computed automatically when creating a code"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "URI_TEST",
                "display": "URI Test Code",
            }
        )

        expected_uri = "urn:test:user#URI_TEST"
        self.assertEqual(code.uri, expected_uri)
        self.assertFalse(code.is_local)

    def test_uri_can_be_overridden(self):
        """Test that URI can be manually set during creation"""
        custom_uri = "urn:custom:namespace#CUSTOM_CODE"
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "OVERRIDE",
                "display": "Override Test",
                "uri": custom_uri,
            }
        )

        self.assertEqual(code.uri, custom_uri)
        self.assertNotEqual(code.uri, f"{self.vocab_user.namespace_uri}#OVERRIDE")

    def test_uri_unique_constraint(self):
        """Test that URI must be globally unique"""
        import uuid

        unique_code = f"UNIQUE_{uuid.uuid4().hex[:8]}"

        # Create first code
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": unique_code,
                "display": "First Code",
            }
        )

        # Try to create another code with same URI (different code in different vocab)
        # Use bypass context since we're writing to system vocabulary
        with self.assertRaises(ValidationError):
            self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
                {
                    "vocabulary_id": self.vocab_system.id,
                    "code": "DIFFERENT",
                    "display": "Different Code",
                    "uri": code1.uri,  # Explicit duplicate URI
                }
            )

    def test_resolve_by_uri_returns_correct_code(self):
        """Test resolve_by_uri() method finds code by URI"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "RESOLVE_ME",
                "display": "Resolvable Code",
            }
        )

        # Clear cache to ensure fresh lookup
        self.env.registry.clear_cache()

        # Resolve by URI
        resolved = self.VocabularyCode.resolve_by_uri(code.uri)

        self.assertEqual(resolved, code)
        self.assertEqual(resolved.code, "RESOLVE_ME")

    def test_resolve_by_uri_returns_empty_when_not_found(self):
        """Test resolve_by_uri() returns empty recordset for non-existent URI"""
        result = self.VocabularyCode.resolve_by_uri("urn:nonexistent:uri#code")
        self.assertFalse(result)

    def test_resolve_by_uri_ignores_inactive(self):
        """Test resolve_by_uri() only returns active codes"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "INACTIVE_URI",
                "display": "Inactive Code",
                "active": False,
            }
        )

        # Clear cache
        self.env.registry.clear_cache()

        # Try to resolve inactive code
        result = self.VocabularyCode.resolve_by_uri(code.uri)
        self.assertFalse(result)

    def test_resolve_by_uri_cached(self):
        """Test that resolve_by_uri() uses caching"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "CACHE_URI",
                "display": "Cache Test",
            }
        )

        # Clear cache first
        self.env.registry.clear_cache()

        # First call should cache the result
        result1 = self.VocabularyCode.resolve_by_uri(code.uri)
        self.assertEqual(result1, code)

        # Modify the code
        code.write({"display": "Modified Display"})

        # Cache should be cleared on write
        result2 = self.VocabularyCode.resolve_by_uri(code.uri)
        self.assertEqual(result2.display, "Modified Display")

    def test_resolve_alias_by_code(self):
        """Test resolve_alias() finds code by code value"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "ALIAS_CODE",
                "display": "Alias Display",
            }
        )

        # Resolve by code value
        resolved = self.VocabularyCode.resolve_alias("ALIAS_CODE")
        self.assertEqual(resolved, code)

    def test_resolve_alias_by_display(self):
        """Test resolve_alias() finds code by display name"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "DISP_CODE",
                "display": "Display Name",
            }
        )

        # Resolve by display name
        resolved = self.VocabularyCode.resolve_alias("Display Name")
        self.assertEqual(resolved, code)

    def test_resolve_alias_with_namespace(self):
        """Test resolve_alias() with namespace filtering"""
        # Create codes with same code in different vocabularies
        code_user = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "SHARED_ALIAS",
                "display": "User Code",
            }
        )

        # Use install_mode context to create code in system vocabulary
        code_system = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.vocab_system.id,
                "code": "SHARED_ALIAS",
                "display": "System Code",
            }
        )

        # Resolve with user namespace
        resolved_user = self.VocabularyCode.resolve_alias("SHARED_ALIAS", namespace="urn:test:user")
        self.assertEqual(resolved_user, code_user)

        # Resolve with system namespace
        resolved_system = self.VocabularyCode.resolve_alias("SHARED_ALIAS", namespace="urn:test:system")
        self.assertEqual(resolved_system, code_system)

    def test_resolve_alias_returns_empty_when_not_found(self):
        """Test resolve_alias() returns empty recordset when not found"""
        result = self.VocabularyCode.resolve_alias("NONEXISTENT_ALIAS")
        self.assertFalse(result)

    def test_local_code_with_reference_uri(self):
        """Test local code with reference URI mapping"""
        # Create a standard code
        standard_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "typhoon",
                "display": "Typhoon",
            }
        )

        # Create a local code that maps to the standard
        # Use install_mode context to create code in system vocabulary
        local_code = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.vocab_system.id,  # Different vocab for local
                "code": "bagyong",
                "display": "Bagyong (Typhoon)",
                "is_local": True,
                "reference_uri": standard_code.uri,
                "equivalence": "equivalent",
            }
        )

        self.assertTrue(local_code.is_local)
        self.assertEqual(local_code.reference_uri, standard_code.uri)
        self.assertEqual(local_code.equivalence, "equivalent")

    def test_resolve_alias_by_reference_uri(self):
        """Test resolve_alias() finds local code by reference URI"""
        # Create standard code
        standard = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "standard",
                "display": "Standard Code",
            }
        )

        # Create local code mapping to standard
        # Use install_mode context to create code in system vocabulary
        local = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.vocab_system.id,
                "code": "local",
                "display": "Local Code",
                "is_local": True,
                "reference_uri": standard.uri,
                "equivalence": "equivalent",
            }
        )

        # Resolve by reference URI (full URI)
        resolved = self.VocabularyCode.resolve_alias(standard.uri)
        self.assertEqual(resolved, local)

    def test_equivalence_types(self):
        """Test all equivalence types are available"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "EQUIV_TEST",
                "display": "Equivalence Test",
                "is_local": True,
            }
        )

        # Test each equivalence type
        for equiv in ["equivalent", "wider", "narrower", "inexact"]:
            code.write({"equivalence": equiv})
            self.assertEqual(code.equivalence, equiv)

    def test_uri_updates_on_code_change(self):
        """Test that URI is recomputed when code or vocabulary changes"""
        code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_user.id,
                "code": "ORIGINAL",
                "display": "Original Code",
            }
        )

        original_uri = code.uri
        self.assertEqual(original_uri, "urn:test:user#ORIGINAL")

        # Change the code
        code.write({"code": "CHANGED"})

        # URI should be recomputed
        self.assertEqual(code.uri, "urn:test:user#CHANGED")
        self.assertNotEqual(code.uri, original_uri)
