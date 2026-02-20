# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import re

_logger = logging.getLogger(__name__)


class AreaMatcher:
    """Service to match HXL area values to spp.area records.

    Supports multiple matching strategies:
    - pcode: Exact match on area code
    - name: Case-insensitive name match
    - gps: Geographic coordinate lookup
    - fuzzy: Fuzzy name matching with normalization
    """

    def __init__(self, env, strategy, level=None):
        """Initialize area matcher.

        Args:
            env: Odoo environment
            strategy: Matching strategy ('pcode', 'name', 'gps', 'fuzzy')
            level: Optional area level filter
        """
        self.env = env
        self.strategy = strategy
        self.level = level
        self._cache = {}

        _logger.info(
            "Initialized AreaMatcher with strategy=%s, level=%s",
            strategy,
            level,
        )

    def match(self, value, lat=None, lon=None):
        """Match a value to an area.

        Args:
            value: Area identifier (pcode, name, etc.)
            lat: Latitude (for GPS matching)
            lon: Longitude (for GPS matching)

        Returns:
            spp.area record (empty recordset if no match)
        """
        # Build cache key
        cache_key = f"{self.strategy}:{value}:{lat}:{lon}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Perform matching
        area = self._do_match(value, lat, lon)

        # Cache result
        self._cache[cache_key] = area

        return area

    def _do_match(self, value, lat, lon):
        """Perform actual matching logic.

        Args:
            value: Area identifier
            lat: Latitude
            lon: Longitude

        Returns:
            spp.area record
        """
        Area = self.env["spp.area"]

        # Base domain
        domain = []
        if self.level is not None:
            domain.append(("level", "=", self.level))

        if self.strategy == "pcode":
            # Exact code match
            if not value:
                return Area.browse()

            domain.append(("code", "=", value))
            return Area.search(domain, limit=1)

        elif self.strategy == "name":
            # Case-insensitive name match
            if not value:
                return Area.browse()

            domain.append(("draft_name", "ilike", value))
            result = Area.search(domain, limit=1)

            # Fallback to alternate names
            if not result:
                domain[-1] = ("altnames", "ilike", value)
                result = Area.search(domain, limit=1)

            return result

        elif self.strategy == "gps":
            # Geographic coordinate lookup
            if lat is None or lon is None:
                return Area.browse()

            try:
                lat_float = float(lat)
                lon_float = float(lon)
            except (ValueError, TypeError):
                _logger.warning("Invalid coordinates: lat=%s, lon=%s", lat, lon)
                return Area.browse()

            # Find area containing this point
            # This requires a geographic lookup - simplified version
            # In production, this would use PostGIS or similar
            return self._find_area_by_coordinates(lat_float, lon_float, domain)

        elif self.strategy == "fuzzy":
            # Fuzzy name matching
            if not value:
                return Area.browse()

            normalized = self._normalize(value)

            # Try exact normalized match first
            domain.append(("draft_name", "ilike", normalized))
            result = Area.search(domain, limit=1)

            if result:
                return result

            # Try partial match with wildcards
            domain[-1] = ("draft_name", "ilike", f"%{normalized}%")
            result = Area.search(domain, limit=1)

            if result:
                return result

            # Try alternate names
            domain[-1] = ("altnames", "ilike", f"%{normalized}%")
            result = Area.search(domain, limit=1)

            return result

        else:
            _logger.warning("Unknown matching strategy: %s", self.strategy)
            return Area.browse()

    def _find_area_by_coordinates(self, lat, lon, base_domain):
        """Find area containing given coordinates.

        This is a simplified implementation. In production, you would use
        PostGIS ST_Contains or similar spatial functions.

        Args:
            lat: Latitude
            lon: Longitude
            base_domain: Base domain for filtering

        Returns:
            spp.area record
        """
        Area = self.env["spp.area"]

        # This is a placeholder - in production you would use spatial queries
        # For now, return empty recordset
        _logger.warning("GPS-based area matching not fully implemented. Requires PostGIS or similar spatial extension.")

        return Area.browse()

    def _normalize(self, value):
        """Normalize area name for fuzzy matching.

        Removes common suffixes, converts to lowercase, strips whitespace.

        Args:
            value: Area name to normalize

        Returns:
            Normalized string
        """
        if not value:
            return ""

        # Convert to lowercase and strip
        value = str(value).lower().strip()

        # Remove common administrative suffixes
        suffixes = [
            "district",
            "division",
            "province",
            "ward",
            "city",
            "municipality",
            "town",
            "village",
            "county",
        ]

        for suffix in suffixes:
            # Remove suffix with word boundary
            pattern = r"\s+" + suffix + r"$"
            value = re.sub(pattern, "", value, flags=re.IGNORECASE)

        # Normalize whitespace
        value = re.sub(r"\s+", " ", value).strip()

        return value

    def get_stats(self):
        """Get matching statistics.

        Returns:
            dict with cache stats
        """
        return {
            "strategy": self.strategy,
            "level": self.level,
            "cache_size": len(self._cache),
            "cache_hits": sum(1 for v in self._cache.values() if v),
            "cache_misses": sum(1 for v in self._cache.values() if not v),
        }

    def clear_cache(self):
        """Clear the matching cache."""
        self._cache.clear()
        _logger.debug("AreaMatcher cache cleared")
