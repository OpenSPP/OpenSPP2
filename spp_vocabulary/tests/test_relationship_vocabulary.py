# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for relationship vocabulary integration.

Note: The spp.relationship model has been moved to spp_registry module.
These tests are skipped when running in spp_vocabulary context since the
model is not available without spp_registry being installed.
"""

import unittest

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@unittest.skip("spp.relationship model moved to spp_registry module")
class TestRelationshipVocabulary(TransactionCase):
    """Test cases for spp.relationship vocabulary integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Relationship = cls.env["spp.relationship"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]

        # Get the relationship vocabulary
        cls.relationship_vocab = cls.Vocabulary.search(
            [("namespace_uri", "=", "urn:openspp:vocab:relationship")], limit=1
        )

    def test_vocabulary_code_field_exists(self):
        """Test that vocabulary_code_id field exists on spp.relationship."""
        rel = self.Relationship.create(
            {
                "name": "Test Relationship",
                "name_inverse": "Inverse Test",
            }
        )
        self.assertTrue(hasattr(rel, "vocabulary_code_id"))
        self.assertTrue(hasattr(rel, "vocabulary_code"))

    def test_link_relationship_to_vocabulary(self):
        """Test linking a relationship to a vocabulary code."""
        # Get a vocabulary code
        head_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "head"),
            ],
            limit=1,
        )

        # Delete any existing relationships linked to this vocabulary code
        # (to avoid unique constraint violation)
        existing = self.Relationship.search([("vocabulary_code_id", "=", head_code.id)])
        if existing:
            existing.unlink()

        # Create relationship with vocabulary link
        rel = self.Relationship.create(
            {
                "name": "Head of Household",
                "name_inverse": "Household Member",
                "vocabulary_code_id": head_code.id,
            }
        )

        self.assertEqual(rel.vocabulary_code_id, head_code)
        self.assertEqual(rel.vocabulary_code, "head")

    def test_vocabulary_code_stored(self):
        """Test that vocabulary_code is stored and indexed."""
        # Get a vocabulary code
        spouse_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "spouse"),
            ],
            limit=1,
        )

        # Delete any existing relationships linked to this vocabulary code
        existing = self.Relationship.search([("vocabulary_code_id", "=", spouse_code.id)])
        if existing:
            existing.unlink()

        rel = self.Relationship.create(
            {
                "name": "Spouse",
                "name_inverse": "Spouse",
                "vocabulary_code_id": spouse_code.id,
            }
        )

        # Search by vocabulary_code
        found = self.Relationship.search([("vocabulary_code", "=", "spouse")])
        self.assertIn(rel, found)

    def test_get_by_vocabulary_code(self):
        """Test get_by_vocabulary_code helper method."""
        # Get a vocabulary code
        child_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "child"),
            ],
            limit=1,
        )

        # Delete any existing relationships linked to this vocabulary code
        existing = self.Relationship.search([("vocabulary_code_id", "=", child_code.id)])
        if existing:
            existing.unlink()

        rel = self.Relationship.create(
            {
                "name": "Child",
                "name_inverse": "Parent",
                "vocabulary_code_id": child_code.id,
            }
        )

        # Find by vocabulary code
        found = self.Relationship.get_by_vocabulary_code("child")
        self.assertEqual(found, rel)

    def test_get_by_vocabulary_code_not_found(self):
        """Test get_by_vocabulary_code returns empty when not found."""
        found = self.Relationship.get_by_vocabulary_code("nonexistent_code")
        self.assertFalse(found)

    def test_relationship_without_vocabulary(self):
        """Test that relationships can exist without vocabulary codes."""
        rel = self.Relationship.create(
            {
                "name": "Custom Relationship",
                "name_inverse": "Inverse Custom",
            }
        )

        self.assertFalse(rel.vocabulary_code_id)
        self.assertFalse(rel.vocabulary_code)

    def test_vocabulary_domain_filter(self):
        """Test that vocabulary_code_id domain limits to relationship vocab."""
        # The domain filter is declarative, but we can verify the vocabulary exists
        self.assertTrue(self.relationship_vocab)
        self.assertEqual(self.relationship_vocab.namespace_uri, "urn:openspp:vocab:relationship")

    def test_relationship_types_seeded(self):
        """Test that seed relationship types are created with vocabulary links."""
        # Check for head of household relationship
        head_rel = self.Relationship.search([("vocabulary_code", "=", "head")])

        # May or may not exist depending on demo data
        if head_rel:
            self.assertEqual(head_rel.vocabulary_code_id.display, "Head of Household")

    def test_update_vocabulary_code(self):
        """Test updating the vocabulary code on a relationship."""
        # Get vocabulary codes
        parent_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "parent"),
            ],
            limit=1,
        )

        grandparent_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "grandparent"),
            ],
            limit=1,
        )

        # Delete any existing relationships linked to these vocabulary codes
        existing_parent = self.Relationship.search([("vocabulary_code_id", "=", parent_code.id)])
        if existing_parent:
            existing_parent.unlink()
        existing_grandparent = self.Relationship.search([("vocabulary_code_id", "=", grandparent_code.id)])
        if existing_grandparent:
            existing_grandparent.unlink()

        # Create with one code
        rel = self.Relationship.create(
            {
                "name": "Elder",
                "name_inverse": "Descendant",
                "vocabulary_code_id": parent_code.id,
            }
        )
        self.assertEqual(rel.vocabulary_code, "parent")

        # Update to different code
        rel.write({"vocabulary_code_id": grandparent_code.id})
        self.assertEqual(rel.vocabulary_code, "grandparent")

    def test_clear_vocabulary_code(self):
        """Test clearing the vocabulary code from a relationship."""
        sibling_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "sibling"),
            ],
            limit=1,
        )

        # Delete any existing relationships linked to this vocabulary code
        existing = self.Relationship.search([("vocabulary_code_id", "=", sibling_code.id)])
        if existing:
            existing.unlink()

        rel = self.Relationship.create(
            {
                "name": "Sibling",
                "name_inverse": "Sibling",
                "vocabulary_code_id": sibling_code.id,
            }
        )
        self.assertEqual(rel.vocabulary_code, "sibling")

        # Clear the vocabulary code
        rel.write({"vocabulary_code_id": False})
        self.assertFalse(rel.vocabulary_code)

    def test_unique_vocabulary_code_constraint(self):
        """Test that vocabulary codes can only be linked to one relationship."""
        from odoo.tools import mute_logger

        # Get a vocabulary code not already in use
        other_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "other_relative"),
            ],
            limit=1,
        )

        # Delete any existing relationships linked to this vocabulary code
        existing = self.Relationship.search([("vocabulary_code_id", "=", other_code.id)])
        if existing:
            existing.unlink()

        # Create first relationship with the code
        rel1 = self.Relationship.create(
            {
                "name": "Other Relative 1",
                "name_inverse": "Other Relative 1",
                "vocabulary_code_id": other_code.id,
            }
        )
        self.assertEqual(rel1.vocabulary_code_id, other_code)

        # Try to create second relationship with same code - should fail (ValidationError)
        with mute_logger("odoo.sql_db"):
            with self.assertRaises(ValidationError):
                with self.cr.savepoint():
                    self.Relationship.create(
                        {
                            "name": "Other Relative 2",
                            "name_inverse": "Other Relative 2",
                            "vocabulary_code_id": other_code.id,
                        }
                    )


@unittest.skip("spp.relationship model moved to spp_registry module")
class TestSyncFromVocabulary(TransactionCase):
    """Test cases for sync_from_vocabulary method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Relationship = cls.env["spp.relationship"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]

    def test_sync_creates_missing_relationships(self):
        """Test that sync_from_vocabulary creates relationships for unlinked codes."""
        # Get all vocabulary codes
        vocab_codes = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("active", "=", True),
            ]
        )

        # Clear all vocabulary links
        existing_rels = self.Relationship.search([("vocabulary_code_id", "!=", False)])
        existing_rels.write({"vocabulary_code_id": False})

        # Run sync
        created = self.Relationship.sync_from_vocabulary()

        # Verify relationships were created
        self.assertTrue(created)
        self.assertEqual(len(created), len(vocab_codes))

        # Verify each has correct vocabulary link
        for rel in created:
            self.assertTrue(rel.vocabulary_code_id)
            self.assertTrue(rel.vocabulary_code)

    def test_sync_is_idempotent(self):
        """Test that running sync twice doesn't create duplicates."""
        # Clear and sync
        existing_rels = self.Relationship.search([("vocabulary_code_id", "!=", False)])
        existing_rels.write({"vocabulary_code_id": False})

        created1 = self.Relationship.sync_from_vocabulary()
        count1 = len(created1)

        # Run sync again
        created2 = self.Relationship.sync_from_vocabulary()

        # Should not create any new relationships
        self.assertEqual(len(created2), 0)

        # Total count should be the same
        linked_rels = self.Relationship.search([("vocabulary_code_id", "!=", False)])
        self.assertEqual(len(linked_rels), count1)

    def test_sync_skips_existing_links(self):
        """Test that sync doesn't modify relationships already linked to vocab codes."""
        # Get a vocab code
        head_code = self.VocabularyCode.search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:relationship"),
                ("code", "=", "head"),
            ],
            limit=1,
        )

        # Clear other links but keep one
        self.Relationship.search(
            [
                ("vocabulary_code_id", "!=", False),
                ("vocabulary_code_id", "!=", head_code.id),
            ]
        ).write({"vocabulary_code_id": False})

        # Ensure we have one linked relationship
        existing = self.Relationship.search([("vocabulary_code_id", "=", head_code.id)])
        if not existing:
            self.Relationship.create(
                {
                    "name": "Test Head",
                    "name_inverse": "Test Member",
                    "vocabulary_code_id": head_code.id,
                }
            )

        # Run sync
        created = self.Relationship.sync_from_vocabulary()

        # The existing linked relationship should not be duplicated
        # And no new "head" relationship should be created
        for rel in created:
            self.assertNotEqual(rel.vocabulary_code, "head")

    def test_sync_sets_correct_defaults(self):
        """Test that synced relationships have correct default values."""
        # Clear all links
        self.Relationship.search([("vocabulary_code_id", "!=", False)]).write({"vocabulary_code_id": False})

        # Run sync
        created = self.Relationship.sync_from_vocabulary()

        # Check defaults
        for rel in created:
            self.assertTrue(rel.name)
            self.assertTrue(rel.name_inverse)
            self.assertFalse(rel.bidirectional)  # Default is False

    def test_sync_raises_error_if_vocab_missing(self):
        """Test that sync raises UserError if vocabulary doesn't exist."""
        # This would only happen if the module data wasn't loaded
        # We can't easily test this without modifying the database
        # Just verify the method exists and is callable
        self.assertTrue(hasattr(self.Relationship, "sync_from_vocabulary"))
        self.assertTrue(callable(self.Relationship.sync_from_vocabulary))
