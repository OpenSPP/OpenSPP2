from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestVocabulary(TransactionCase):
    """Test the spp.vocabulary model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

    def test_create_vocabulary(self):
        """Test creating a vocabulary and verify all fields are set correctly"""
        vocab = self.Vocabulary.create(
            {
                "name": "Test Gender Vocabulary",
                "namespace_uri": "urn:test:vocab:gender",
                "version": "2024",
                "description": "Test vocabulary for gender codes",
                "reference_url": "https://example.com/gender",
                "is_system": True,
                "is_hierarchical": False,
                "domain": "core",
            }
        )

        self.assertEqual(vocab.name, "Test Gender Vocabulary")
        self.assertEqual(vocab.namespace_uri, "urn:test:vocab:gender")
        self.assertEqual(vocab.version, "2024")
        self.assertEqual(vocab.description, "Test vocabulary for gender codes")
        self.assertEqual(vocab.reference_url, "https://example.com/gender")
        self.assertTrue(vocab.is_system)
        self.assertFalse(vocab.is_hierarchical)
        self.assertEqual(vocab.domain, "core")
        self.assertTrue(vocab.active)

    def test_namespace_unique_constraint(self):
        """Test that namespace_uri must be unique"""
        # Use a unique namespace URI to avoid conflicts with other tests
        import uuid

        unique_namespace = f"urn:test:unique_{uuid.uuid4().hex[:8]}"

        # Delete any existing vocabulary with this namespace_uri (shouldn't exist, but be safe)
        existing = self.Vocabulary.search([("namespace_uri", "=", unique_namespace)])
        if existing:
            existing.unlink()

        # Create first vocabulary
        self.Vocabulary.create(
            {
                "name": "First Vocabulary",
                "namespace_uri": unique_namespace,
            }
        )

        # Try to create second vocabulary with same namespace_uri
        with self.assertRaises(ValidationError):
            self.Vocabulary.create(
                {
                    "name": "Second Vocabulary",
                    "namespace_uri": unique_namespace,
                }
            )

    def test_code_count_computed(self):
        """Test that code_count is computed correctly"""
        vocab = self.Vocabulary.create(
            {
                "name": "Test Vocabulary",
                "namespace_uri": "urn:test:code-count",
            }
        )

        # Initially no codes
        self.assertEqual(vocab.code_count, 0)

        # Add one code
        self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "code1",
                "display": "Code 1",
            }
        )
        self.assertEqual(vocab.code_count, 1)

        # Add another code
        self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "code2",
                "display": "Code 2",
            }
        )
        self.assertEqual(vocab.code_count, 2)

        # Add a third code
        self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "code3",
                "display": "Code 3",
            }
        )
        self.assertEqual(vocab.code_count, 3)

    def test_action_view_codes(self):
        """Test that action_view_codes returns proper domain and context"""
        vocab = self.Vocabulary.create(
            {
                "name": "Test Vocabulary",
                "namespace_uri": "urn:test:action",
            }
        )

        # Create some codes
        code1 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "test1",
                "display": "Test 1",
            }
        )
        code2 = self.VocabularyCode.create(
            {
                "vocabulary_id": vocab.id,
                "code": "test2",
                "display": "Test 2",
            }
        )

        action = vocab.action_view_codes()

        # Verify action structure
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.vocabulary.code")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["domain"], [("vocabulary_id", "=", vocab.id)])
        self.assertEqual(action["context"], {"default_vocabulary_id": vocab.id})
        self.assertIn(vocab.name, action["name"])

        # Verify the domain filters correctly
        codes = self.VocabularyCode.search(action["domain"])
        self.assertEqual(len(codes), 2)
        self.assertIn(code1, codes)
        self.assertIn(code2, codes)

    def test_vocabulary_default_values(self):
        """Test that default values are set correctly"""
        vocab = self.Vocabulary.create(
            {
                "name": "Test Defaults",
                "namespace_uri": "urn:test:defaults",
            }
        )

        self.assertFalse(vocab.is_system)
        self.assertFalse(vocab.is_hierarchical)
        self.assertEqual(vocab.domain, "core")
        self.assertTrue(vocab.active)

    def test_vocabulary_domain_options(self):
        """Test that all domain options can be set"""
        domains = [
            "core",
            "social_assistance",
            "social_insurance",
            "labor",
            "disability",
            "agriculture",
            "health",
            "education",
        ]

        for domain in domains:
            vocab = self.Vocabulary.create(
                {
                    "name": f"Test {domain}",
                    "namespace_uri": f"urn:test:{domain}",
                    "domain": domain,
                }
            )
            self.assertEqual(vocab.domain, domain)

    def test_vocabulary_hierarchical_setting(self):
        """Test is_hierarchical flag"""
        vocab = self.Vocabulary.create(
            {
                "name": "Hierarchical Vocabulary",
                "namespace_uri": "urn:test:hierarchical",
                "is_hierarchical": True,
            }
        )
        self.assertTrue(vocab.is_hierarchical)

    def test_vocabulary_inactive(self):
        """Test that vocabulary can be set inactive"""
        vocab = self.Vocabulary.create(
            {
                "name": "Test Inactive",
                "namespace_uri": "urn:test:inactive",
                "active": False,
            }
        )
        self.assertFalse(vocab.active)

        # Verify it's not found in default search
        found = self.Vocabulary.search([("namespace_uri", "=", "urn:test:inactive")])
        self.assertFalse(found)

        # Verify it's found when searching without active_test
        found = self.Vocabulary.with_context(active_test=False).search([("namespace_uri", "=", "urn:test:inactive")])
        self.assertEqual(found, vocab)
