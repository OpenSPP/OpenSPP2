#!/usr/bin/env python3
"""
Logger Setup Checker for OpenSPP

Validates that Python files using logging follow the standard pattern:
    import logging
    _logger = logging.getLogger(__name__)

Also checks for:
- Direct use of print() statements (should use _logger instead)
- Potential PII in log messages

Features:
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Severity levels (error, warning, info)

Based on docs/principles/error-handling.md

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


# Fields that might contain PII - warn if logged directly
PII_FIELD_PATTERNS = [
    r"\.name\b",
    r"\.national_id\b",
    r"\.phone\b",
    r"\.mobile\b",
    r"\.email\b",
    r"\.address\b",
    r"\.street\b",
    r"\.birth_date\b",
    r"\.ssn\b",
    r"\.tax_id\b",
    r"\.bank_account\b",
    r"\.passport\b",
]


class LoggerChecker:
    """Checks logger usage patterns in Python files."""

    def __init__(self, check_pii: bool = True, check_print: bool = False, config: LintConfig = None):
        self.check_pii = check_pii
        self.check_print = check_print  # Already handled by pylint, optional here
        self.config = config or LintConfig.load()
        self.violations: list[Violation] = []

    def check_file(self, file_path: str) -> list[Violation]:
        """Check a single Python file for logger violations."""
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

        # Check if file uses logging
        uses_logging = self._uses_logging(tree)
        has_logger_setup = self._has_logger_setup(content)

        # If file uses logging but doesn't have proper setup
        if uses_logging and not has_logger_setup:
            severity = self.config.get_severity("logger.missing_setup", Severity.WARNING)
            violations.append(
                Violation(
                    file_path=file_path,
                    line=1,
                    message="File uses logging but missing '_logger = logging.getLogger(__name__)'",
                    rule_id="logger.missing_setup",
                    severity=severity,
                    suggestion="Add: import logging; _logger = logging.getLogger(__name__)",
                    doc_link="docs/principles/error-handling.md#setup",
                )
            )

        # Check for PII in log messages
        if self.check_pii:
            violations.extend(self._check_pii_in_logs(file_path, content))

        # Check for print statements (optional, usually handled by pylint)
        if self.check_print:
            violations.extend(self._check_print_statements(file_path, tree))

        return violations

    def _uses_logging(self, tree: ast.AST) -> bool:
        """Check if file uses logging calls."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for _logger.info(), _logger.warning(), etc.
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "_logger":
                            return True
                    # Also check logging.info(), etc.
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "logging":
                            if node.func.attr in ["debug", "info", "warning", "error", "critical", "exception"]:
                                return True
        return False

    def _has_logger_setup(self, content: str) -> bool:
        """Check if file has proper logger setup."""
        # Look for the standard pattern
        pattern = r"_logger\s*=\s*logging\.getLogger\s*\(\s*__name__\s*\)"
        return bool(re.search(pattern, content))

    def _check_pii_in_logs(self, file_path: str, content: str) -> list[Violation]:
        """Check for potential PII in log messages."""
        violations = []
        lines = content.split("\n")
        severity = self.config.get_severity("logger.pii_in_log", Severity.WARNING)

        # Pattern to match logger calls
        logger_pattern = r"_logger\.(debug|info|warning|error|critical|exception)\s*\("

        for line_num, line in enumerate(lines, start=1):
            if re.search(logger_pattern, line):
                # Check for PII field access in the log line
                for pii_pattern in PII_FIELD_PATTERNS:
                    if re.search(pii_pattern, line):
                        # Extract the field name for the message
                        match = re.search(pii_pattern, line)
                        if match:
                            field = match.group(0).lstrip(".")
                            violations.append(
                                Violation(
                                    file_path=file_path,
                                    line=line_num,
                                    message=f"Potential PII in log message: '{field}' - use record.id instead",
                                    rule_id="logger.pii_in_log",
                                    severity=severity,
                                    suggestion=f"Replace .{field} with .id in log messages",
                                    doc_link="docs/principles/error-handling.md#pii-protection",
                                )
                            )
                            break  # Only report once per line

        return violations

    def _check_print_statements(self, file_path: str, tree: ast.AST) -> list[Violation]:
        """Check for print() statements (should use _logger instead)."""
        violations = []
        severity = self.config.get_severity("logger.use_print", Severity.INFO)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    violations.append(
                        Violation(
                            file_path=file_path,
                            line=node.lineno,
                            message="Use '_logger' instead of 'print()' for output",
                            rule_id="logger.use_print",
                            severity=severity,
                            suggestion="Replace print() with _logger.info() or _logger.debug()",
                            doc_link="docs/principles/error-handling.md#logging-standards",
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
        description="Check logger setup and usage patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s spp_registry_base/models/*.py
  %(prog)s --check-print spp_programs/models/program.py
  %(prog)s --no-pii-check file.py
  %(prog)s --format json spp_grm/models/*.py

Checks:
  - Logger setup: _logger = logging.getLogger(__name__)
  - PII in logs: Warns about logging sensitive fields
  - Print statements: Optional check for print() usage

See docs/principles/error-handling.md for guidelines.
""",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Python files to check",
    )
    parser.add_argument(
        "--no-pii-check",
        action="store_true",
        help="Disable PII in logs check",
    )
    parser.add_argument(
        "--check-print",
        action="store_true",
        help="Also check for print() statements (usually handled by pylint)",
    )

    # Add common arguments
    add_common_args(parser)

    args = parser.parse_args()

    # Load config
    config = LintConfig.load(args.config) if args.config else LintConfig.load()

    # Run checker
    checker = LoggerChecker(
        check_pii=not args.no_pii_check,
        check_print=args.check_print,
        config=config,
    )
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

    # Return appropriate exit code
    has_errors = any(v.severity == Severity.ERROR for v in violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
