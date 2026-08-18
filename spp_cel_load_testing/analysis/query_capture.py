# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""SQL Query Capture Module.

Provides a thread-safe context manager to intercept and capture SQL queries
executed during CEL expression evaluation. Extracts query metadata including
tables and columns for performance analysis.
"""

import logging
import re
import threading
from contextlib import contextmanager
from typing import Any

_logger = logging.getLogger(__name__)


class QueryCapture:
    """Thread-safe SQL query interceptor for Odoo cursor operations.

    Intercepts Cursor.execute() calls to capture SELECT queries and their metadata.
    Stores query text, parameters, and extracted table/column information.
    """

    def __init__(self):
        """Initialize query capture storage."""
        self.queries: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._original_execute = None
        self._capture_enabled = False

    def _extract_tables(self, query: str) -> list[str]:
        """Extract table names from SQL query using regex.

        Args:
            query: SQL query text

        Returns:
            List of table names found in the query
        """
        tables = []

        # Pattern for FROM clause: FROM table_name or FROM schema.table_name
        from_pattern = r'\bFROM\s+(?:"?(\w+)"?\."?(\w+)"?|"?(\w+)"?)'
        from_matches = re.finditer(from_pattern, query, re.IGNORECASE)
        for match in from_matches:
            # Group 2 is table name when schema is present, Group 3 when not
            table = match.group(2) or match.group(3)
            if table:
                tables.append(table)

        # Pattern for JOIN clauses
        join_pattern = r'\bJOIN\s+(?:"?(\w+)"?\."?(\w+)"?|"?(\w+)"?)'
        join_matches = re.finditer(join_pattern, query, re.IGNORECASE)
        for match in join_matches:
            table = match.group(2) or match.group(3)
            if table:
                tables.append(table)

        return list(set(tables))  # Remove duplicates

    def _extract_columns(self, query: str) -> list[str]:
        """Extract column names from SQL query WHERE clause.

        Args:
            query: SQL query text

        Returns:
            List of column names found in WHERE conditions
        """
        columns = []

        # Pattern for columns in WHERE clause: column_name = or column_name IN, etc.
        where_pattern = r"\bWHERE\s+(.+?)(?:ORDER BY|GROUP BY|LIMIT|;|$)"
        where_match = re.search(where_pattern, query, re.IGNORECASE | re.DOTALL)

        if where_match:
            where_clause = where_match.group(1)
            # Extract column references (handle table.column and just column)
            col_pattern = r'(?:"?(\w+)"?\."?(\w+)"?|"?(\w+)"?)\s*(?:=|<|>|IN|LIKE|IS)'
            col_matches = re.finditer(col_pattern, where_clause, re.IGNORECASE)
            for match in col_matches:
                # Group 2 is column when table.column, Group 3 is just column
                column = match.group(2) or match.group(3)
                if column and column.upper() not in ("NULL", "TRUE", "FALSE"):
                    columns.append(column)

        return list(set(columns))

    def _intercepted_execute(self, original_method):
        """Create interceptor wrapper for cursor.execute().

        Args:
            original_method: The original execute method to wrap

        Returns:
            Wrapped execute method that captures queries
        """

        def wrapper(query, params=None):
            # Call original method first
            result = original_method(query, params)

            # Capture SELECT queries only if enabled
            if self._capture_enabled and isinstance(query, str):
                query_upper = query.strip().upper()
                if query_upper.startswith("SELECT"):
                    with self._lock:
                        try:
                            tables = self._extract_tables(query)
                            columns = self._extract_columns(query)

                            self.queries.append(
                                {
                                    "query": query,
                                    "params": params,
                                    "tables": tables,
                                    "columns": columns,
                                }
                            )
                        except Exception as e:
                            _logger.debug("Failed to parse query for capture: %s", e, exc_info=False)

            return result

        return wrapper

    def start_capture(self, cursor):
        """Start capturing queries on the given cursor.

        Args:
            cursor: Odoo database cursor to intercept
        """
        with self._lock:
            if not self._capture_enabled:
                self._original_execute = cursor.execute
                cursor.execute = self._intercepted_execute(self._original_execute)
                self._capture_enabled = True
                _logger.debug("Query capture started")

    def stop_capture(self, cursor):
        """Stop capturing queries and restore original cursor.execute.

        Args:
            cursor: Odoo database cursor to restore
        """
        with self._lock:
            if self._capture_enabled and self._original_execute:
                cursor.execute = self._original_execute
                self._original_execute = None
                self._capture_enabled = False
                _logger.debug("Query capture stopped. Captured %d queries", len(self.queries))

    def get_queries(self) -> list[dict[str, Any]]:
        """Get all captured queries.

        Returns:
            List of query dictionaries with query, params, tables, columns
        """
        with self._lock:
            return list(self.queries)

    def clear(self):
        """Clear all captured queries."""
        with self._lock:
            self.queries.clear()

    def get_query_stats(self) -> dict[str, Any]:
        """Get statistics about captured queries.

        Returns:
            Dictionary with query count, unique tables, unique columns
        """
        with self._lock:
            all_tables = set()
            all_columns = set()

            for query_info in self.queries:
                all_tables.update(query_info.get("tables", []))
                all_columns.update(query_info.get("columns", []))

            return {
                "total_queries": len(self.queries),
                "unique_tables": len(all_tables),
                "unique_columns": len(all_columns),
                "tables": sorted(list(all_tables)),
                "columns": sorted(list(all_columns)),
            }


@contextmanager
def capture_queries(cursor):
    """Context manager to capture SQL queries during a code block.

    Usage:
        with capture_queries(cr) as capture:
            # Execute code that runs queries
            do_something()

        # Access captured queries
        queries = capture.get_queries()

    Args:
        cursor: Odoo database cursor

    Yields:
        QueryCapture instance with captured queries
    """
    capture = QueryCapture()
    try:
        capture.start_capture(cursor)
        yield capture
    finally:
        capture.stop_capture(cursor)
