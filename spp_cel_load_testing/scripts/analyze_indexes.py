#!/usr/bin/env python3
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Database Index Analysis CLI for CEL Expression Performance.

This standalone script analyzes database indexes for CEL query performance.
It can check existing indexes, run sample expressions to detect missing indexes,
and generate CREATE INDEX DDL statements.

Usage:
    # Check existing index coverage
    ./analyze_indexes.py --db openspp_db --check-existing

    # Run sample expressions and analyze queries
    ./analyze_indexes.py --db openspp_db --run-expressions

    # Generate CREATE INDEX DDL for missing indexes
    ./analyze_indexes.py --db openspp_db --generate-ddl --output sql

    # Export results to file
    ./analyze_indexes.py --db openspp_db --check-existing --output json --output-file results.json
"""

import argparse
import json
import logging
import os
import sys
from typing import Any

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Install it with: pip install psycopg2-binary")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
_logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages PostgreSQL database connection for index analysis."""

    def __init__(self, dbname: str, user: str = None, password: str = None, host: str = "localhost", port: int = 5432):
        """Initialize database connection.

        Args:
            dbname: Database name
            user: Database user (defaults to current user)
            password: Database password (optional)
            host: Database host
            port: Database port
        """
        self.dbname = dbname
        self.user = user or os.getenv("USER")
        self.password = password or os.getenv("PGPASSWORD", "")
        self.host = host
        self.port = port
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
            )
            self.cursor = self.conn.cursor()
            _logger.info(f"Connected to database: {self.dbname}")
            return self
        except psycopg2.Error as e:
            _logger.error(f"Failed to connect to database {self.dbname}: {e}")
            sys.exit(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        _logger.info("Database connection closed")


class IndexAnalysisCLI:
    """Command-line interface for database index analysis."""

    def __init__(self, db_conn: DatabaseConnection):
        """Initialize CLI with database connection.

        Args:
            db_conn: Database connection wrapper
        """
        self.db_conn = db_conn
        self.cursor = db_conn.cursor

        # Import analysis modules
        try:
            from analysis.explain_analyzer import ExplainAnalyzer
            from analysis.index_advisor import CEL_RELEVANT_TABLES, IndexAdvisor

            self.index_advisor = IndexAdvisor(self.cursor)
            self.explain_analyzer = ExplainAnalyzer(self.cursor)
            self.cel_tables = CEL_RELEVANT_TABLES
        except ImportError as e:
            _logger.error(f"Failed to import analysis modules: {e}")
            sys.exit(1)

    def check_existing_indexes(self) -> dict[str, Any]:
        """Check existing index coverage for CEL-relevant tables.

        Returns:
            Dictionary with coverage stats and missing indexes
        """
        _logger.info("Checking existing index coverage...")

        # Get recommended indexes
        recommendations = self.index_advisor.get_recommended_cel_indexes()
        missing = self.index_advisor.analyze_missing_indexes()

        # Calculate coverage
        total_recommended = len(recommendations)
        total_missing = len(missing)
        coverage_pct = (total_recommended - total_missing) / total_recommended * 100 if total_recommended > 0 else 100.0

        # Group by table
        coverage_by_table = {}
        for rec in recommendations:
            table = rec["table"]
            if table not in coverage_by_table:
                coverage_by_table[table] = {
                    "recommended": 0,
                    "missing": 0,
                    "coverage_pct": 0,
                }
            coverage_by_table[table]["recommended"] += 1

        for miss in missing:
            table = miss["table"]
            if table in coverage_by_table:
                coverage_by_table[table]["missing"] += 1

        # Calculate per-table coverage
        for _table, stats in coverage_by_table.items():
            recommended = stats["recommended"]
            missing = stats["missing"]
            stats["coverage_pct"] = (recommended - missing) / recommended * 100 if recommended > 0 else 100.0

        return {
            "total_recommended": total_recommended,
            "total_missing": total_missing,
            "total_existing": total_recommended - total_missing,
            "coverage_pct": coverage_pct,
            "coverage_by_table": coverage_by_table,
            "missing_indexes": missing,
        }

    def run_expression_analysis(self) -> dict[str, Any]:
        """Run sample CEL expressions and analyze generated queries.

        Returns:
            Dictionary with query analysis results and recommendations
        """
        _logger.info("Running expression analysis (requires Odoo environment)...")
        _logger.warning(
            "Expression analysis requires Odoo environment. " "This feature is not yet implemented in standalone mode."
        )

        # This would require:
        # 1. Loading Odoo environment
        # 2. Running sample expressions from expression_templates
        # 3. Capturing generated SQL queries
        # 4. Running EXPLAIN ANALYZE on each query
        # 5. Collecting recommendations

        return {
            "status": "not_implemented",
            "message": "Expression analysis requires Odoo environment",
        }

    def generate_ddl(self, missing_indexes: list[dict[str, Any]]) -> list[str]:
        """Generate CREATE INDEX DDL statements for missing indexes.

        Args:
            missing_indexes: List of missing index recommendations

        Returns:
            List of DDL statements
        """
        ddl_statements = []

        # Sort by priority (table importance)
        table_priority = {
            "res_partner": 1,
            "spp_group_membership": 2,
            "spp_program_membership": 3,
            "spp_entitlement": 4,
            "spp_indicator_value": 5,
            "spp_event_data": 6,
            "spp_grm_ticket": 7,
        }

        sorted_indexes = sorted(missing_indexes, key=lambda x: (table_priority.get(x["table"], 999), x["table"]))

        for idx_info in sorted_indexes:
            table = idx_info["table"]
            columns = idx_info["columns"]
            rationale = idx_info["rationale"]
            index_name = idx_info["index_name"]

            # Generate DDL with comment
            columns_str = ", ".join(columns)
            ddl = f"-- {rationale}\n"
            ddl += f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}\n"
            ddl += f"  ON {table} ({columns_str});\n"

            ddl_statements.append(ddl)

        return ddl_statements

    def format_output_table(self, results: dict[str, Any]) -> str:
        """Format results as ASCII table.

        Args:
            results: Analysis results

        Returns:
            Formatted ASCII table
        """
        lines = []
        lines.append("=" * 80)
        lines.append("DATABASE INDEX ANALYSIS FOR CEL PERFORMANCE")
        lines.append("=" * 80)
        lines.append("")

        # Overall coverage
        lines.append("OVERALL COVERAGE:")
        lines.append(f"  Total Recommended: {results['total_recommended']}")
        lines.append(f"  Existing:          {results['total_existing']}")
        lines.append(f"  Missing:           {results['total_missing']}")
        lines.append(f"  Coverage:          {results['coverage_pct']:.1f}%")
        lines.append("")

        # Per-table coverage
        lines.append("COVERAGE BY TABLE:")
        lines.append("-" * 80)
        lines.append(f"{'Table':<30} {'Recommended':<15} {'Missing':<15} {'Coverage':<15}")
        lines.append("-" * 80)

        for table, stats in sorted(results["coverage_by_table"].items()):
            coverage = stats["coverage_pct"]
            status = "✅" if coverage == 100 else "❌" if coverage < 50 else "⚠️"
            lines.append(
                f"{table:<30} {stats['recommended']:<15} {stats['missing']:<15} " f"{status} {coverage:>5.1f}%"
            )

        lines.append("-" * 80)
        lines.append("")

        # Missing indexes
        if results["missing_indexes"]:
            lines.append(f"MISSING INDEXES ({len(results['missing_indexes'])}):")
            lines.append("-" * 80)

            for idx_info in results["missing_indexes"]:
                lines.append(f"  Table:     {idx_info['table']}")
                lines.append(f"  Columns:   {', '.join(idx_info['columns'])}")
                lines.append(f"  Rationale: {idx_info['rationale']}")
                lines.append(f"  Index:     {idx_info['index_name']}")
                lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def format_output_sql(self, results: dict[str, Any]) -> str:
        """Format results as SQL DDL statements.

        Args:
            results: Analysis results

        Returns:
            SQL DDL statements
        """
        lines = []
        lines.append("-- Database Index Recommendations for CEL Performance")
        lines.append(f"-- Database: {self.db_conn.dbname}")
        lines.append(f"-- Total Missing Indexes: {results['total_missing']}")
        lines.append(f"-- Coverage: {results['coverage_pct']:.1f}%")
        lines.append("")

        if results["missing_indexes"]:
            ddl_statements = self.generate_ddl(results["missing_indexes"])
            lines.extend(ddl_statements)
        else:
            lines.append("-- No missing indexes found!")
            lines.append("-- All recommended indexes already exist.")

        return "\n".join(lines)

    def format_output_json(self, results: dict[str, Any]) -> str:
        """Format results as JSON.

        Args:
            results: Analysis results

        Returns:
            JSON string
        """
        return json.dumps(results, indent=2)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze database indexes for CEL expression performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check existing index coverage
  %(prog)s --db openspp_db --check-existing

  # Generate CREATE INDEX DDL
  %(prog)s --db openspp_db --generate-ddl --output sql

  # Export to JSON file
  %(prog)s --db openspp_db --check-existing --output json --output-file indexes.json

Environment Variables:
  PGPASSWORD    Database password (optional)
  PGHOST        Database host (default: localhost)
  PGPORT        Database port (default: 5432)
  PGUSER        Database user (default: current user)
        """,
    )

    # Database connection args
    parser.add_argument("--db", required=True, help="Database name (required)")
    parser.add_argument("--user", default=os.getenv("PGUSER"), help="Database user (default: $PGUSER or current user)")
    parser.add_argument("--password", default=os.getenv("PGPASSWORD"), help="Database password (default: $PGPASSWORD)")
    parser.add_argument(
        "--host", default=os.getenv("PGHOST", "localhost"), help="Database host (default: $PGHOST or localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("PGPORT", "5432")), help="Database port (default: $PGPORT or 5432)"
    )

    # Analysis mode args
    parser.add_argument("--check-existing", action="store_true", help="Check existing index coverage")
    parser.add_argument(
        "--run-expressions", action="store_true", help="Run sample expressions and analyze queries (requires Odoo)"
    )
    parser.add_argument("--generate-ddl", action="store_true", help="Generate CREATE INDEX DDL for missing indexes")

    # Output args
    parser.add_argument(
        "--output", choices=["table", "sql", "json"], default="table", help="Output format (default: table)"
    )
    parser.add_argument("--output-file", help="Write output to file (optional)")

    args = parser.parse_args()

    # Validate args
    if not any([args.check_existing, args.run_expressions, args.generate_ddl]):
        parser.error("At least one analysis mode required: " "--check-existing, --run-expressions, or --generate-ddl")

    # Connect to database
    with DatabaseConnection(
        dbname=args.db,
        user=args.user,
        password=args.password,
        host=args.host,
        port=args.port,
    ) as db_conn:
        # Initialize CLI
        cli = IndexAnalysisCLI(db_conn)

        # Run analysis
        results = None

        if args.check_existing:
            results = cli.check_existing_indexes()

        if args.run_expressions:
            expr_results = cli.run_expression_analysis()
            if results:
                results["expression_analysis"] = expr_results
            else:
                results = expr_results

        # Format output
        if results:
            if args.output == "table":
                output = cli.format_output_table(results)
            elif args.output == "sql":
                output = cli.format_output_sql(results)
            elif args.output == "json":
                output = cli.format_output_json(results)
            else:
                output = str(results)

            # Write to file or stdout
            if args.output_file:
                with open(args.output_file, "w") as f:
                    f.write(output)
                _logger.info(f"Results written to: {args.output_file}")
            else:
                print(output)

        # Generate DDL if requested
        if args.generate_ddl and results and "missing_indexes" in results:
            if args.output != "sql":
                # Generate DDL separately
                ddl_output = cli.format_output_sql(results)
                if args.output_file:
                    ddl_file = args.output_file.replace(".json", ".sql")
                    with open(ddl_file, "w") as f:
                        f.write(ddl_output)
                    _logger.info(f"DDL written to: {ddl_file}")
                else:
                    print("\n" + "=" * 80)
                    print("DDL STATEMENTS:")
                    print("=" * 80)
                    print(ddl_output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        _logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
