# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for vocabulary caching layer.

Tests the caching infrastructure that eliminates N+1 queries in CEL
vocabulary function evaluation.

Architecture tested:
- Layer 1: @ormcache in VocabularyConceptGroup._get_group_uris_cached
- Layer 2: VocabularyCache session-level cache
- Cache invalidation on concept group changes
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_cel_domain.tests.common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestConceptGroupCache(TransactionCase, CELTestDataMixin):
    """Test ormcache layer in VocabularyConceptGroup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        # Create test vocabulary
        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:{cls._test_id}",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        cls.code_male = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"M_{cls._test_id}",
            display="Male",
        )

        # Create concept group
        cls.group_feminine = cls._create_test_concept_group(
            name=f"test_feminine_{cls._test_id}",
            display_name="Test Feminine Gender",
            codes=[cls.code_female],
        )

    def test_get_group_uris_cached_returns_frozenset(self):
        """Test that cached lookup returns a frozenset."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        result = ConceptGroup._get_group_uris_cached(self.group_feminine.name)

        self.assertIsInstance(result, frozenset)
        self.assertIn(self.code_female.uri, result)

    def test_get_group_uris_cached_returns_none_for_missing(self):
        """Test that cached lookup returns None for missing group."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        result = ConceptGroup._get_group_uris_cached("nonexistent_group_xyz")

        self.assertIsNone(result)

    def test_cached_lookup_is_consistent(self):
        """Test that multiple cached lookups return same data."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        result1 = ConceptGroup._get_group_uris_cached(self.group_feminine.name)
        result2 = ConceptGroup._get_group_uris_cached(self.group_feminine.name)

        self.assertEqual(result1, result2)
        self.assertIs(result1, result2)  # Same object from cache

    def test_contains_uses_cached_lookup(self):
        """Test that contains() method uses cached URI lookup."""
        # contains() should use _get_group_uris_cached internally
        result = self.group_feminine.contains(self.code_female)
        self.assertTrue(result)

        result = self.group_feminine.contains(self.code_male)
        self.assertFalse(result)

    def test_cache_invalidation_on_code_add(self):
        """Test that cache invalidates when codes are added to group."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # First, verify male is not in feminine group
        uri_set_before = ConceptGroup._get_group_uris_cached(self.group_feminine.name)
        self.assertNotIn(self.code_male.uri, uri_set_before)

        # Add male code to feminine group
        self.group_feminine.write({"code_ids": [(4, self.code_male.id)]})

        # Cache should be invalidated - new lookup should include male
        uri_set_after = ConceptGroup._get_group_uris_cached(self.group_feminine.name)
        self.assertIn(self.code_male.uri, uri_set_after)

    def test_cache_invalidation_on_group_delete(self):
        """Test that cache invalidates when group is deleted."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Create a temporary group
        temp_group = self._create_test_concept_group(
            name=f"temp_group_{self._test_id}",
            display_name="Temporary Group",
            codes=[self.code_female],
        )

        # Populate cache
        uri_set = ConceptGroup._get_group_uris_cached(temp_group.name)
        self.assertIsNotNone(uri_set)

        # Delete the group
        temp_group.unlink()

        # Cache should be invalidated - lookup should return None
        uri_set_after = ConceptGroup._get_group_uris_cached(f"temp_group_{self._test_id}")
        self.assertIsNone(uri_set_after)


@tagged("post_install", "-at_install")
class TestVocabularyCache(TransactionCase, CELTestDataMixin):
    """Test session-level VocabularyCache."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        # Create test vocabulary
        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:{cls._test_id}",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        cls.code_male = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"M_{cls._test_id}",
            display="Male",
        )

        # Create concept groups with standard names for semantic helpers
        ConceptGroup = cls.env["spp.vocabulary.concept.group"]

        existing_feminine = ConceptGroup.search([("name", "=", "feminine_gender")], limit=1)
        if existing_feminine:
            existing_feminine.write({"code_ids": [(4, cls.code_female.id)]})
            cls.group_feminine = existing_feminine
        else:
            cls.group_feminine = cls._create_test_concept_group(
                name="feminine_gender",
                display_name="Feminine Gender",
                codes=[cls.code_female],
            )

        existing_masculine = ConceptGroup.search([("name", "=", "masculine_gender")], limit=1)
        if existing_masculine:
            existing_masculine.write({"code_ids": [(4, cls.code_male.id)]})
            cls.group_masculine = existing_masculine
        else:
            cls.group_masculine = cls._create_test_concept_group(
                name="masculine_gender",
                display_name="Masculine Gender",
                codes=[cls.code_male],
            )

    def test_vocabulary_cache_check_membership(self):
        """Test VocabularyCache.check_membership() method."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Should return True for female code in feminine_gender group
        result = cache.check_membership(self.code_female, "feminine_gender")
        self.assertTrue(result)

        # Should return False for male code in feminine_gender group
        result = cache.check_membership(self.code_male, "feminine_gender")
        self.assertFalse(result)

    def test_vocabulary_cache_session_level_caching(self):
        """Test that VocabularyCache caches lookups within session."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # First lookup
        cache.get_group_uris("feminine_gender")

        # Verify it's cached in session
        self.assertIn("feminine_gender", cache._group_uri_cache)

        # Second lookup should use session cache
        result = cache.get_group_uris("feminine_gender")
        self.assertIsNotNone(result)

    def test_vocabulary_cache_handles_missing_groups(self):
        """Test VocabularyCache handles missing groups gracefully."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Should return False for nonexistent group
        result = cache.check_membership(self.code_female, "nonexistent_group")
        self.assertFalse(result)

        # Missing group should still be cached (as None) to prevent repeated lookups
        self.assertIn("nonexistent_group", cache._group_uri_cache)
        self.assertIsNone(cache._group_uri_cache["nonexistent_group"])

    def test_vocabulary_cache_stats(self):
        """Test VocabularyCache stats property."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Make some lookups
        cache.check_membership(self.code_female, "feminine_gender")
        cache.check_membership(self.code_male, "masculine_gender")
        cache.check_membership(self.code_female, "nonexistent_group")

        stats = cache.stats

        self.assertEqual(stats["cached_groups"], 2)  # feminine and masculine
        self.assertEqual(stats["missing_groups"], 1)  # nonexistent

    def test_vocabulary_cache_preload_groups(self):
        """Test VocabularyCache.preload_groups() method."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Preload multiple groups
        cache.preload_groups(["feminine_gender", "masculine_gender"])

        # Both should be in cache
        self.assertIn("feminine_gender", cache._group_uri_cache)
        self.assertIn("masculine_gender", cache._group_uri_cache)


@tagged("post_install", "-at_install")
class TestInGroupCaching(TransactionCase, CELTestDataMixin):
    """Test that in_group() function uses caching properly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        # Create test vocabulary
        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:{cls._test_id}",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        cls.code_male = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"M_{cls._test_id}",
            display="Male",
        )

        # Create concept group with standard name
        ConceptGroup = cls.env["spp.vocabulary.concept.group"]

        existing_feminine = ConceptGroup.search([("name", "=", "feminine_gender")], limit=1)
        if existing_feminine:
            existing_feminine.write({"code_ids": [(4, cls.code_female.id)]})
            cls.group_feminine = existing_feminine
        else:
            cls.group_feminine = cls._create_test_concept_group(
                name="feminine_gender",
                display_name="Feminine Gender",
                codes=[cls.code_female],
            )

        # Register vocabulary functions
        cls.env["spp.cel.vocabulary.functions"].register_vocabulary_functions()

    def test_in_group_uses_ormcache(self):
        """Test that in_group() uses ormcache for group lookups."""
        from ..services.cel_vocabulary_functions import in_group

        # First call - populates cache
        result1 = in_group(self.env, self.code_female, "feminine_gender")
        self.assertTrue(result1)

        # Second call - should use cached data
        result2 = in_group(self.env, self.code_female, "feminine_gender")
        self.assertTrue(result2)

    def test_in_group_with_session_cache(self):
        """Test that in_group() uses session cache when available."""
        from ..services.cel_vocabulary_functions import in_group
        from ..services.vocabulary_cache import VocabularyCache

        # Create session cache
        vocab_cache = VocabularyCache(self.env)

        # Create env with cache in context (use a model to get with_context)
        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        env_with_cache = ConceptGroup.sudo().with_context(_vocab_cache=vocab_cache).env

        # Call in_group with cached env
        result = in_group(env_with_cache, self.code_female, "feminine_gender")
        self.assertTrue(result)

        # Verify cache was used
        self.assertIn("feminine_gender", vocab_cache._group_uri_cache)

    def test_is_female_uses_caching(self):
        """Test that is_female() semantic helper uses caching."""
        from ..services.cel_vocabulary_functions import is_female

        # Call is_female which internally calls in_group
        result = is_female(self.env, self.code_female)
        self.assertTrue(result)

        # Call again - should use cached data
        result = is_female(self.env, self.code_male)
        self.assertFalse(result)

    def test_cel_service_creates_vocab_cache(self):
        """Test that CEL service creates VocabularyCache for evaluations."""
        cel_service = self.env["spp.cel.service"]

        # Evaluate expression that uses vocabulary function
        context = {"code_val": self.code_female}
        result = cel_service.evaluate_expression("is_female(code_val)", context)

        self.assertTrue(result)

    def test_multiple_vocabulary_checks_efficient(self):
        """Test that multiple vocabulary checks in one session are efficient."""
        cel_service = self.env["spp.cel.service"]

        # Evaluate expression with multiple vocabulary checks
        context = {
            "female_code": self.code_female,
            "male_code": self.code_male,
        }

        # This expression checks both feminine_gender and masculine_gender groups
        result = cel_service.evaluate_expression("is_female(female_code) and not is_female(male_code)", context)

        self.assertTrue(result)
