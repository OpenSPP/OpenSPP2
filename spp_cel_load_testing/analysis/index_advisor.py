# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Database Index Advisor for CEL Expression Performance.

Recommends missing database indexes based on CEL query patterns and
EXPLAIN ANALYZE results. Provides standard CEL performance indexes
and generates CREATE INDEX DDL statements.
"""

import logging
from typing import Any

_logger = logging.getLogger(__name__)


# Tables frequently accessed by CEL expressions
CEL_RELEVANT_TABLES = [
    "res_partner",
    "spp_group_membership",
    "spp_program_membership",
    "spp_entitlement",
    "spp_grm_ticket",
    "spp_indicator_value",
    "spp_event_data",
]


class IndexAdvisor:
    """Recommends database indexes for CEL expression performance.

    Analyzes existing indexes and query patterns to suggest missing indexes
    that would improve CEL evaluation performance.
    """

    def __init__(self, cursor):
        """Initialize index advisor with database cursor.

        Args:
            cursor: Odoo database cursor for querying pg_index
        """
        self.cursor = cursor
        self._existing_indexes_cache = None

    def get_existing_indexes(self, refresh: bool = False) -> dict[str, list[dict[str, Any]]]:
        """Query pg_index to get all existing indexes grouped by table.

        Args:
            refresh: If True, refresh the cache

        Returns:
            Dictionary mapping table name to list of index definitions
        """
        if self._existing_indexes_cache and not refresh:
            return self._existing_indexes_cache

        try:
            self.cursor.execute("""
                SELECT
                    t.relname AS table_name,
                    i.relname AS index_name,
                    a.attname AS column_name,
                    ix.indisunique AS is_unique,
                    ix.indisprimary AS is_primary,
                    am.amname AS index_type
                FROM
                    pg_index ix
                    JOIN pg_class t ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid
                    JOIN pg_am am ON am.oid = i.relam
                WHERE
                    a.attnum = ANY(ix.indkey)
                    AND t.relkind = 'r'
                ORDER BY
                    t.relname,
                    i.relname,
                    a.attnum
            """)

            rows = self.cursor.fetchall()

            # Group by table and index
            indexes_by_table = {}
            current_index = None
            current_index_data = None

            for row in rows:
                table_name, index_name, column_name, is_unique, is_primary, index_type = row

                if current_index != index_name:
                    # Save previous index
                    if current_index_data:
                        table = current_index_data["table"]
                        if table not in indexes_by_table:
                            indexes_by_table[table] = []
                        indexes_by_table[table].append(current_index_data)

                    # Start new index
                    current_index = index_name
                    current_index_data = {
                        "table": table_name,
                        "name": index_name,
                        "columns": [column_name],
                        "is_unique": is_unique,
                        "is_primary": is_primary,
                        "type": index_type,
                    }
                else:
                    # Add column to current index
                    current_index_data["columns"].append(column_name)

            # Save last index
            if current_index_data:
                table = current_index_data["table"]
                if table not in indexes_by_table:
                    indexes_by_table[table] = []
                indexes_by_table[table].append(current_index_data)

            self._existing_indexes_cache = indexes_by_table
            return indexes_by_table

        except Exception as e:
            _logger.error("Failed to query existing indexes: %s", e, exc_info=True)
            return {}

    def check_index_exists(self, table: str, columns: list[str]) -> bool:
        """Check if an index exists for given table and columns.

        Args:
            table: Table name
            columns: List of column names (order matters for composite indexes)

        Returns:
            True if matching index exists
        """
        existing = self.get_existing_indexes()
        table_indexes = existing.get(table, [])

        for index in table_indexes:
            # Check if index columns match (order matters)
            if index["columns"] == columns:
                return True
            # Also check if index starts with these columns (can be used)
            if index["columns"][: len(columns)] == columns:
                return True

        return False

    def get_recommended_cel_indexes(self) -> list[dict[str, Any]]:
        """Get standard recommended indexes for CEL expression performance.

        Returns:
            List of recommended index definitions with table, columns, rationale
        """
        recommendations = [
            # res_partner indexes for registrant lookups
            {
                "table": "res_partner",
                "columns": ["is_registrant", "is_group"],
                "rationale": "Filter registrants by type (individual/group) in CEL expressions",
            },
            {
                "table": "res_partner",
                "columns": ["is_registrant", "active"],
                "rationale": "Filter active registrants in eligibility checks",
            },
            {
                "table": "res_partner",
                "columns": ["birthdate"],
                "rationale": "Age-based eligibility calculations",
            },
            # spp_group_membership for household queries
            {
                "table": "spp_group_membership",
                "columns": ["group"],
                "rationale": "Look up members of a household/group",
            },
            {
                "table": "spp_group_membership",
                "columns": ["individual"],
                "rationale": "Look up groups an individual belongs to",
            },
            {
                "table": "spp_group_membership",
                "columns": ["group", "individual"],
                "rationale": "Composite index for membership checks",
            },
            # spp_program_membership for enrollment checks
            {
                "table": "spp_program_membership",
                "columns": ["partner_id", "program_id"],
                "rationale": "Check program enrollment status",
            },
            {
                "table": "spp_program_membership",
                "columns": ["partner_id", "state"],
                "rationale": "Find active enrollments for a beneficiary",
            },
            {
                "table": "spp_program_membership",
                "columns": ["program_id", "state"],
                "rationale": "Count enrollments by program and state",
            },
            # spp_entitlement for payment history
            {
                "table": "spp_entitlement",
                "columns": ["partner_id", "state"],
                "rationale": "Check entitlement status for beneficiary",
            },
            {
                "table": "spp_entitlement",
                "columns": ["cycle_id", "state"],
                "rationale": "Query entitlements by cycle",
            },
            {
                "table": "spp_entitlement",
                "columns": ["partner_id", "cycle_id"],
                "rationale": "Lookup specific beneficiary entitlements in cycle",
            },
            # spp_grm_ticket for grievance checks
            {
                "table": "spp_grm_ticket",
                "columns": ["partner_id", "stage_id"],
                "rationale": "Check open grievances for registrant",
            },
            {
                "table": "spp_grm_ticket",
                "columns": ["partner_id", "priority"],
                "rationale": "Find high-priority tickets for registrant",
            },
            # spp_indicator_value for indicator-based eligibility
            {
                "table": "spp_indicator_value",
                "columns": ["partner_id", "indicator_id"],
                "rationale": "Lookup indicator values for eligibility",
            },
            {
                "table": "spp_indicator_value",
                "columns": ["partner_id", "indicator_id", "value_date"],
                "rationale": "Get latest indicator value for beneficiary",
            },
            # spp_event_data for event-based checks
            {
                "table": "spp_event_data",
                "columns": ["partner_id", "event_type_id"],
                "rationale": "Query events by registrant and type",
            },
            {
                "table": "spp_event_data",
                "columns": ["partner_id", "state"],
                "rationale": "Find active events for registrant",
            },
        ]

        return recommendations

    def analyze_missing_indexes(self) -> list[dict[str, Any]]:
        """Analyze which recommended indexes are missing.

        Returns:
            List of missing index recommendations with DDL statements
        """
        recommendations = self.get_recommended_cel_indexes()
        missing = []

        for rec in recommendations:
            table = rec["table"]
            columns = rec["columns"]

            if not self.check_index_exists(table, columns):
                # Generate index name
                index_name = self._generate_index_name(table, columns)

                # Generate CREATE INDEX DDL
                ddl = self._generate_create_index_ddl(index_name, table, columns)

                missing.append(
                    {
                        "table": table,
                        "columns": columns,
                        "rationale": rec["rationale"],
                        "index_name": index_name,
                        "ddl": ddl,
                    }
                )

        return missing

    def analyze_explain_issues(self, explain_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Recommend indexes based on EXPLAIN ANALYZE issues.

        Args:
            explain_issues: List of issues from ExplainAnalyzer

        Returns:
            List of index recommendations based on detected issues
        """
        recommendations = []
        seen = set()  # Track (table, columns) to avoid duplicates

        for issue in explain_issues:
            issue_type = issue.get("type")
            table = issue.get("table", "")

            # Sequential scan on large table
            if issue_type == "sequential_scan_large_table" and table:
                # Recommend index on commonly filtered columns
                # This is a heuristic - real recommendation needs query analysis
                suggested_columns = self._suggest_columns_for_table(table)

                for columns in suggested_columns:
                    key = (table, tuple(columns))
                    if key not in seen and not self.check_index_exists(table, columns):
                        index_name = self._generate_index_name(table, columns)
                        ddl = self._generate_create_index_ddl(index_name, table, columns)

                        recommendations.append(
                            {
                                "table": table,
                                "columns": columns,
                                "rationale": f"Sequential scan detected on {table} with {issue.get('rows', 0):,} rows",
                                "index_name": index_name,
                                "ddl": ddl,
                                "issue": issue,
                            }
                        )
                        seen.add(key)

            # Nested loop without index
            elif issue_type == "nested_loop_no_index":
                # This is harder to analyze without full query context
                # Log for manual review
                _logger.info("Nested loop without index detected (manual review needed): %s", issue.get("message"))

        return recommendations

    def _suggest_columns_for_table(self, table: str) -> list[list[str]]:
        """Suggest commonly filtered columns for a table.

        Args:
            table: Table name

        Returns:
            List of column lists to consider for indexing
        """
        # Common patterns based on table
        suggestions = {
            "res_partner": [
                ["is_registrant"],
                ["is_group"],
                ["active"],
            ],
            "spp_group_membership": [
                ["group"],
                ["individual"],
            ],
            "spp_program_membership": [
                ["partner_id"],
                ["program_id"],
                ["state"],
            ],
            "spp_entitlement": [
                ["partner_id"],
                ["cycle_id"],
                ["state"],
            ],
            "spp_grm_ticket": [
                ["partner_id"],
                ["stage_id"],
            ],
            "spp_indicator_value": [
                ["partner_id"],
                ["indicator_id"],
            ],
            "spp_event_data": [
                ["partner_id"],
                ["event_type_id"],
                ["state"],
            ],
        }

        return suggestions.get(table, [])

    def _generate_index_name(self, table: str, columns: list[str]) -> str:
        """Generate index name following convention.

        Args:
            table: Table name
            columns: List of column names

        Returns:
            Generated index name
        """
        # Pattern: {table}__{col1}_{col2}_idx
        col_str = "_".join(columns)
        return f"{table}__{col_str}_idx"

    def _generate_create_index_ddl(self, index_name: str, table: str, columns: list[str]) -> str:
        """Generate CREATE INDEX DDL statement.

        Args:
            index_name: Name for the index
            table: Table name
            columns: List of column names

        Returns:
            CREATE INDEX statement
        """
        columns_str = ", ".join(columns)
        return f"CREATE INDEX {index_name} ON {table} ({columns_str});"

    def print_recommendations_report(self, recommendations: list[dict[str, Any]]):
        """Print index recommendations report to logger.

        Args:
            recommendations: List of index recommendations
        """
        if not recommendations:
            _logger.info("No missing indexes found - all recommended indexes exist!")
            return

        _logger.info("=" * 80)
        _logger.info("INDEX RECOMMENDATIONS FOR CEL PERFORMANCE")
        _logger.info("=" * 80)
        _logger.info("")
        _logger.info("Found %d missing indexes:", len(recommendations))
        _logger.info("")

        for i, rec in enumerate(recommendations, 1):
            _logger.info("%d. Table: %s", i, rec["table"])
            _logger.info("   Columns: %s", ", ".join(rec["columns"]))
            _logger.info("   Rationale: %s", rec["rationale"])
            _logger.info("   DDL: %s", rec["ddl"])
            _logger.info("")

        _logger.info("=" * 80)
        _logger.info("To create all indexes, run:")
        _logger.info("")
        for rec in recommendations:
            _logger.info(rec["ddl"])
        _logger.info("=" * 80)
