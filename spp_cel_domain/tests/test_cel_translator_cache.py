# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit tests for the CEL translator's module-level translation cache."""

from odoo.tests import TransactionCase, tagged

from ..models import cel_translator as ct


@tagged("post_install", "-at_install")
class TestCelTranslatorCache(TransactionCase):
    """Cover the module-level translation cache helpers."""

    def setUp(self):
        super().setUp()
        ct.invalidate_translation_cache()
        self.addCleanup(ct.invalidate_translation_cache)

    def test_make_cache_key_deterministic_and_config_sensitive(self):
        """Same inputs yield the same key; a different config yields a different key."""
        k1 = ct._make_cache_key("a > 1", "res.partner", {"x": 1})
        k2 = ct._make_cache_key("a > 1", "res.partner", {"x": 1})
        k3 = ct._make_cache_key("a > 1", "res.partner", {"x": 2})
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)

    def test_make_cache_key_unsortable_config_falls_back(self):
        """An unsortable config (mixed-type keys) uses the fallback hash path."""
        key = ct._make_cache_key("a", "m", {1: "x", "y": 2})
        self.assertEqual(key[0], "a")
        self.assertEqual(key[1], "m")

    def test_cache_roundtrip_and_invalidate(self):
        """A cached translation can be retrieved and then invalidated."""
        self.assertIsNone(ct.get_cached_translation("e", "m", {}))
        ct.cache_translation("e", "m", {}, ("plan", "explain"))
        self.assertEqual(ct.get_cached_translation("e", "m", {}), ("plan", "explain"))
        ct.invalidate_translation_cache()
        self.assertIsNone(ct.get_cached_translation("e", "m", {}))

    def test_cache_fifo_eviction(self):
        """Exceeding the cache limit evicts the oldest entries (FIFO)."""
        total = ct._TRANSLATION_CACHE_MAX_SIZE + ct._TRANSLATION_CACHE_EVICT_SIZE + 1
        for i in range(total):
            ct.cache_translation(f"expr_{i}", "m", {}, (i, ""))
        # The oldest entry has been evicted, and the cache stays bounded.
        self.assertIsNone(ct.get_cached_translation("expr_0", "m", {}))
        self.assertLessEqual(len(ct._translation_cache), ct._TRANSLATION_CACHE_MAX_SIZE)
