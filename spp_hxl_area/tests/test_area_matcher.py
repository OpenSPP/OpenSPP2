# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from ..services.area_matcher import AreaMatcher


@tagged("post_install", "-at_install")
class TestAreaMatcher(TransactionCase):
    """Test Area Matcher service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Area = cls.env["spp.area"]

        # Create test areas
        cls.province = cls.Area.create(
            {
                "draft_name": "Test Province",
                "code": "PROV01",
                "level": 1,
            }
        )

        cls.district = cls.Area.create(
            {
                "draft_name": "Test District",
                "code": "DIST01",
                "level": 2,
                "parent_id": cls.province.id,
            }
        )

        cls.division = cls.Area.create(
            {
                "draft_name": "Test Division Municipality",
                "code": "DIV01",
                "level": 3,
                "parent_id": cls.district.id,
                "altnames": "Alternative Name, Another Name",
            }
        )

    def test_pcode_matching_exact(self):
        """Test exact P-code matching."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=2)

        area = matcher.match("DIST01")

        self.assertEqual(area, self.district)

    def test_pcode_matching_case_sensitive(self):
        """Test that P-code matching is case-sensitive."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=2)

        area = matcher.match("dist01")

        # Should not match (case-sensitive)
        self.assertFalse(area)

    def test_pcode_matching_with_level_filter(self):
        """Test P-code matching with level filter."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=3)

        # Should only match level 3
        area = matcher.match("DIV01")
        self.assertEqual(area, self.division)

        # Should not match level 2
        area = matcher.match("DIST01")
        self.assertFalse(area)

    def test_name_matching_exact(self):
        """Test exact name matching."""
        matcher = AreaMatcher(self.env, strategy="name", level=2)

        area = matcher.match("Test District")

        self.assertEqual(area, self.district)

    def test_name_matching_case_insensitive(self):
        """Test case-insensitive name matching."""
        matcher = AreaMatcher(self.env, strategy="name", level=2)

        area = matcher.match("test district")

        self.assertEqual(area, self.district)

    def test_name_matching_alternate_names(self):
        """Test matching against alternate names."""
        matcher = AreaMatcher(self.env, strategy="name", level=3)

        area = matcher.match("Alternative Name")

        self.assertEqual(area, self.division)

    def test_fuzzy_matching_exact(self):
        """Test fuzzy matching with exact name."""
        matcher = AreaMatcher(self.env, strategy="fuzzy", level=3)

        area = matcher.match("Test Division Municipality")

        self.assertEqual(area, self.division)

    def test_fuzzy_matching_normalized(self):
        """Test fuzzy matching with suffix removed."""
        matcher = AreaMatcher(self.env, strategy="fuzzy", level=3)

        # Should match even with "Municipality" suffix
        area = matcher.match("Test Division")

        self.assertEqual(area, self.division)

    def test_fuzzy_matching_partial(self):
        """Test fuzzy matching with partial name."""
        matcher = AreaMatcher(self.env, strategy="fuzzy", level=3)

        area = matcher.match("Division")

        self.assertEqual(area, self.division)

    def test_gps_matching_not_implemented(self):
        """Test that GPS matching returns empty recordset (not implemented)."""
        matcher = AreaMatcher(self.env, strategy="gps", level=2)

        area = matcher.match("", lat=12.34, lon=56.78)

        # Should return empty recordset (not fully implemented)
        self.assertFalse(area)

    def test_matching_with_cache(self):
        """Test that matcher caches results."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=2)

        # First match
        area1 = matcher.match("DIST01")
        self.assertEqual(area1, self.district)

        # Second match should be cached
        area2 = matcher.match("DIST01")
        self.assertEqual(area2, self.district)

        # Check cache stats
        stats = matcher.get_stats()
        self.assertEqual(stats["cache_size"], 1)
        self.assertEqual(stats["cache_hits"], 1)

    def test_matching_empty_value(self):
        """Test matching with empty value."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=2)

        area = matcher.match("")

        self.assertFalse(area)

    def test_matching_nonexistent_code(self):
        """Test matching with non-existent code."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=2)

        area = matcher.match("NONEXIST")

        self.assertFalse(area)

    def test_normalize_method(self):
        """Test the normalize method."""
        matcher = AreaMatcher(self.env, strategy="fuzzy")

        # Test suffix removal - common suffixes are removed from end
        self.assertEqual(matcher._normalize("Test District"), "test")
        self.assertEqual(matcher._normalize("Test District District"), "test district")
        self.assertEqual(matcher._normalize("Test Division Municipality"), "test division")

        # Test whitespace normalization
        self.assertEqual(matcher._normalize("Test  Area  Name"), "test area name")

        # Test empty string
        self.assertEqual(matcher._normalize(""), "")

    def test_clear_cache(self):
        """Test cache clearing."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=2)

        # Add to cache
        matcher.match("DIST01")
        self.assertEqual(matcher.get_stats()["cache_size"], 1)

        # Clear cache
        matcher.clear_cache()
        self.assertEqual(matcher.get_stats()["cache_size"], 0)

    def test_matcher_without_level_filter(self):
        """Test matcher without level filter."""
        matcher = AreaMatcher(self.env, strategy="pcode", level=None)

        # Should match at any level
        area = matcher.match("PROV01")
        self.assertEqual(area, self.province)

        area = matcher.match("DIST01")
        self.assertEqual(area, self.district)

        area = matcher.match("DIV01")
        self.assertEqual(area, self.division)
