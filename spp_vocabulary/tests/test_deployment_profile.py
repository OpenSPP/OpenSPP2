from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDeploymentProfile(TransactionCase):
    """Test the spp.deployment.profile and spp.vocabulary.selection models"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DeploymentProfile = cls.env["spp.deployment.profile"]
        cls.VocabularySelection = cls.env["spp.vocabulary.selection"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Create test vocabulary
        cls.gender_vocab = cls.Vocabulary.create(
            {
                "name": "Gender Test",
                "namespace_uri": "urn:test:gender-profile",
            }
        )

        # Create test codes
        cls.code_male = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.gender_vocab.id,
                "code": "male",
                "display": "Male",
            }
        )
        cls.code_female = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.gender_vocab.id,
                "code": "female",
                "display": "Female",
            }
        )
        cls.code_nonbinary = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.gender_vocab.id,
                "code": "nonbinary",
                "display": "Non-Binary",
            }
        )
        cls.code_other = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.gender_vocab.id,
                "code": "other",
                "display": "Other",
            }
        )

    def test_create_deployment_profile(self):
        """Test creating a deployment profile"""
        profile = self.DeploymentProfile.create(
            {
                "name": "Test Profile",
                "description": "Test profile description",
            }
        )

        self.assertEqual(profile.name, "Test Profile")
        self.assertEqual(profile.description, "Test profile description")
        self.assertFalse(profile.is_active)
        self.assertTrue(profile.active)
        self.assertEqual(profile.vocabulary_count, 0)
        self.assertEqual(profile.total_code_count, 0)

    def test_single_active_profile_constraint(self):
        """Test that only one profile can be active at a time"""
        profile1 = self.DeploymentProfile.create(
            {
                "name": "Profile 1",
                "is_active": True,
            }
        )
        self.assertTrue(profile1.is_active)

        # Try to create another active profile
        with self.assertRaises(ValidationError):
            self.DeploymentProfile.create(
                {
                    "name": "Profile 2",
                    "is_active": True,
                }
            )

    def test_single_active_profile_per_company(self):
        """Test that one profile can be active per company"""
        # First deactivate any existing active profiles without company
        existing_active = self.DeploymentProfile.search(
            [
                ("is_active", "=", True),
                ("company_id", "=", False),
            ]
        )
        existing_active.write({"is_active": False})

        # Create first active profile without company
        profile1 = self.DeploymentProfile.create(
            {
                "name": "Profile Global 1",
                "is_active": True,
            }
        )
        self.assertTrue(profile1.is_active)

        # Should not be able to create another active global profile
        with self.assertRaises(ValidationError):
            self.DeploymentProfile.create(
                {
                    "name": "Profile Global 2",
                    "is_active": True,
                }
            )

        # But can create an inactive profile
        profile2 = self.DeploymentProfile.create(
            {
                "name": "Profile Global 2",
                "is_active": False,
            }
        )
        self.assertFalse(profile2.is_active)

    def test_action_activate(self):
        """Test activating a profile"""
        profile1 = self.DeploymentProfile.create(
            {
                "name": "Profile 1",
                "is_active": True,
            }
        )
        profile2 = self.DeploymentProfile.create(
            {
                "name": "Profile 2",
                "is_active": False,
            }
        )

        # Activate profile 2
        result = profile2.action_activate()

        # Profile 1 should be deactivated
        self.assertFalse(profile1.is_active)
        # Profile 2 should be activated
        self.assertTrue(profile2.is_active)
        # Should return notification
        self.assertEqual(result["type"], "ir.actions.client")

    def test_get_active_profile(self):
        """Test getting the active profile"""
        # No active profile initially
        profile = self.DeploymentProfile.get_active_profile()
        self.assertFalse(profile)

        # Create active profile
        active_profile = self.DeploymentProfile.create(
            {
                "name": "Active Profile",
                "is_active": True,
            }
        )

        # Should return active profile
        profile = self.DeploymentProfile.get_active_profile()
        self.assertEqual(profile, active_profile)

    def test_create_vocabulary_selection(self):
        """Test creating a vocabulary selection"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
                "active_code_ids": [(6, 0, [self.code_male.id, self.code_female.id])],
            }
        )

        self.assertEqual(selection.deployment_profile_id, profile)
        self.assertEqual(selection.vocabulary_id, self.gender_vocab)
        self.assertEqual(len(selection.active_code_ids), 2)
        self.assertIn(self.code_male, selection.active_code_ids)
        self.assertIn(self.code_female, selection.active_code_ids)

    def test_unique_profile_vocabulary_constraint(self):
        """Test that each vocabulary can only have one selection per profile"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
            }
        )

        # Try to create duplicate - can raise ValidationError or IntegrityError (from SQL constraint)
        with self.assertRaises(Exception) as ctx:
            self.VocabularySelection.create(
                {
                    "deployment_profile_id": profile.id,
                    "vocabulary_id": self.gender_vocab.id,
                }
            )

        # Verify it's a uniqueness/constraint error
        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            any(x in error_msg for x in ["unique", "duplicate", "constraint", "already exists"]),
            f"Expected uniqueness constraint error, got: {ctx.exception}",
        )

    def test_effective_codes_without_parent(self):
        """Test effective codes calculation without parent"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
                "active_code_ids": [(6, 0, [self.code_male.id, self.code_female.id])],
            }
        )

        effective = selection.get_effective_codes()
        self.assertEqual(len(effective), 2)
        self.assertIn(self.code_male, effective)
        self.assertIn(self.code_female, effective)
        self.assertEqual(selection.effective_code_count, 2)

    def test_effective_codes_with_parent(self):
        """Test effective codes calculation with parent inheritance"""
        # Parent profile with base selection
        parent_profile = self.DeploymentProfile.create({"name": "Parent Profile"})
        # Child profile that inherits
        child_profile = self.DeploymentProfile.create({"name": "Child Profile"})

        # Create vocabulary for testing
        vocab = self.Vocabulary.create(
            {
                "name": "Gender Test 2",
                "namespace_uri": "urn:test:gender-profile-2",
            }
        )
        code_male = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "male",
                "display": "Male",
            }
        )
        code_female = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "female",
                "display": "Female",
            }
        )
        code_nonbinary = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "nonbinary",
                "display": "Non-Binary",
            }
        )

        # Parent selection with male and female in parent profile
        parent_selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": parent_profile.id,
                "vocabulary_id": vocab.id,
                "active_code_ids": [(6, 0, [code_male.id, code_female.id])],
            }
        )

        # Child selection in child profile adds nonbinary, inherits from parent
        child_selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": child_profile.id,
                "vocabulary_id": vocab.id,
                "parent_selection_id": parent_selection.id,
                "active_code_ids": [(6, 0, [code_nonbinary.id])],
            }
        )

        # Effective codes should include parent codes + child codes
        effective = child_selection.get_effective_codes()
        self.assertEqual(len(effective), 3)
        self.assertIn(code_male, effective)
        self.assertIn(code_female, effective)
        self.assertIn(code_nonbinary, effective)

    def test_effective_codes_with_exclusions(self):
        """Test effective codes calculation with exclusions from parent"""
        # Parent profile with base selection
        parent_profile = self.DeploymentProfile.create({"name": "Parent Profile Exclusions"})
        # Child profile that inherits and excludes
        child_profile = self.DeploymentProfile.create({"name": "Child Profile Exclusions"})

        # Create vocabulary
        vocab = self.Vocabulary.create(
            {
                "name": "Gender Test 3",
                "namespace_uri": "urn:test:gender-profile-3",
            }
        )
        code_male = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "male",
                "display": "Male",
            }
        )
        code_female = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "female",
                "display": "Female",
            }
        )
        code_other = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "other",
                "display": "Other",
            }
        )

        # Parent selection with male, female, other in parent profile
        parent_selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": parent_profile.id,
                "vocabulary_id": vocab.id,
                "active_code_ids": [(6, 0, [code_male.id, code_female.id, code_other.id])],
            }
        )

        # Child selection in child profile excludes 'other'
        child_selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": child_profile.id,
                "vocabulary_id": vocab.id,
                "parent_selection_id": parent_selection.id,
                "excluded_code_ids": [(6, 0, [code_other.id])],
            }
        )

        # Effective codes should only have male and female
        effective = child_selection.get_effective_codes()
        self.assertEqual(len(effective), 2)
        self.assertIn(code_male, effective)
        self.assertIn(code_female, effective)
        self.assertNotIn(code_other, effective)

    def test_parent_recursion_check(self):
        """Test that circular parent relationships are prevented"""
        # Use different profiles for each selection (same vocab, different profiles)
        profile1 = self.DeploymentProfile.create({"name": "Profile 1 Recursion"})
        profile2 = self.DeploymentProfile.create({"name": "Profile 2 Recursion"})
        profile3 = self.DeploymentProfile.create({"name": "Profile 3 Recursion"})

        vocab = self.Vocabulary.create(
            {
                "name": "Vocab Recursion",
                "namespace_uri": "urn:test:vocab-recursion",
            }
        )

        # Create a chain: selection1 <- selection2 <- selection3
        selection1 = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile1.id,
                "vocabulary_id": vocab.id,
            }
        )
        selection2 = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile2.id,
                "vocabulary_id": vocab.id,
                "parent_selection_id": selection1.id,
            }
        )
        selection3 = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile3.id,
                "vocabulary_id": vocab.id,
                "parent_selection_id": selection2.id,
            }
        )

        # Try to create circular reference (selection1 -> selection3 would create cycle)
        with self.assertRaises(ValidationError):
            selection1.write({"parent_selection_id": selection3.id})

    def test_parent_same_vocabulary_check(self):
        """Test that parent selection must be for same vocabulary"""
        # Use different profiles to avoid unique constraint
        parent_profile = self.DeploymentProfile.create({"name": "Parent Profile Same Vocab"})
        child_profile = self.DeploymentProfile.create({"name": "Child Profile Same Vocab"})

        vocab1 = self.Vocabulary.create(
            {
                "name": "Vocab 1",
                "namespace_uri": "urn:test:vocab-parent-1",
            }
        )
        vocab2 = self.Vocabulary.create(
            {
                "name": "Vocab 2",
                "namespace_uri": "urn:test:vocab-parent-2",
            }
        )

        selection1 = self.VocabularySelection.create(
            {
                "deployment_profile_id": parent_profile.id,
                "vocabulary_id": vocab1.id,
            }
        )

        # Try to create selection with parent from different vocabulary
        with self.assertRaises(ValidationError):
            self.VocabularySelection.create(
                {
                    "deployment_profile_id": child_profile.id,
                    "vocabulary_id": vocab2.id,
                    "parent_selection_id": selection1.id,
                }
            )

    def test_get_active_domain(self):
        """Test getting active domain for vocabulary codes"""
        profile = self.DeploymentProfile.create(
            {
                "name": "Test Profile",
                "is_active": True,
            }
        )

        self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
                "active_code_ids": [(6, 0, [self.code_male.id, self.code_female.id])],
            }
        )

        # Get domain for gender vocabulary
        domain = self.DeploymentProfile.get_active_domain("urn:test:gender-profile")

        # Should return domain filtering by URIs
        self.assertTrue(domain)
        self.assertEqual(domain[0][0], "uri")
        self.assertEqual(domain[0][1], "in")
        self.assertEqual(len(domain[0][2]), 2)

    def test_get_active_domain_no_profile(self):
        """Test getting domain when no profile is active"""
        # Ensure no active profile
        self.DeploymentProfile.search([("is_active", "=", True)]).write({"is_active": False})

        # Should return empty domain
        domain = self.DeploymentProfile.get_active_domain("urn:test:gender-profile")
        self.assertEqual(domain, [])

    def test_get_active_domain_no_selection(self):
        """Test getting domain when profile has no selection for vocabulary"""
        self.DeploymentProfile.create(
            {
                "name": "Test Profile",
                "is_active": True,
            }
        )

        # No selection for this vocabulary
        domain = self.DeploymentProfile.get_active_domain("urn:test:gender-profile")
        self.assertEqual(domain, [])

    def test_action_add_all_codes(self):
        """Test adding all codes to a selection"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
            }
        )

        # Initially no codes
        self.assertEqual(len(selection.active_code_ids), 0)

        # Add all codes
        selection.action_add_all_codes()

        # Should have all 4 codes
        self.assertEqual(len(selection.active_code_ids), 4)
        self.assertIn(self.code_male, selection.active_code_ids)
        self.assertIn(self.code_female, selection.active_code_ids)
        self.assertIn(self.code_nonbinary, selection.active_code_ids)
        self.assertIn(self.code_other, selection.active_code_ids)

    def test_action_clear_codes(self):
        """Test clearing all codes from a selection"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
                "active_code_ids": [(6, 0, [self.code_male.id, self.code_female.id])],
            }
        )

        # Initially has 2 codes
        self.assertEqual(len(selection.active_code_ids), 2)

        # Clear codes
        selection.action_clear_codes()

        # Should have no codes
        self.assertEqual(len(selection.active_code_ids), 0)

    def test_vocabulary_count_computed(self):
        """Test that vocabulary_count is computed correctly"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        # Initially no vocabularies
        self.assertEqual(profile.vocabulary_count, 0)

        # Add one selection
        vocab1 = self.Vocabulary.create(
            {
                "name": "Vocab 1",
                "namespace_uri": "urn:test:count-1",
            }
        )
        self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": vocab1.id,
            }
        )
        self.assertEqual(profile.vocabulary_count, 1)

        # Add another selection
        vocab2 = self.Vocabulary.create(
            {
                "name": "Vocab 2",
                "namespace_uri": "urn:test:count-2",
            }
        )
        self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": vocab2.id,
            }
        )
        self.assertEqual(profile.vocabulary_count, 2)

    def test_total_code_count_computed(self):
        """Test that total_code_count is computed correctly"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        # Create vocabulary 1 with 2 codes
        vocab1 = self.Vocabulary.create(
            {
                "name": "Vocab 1",
                "namespace_uri": "urn:test:total-1",
            }
        )
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab1.id,
                "code": "code1",
                "display": "Code 1",
            }
        )
        code2 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab1.id,
                "code": "code2",
                "display": "Code 2",
            }
        )

        self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": vocab1.id,
                "active_code_ids": [(6, 0, [code1.id, code2.id])],
            }
        )

        # Should have 2 codes
        self.assertEqual(profile.total_code_count, 2)

        # Create vocabulary 2 with 3 codes
        vocab2 = self.Vocabulary.create(
            {
                "name": "Vocab 2",
                "namespace_uri": "urn:test:total-2",
            }
        )
        code3 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab2.id,
                "code": "code3",
                "display": "Code 3",
            }
        )
        code4 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab2.id,
                "code": "code4",
                "display": "Code 4",
            }
        )
        code5 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab2.id,
                "code": "code5",
                "display": "Code 5",
            }
        )

        self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": vocab2.id,
                "active_code_ids": [(6, 0, [code3.id, code4.id, code5.id])],
            }
        )

        # Should have 5 total codes
        self.assertEqual(profile.total_code_count, 5)

    def test_selection_name_get(self):
        """Test name_get for vocabulary selection"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        selection = self.VocabularySelection.create(
            {
                "deployment_profile_id": profile.id,
                "vocabulary_id": self.gender_vocab.id,
            }
        )

        name = selection.name_get()[0][1]
        self.assertIn("Test Profile", name)
        self.assertIn("Gender Test", name)
        # Verify the format is "Profile - Vocabulary"
        self.assertEqual(name, "Test Profile - Gender Test")

    def test_selection_name_get_new_record(self):
        """Test name_get for new (unsaved) vocabulary selection"""
        # Create a new record without saving it
        new_selection = self.VocabularySelection.new(
            {
                "deployment_profile_id": self.DeploymentProfile.create({"name": "New Profile"}).id,
                "vocabulary_id": self.gender_vocab.id,
            }
        )

        name = new_selection.name_get()[0][1]
        self.assertEqual(name, "New Vocabulary Selection")

    def test_action_view_vocabulary_selections(self):
        """Test action to view vocabulary selections"""
        profile = self.DeploymentProfile.create({"name": "Test Profile"})

        action = profile.action_view_vocabulary_selections()

        # Verify action structure
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.vocabulary.selection")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["domain"], [("deployment_profile_id", "=", profile.id)])
        self.assertIn(profile.name, action["name"])
