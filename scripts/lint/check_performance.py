#!/usr/bin/env python3
"""
Performance Anti-Pattern Checker for OpenSPP

Detects common performance issues based on docs/principles/performance-scalability.md:
- Offset-based pagination (should use cursor-based)
- cr.commit() in loops (should use queue_job)
- N+1 query patterns (attribute access in loops without prefetch)

Features:
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Severity levels and configurable thresholds

Exit codes:
    0: No violations found
    1: Violations found
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Import common utilities
try:
    from .common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary
except ImportError:
    from common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary


class PerformanceChecker:
    """Checks for performance anti-patterns in Python files."""

    def __init__(self, config: LintConfig = None):
        self.config = config or LintConfig.load()
        self.violations: list[Violation] = []

        # Load config settings
        rule_config = self.config.get_rule_config("performance")
        self.n_plus_one_threshold = rule_config.get("n_plus_one_threshold", 1)

    def check_file(self, file_path: str) -> list[Violation]:
        """Check a single Python file for performance violations."""
        violations = []
        path = Path(file_path)

        if not path.exists() or not path.suffix == ".py":
            return violations

        # Check if file should be ignored
        if self.config.should_ignore(file_path):
            return violations

        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return violations
        except Exception:
            return violations

        # Check for offset-based pagination
        violations.extend(self._check_offset_pagination(file_path, content))

        # Check for cr.commit() in loops
        violations.extend(self._check_commit_in_loops(file_path, tree))

        # Check for potential N+1 queries
        violations.extend(self._check_n_plus_one(file_path, tree, content))

        return violations

    def _check_offset_pagination(self, file_path: str, content: str) -> list[Violation]:
        """Check for offset-based pagination anti-pattern."""
        violations = []
        lines = content.split("\n")

        # Pattern to match .search() with offset parameter
        offset_pattern = r"\.search\s*\([^)]*\boffset\s*="
        severity = self.config.get_severity("performance.offset_pagination", Severity.WARNING)

        for line_num, line in enumerate(lines, start=1):
            if re.search(offset_pattern, line):
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=line_num,
                        message="Offset-based pagination detected - use cursor-based pagination for large datasets",
                        rule_id="performance.offset_pagination",
                        severity=severity,
                        suggestion="Use cursor-based pagination with ID filtering instead",
                        doc_link="docs/principles/performance-scalability.md#pagination",
                    )
                )

        return violations

    def _check_commit_in_loops(self, file_path: str, tree: ast.AST) -> list[Violation]:
        """Check for cr.commit() inside loops."""
        violations = []
        severity = self.config.get_severity("performance.commit_in_loop", Severity.ERROR)

        class CommitInLoopVisitor(ast.NodeVisitor):
            def __init__(self):
                self.in_loop = False
                self.loop_depth = 0
                self.found_commits = []

            def visit_For(self, node):
                self.loop_depth += 1
                self.in_loop = True
                self.generic_visit(node)
                self.loop_depth -= 1
                if self.loop_depth == 0:
                    self.in_loop = False

            def visit_While(self, node):
                self.loop_depth += 1
                self.in_loop = True
                self.generic_visit(node)
                self.loop_depth -= 1
                if self.loop_depth == 0:
                    self.in_loop = False

            def visit_Call(self, node):
                if self.in_loop:
                    # Check for cr.commit() or self.env.cr.commit()
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == "commit":
                            # Check if it's cr.commit or env.cr.commit
                            value = node.func.value
                            if isinstance(value, ast.Attribute) and value.attr == "cr":
                                self.found_commits.append(node.lineno)
                            elif isinstance(value, ast.Name) and value.id == "cr":
                                self.found_commits.append(node.lineno)
                self.generic_visit(node)

        visitor = CommitInLoopVisitor()
        visitor.visit(tree)

        for line_num in visitor.found_commits:
            violations.append(
                Violation(
                    file_path=file_path,
                    line=line_num,
                    message="cr.commit() inside loop - use queue_job for batch processing instead",
                    rule_id="performance.commit_in_loop",
                    severity=severity,
                    suggestion="Use queue_job to process records asynchronously",
                    doc_link="docs/principles/performance-scalability.md#batch-processing-pattern",
                )
            )

        return violations

    def _check_n_plus_one(self, file_path: str, tree: ast.AST, content: str) -> list[Violation]:
        """Check for potential N+1 query patterns using AST analysis.

        This check is Odoo-aware and accounts for:
        - @api.depends decorators (Odoo prefetches these fields)
        - .mapped() calls for prefetching
        - Nested loop tracking
        """
        violations = []
        severity = self.config.get_severity("performance.n_plus_one", Severity.WARNING)

        # Common relational field suffixes that trigger N+1 queries
        relation_suffixes = ("_id", "_ids")
        # Common relational field names
        relation_fields = {
            "partner_id",
            "company_id",
            "user_id",
            "parent_id",
            "program_id",
            "cycle_id",
            "currency_id",
            "country_id",
        }

        # First pass: collect @api.depends info for each method
        method_depends = {}  # method_name -> set of dependency field paths

        class DependsCollector(ast.NodeVisitor):
            """Collect @api.depends decorator information."""

            def visit_FunctionDef(self, node):
                depends_fields = set()
                for decorator in node.decorator_list:
                    # Handle @api.depends("field1", "field2.subfield")
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == "depends":
                                for arg in decorator.args:
                                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                        depends_fields.add(arg.value)
                if depends_fields:
                    method_depends[node.name] = depends_fields
                self.generic_visit(node)

        DependsCollector().visit(tree)

        # Common ORM method names that don't cause N+1 when called on related objects
        orm_methods = {
            # CRUD operations
            "write",
            "create",
            "read",
            "update",
            "unlink",
            "copy",
            # Search/browse
            "search",
            "browse",
            "filtered",
            "mapped",
            "sorted",
            "exists",
            # Context modifiers
            "with_context",
            "with_company",
            "sudo",
            "with_user",
            "with_env",
            # Other common methods
            "ensure_one",
            "invalidate_cache",
            "flush",
            "refresh",
            "name_get",
            "name_search",
            "default_get",
        }

        class NPlusOneVisitor(ast.NodeVisitor):
            def __init__(self):
                self.loop_stack = []  # Stack of (loop_var, loop_start_line, has_prefetch)
                self.found_violations = []  # List of (line, loop_var, field_chain)
                self.prefetch_vars = set()  # Variables that have been prefetched
                self.current_method = None  # Track current method name
                self.current_method_depends = set()  # Dependencies of current method
                self.call_attrs = set()  # Attribute nodes that are Call functions

            def visit_FunctionDef(self, node):
                """Track the current method and its @api.depends fields."""
                old_method = self.current_method
                old_depends = self.current_method_depends

                self.current_method = node.name
                self.current_method_depends = method_depends.get(node.name, set())

                # Visit method body
                self.generic_visit(node)

                # Restore
                self.current_method = old_method
                self.current_method_depends = old_depends

            def visit_For(self, node):
                # Get the loop variable name
                loop_var = None
                if isinstance(node.target, ast.Name):
                    loop_var = node.target.id
                elif isinstance(node.target, ast.Tuple):
                    # Handle tuple unpacking: for a, b in items
                    for elt in node.target.elts:
                        if isinstance(elt, ast.Name):
                            loop_var = elt.id
                            break

                # Check if there's a .mapped() call in the iterable (prefetch pattern)
                has_prefetch = self._check_prefetch(node.iter)

                if loop_var:
                    self.loop_stack.append((loop_var, node.lineno, has_prefetch))

                # Visit the loop body
                for child in node.body:
                    self.visit(child)

                if loop_var:
                    self.loop_stack.pop()

            def visit_While(self, node):
                # For while loops, we don't have a clear loop variable
                # but we should still track nesting
                self.loop_stack.append((None, node.lineno, False))
                for child in node.body:
                    self.visit(child)
                self.loop_stack.pop()

            def _check_prefetch(self, node):
                """Check if a node contains a .mapped() call (prefetch pattern)."""
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == "mapped":
                            return True
                        # Recursively check the value
                        return self._check_prefetch(node.func.value)
                    elif isinstance(node.func, ast.Name):
                        # Check if it's a variable that was previously prefetched
                        return node.func.id in self.prefetch_vars
                elif isinstance(node, ast.Name):
                    return node.id in self.prefetch_vars
                return False

            def _is_covered_by_depends(self, field_chain: list) -> bool:
                """Check if a field chain is covered by @api.depends.

                For example, if @api.depends("cycle_id.program_id.journal_id"),
                then accessing record.cycle_id.program_id.journal_id.id is covered.
                """
                if not self.current_method_depends:
                    return False

                # Build the field path (excluding the loop variable)
                field_path = ".".join(field_chain)

                for depends_field in self.current_method_depends:
                    # Check if the accessed field starts with a depends field
                    # e.g., "cycle_id.program_id" is covered by depends on "cycle_id.program_id.journal_id"
                    if field_path.startswith(depends_field) or depends_field.startswith(field_path.split(".")[0]):
                        return True
                    # Also check partial matches for nested fields
                    # e.g., accessing "cycle_id.program_id.name" when depends has "cycle_id.program_id"
                    depends_parts = depends_field.split(".")
                    field_parts = field_path.split(".")
                    if len(field_parts) >= len(depends_parts):
                        if field_parts[: len(depends_parts)] == depends_parts:
                            return True

                return False

            def visit_Call(self, node):
                """Track Attribute nodes that are used as Call functions."""
                if isinstance(node.func, ast.Attribute):
                    self.call_attrs.add(id(node.func))
                self.generic_visit(node)

            def visit_Attribute(self, node):
                """Check for chained attribute access on loop variables."""
                if not self.loop_stack:
                    self.generic_visit(node)
                    return

                # Skip if this attribute is being called as a method
                if id(node) in self.call_attrs:
                    self.generic_visit(node)
                    return

                # Build the attribute chain
                chain = []
                current = node
                while isinstance(current, ast.Attribute):
                    chain.append(current.attr)
                    current = current.value

                # Check if the base is a loop variable
                if isinstance(current, ast.Name):
                    var_name = current.id
                    chain.reverse()  # Now chain is [field1, field2, ...]

                    # Skip if the last attribute is an ORM method name
                    if chain and chain[-1] in orm_methods:
                        self.generic_visit(node)
                        return

                    # Check each loop in the stack
                    for loop_var, loop_line, has_prefetch in self.loop_stack:
                        if var_name == loop_var and len(chain) >= 2:
                            first_field = chain[0]
                            # Check if accessing a relational field and then its attribute
                            if first_field.endswith(relation_suffixes) or first_field in relation_fields:
                                # Skip if prefetched via .mapped() or covered by @api.depends
                                if has_prefetch:
                                    break
                                if self._is_covered_by_depends(chain):
                                    break
                                self.found_violations.append((node.lineno, loop_var, ".".join([var_name] + chain)))
                                break

                self.generic_visit(node)

            def visit_Assign(self, node):
                """Track variables that receive prefetched data."""
                # Check for patterns like: prefetched = records.mapped('field')
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr == "mapped":
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    self.prefetch_vars.add(target.id)
                self.generic_visit(node)

        visitor = NPlusOneVisitor()
        visitor.visit(tree)

        # Deduplicate violations (same line might be flagged multiple times)
        seen_lines = set()
        for line_num, loop_var, field_chain in visitor.found_violations:
            if line_num not in seen_lines:
                seen_lines.add(line_num)
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=line_num,
                        message=f"Potential N+1 query: accessing '{field_chain}' in loop without prefetch",
                        rule_id="performance.n_plus_one",
                        severity=severity,
                        suggestion="Use .mapped() before the loop or add to @api.depends",
                        doc_link="docs/principles/performance-scalability.md#avoid-n1-queries",
                    )
                )

        return violations

    def check_files(self, file_paths: list[str]) -> int:
        """Check multiple files."""
        for file_path in file_paths:
            violations = self.check_file(file_path)
            self.violations.extend(violations)
        return len(self.violations)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for performance anti-patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s spp_registry_base/models/*.py
  %(prog)s --check-only spp_programs/models/program.py
  %(prog)s --format json spp_programs/models/*.py

Checks:
  - Offset pagination: .search(..., offset=...) should use cursor-based
  - Commit in loops: cr.commit() in loops should use queue_job
  - N+1 queries: Related field access in loops without prefetch

See docs/principles/performance-scalability.md for guidelines.
""",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Python files to check",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report issues without failing (exit code 0)",
    )

    # Add common arguments
    add_common_args(parser)

    args = parser.parse_args()

    # Load config
    config = LintConfig.load(args.config) if args.config else LintConfig.load()

    # Run checker
    checker = PerformanceChecker(config)
    checker.check_files(args.files)

    # Filter by severity if specified
    violations = checker.violations
    if args.severity != "all":
        min_severity = Severity(args.severity)
        severity_order = [Severity.INFO, Severity.WARNING, Severity.ERROR]
        min_index = severity_order.index(min_severity)
        violations = [v for v in violations if severity_order.index(v.severity) >= min_index]

    # Output results
    formatter = OutputFormatter(args.format)
    output = formatter.format(violations, show_summary=not args.summary)
    print(output)

    if args.summary:
        print_summary(violations)

    # Determine exit code
    if args.check_only:
        return 0

    has_errors = any(v.severity == Severity.ERROR for v in violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
