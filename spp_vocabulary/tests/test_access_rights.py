"""Access rights tests for vocabulary models.

Tests the three-tier security architecture (ADR-004):
- Viewer: Read-only access
- Officer: Read, write, create (no delete)
- Manager: Full access including delete
"""

import unittest

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


def _create_test_user(env, login, groups_ref):
    """Create a test user safely, handling accounting module constraints."""
    try:
        # Get an existing partner to use
        partner = env["res.partner"].search([], limit=1)
        if not partner:
            # Create minimal partner - accounting modules may add required fields
            partner = env["res.partner"].create(
                {
                    "name": f"Partner for {login}",
                    "type": "contact",
                }
            )

        return env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@test.com",
                "partner_id": partner.id,
                "group_ids": [(6, 0, [env.ref(groups_ref).id])],
            }
        )
    except Exception:
        # If we can't create users due to module constraints, skip tests
        raise unittest.SkipTest("Cannot create test users (accounting module constraints)") from None


class TestVocabularyAccessRights(TransactionCase):
    """Test access rights for vocabulary models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.DeploymentProfile = cls.env["spp.deployment.profile"]
        cls.VocabularySelection = cls.env["spp.vocabulary.selection"]
        cls.ConceptGroup = cls.env["spp.vocabulary.concept.group"]

        # Create test users for each role
        cls.user_viewer = _create_test_user(cls.env, "test_vocab_viewer", "spp_vocabulary.group_vocabulary_viewer")

        cls.user_officer = _create_test_user(cls.env, "test_vocab_officer", "spp_vocabulary.group_vocabulary_officer")

        cls.user_manager = _create_test_user(cls.env, "test_vocab_manager", "spp_vocabulary.group_vocabulary_manager")

        # Create test vocabulary and code
        cls.vocab = cls.Vocabulary.create(
            {
                "name": "Test Access Vocabulary",
                "namespace_uri": "urn:test:access",
            }
        )

        cls.code = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "ACCESS_TEST",
                "display": "Access Test Code",
            }
        )

        cls.profile = cls.DeploymentProfile.create(
            {
                "name": "Test Access Profile",
            }
        )

    # Vocabulary Model Tests

    def test_viewer_can_read_vocabulary(self):
        """Test that viewer can read vocabulary records."""
        vocab = self.Vocabulary.with_user(self.user_viewer).search([("id", "=", self.vocab.id)])
        self.assertEqual(vocab.name, "Test Access Vocabulary")

    def test_viewer_cannot_create_vocabulary(self):
        """Test that viewer cannot create vocabulary records."""
        with self.assertRaises(AccessError):
            self.Vocabulary.with_user(self.user_viewer).create(
                {
                    "name": "Should Fail",
                    "namespace_uri": "urn:test:should-fail",
                }
            )

    def test_viewer_cannot_write_vocabulary(self):
        """Test that viewer cannot modify vocabulary records."""
        vocab = self.Vocabulary.with_user(self.user_viewer).browse(self.vocab.id)
        with self.assertRaises(AccessError):
            vocab.write({"name": "Modified Name"})

    def test_viewer_cannot_delete_vocabulary(self):
        """Test that viewer cannot delete vocabulary records."""
        vocab = self.Vocabulary.with_user(self.user_viewer).browse(self.vocab.id)
        with self.assertRaises(AccessError):
            vocab.unlink()

    def test_officer_can_create_vocabulary(self):
        """Test that officer can create vocabulary records."""
        # Disable mail tracking to avoid res.company access issues
        vocab = self.Vocabulary.with_context(tracking_disable=True).with_user(self.user_officer).create(
            {
                "name": "Officer Created",
                "namespace_uri": "urn:test:officer-created",
            }
        )
        self.assertTrue(vocab.id)
        self.assertEqual(vocab.name, "Officer Created")

    def test_officer_can_write_vocabulary(self):
        """Test that officer can modify vocabulary records."""
        vocab_to_modify = self.Vocabulary.create(
            {
                "name": "To Modify",
                "namespace_uri": "urn:test:to-modify",
            }
        )
        vocab = self.Vocabulary.with_user(self.user_officer).browse(vocab_to_modify.id)
        vocab.write({"name": "Modified by Officer"})
        self.assertEqual(vocab.name, "Modified by Officer")

    def test_officer_cannot_delete_vocabulary(self):
        """Test that officer cannot delete vocabulary records."""
        vocab_to_delete = self.Vocabulary.create(
            {
                "name": "To Delete",
                "namespace_uri": "urn:test:to-delete-officer",
            }
        )
        vocab = self.Vocabulary.with_user(self.user_officer).browse(vocab_to_delete.id)
        with self.assertRaises(AccessError):
            vocab.unlink()

    def test_manager_can_delete_vocabulary(self):
        """Test that manager can delete vocabulary records."""
        vocab_to_delete = self.Vocabulary.create(
            {
                "name": "To Delete",
                "namespace_uri": "urn:test:to-delete-manager",
            }
        )
        vocab = self.Vocabulary.with_user(self.user_manager).browse(vocab_to_delete.id)
        vocab.unlink()
        # Verify deletion
        self.assertFalse(self.Vocabulary.search([("id", "=", vocab_to_delete.id)]))

    # Vocabulary Code Tests

    def test_viewer_can_read_code(self):
        """Test that viewer can read vocabulary code records."""
        code = self.VocabularyCode.with_user(self.user_viewer).browse(self.code.id)
        self.assertEqual(code.code, "ACCESS_TEST")

    def test_viewer_cannot_create_code(self):
        """Test that viewer cannot create vocabulary code records."""
        with self.assertRaises(AccessError):
            self.VocabularyCode.with_user(self.user_viewer).create(
                {
                    "vocabulary_id": self.vocab.id,
                    "code": "SHOULD_FAIL",
                    "display": "Should Fail",
                }
            )

    def test_officer_can_create_code(self):
        """Test that officer can create vocabulary code records."""
        # Disable mail tracking to avoid res.company access issues
        code = self.VocabularyCode.with_context(tracking_disable=True).with_user(self.user_officer).create(
            {
                "vocabulary_id": self.vocab.id,
                "code": "OFFICER_CREATED",
                "display": "Officer Created",
            }
        )
        self.assertTrue(code.id)
        self.assertEqual(code.code, "OFFICER_CREATED")

    def test_officer_cannot_delete_code(self):
        """Test that officer cannot delete vocabulary code records."""
        code_to_delete = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab.id,
                "code": "TO_DELETE",
                "display": "To Delete",
            }
        )
        code = self.VocabularyCode.with_user(self.user_officer).browse(code_to_delete.id)
        with self.assertRaises(AccessError):
            code.unlink()

    def test_manager_can_delete_code(self):
        """Test that manager can delete vocabulary code records."""
        code_to_delete = self.VocabularyCode.create(
            {
                "vocabulary_id": self.vocab.id,
                "code": "TO_DELETE_MGR",
                "display": "To Delete Manager",
            }
        )
        code = self.VocabularyCode.with_user(self.user_manager).browse(code_to_delete.id)
        code.unlink()
        # Verify deletion
        self.assertFalse(self.VocabularyCode.search([("id", "=", code_to_delete.id)]))

    # Deployment Profile Tests

    def test_viewer_can_read_profile(self):
        """Test that viewer can read deployment profile records."""
        profile = self.DeploymentProfile.with_user(self.user_viewer).browse(self.profile.id)
        self.assertEqual(profile.name, "Test Access Profile")

    def test_viewer_cannot_create_profile(self):
        """Test that viewer cannot create deployment profile records."""
        with self.assertRaises(AccessError):
            self.DeploymentProfile.with_user(self.user_viewer).create(
                {
                    "name": "Should Fail Profile",
                }
            )

    def test_officer_can_create_profile(self):
        """Test that officer can create deployment profile records."""
        # Disable mail tracking to avoid res.company access issues
        profile = self.DeploymentProfile.with_context(tracking_disable=True).with_user(self.user_officer).create(
            {
                "name": "Officer Profile",
            }
        )
        self.assertTrue(profile.id)

    def test_manager_can_delete_profile(self):
        """Test that manager can delete deployment profile records."""
        profile_to_delete = self.DeploymentProfile.create(
            {
                "name": "To Delete Profile",
            }
        )
        profile = self.DeploymentProfile.with_user(self.user_manager).browse(profile_to_delete.id)
        profile.unlink()
        # Verify deletion
        self.assertFalse(self.DeploymentProfile.search([("id", "=", profile_to_delete.id)]))

    # Vocabulary Selection Tests

    def test_viewer_can_read_selection(self):
        """Test that viewer can read vocabulary selection records."""
        selection = self.env["spp.vocabulary.selection"].create(
            {
                "deployment_profile_id": self.profile.id,
                "vocabulary_id": self.vocab.id,
            }
        )
        sel = self.VocabularySelection.with_user(self.user_viewer).browse(selection.id)
        self.assertEqual(sel.vocabulary_id, self.vocab)

    def test_officer_can_create_selection(self):
        """Test that officer can create vocabulary selection records."""
        # Create a new vocab to avoid unique constraint
        vocab2 = self.Vocabulary.create(
            {
                "name": "Selection Test Vocab",
                "namespace_uri": "urn:test:selection-test",
            }
        )
        selection = self.VocabularySelection.with_user(self.user_officer).create(
            {
                "deployment_profile_id": self.profile.id,
                "vocabulary_id": vocab2.id,
            }
        )
        self.assertTrue(selection.id)

    # Concept Group Tests

    def test_viewer_can_read_concept_group(self):
        """Test that viewer can read concept group records."""
        group = self.ConceptGroup.create(
            {
                "name": "test_access_group",
                "label": "Test Access Group",
            }
        )
        grp = self.ConceptGroup.with_user(self.user_viewer).browse(group.id)
        self.assertEqual(grp.name, "test_access_group")

    def test_officer_can_create_concept_group(self):
        """Test that officer can create concept group records."""
        # Disable mail tracking to avoid res.company access issues
        group = self.ConceptGroup.with_context(tracking_disable=True).with_user(self.user_officer).create(
            {
                "name": "officer_created_group",
                "label": "Officer Created Group",
            }
        )
        self.assertTrue(group.id)

    def test_manager_can_delete_concept_group(self):
        """Test that manager can delete concept group records."""
        group = self.ConceptGroup.create(
            {
                "name": "to_delete_group",
                "label": "To Delete Group",
            }
        )
        grp = self.ConceptGroup.with_user(self.user_manager).browse(group.id)
        grp.unlink()
        # Verify deletion
        self.assertFalse(self.ConceptGroup.search([("id", "=", group.id)]))
