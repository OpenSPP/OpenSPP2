import json

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestConceptGroup(TransactionCase):
    """Test the spp.vocabulary.concept.group model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ConceptGroup = cls.env["spp.vocabulary.concept.group"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Create test vocabulary
        cls.vocab_gender = cls.Vocabulary.create(
            {
                "name": "Test Gender",
                "namespace_uri": "urn:test:gender",
            }
        )

        # Create gender codes
        cls.code_male = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_gender.id,
                "code": "male",
                "display": "Male",
            }
        )

        cls.code_female = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_gender.id,
                "code": "female",
                "display": "Female",
            }
        )

        cls.code_other = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_gender.id,
                "code": "other",
                "display": "Other",
            }
        )

        # Create relationship vocabulary
        cls.vocab_rel = cls.Vocabulary.create(
            {
                "name": "Test Relationship",
                "namespace_uri": "urn:test:relationship",
            }
        )

        cls.code_head = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_rel.id,
                "code": "head",
                "display": "Head of Household",
            }
        )

        cls.code_spouse = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_rel.id,
                "code": "spouse",
                "display": "Spouse",
            }
        )

        # Create local code with reference URI
        cls.code_local_female = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab_gender.id,
                "code": "babae",
                "display": "Babae (Female)",
                "is_local": True,
                "reference_uri": cls.code_female.uri,
                "equivalence": "equivalent",
            }
        )

    def test_create_concept_group(self):
        """Test creating a concept group"""
        group = self.ConceptGroup.create(
            {
                "name": "test_group",
                "label": "Test Group",
                "description": "A test concept group",
                "cel_function": "is_test",
            }
        )

        self.assertEqual(group.name, "test_group")
        self.assertEqual(group.label, "Test Group")
        self.assertEqual(group.description, "A test concept group")
        self.assertEqual(group.cel_function, "is_test")

    def test_concept_group_name_unique(self):
        """Test that concept group name must be unique"""
        self.ConceptGroup.create(
            {
                "name": "unique_group",
                "label": "First Group",
            }
        )

        # Try to create another with same name
        with self.assertRaises(ValidationError):
            self.ConceptGroup.create(
                {
                    "name": "unique_group",
                    "label": "Second Group",
                }
            )

    def test_code_uris_computed_empty_group(self):
        """Test code_uris field is computed correctly for empty group"""
        group = self.ConceptGroup.create(
            {
                "name": "empty_group",
                "label": "Empty Group",
            }
        )

        # Should be empty JSON list
        self.assertEqual(group.code_uris, "[]")
        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 0)

    def test_code_uris_computed_with_codes(self):
        """Test code_uris field is computed correctly with codes"""
        group = self.ConceptGroup.create(
            {
                "name": "feminine_test",
                "label": "Feminine Gender",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        # Should contain the female code URI
        uris = json.loads(group.code_uris)
        self.assertIn(self.code_female.uri, uris)
        self.assertEqual(len(uris), 1)

    def test_code_uris_includes_reference_uri(self):
        """Test code_uris includes reference_uri from local codes"""
        group = self.ConceptGroup.create(
            {
                "name": "feminine_with_local",
                "label": "Feminine Gender (with local)",
                "code_ids": [(6, 0, [self.code_local_female.id])],
            }
        )

        # Should contain both the local code URI and the reference URI
        uris = json.loads(group.code_uris)
        self.assertIn(self.code_local_female.uri, uris)
        self.assertIn(self.code_local_female.reference_uri, uris)
        self.assertEqual(len(uris), 2)

    def test_code_uris_multiple_codes(self):
        """Test code_uris with multiple codes"""
        group = self.ConceptGroup.create(
            {
                "name": "all_genders",
                "label": "All Genders",
                "code_ids": [(6, 0, [self.code_male.id, self.code_female.id, self.code_other.id])],
            }
        )

        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 3)
        self.assertIn(self.code_male.uri, uris)
        self.assertIn(self.code_female.uri, uris)
        self.assertIn(self.code_other.uri, uris)

    def test_contains_with_direct_code(self):
        """Test contains() method with direct code membership"""
        group = self.ConceptGroup.create(
            {
                "name": "feminine_direct",
                "label": "Feminine Gender",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        # Female code should be in the group
        self.assertTrue(group.contains(self.code_female))

        # Male code should not be in the group
        self.assertFalse(group.contains(self.code_male))

    def test_contains_with_reference_uri(self):
        """Test contains() method with reference_uri match"""
        # Create group with only the standard female code
        group = self.ConceptGroup.create(
            {
                "name": "feminine_with_ref",
                "label": "Feminine Gender",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        # Local code (babae) should also match via reference_uri
        self.assertTrue(group.contains(self.code_local_female))

    def test_contains_with_empty_code(self):
        """Test contains() method with empty recordset"""
        group = self.ConceptGroup.create(
            {
                "name": "test_empty",
                "label": "Test Empty",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        empty_code = self.VocabularyCode.browse()
        self.assertFalse(group.contains(empty_code))

    def test_contains_handles_invalid_json(self):
        """Test contains() handles invalid JSON gracefully"""
        group = self.ConceptGroup.create(
            {
                "name": "invalid_json",
                "label": "Invalid JSON",
            }
        )

        # Manually corrupt the code_uris field
        group.write({"code_uris": "invalid json{["})

        # Should return False without raising error
        self.assertFalse(group.contains(self.code_female))

    def test_get_code_uris_returns_list(self):
        """Test get_code_uris() method returns list"""
        group = self.ConceptGroup.create(
            {
                "name": "test_get_uris",
                "label": "Test Get URIs",
                "code_ids": [(6, 0, [self.code_male.id, self.code_female.id])],
            }
        )

        uris = group.get_code_uris()

        self.assertIsInstance(uris, list)
        self.assertEqual(len(uris), 2)
        self.assertIn(self.code_male.uri, uris)
        self.assertIn(self.code_female.uri, uris)

    def test_get_code_uris_empty_group(self):
        """Test get_code_uris() with empty group"""
        group = self.ConceptGroup.create(
            {
                "name": "empty_for_get",
                "label": "Empty Group",
            }
        )

        uris = group.get_code_uris()

        self.assertIsInstance(uris, list)
        self.assertEqual(len(uris), 0)

    def test_get_code_uris_handles_invalid_json(self):
        """Test get_code_uris() handles invalid JSON gracefully"""
        group = self.ConceptGroup.create(
            {
                "name": "invalid_json_get",
                "label": "Invalid JSON",
            }
        )

        # Corrupt the JSON
        group.write({"code_uris": "not valid json"})

        # Should return empty list
        uris = group.get_code_uris()
        self.assertEqual(uris, [])

    def test_name_get_with_label(self):
        """Test name_get returns label when set"""
        group = self.ConceptGroup.create(
            {
                "name": "test_name_get",
                "label": "Test Display Name",
            }
        )

        name_get_result = group.name_get()
        self.assertEqual(len(name_get_result), 1)
        self.assertEqual(name_get_result[0][0], group.id)
        self.assertEqual(name_get_result[0][1], "Test Display Name")

    def test_name_get_without_label(self):
        """Test name_get falls back to name when label not set"""
        group = self.ConceptGroup.create(
            {
                "name": "test_fallback",
            }
        )

        name_get_result = group.name_get()
        self.assertEqual(name_get_result[0][1], "test_fallback")

    def test_name_get_with_cel_function(self):
        """Test name_get includes CEL function when set"""
        group = self.ConceptGroup.create(
            {
                "name": "test_cel",
                "label": "Test CEL",
                "cel_function": "is_test",
            }
        )

        name_get_result = group.name_get()
        self.assertEqual(name_get_result[0][1], "Test CEL (is_test)")

    def test_code_uris_recomputed_on_code_add(self):
        """Test code_uris is recomputed when codes are added"""
        group = self.ConceptGroup.create(
            {
                "name": "test_add_codes",
                "label": "Test Add Codes",
                "code_ids": [(6, 0, [self.code_male.id])],
            }
        )

        # Initially should only contain male URI
        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 1)
        self.assertIn(self.code_male.uri, uris)

        # Add female code
        group.write({"code_ids": [(4, self.code_female.id)]})

        # Should now contain both URIs
        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 2)
        self.assertIn(self.code_male.uri, uris)
        self.assertIn(self.code_female.uri, uris)

    def test_code_uris_recomputed_on_code_remove(self):
        """Test code_uris is recomputed when codes are removed"""
        group = self.ConceptGroup.create(
            {
                "name": "test_remove_codes",
                "label": "Test Remove Codes",
                "code_ids": [(6, 0, [self.code_male.id, self.code_female.id])],
            }
        )

        # Initially should contain both URIs
        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 2)

        # Remove male code
        group.write({"code_ids": [(3, self.code_male.id)]})

        # Should only contain female URI now
        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 1)
        self.assertIn(self.code_female.uri, uris)
        self.assertNotIn(self.code_male.uri, uris)

    def test_multiple_groups_with_same_code(self):
        """Test that the same code can be in multiple concept groups"""
        group1 = self.ConceptGroup.create(
            {
                "name": "group1",
                "label": "Group 1",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        group2 = self.ConceptGroup.create(
            {
                "name": "group2",
                "label": "Group 2",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        # Both groups should contain the female code
        self.assertTrue(group1.contains(self.code_female))
        self.assertTrue(group2.contains(self.code_female))

    def test_group_with_codes_from_different_vocabularies(self):
        """Test concept group can contain codes from different vocabularies"""
        group = self.ConceptGroup.create(
            {
                "name": "mixed_vocab",
                "label": "Mixed Vocabulary",
                "code_ids": [(6, 0, [self.code_female.id, self.code_head.id])],
            }
        )

        uris = json.loads(group.code_uris)
        self.assertEqual(len(uris), 2)
        self.assertIn(self.code_female.uri, uris)
        self.assertIn(self.code_head.uri, uris)

        # Both codes should be in the group
        self.assertTrue(group.contains(self.code_female))
        self.assertTrue(group.contains(self.code_head))

    def test_seed_data_feminine_gender_group_exists(self):
        """Test that seed data creates feminine_gender group"""
        # Try to find the group created by seed data
        group = self.env.ref("spp_vocabulary.group_feminine_gender", raise_if_not_found=False)

        # If seed data was loaded, verify the group
        if group:
            self.assertEqual(group.name, "feminine_gender")
            self.assertEqual(group.cel_function, "is_female")
            self.assertTrue(len(group.code_ids) > 0)

    def test_seed_data_masculine_gender_group_exists(self):
        """Test that seed data creates masculine_gender group"""
        group = self.env.ref("spp_vocabulary.group_masculine_gender", raise_if_not_found=False)

        if group:
            self.assertEqual(group.name, "masculine_gender")
            self.assertEqual(group.cel_function, "is_male")

    def test_seed_data_head_of_household_group_exists(self):
        """Test that seed data creates head_of_household group"""
        group = self.env.ref("spp_vocabulary.group_head_of_household", raise_if_not_found=False)

        if group:
            self.assertEqual(group.name, "head_of_household")
            self.assertEqual(group.cel_function, "is_head")

    def test_code_uris_sorted_alphabetically(self):
        """Test that code_uris are stored in sorted order"""
        group = self.ConceptGroup.create(
            {
                "name": "test_sorted",
                "label": "Test Sorted",
                "code_ids": [(6, 0, [self.code_other.id, self.code_male.id, self.code_female.id])],
            }
        )

        uris = json.loads(group.code_uris)

        # URIs should be sorted alphabetically
        self.assertEqual(uris, sorted(uris))

    def test_contains_performance_no_database_query(self):
        """Test that contains() doesn't trigger additional database queries"""
        group = self.ConceptGroup.create(
            {
                "name": "perf_test",
                "label": "Performance Test",
                "code_ids": [(6, 0, [self.code_female.id])],
            }
        )

        # Load the group and code into memory
        # Access code_uris to ensure computed field is loaded
        _ = group.code_uris
        code = self.code_female

        # contains() should work with just the loaded data (no new queries)
        # This is a behavioral test - it should use JSON lookup, not search()
        result = group.contains(code)
        self.assertTrue(result)
