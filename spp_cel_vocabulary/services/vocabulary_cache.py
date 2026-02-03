"""Session-scoped vocabulary cache for CEL evaluation.

This module provides a request-scoped cache for vocabulary concept group
lookups during CEL expression evaluation. It eliminates N+1 database queries
by caching group membership data for the duration of a single evaluation session.

Architecture:
    Layer 1: @ormcache in VocabularyConceptGroup (registry-scoped)
    Layer 2: VocabularyCache (session-scoped, created per evaluation)

The session cache wraps the ormcache layer, providing:
    - Consistent frozenset access without repeated ormcache calls
    - Cleaner API for CEL functions
    - Easy integration with CEL service namespace building
"""

import logging

_logger = logging.getLogger(__name__)


class VocabularyCache:
    """Session-scoped cache for vocabulary lookups during CEL evaluation.

    This cache is designed to be created once per CEL evaluation session
    (e.g., when computing values for a single partner or evaluating a
    member aggregate expression). It provides O(1) lookups for repeated
    group membership checks.

    The cache wraps the ormcache layer in VocabularyConceptGroup, ensuring
    that even within a single session, we don't make redundant ormcache
    dictionary lookups.

    Usage:
        cache = VocabularyCache(env)
        is_in_group = cache.check_membership(code_value, "feminine_gender")

    Example in CEL evaluation:
        # Created once at start of _build_eval_namespace
        vocab_cache = VocabularyCache(self.env)

        # Used many times during evaluation
        vocab_cache.check_membership(member.gender_id, "feminine_gender")
        vocab_cache.check_membership(member.gender_id, "masculine_gender")
    """

    def __init__(self, env):
        """Initialize the vocabulary cache.

        Args:
            env: Odoo environment (must have valid cursor)
        """
        self.env = env
        self._group_uri_cache = {}  # group_name -> frozenset(uris) or None

    def get_group_uris(self, group_name):
        """Get URIs for a concept group with session caching.

        First checks session cache, then falls back to ormcache layer
        in VocabularyConceptGroup.

        Args:
            group_name: Name of the concept group

        Returns:
            frozenset or None: Set of URIs, None if group not found
        """
        if group_name in self._group_uri_cache:
            return self._group_uri_cache[group_name]

        # Fetch from ormcache layer
        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        uri_set = ConceptGroup._get_group_uris_cached(group_name)

        # Cache for this session (even if None, to avoid repeated lookups)
        self._group_uri_cache[group_name] = uri_set
        return uri_set

    def check_membership(self, code_value, group_name):
        """Check if code is in group with full caching.

        This is the primary method for CEL vocabulary functions to use.
        It combines session caching with efficient frozenset membership checking.

        Args:
            code_value: spp.vocabulary.code recordset (can be empty)
            group_name: Concept group name

        Returns:
            bool: True if code is in group
        """
        if not code_value or not group_name:
            return False

        uri_set = self.get_group_uris(group_name)
        if uri_set is None:
            _logger.debug("[VocabularyCache] Concept group '%s' not found", group_name)
            return False

        if len(uri_set) == 0:
            # Empty group - exists but no codes assigned yet
            _logger.debug("[VocabularyCache] Concept group '%s' is empty (no codes)", group_name)
            return False

        # Direct frozenset membership check - O(1)
        if code_value.uri and code_value.uri in uri_set:
            return True
        if code_value.reference_uri and code_value.reference_uri in uri_set:
            return True

        return False

    def preload_groups(self, group_names):
        """Preload multiple groups into the session cache.

        Useful when you know ahead of time which groups will be needed.
        This can help with debugging and explicit cache warming.

        Args:
            group_names: List of group names to preload
        """
        for name in group_names:
            if name not in self._group_uri_cache:
                self.get_group_uris(name)

    def clear(self):
        """Clear the session cache.

        Typically not needed as the cache is discarded with the
        VocabularyCache instance at the end of the evaluation session.
        """
        self._group_uri_cache.clear()

    @property
    def stats(self):
        """Return cache statistics for debugging.

        Returns:
            dict: Statistics about cache usage
        """
        cached_groups = [k for k, v in self._group_uri_cache.items() if v is not None]
        missing_groups = [k for k, v in self._group_uri_cache.items() if v is None]
        return {
            "cached_groups": len(cached_groups),
            "missing_groups": len(missing_groups),
            "group_names": cached_groups,
        }
