"""End-to-end workflow tests for vocabulary system.

Tests complete workflows from vocabulary creation through deployment profiles
and concept groups - the critical paths for ADR-016 implementation.
"""

from odoo.tests.common import TransactionCase


class TestE2EWorkflow(TransactionCase):
    """End-to-end workflow tests for vocabulary system."""

    def test_complete_gender_vocabulary_workflow(self):
        """Test complete workflow: vocabulary -> codes -> profile -> selection."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]
        DeploymentProfile = self.env["spp.deployment.profile"]
        VocabularySelection = self.env["spp.vocabulary.selection"]

        # Step 1: Create vocabulary
        gender_vocab = Vocabulary.create(
            {
                "name": "Gender (ISO 5218)",
                "namespace_uri": "urn:iso:std:iso:5218-workflow",
                "domain": "core",
                "description": "ISO 5218 standard codes for sex",
            }
        )

        self.assertTrue(gender_vocab.id)
        self.assertEqual(gender_vocab.domain, "core")

        # Step 2: Create standard codes
        code_male = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "1",
                "display": "Male",
                "definition": "Person is male",
                "sequence": 10,
            }
        )
        code_female = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "2",
                "display": "Female",
                "definition": "Person is female",
                "sequence": 20,
            }
        )
        code_not_applicable = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "9",
                "display": "Not applicable",
                "definition": "Not applicable",
                "sequence": 30,
            }
        )
        code_unknown = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "0",
                "display": "Not known",
                "definition": "Sex is not known",
                "sequence": 40,
            }
        )

        # Verify URIs are computed
        self.assertEqual(code_male.uri, "urn:iso:std:iso:5218-workflow#1")
        self.assertEqual(code_female.uri, "urn:iso:std:iso:5218-workflow#2")

        # Step 3: Create deployment profile
        profile_ph = DeploymentProfile.create(
            {
                "name": "Philippines 4Ps",
                "description": "Philippines Pantawid Pamilyang Pilipino Program",
            }
        )

        self.assertTrue(profile_ph.id)
        self.assertFalse(profile_ph.is_active)

        # Step 4: Create vocabulary selection (only male/female for conservative deployment)
        selection_ph = VocabularySelection.create(
            {
                "deployment_profile_id": profile_ph.id,
                "vocabulary_id": gender_vocab.id,
                "active_code_ids": [(6, 0, [code_male.id, code_female.id])],
            }
        )

        # Verify effective codes
        effective = selection_ph.get_effective_codes()
        self.assertEqual(len(effective), 2)
        self.assertIn(code_male, effective)
        self.assertIn(code_female, effective)
        self.assertNotIn(code_not_applicable, effective)
        self.assertNotIn(code_unknown, effective)

        # Step 5: Activate the profile
        profile_ph.action_activate()
        self.assertTrue(profile_ph.is_active)

        # Step 6: Verify get_active_domain returns correct filter
        domain = DeploymentProfile.get_active_domain("urn:iso:std:iso:5218-workflow")

        # Should filter to only male and female
        self.assertTrue(domain)
        self.assertEqual(domain[0][0], "uri")
        self.assertEqual(domain[0][1], "in")
        uri_list = domain[0][2]
        self.assertEqual(len(uri_list), 2)
        self.assertIn(code_male.uri, uri_list)
        self.assertIn(code_female.uri, uri_list)

    def test_local_code_extension_workflow(self):
        """Test workflow with local code extensions mapping to standards."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]

        # Step 1: Create standard vocabulary
        hazard_vocab = Vocabulary.create(
            {
                "name": "Hazard Types",
                "namespace_uri": "urn:openspp:vocab:hazard-workflow",
                "domain": "social_assistance",
            }
        )

        # Step 2: Create standard codes
        code_typhoon = VocabularyCode.create(
            {
                "vocabulary_id": hazard_vocab.id,
                "code": "typhoon",
                "display": "Typhoon",
            }
        )
        code_earthquake = VocabularyCode.create(
            {
                "vocabulary_id": hazard_vocab.id,
                "code": "earthquake",
                "display": "Earthquake",
            }
        )

        # Step 3: Create local vocabulary for Philippines
        hazard_vocab_ph = Vocabulary.create(
            {
                "name": "Hazard Types (Philippines)",
                "namespace_uri": "urn:gov:ph:hazard-workflow",
            }
        )

        # Step 4: Create local codes with reference mapping
        code_bagyo = VocabularyCode.create(
            {
                "vocabulary_id": hazard_vocab_ph.id,
                "code": "bagyo",
                "display": "Bagyo (Typhoon)",
                "is_local": True,
                "reference_uri": code_typhoon.uri,
                "equivalence": "equivalent",
            }
        )
        VocabularyCode.create(
            {
                "vocabulary_id": hazard_vocab_ph.id,
                "code": "lindol",
                "display": "Lindol (Earthquake)",
                "is_local": True,
                "reference_uri": code_earthquake.uri,
                "equivalence": "equivalent",
            }
        )

        # Verify local codes
        self.assertTrue(code_bagyo.is_local)
        self.assertEqual(code_bagyo.reference_uri, code_typhoon.uri)
        self.assertEqual(code_bagyo.equivalence, "equivalent")

        # Step 5: Verify alias resolution works
        resolved = VocabularyCode.resolve_alias("bagyo")
        self.assertEqual(resolved, code_bagyo)

        # Step 6: Verify resolving by standard URI finds local code
        resolved_by_ref = VocabularyCode.resolve_alias(code_typhoon.uri)
        self.assertEqual(resolved_by_ref, code_bagyo)

    def test_concept_group_workflow(self):
        """Test concept group workflow for semantic abstraction."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Step 1: Create vocabulary
        gender_vocab = Vocabulary.create(
            {
                "name": "Gender (Extended)",
                "namespace_uri": "urn:test:gender-extended-workflow",
            }
        )

        # Step 2: Create codes
        code_male = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "male",
                "display": "Male",
            }
        )
        code_female = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "female",
                "display": "Female",
            }
        )
        code_trans_woman = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "trans_woman",
                "display": "Trans Woman",
            }
        )
        code_trans_man = VocabularyCode.create(
            {
                "vocabulary_id": gender_vocab.id,
                "code": "trans_man",
                "display": "Trans Man",
            }
        )

        # Step 3: Create concept groups
        feminine_group = ConceptGroup.create(
            {
                "name": "feminine_gender_workflow",
                "label": "Feminine Gender",
                "cel_function": "is_female",
                "description": "Codes representing feminine gender identity",
                "code_ids": [(6, 0, [code_female.id, code_trans_woman.id])],
            }
        )
        masculine_group = ConceptGroup.create(
            {
                "name": "masculine_gender_workflow",
                "label": "Masculine Gender",
                "cel_function": "is_male",
                "description": "Codes representing masculine gender identity",
                "code_ids": [(6, 0, [code_male.id, code_trans_man.id])],
            }
        )

        # Step 4: Verify group membership
        self.assertTrue(feminine_group.contains(code_female))
        self.assertTrue(feminine_group.contains(code_trans_woman))
        self.assertFalse(feminine_group.contains(code_male))

        self.assertTrue(masculine_group.contains(code_male))
        self.assertTrue(masculine_group.contains(code_trans_man))
        self.assertFalse(masculine_group.contains(code_female))

        # Step 5: Verify URI list
        feminine_uris = feminine_group.get_code_uris()
        self.assertEqual(len(feminine_uris), 2)
        self.assertIn(code_female.uri, feminine_uris)
        self.assertIn(code_trans_woman.uri, feminine_uris)

    def test_inheritance_workflow(self):
        """Test vocabulary selection inheritance workflow."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]
        DeploymentProfile = self.env["spp.deployment.profile"]
        VocabularySelection = self.env["spp.vocabulary.selection"]

        # Step 1: Create vocabulary with codes
        vocab = Vocabulary.create(
            {
                "name": "Relationship Type",
                "namespace_uri": "urn:test:relationship-workflow",
            }
        )
        code_head = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "head",
                "display": "Head of Household",
            }
        )
        code_spouse = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "spouse",
                "display": "Spouse",
            }
        )
        code_child = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "child",
                "display": "Child",
            }
        )
        code_parent = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "parent",
                "display": "Parent",
            }
        )
        code_other = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "other",
                "display": "Other",
            }
        )

        # Step 2: Create base profile and selection
        base_profile = DeploymentProfile.create(
            {
                "name": "Base Profile E2E",
            }
        )
        base_selection = VocabularySelection.create(
            {
                "deployment_profile_id": base_profile.id,
                "vocabulary_id": vocab.id,
                "active_code_ids": [
                    (6, 0, [code_head.id, code_spouse.id, code_child.id, code_parent.id, code_other.id])
                ],
            }
        )

        # Verify base has all 5 codes
        base_effective = base_selection.get_effective_codes()
        self.assertEqual(len(base_effective), 5)

        # Step 3: Create child profile that inherits from base and excludes "other"
        child_profile = DeploymentProfile.create(
            {
                "name": "Child Profile E2E",
            }
        )
        child_selection = VocabularySelection.create(
            {
                "deployment_profile_id": child_profile.id,
                "vocabulary_id": vocab.id,
                "parent_selection_id": base_selection.id,
                "excluded_code_ids": [(6, 0, [code_other.id])],
            }
        )

        # Verify child has 4 codes (excluding "other")
        child_effective = child_selection.get_effective_codes()
        self.assertEqual(len(child_effective), 4)
        self.assertIn(code_head, child_effective)
        self.assertIn(code_spouse, child_effective)
        self.assertIn(code_child, child_effective)
        self.assertIn(code_parent, child_effective)
        self.assertNotIn(code_other, child_effective)

    def test_code_resolution_workflow(self):
        """Test various code resolution methods work correctly."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]

        # Create vocabulary and codes
        vocab = Vocabulary.create(
            {
                "name": "Resolution Test",
                "namespace_uri": "urn:test:resolution-workflow",
            }
        )
        code = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "TEST",
                "display": "Test Display Name",
            }
        )

        # Clear cache for fresh lookups
        self.env.registry.clear_cache()

        # Method 1: get_code() by namespace + code
        result = VocabularyCode.get_code("urn:test:resolution-workflow", "TEST")
        self.assertEqual(result, code)

        # Method 2: resolve_by_uri()
        result = VocabularyCode.resolve_by_uri(code.uri)
        self.assertEqual(result, code)

        # Method 3: resolve_alias() by code
        result = VocabularyCode.resolve_alias("TEST")
        self.assertEqual(result, code)

        # Method 4: resolve_alias() by display
        result = VocabularyCode.resolve_alias("Test Display Name")
        self.assertEqual(result, code)

        # Method 5: resolve_alias() with namespace filter
        result = VocabularyCode.resolve_alias("TEST", namespace="urn:test:resolution-workflow")
        self.assertEqual(result, code)

    def test_profile_activation_deactivates_others(self):
        """Test that activating a profile deactivates others."""
        DeploymentProfile = self.env["spp.deployment.profile"]

        # Create first active profile
        profile1 = DeploymentProfile.create(
            {
                "name": "Profile 1",
                "is_active": True,
            }
        )
        self.assertTrue(profile1.is_active)

        # Create and activate second profile
        profile2 = DeploymentProfile.create(
            {
                "name": "Profile 2",
                "is_active": False,
            }
        )
        profile2.action_activate()

        # Verify profile2 is active and profile1 is deactivated
        self.assertTrue(profile2.is_active)
        self.assertFalse(profile1.is_active)

        # Activate profile1 again
        profile1.action_activate()
        self.assertTrue(profile1.is_active)
        self.assertFalse(profile2.is_active)

    def test_hierarchical_vocabulary_workflow(self):
        """Test hierarchical vocabulary codes workflow."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]

        # Create hierarchical vocabulary
        vocab = Vocabulary.create(
            {
                "name": "Location (Hierarchical)",
                "namespace_uri": "urn:test:location-hierarchy-workflow",
                "is_hierarchical": True,
            }
        )

        # Create hierarchy: Country > Region > Province > Municipality
        code_country = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "PH",
                "display": "Philippines",
            }
        )
        code_region = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "R04A",
                "display": "CALABARZON",
                "parent_id": code_country.id,
            }
        )
        code_province = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "LAG",
                "display": "Laguna",
                "parent_id": code_region.id,
            }
        )
        code_municipality = VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "CAL",
                "display": "Calamba",
                "parent_id": code_province.id,
            }
        )

        # Verify hierarchy levels
        self.assertEqual(code_country.level, 0)
        self.assertEqual(code_region.level, 1)
        self.assertEqual(code_province.level, 2)
        self.assertEqual(code_municipality.level, 3)

        # Verify parent-child relationships
        self.assertEqual(code_region.parent_id, code_country)
        self.assertIn(code_region, code_country.child_ids)
        self.assertEqual(code_province.parent_id, code_region)
        self.assertIn(code_municipality, code_province.child_ids)

    def test_concept_group_with_local_codes(self):
        """Test concept group membership with local code reference mapping."""
        Vocabulary = self.env["spp.vocabulary"]
        VocabularyCode = self.env["spp.vocabulary.code"]
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Create standard vocabulary
        std_vocab = Vocabulary.create(
            {
                "name": "Gender Standard",
                "namespace_uri": "urn:std:gender-workflow",
            }
        )
        std_female = VocabularyCode.create(
            {
                "vocabulary_id": std_vocab.id,
                "code": "female",
                "display": "Female",
            }
        )

        # Create local vocabulary
        local_vocab = Vocabulary.create(
            {
                "name": "Gender Local",
                "namespace_uri": "urn:local:gender-workflow",
            }
        )
        local_babae = VocabularyCode.create(
            {
                "vocabulary_id": local_vocab.id,
                "code": "babae",
                "display": "Babae (Female)",
                "is_local": True,
                "reference_uri": std_female.uri,
                "equivalence": "equivalent",
            }
        )

        # Create concept group with standard code
        feminine_group = ConceptGroup.create(
            {
                "name": "feminine_local_test",
                "label": "Feminine Gender",
                "code_ids": [(6, 0, [std_female.id])],
            }
        )

        # Verify standard code is in group
        self.assertTrue(feminine_group.contains(std_female))

        # Verify local code is also in group via reference_uri mapping
        self.assertTrue(feminine_group.contains(local_babae))

    def test_empty_profile_returns_all_codes(self):
        """Test that no active profile returns all codes (empty domain)."""
        DeploymentProfile = self.env["spp.deployment.profile"]

        # Ensure no active profiles
        DeploymentProfile.search([("is_active", "=", True)]).write({"is_active": False})

        # Get domain for any vocabulary
        domain = DeploymentProfile.get_active_domain("urn:any:namespace")

        # Should return empty domain (no filtering)
        self.assertEqual(domain, [])

    def test_profile_without_selection_returns_all_codes(self):
        """Test that profile without selection for a vocab returns all codes."""
        Vocabulary = self.env["spp.vocabulary"]
        DeploymentProfile = self.env["spp.deployment.profile"]

        # Create vocabulary
        Vocabulary.create(
            {
                "name": "Unselected Vocab",
                "namespace_uri": "urn:test:unselected-workflow",
            }
        )

        # Create active profile but don't add selection for this vocab
        DeploymentProfile.create(
            {
                "name": "Profile Without Selection",
                "is_active": True,
            }
        )

        # Get domain - should return empty (no filtering)
        domain = DeploymentProfile.get_active_domain("urn:test:unselected-workflow")
        self.assertEqual(domain, [])
