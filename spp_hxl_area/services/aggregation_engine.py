# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


class AggregationEngine:
    """Engine to aggregate HXL rows by area according to rules.

    Takes parsed HXL rows and applies aggregation rules to generate
    area-level indicators.
    """

    def __init__(self, env, profile, area_matcher):
        """Initialize aggregation engine.

        Args:
            env: Odoo environment
            profile: spp.hxl.import.profile record
            area_matcher: AreaMatcher instance
        """
        self.env = env
        self.profile = profile
        self.matcher = area_matcher

        _logger.info(
            "Initialized AggregationEngine for profile: %s",
            profile.name,
        )

    def aggregate(self, rows, hxl_columns):
        """Aggregate rows and return area indicators.

        Args:
            rows: List of dicts, each representing one HXL row
            hxl_columns: Dict mapping HXL tags to column headers

        Returns:
            tuple: (indicators, unmatched_rows)
                - indicators: List of indicator dicts ready for creation
                - unmatched_rows: List of rows that couldn't be matched to areas
        """
        _logger.info("Starting aggregation of %d rows", len(rows))

        # Group rows by area
        area_rows = defaultdict(list)
        unmatched = []

        # Identify area column
        area_col_tag = self.profile.area_column_tag
        lat_col_tag = self.profile.latitude_tag if self.profile.area_matching_strategy == "gps" else None
        lon_col_tag = self.profile.longitude_tag if self.profile.area_matching_strategy == "gps" else None

        # Match each row to an area
        for row in rows:
            area_value = row.get(area_col_tag, "")
            lat = row.get(lat_col_tag) if lat_col_tag else None
            lon = row.get(lon_col_tag) if lon_col_tag else None

            # Try matching
            area = self.matcher.match(area_value, lat, lon)

            if area:
                area_rows[area.id].append(row)
            else:
                unmatched.append(row)
                _logger.debug(
                    "Could not match row to area: %s (lat=%s, lon=%s)",
                    area_value,
                    lat,
                    lon,
                )

        _logger.info(
            "Matched %d rows to %d areas, %d unmatched",
            len(rows) - len(unmatched),
            len(area_rows),
            len(unmatched),
        )

        # Apply aggregation rules per area
        indicators = []

        for area_id, area_rows_list in area_rows.items():
            for rule in self.profile.aggregation_ids:
                if not rule.active:
                    continue

                try:
                    result = self._apply_rule(rule, area_rows_list, hxl_columns)

                    indicators.append(
                        {
                            "area_id": area_id,
                            "rule_id": rule.id,
                            "variable_id": rule.variable_id.id if rule.variable_id else False,
                            "value": result["total"],
                            "value_count": result["count"],
                            "disaggregation_json": json.dumps(result.get("disaggregation", {})),
                            "hxl_tag": rule.output_hxl_tag,
                        }
                    )

                except Exception as e:
                    _logger.error(
                        "Failed to apply rule %s for area %s: %s",
                        rule.name,
                        area_id,
                        e,
                        exc_info=True,
                    )

        _logger.info("Generated %d indicators", len(indicators))

        return indicators, unmatched

    def _apply_rule(self, rule, rows, hxl_columns):
        """Apply a single aggregation rule to rows.

        Args:
            rule: spp.hxl.aggregation.rule record
            rows: List of row dicts for this area
            hxl_columns: Dict mapping HXL tags to headers

        Returns:
            dict with keys: total, count, disaggregation (optional)
        """
        # Filter rows if expression provided
        filtered_rows = rows

        if rule.filter_expression:
            filtered_rows = []
            for row in rows:
                try:
                    # Evaluate filter expression
                    # WARNING: eval() is dangerous - in production use a safe expression evaluator
                    if self._eval_filter(row, rule.filter_expression):
                        filtered_rows.append(row)
                except Exception as e:
                    _logger.warning(
                        "Failed to evaluate filter for row: %s",
                        e,
                    )

        # Get source column if needed
        source_col_tag = rule.source_column_tag

        # Apply aggregation
        if rule.aggregation_type == "count":
            total = len(filtered_rows)

        elif rule.aggregation_type == "sum":
            if not source_col_tag:
                _logger.warning("Sum aggregation requires source_column_tag")
                total = 0
            else:
                total = sum(self._to_float(row.get(source_col_tag, 0)) for row in filtered_rows)

        elif rule.aggregation_type == "avg":
            if not source_col_tag:
                _logger.warning("Average aggregation requires source_column_tag")
                total = 0
            else:
                values = [self._to_float(row.get(source_col_tag, 0)) for row in filtered_rows]
                total = sum(values) / len(values) if values else 0

        elif rule.aggregation_type == "min":
            if not source_col_tag:
                _logger.warning("Min aggregation requires source_column_tag")
                total = 0
            else:
                values = [self._to_float(row.get(source_col_tag, 0)) for row in filtered_rows]
                total = min(values) if values else 0

        elif rule.aggregation_type == "max":
            if not source_col_tag:
                _logger.warning("Max aggregation requires source_column_tag")
                total = 0
            else:
                values = [self._to_float(row.get(source_col_tag, 0)) for row in filtered_rows]
                total = max(values) if values else 0

        elif rule.aggregation_type == "count_distinct":
            if not source_col_tag:
                _logger.warning("Count distinct requires source_column_tag")
                total = 0
            else:
                distinct_values = set(row.get(source_col_tag) for row in filtered_rows)
                total = len(distinct_values)

        elif rule.aggregation_type == "percentage":
            total = (len(filtered_rows) / len(rows) * 100) if rows else 0

        else:
            _logger.warning("Unknown aggregation type: %s", rule.aggregation_type)
            total = len(filtered_rows)

        result = {
            "total": total,
            "count": len(filtered_rows),
        }

        # Handle disaggregation
        if rule.disaggregate_by_tags:
            result["disaggregation"] = self._disaggregate(
                filtered_rows,
                rule,
                hxl_columns,
                source_col_tag,
            )

        return result

    def _disaggregate(self, rows, rule, hxl_columns, source_col_tag):
        """Disaggregate values by HXL attributes.

        Args:
            rows: Filtered rows to disaggregate
            rule: Aggregation rule
            hxl_columns: Column mapping
            source_col_tag: Source column tag

        Returns:
            dict mapping disaggregation attributes to values
        """
        disagg_tags = [tag.strip() for tag in rule.disaggregate_by_tags.split(",")]

        result = {}

        for tag in disagg_tags:
            # Count rows that have this attribute
            matching_rows = [row for row in rows if self._has_attribute(row, tag, hxl_columns)]

            if rule.aggregation_type == "count":
                result[tag] = len(matching_rows)
            elif rule.aggregation_type in ("sum", "avg", "min", "max"):
                if source_col_tag:
                    values = [self._to_float(row.get(source_col_tag, 0)) for row in matching_rows]
                    if rule.aggregation_type == "sum":
                        result[tag] = sum(values)
                    elif rule.aggregation_type == "avg":
                        result[tag] = sum(values) / len(values) if values else 0
                    elif rule.aggregation_type == "min":
                        result[tag] = min(values) if values else 0
                    elif rule.aggregation_type == "max":
                        result[tag] = max(values) if values else 0
                else:
                    result[tag] = 0
            else:
                result[tag] = len(matching_rows)

        return result

    def _has_attribute(self, row, attribute, hxl_columns):
        """Check if a row has a specific HXL attribute.

        This is simplified - in production you would check all columns
        for the attribute marker.

        Args:
            row: Row dict
            attribute: HXL attribute (e.g., '+f', '+m')
            hxl_columns: Column mapping

        Returns:
            bool
        """
        # Normalize attribute (remove leading + if present)
        attr_normalized = attribute.lstrip("+")

        # Look for columns with this attribute
        for tag in hxl_columns.keys():
            # Split tag into hashtag and attributes: #affected+f+elderly -> ['#affected', 'f', 'elderly']
            parts = tag.split("+")
            attributes = parts[1:] if len(parts) > 1 else []

            if attr_normalized in attributes:
                value = row.get(tag)
                # Consider non-empty, non-zero values as having the attribute
                if value and str(value).strip() and str(value) != "0":
                    return True

        return False

    def _eval_filter(self, row, expression):
        """Evaluate a filter expression against a row.

        Uses CEL (Common Expression Language) for secure expression evaluation.
        CEL provides a sandboxed environment with no access to system resources.

        Expression examples:
        - row.get('#affected') > 100
        - row.get('#status') == 'confirmed'
        - int(row.get('#population', 0)) >= 1000

        Args:
            row: Row dict with HXL column values
            expression: CEL expression to evaluate

        Returns:
            bool
        """
        try:
            # Build context for CEL evaluation
            context = {
                "row": row,
                "get": row.get,
            }

            # Use CEL service for secure expression evaluation
            cel_service = self.env["spp.cel.service"]
            result = cel_service.evaluate_expression(expression, context)
            return bool(result)

        except Exception as e:
            _logger.warning(
                "Failed to evaluate filter expression '%s': %s",
                expression,
                e,
            )
            return False

    @staticmethod
    def _to_float(value):
        """Convert value to float, handling various formats.

        Args:
            value: Value to convert

        Returns:
            float
        """
        if value is None:
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # Remove common formatting
            value = value.strip().replace(",", "").replace(" ", "")

            if not value:
                return 0.0

            try:
                return float(value)
            except ValueError:
                _logger.debug("Could not convert '%s' to float", value)
                return 0.0

        return 0.0
