# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestVocabularyMapping(TransactionCase):
    """Test cases for spp.vocabulary.mapping model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.VocabularyMapping = cls.env["spp.vocabulary.mapping"]

        # Create two vocabularies for cross-mapping tests
        cls.vocab_iso = cls.Vocabulary.create(
            {
                "name": "ISO Gender",
                "namespace_uri": "urn:iso:test:gender",
                "domain": "core",
            }
        )
        cls.vocab_local = cls.Vocabulary.create(
            {
                "name": "Local Gender",
                "namespace_uri": "urn:local:gender",
                "domain": "core",
            }
        )

        # Create codes in each vocabulary
        cls.code_iso_male = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_iso.id,
                "code": "1",
                "display": "Male",
            }
        )
        cls.code_iso_female = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_iso.id,
                "code": "2",
                "display": "Female",
            }
        )
        cls.code_local_m = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_local.id,
                "code": "M",
                "display": "Masculino",
            }
        )
        cls.code_local_f = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_local.id,
                "code": "F",
                "display": "Femenino",
            }
        )

    def test_create_mapping(self):
        """Test creating a mapping and verify all fields are set correctly"""
        mapping = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "equivalence": "equivalent",
                "comment": "Local gender code to ISO standard",
            }
        )

        self.assertEqual(mapping.source_id, self.code_local_m)
        self.assertEqual(mapping.target_id, self.code_iso_male)
        self.assertEqual(mapping.equivalence, "equivalent")
        self.assertEqual(mapping.comment, "Local gender code to ISO standard")

    @mute_logger("odoo.sql_db")
    def test_create_mapping_requires_source(self):
        """Test that source_id is required"""
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.VocabularyMapping.create(
                    {
                        "target_id": self.code_iso_male.id,
                        "equivalence": "equivalent",
                    }
                )

    @mute_logger("odoo.sql_db")
    def test_create_mapping_requires_target(self):
        """Test that target_id is required"""
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.VocabularyMapping.create(
                    {
                        "source_id": self.code_local_m.id,
                        "equivalence": "equivalent",
                    }
                )

    def test_equivalence_default_value(self):
        """Test that equivalence defaults to 'equivalent'"""
        mapping = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
            }
        )
        self.assertEqual(mapping.equivalence, "equivalent")

    def test_unique_mapping_constraint(self):
        """Test that mapping between same source and target must be unique"""
        # Create unique codes for this test to avoid conflicts
        code_source = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": f"TEST_SRC_{id(self)}",
                "display": "Test Source",
            }
        )
        code_target = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_iso.id,
                "code": f"TEST_TGT_{id(self)}",
                "display": "Test Target",
            }
        )

        # Delete any existing mapping between these codes (shouldn't exist, but be safe)
        existing = self.VocabularyMapping.search(
            [
                ("source_id", "=", code_source.id),
                ("target_id", "=", code_target.id),
            ]
        )
        if existing:
            existing.unlink()

        # Create first mapping
        self.VocabularyMapping.create(
            {
                "source_id": code_source.id,
                "target_id": code_target.id,
                "equivalence": "equivalent",
            }
        )

        # Try to create duplicate mapping - Python constraint raises ValidationError
        with self.assertRaises(ValidationError):
            self.VocabularyMapping.create(
                {
                    "source_id": code_source.id,
                    "target_id": code_target.id,
                    "equivalence": "wider",  # Even with different equivalence
                }
            )

    def test_display_name_computed(self):
        """Test that display_name is computed correctly"""
        mapping = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "equivalence": "equivalent",
            }
        )

        expected = "M → 1 (equivalent)"
        self.assertEqual(mapping.display_name, expected)

    def test_display_name_with_all_equivalence_types(self):
        """Test display_name with different equivalence types"""
        # Test equivalent
        mapping_eq = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "equivalence": "equivalent",
            }
        )
        self.assertEqual(mapping_eq.display_name, "M → 1 (equivalent)")

        # Test wider
        mapping_wider = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_f.id,
                "target_id": self.code_iso_female.id,
                "equivalence": "wider",
            }
        )
        self.assertEqual(mapping_wider.display_name, "F → 2 (wider)")

        # Create additional codes for narrower and inexact tests
        code_local_other = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": "O",
                "display": "Otro",
            }
        )
        code_iso_other = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_iso.id,
                "code": "9",
                "display": "Not applicable",
            }
        )

        # Test narrower
        mapping_narrower = self.VocabularyMapping.create(
            {
                "source_id": code_local_other.id,
                "target_id": code_iso_other.id,
                "equivalence": "narrower",
            }
        )
        self.assertEqual(mapping_narrower.display_name, "O → 9 (narrower)")

        # Test inexact
        code_local_unknown = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": "U",
                "display": "Unknown",
            }
        )
        mapping_inexact = self.VocabularyMapping.create(
            {
                "source_id": code_local_unknown.id,
                "target_id": code_iso_other.id,
                "equivalence": "inexact",
            }
        )
        self.assertEqual(mapping_inexact.display_name, "U → 9 (inexact)")

    def test_display_name_incomplete_mapping(self):
        """Test display_name when mapping is incomplete"""
        # This shouldn't normally happen due to required fields,
        # but test the defensive code
        mapping = self.VocabularyMapping.new(
            {
                "source_id": False,
                "target_id": False,
                "equivalence": "equivalent",
            }
        )
        mapping._compute_display_name()
        self.assertEqual(mapping.display_name, "Incomplete Mapping")

    def test_map_code_finds_mapping(self):
        """Test map_code() method finds correct target code"""
        # Create mapping
        self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "equivalence": "equivalent",
            }
        )

        # Use map_code to find target
        result = self.VocabularyMapping.map_code("urn:local:gender", "M", "urn:iso:test:gender")

        self.assertEqual(result, self.code_iso_male)
        self.assertEqual(result.code, "1")
        self.assertEqual(result.display, "Male")

    def test_map_code_returns_empty_when_not_found(self):
        """Test map_code() returns empty recordset when mapping doesn't exist"""
        result = self.VocabularyMapping.map_code("urn:local:gender", "NONEXISTENT", "urn:iso:test:gender")

        self.assertFalse(result)
        self.assertEqual(len(result), 0)

    def test_map_code_with_nonexistent_namespace(self):
        """Test map_code() with nonexistent namespaces"""
        # Create mapping
        self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
            }
        )

        # Try with wrong source namespace
        result = self.VocabularyMapping.map_code("urn:wrong:namespace", "M", "urn:iso:test:gender")
        self.assertFalse(result)

        # Try with wrong target namespace
        result = self.VocabularyMapping.map_code("urn:local:gender", "M", "urn:wrong:namespace")
        self.assertFalse(result)

    def test_delete_source_cascades_mapping(self):
        """Test that deleting source code cascades to mapping"""
        mapping = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
            }
        )

        mapping_id = mapping.id
        self.assertTrue(mapping.exists())

        # Delete source code
        self.code_local_m.unlink()

        # Mapping should be deleted due to cascade
        self.assertFalse(self.VocabularyMapping.browse(mapping_id).exists())

    def test_delete_target_cascades_mapping(self):
        """Test that deleting target code cascades to mapping"""
        # Create a new code pair for this test
        code_source = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": "TEST_SRC",
                "display": "Test Source",
            }
        )
        code_target = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_iso.id,
                "code": "TEST_TGT",
                "display": "Test Target",
            }
        )

        mapping = self.VocabularyMapping.create(
            {
                "source_id": code_source.id,
                "target_id": code_target.id,
            }
        )

        mapping_id = mapping.id
        self.assertTrue(mapping.exists())

        # Delete target code
        code_target.unlink()

        # Mapping should be deleted due to cascade
        self.assertFalse(self.VocabularyMapping.browse(mapping_id).exists())

    def test_comment_field(self):
        """Test that comment field can store text"""
        long_comment = """This is a detailed explanation of why this mapping exists.
        It can span multiple lines and contain important context about the
        equivalence between these two coding systems."""

        mapping = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "comment": long_comment,
            }
        )

        self.assertEqual(mapping.comment, long_comment)

    def test_mapping_between_same_vocabulary(self):
        """Test that mapping between codes in same vocabulary is allowed"""
        # Create two codes in same vocabulary
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": "OLD_CODE",
                "display": "Old Code",
            }
        )
        code2 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": "NEW_CODE",
                "display": "New Code",
            }
        )

        # Should allow mapping within same vocabulary
        mapping = self.VocabularyMapping.create(
            {
                "source_id": code1.id,
                "target_id": code2.id,
                "equivalence": "equivalent",
            }
        )

        self.assertEqual(mapping.source_id.vocabulary_id, mapping.target_id.vocabulary_id)
        self.assertEqual(mapping.display_name, "OLD_CODE → NEW_CODE (equivalent)")

    def test_multiple_mappings_from_same_source(self):
        """Test that same source can map to different targets"""
        # Create additional target code
        code_iso_other = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_iso.id,
                "code": "9",
                "display": "Not applicable",
            }
        )

        # Create first mapping
        mapping1 = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "equivalence": "equivalent",
            }
        )

        # Create second mapping from same source to different target
        mapping2 = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": code_iso_other.id,
                "equivalence": "inexact",
            }
        )

        # Both mappings should exist
        self.assertTrue(mapping1.exists())
        self.assertTrue(mapping2.exists())
        self.assertEqual(mapping1.source_id, mapping2.source_id)
        self.assertNotEqual(mapping1.target_id, mapping2.target_id)

    def test_map_code_with_multiple_targets(self):
        """Test map_code() returns first mapping when multiple exist"""
        # Create two targets in same vocabulary
        code_target1 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_iso.id,
                "code": "TARGET1",
                "display": "Target 1",
            }
        )
        code_target2 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_iso.id,
                "code": "TARGET2",
                "display": "Target 2",
            }
        )

        # Create mappings (first one should be returned)
        self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": code_target1.id,
                "equivalence": "equivalent",
            }
        )
        self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": code_target2.id,
                "equivalence": "wider",
            }
        )

        # map_code should return only one result (limit=1)
        result = self.VocabularyMapping.map_code("urn:local:gender", "M", "urn:iso:test:gender")

        self.assertEqual(len(result), 1)
        # Should return the first mapping created
        self.assertEqual(result, code_target1)

    def test_map_code_case_sensitive(self):
        """Test that map_code() is case-sensitive"""
        # Create mapping with lowercase code
        code_lower = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab_local.id,
                "code": "lowercase",
                "display": "Lower Case",
            }
        )

        self.VocabularyMapping.create(
            {
                "source_id": code_lower.id,
                "target_id": self.code_iso_male.id,
            }
        )

        # Should find with exact case
        result = self.VocabularyMapping.map_code("urn:local:gender", "lowercase", "urn:iso:test:gender")
        self.assertTrue(result)

        # Should not find with different case
        result = self.VocabularyMapping.map_code("urn:local:gender", "LOWERCASE", "urn:iso:test:gender")
        self.assertFalse(result)

    def test_bidirectional_mapping(self):
        """Test creating bidirectional mappings between vocabularies"""
        # Create mapping from local to ISO
        mapping_forward = self.VocabularyMapping.create(
            {
                "source_id": self.code_local_m.id,
                "target_id": self.code_iso_male.id,
                "equivalence": "equivalent",
            }
        )

        # Create reverse mapping from ISO to local
        mapping_reverse = self.VocabularyMapping.create(
            {
                "source_id": self.code_iso_male.id,
                "target_id": self.code_local_m.id,
                "equivalence": "equivalent",
            }
        )

        # Both should exist
        self.assertTrue(mapping_forward.exists())
        self.assertTrue(mapping_reverse.exists())

        # Test mapping in both directions
        result_forward = self.VocabularyMapping.map_code("urn:local:gender", "M", "urn:iso:test:gender")
        self.assertEqual(result_forward, self.code_iso_male)

        result_reverse = self.VocabularyMapping.map_code("urn:iso:test:gender", "1", "urn:local:gender")
        self.assertEqual(result_reverse, self.code_local_m)
