#!/usr/bin/env python3
"""
OpenSPP Unified Lint Runner

Runs all OpenSPP linting checks in a single command with combined output.

Checks included:
- Naming conventions (modules, models, fields)
- XML ID patterns
- ACL file existence
- Performance anti-patterns
- Logger setup and PII
- UI patterns (list limits, sample data, XPath, statusbar, extension points)

Features:
- Run all or specific checks
- Combined output in multiple formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Summary statistics

Usage:
    # Run all checks
    openspp-lint

    # Run specific checks
    openspp-lint --check naming xml_ids

    # Run on specific files/modules
    openspp-lint --module spp_programs

    # Output in different formats
    openspp-lint --format json
"""

import argparse
import sys
from pathlib import Path

# Import common utilities
try:
    from .check_acl import ACLChecker
    from .check_logger import LoggerChecker
    from .check_naming import NamingChecker
    from .check_performance import PerformanceChecker
    from .check_ui_patterns import UIPatternChecker
    from .check_xml_ids import XMLValidator, find_xml_files_in_module
    from .common import LintConfig, OutputFormatter, Severity, Violation, get_summary_stats, print_summary
except ImportError:
    from check_acl import ACLChecker
    from check_logger import LoggerChecker
    from check_naming import NamingChecker
    from check_performance import PerformanceChecker
    from check_ui_patterns import UIPatternChecker
    from check_xml_ids import XMLValidator
    from common import LintConfig, OutputFormatter, Severity, Violation, print_summary


AVAILABLE_CHECKS = ["naming", "xml_ids", "acl", "performance", "logger", "ui"]


class UnifiedLinter:
    """Runs all OpenSPP linting checks."""

    def __init__(self, config: LintConfig = None, checks: list[str] = None):
        self.config = config or LintConfig.load()
        self.checks = checks or AVAILABLE_CHECKS
        self.violations: list[Violation] = []
        self.check_results: dict[str, list[Violation]] = {}

    def run_all(self, root_dir: str = ".", module: str = None) -> list[Violation]:
        """Run all configured checks."""
        root = Path(root_dir)

        # Collect files
        py_files = []
        xml_files = []

        if module:
            module_path = root / module
            if module_path.exists():
                py_files = list(module_path.glob("**/*.py"))
                xml_files = list(module_path.glob("**/*.xml"))
        else:
            # Find all modules
            for manifest in root.glob("*/__manifest__.py"):
                module_path = manifest.parent
                # Skip tests and migrations
                py_files.extend(
                    [f for f in module_path.glob("**/*.py") if "/tests/" not in str(f) and "/migrations/" not in str(f)]
                )
                xml_files.extend(
                    [
                        f
                        for f in module_path.glob("**/*.xml")
                        if "/tests/" not in str(f) and "/data/" not in str(f) and "/demo/" not in str(f)
                    ]
                )

        py_file_paths = [str(f) for f in py_files]
        xml_file_paths = [str(f) for f in xml_files]

        # Run naming check
        if "naming" in self.checks and py_file_paths:
            self._run_naming_check(root_dir, py_file_paths)

        # Run XML ID check
        if "xml_ids" in self.checks and xml_file_paths:
            self._run_xml_id_check(xml_file_paths)

        # Run ACL check
        if "acl" in self.checks:
            self._run_acl_check(root_dir, module)

        # Run performance check
        if "performance" in self.checks and py_file_paths:
            self._run_performance_check(py_file_paths)

        # Run logger check
        if "logger" in self.checks and py_file_paths:
            self._run_logger_check(py_file_paths)

        # Run UI patterns check
        if "ui" in self.checks and xml_file_paths:
            self._run_ui_check(xml_file_paths)

        return self.violations

    def _run_naming_check(self, root_dir: str, files: list[str]):
        """Run naming convention checks."""
        checker = NamingChecker(root_dir=root_dir, config=self.config)
        checker.check_files(files)
        # Also check module names
        module_violations = checker.check_module_names()
        checker.violations.extend(module_violations)
        self.check_results["naming"] = checker.violations
        self.violations.extend(checker.violations)

    def _run_xml_id_check(self, files: list[str]):
        """Run XML ID checks."""
        validator = XMLValidator(config=self.config)
        for file_path in files:
            validator.validate_file(Path(file_path))
        self.check_results["xml_ids"] = validator.violations
        self.violations.extend(validator.violations)

    def _run_acl_check(self, root_dir: str, module: str = None):
        """Run ACL file checks."""
        if module:
            # Check only the specific module
            module_path = Path(root_dir) / module
            if module_path.exists():
                checker = ACLChecker(str(module_path.parent), self.config)
                # Filter to only check this module
                all_violations = checker.check_all_modules()
                checker.violations = [v for v in checker.violations if module in v.file_path]
        else:
            checker = ACLChecker(root_dir, self.config)
            checker.check_all_modules()
        self.check_results["acl"] = checker.violations
        self.violations.extend(checker.violations)

    def _run_performance_check(self, files: list[str]):
        """Run performance anti-pattern checks."""
        checker = PerformanceChecker(self.config)
        checker.check_files(files)
        self.check_results["performance"] = checker.violations
        self.violations.extend(checker.violations)

    def _run_logger_check(self, files: list[str]):
        """Run logger setup checks."""
        checker = LoggerChecker(config=self.config)
        checker.check_files(files)
        self.check_results["logger"] = checker.violations
        self.violations.extend(checker.violations)

    def _run_ui_check(self, files: list[str]):
        """Run UI pattern checks."""
        checker = UIPatternChecker(config=self.config)
        for file_path in files:
            violations = checker.check_file(file_path)
            checker.violations.extend(violations)
        self.check_results["ui"] = checker.violations
        self.violations.extend(checker.violations)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OpenSPP Unified Lint Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run all checks
  %(prog)s --check naming xml_ids    # Run specific checks
  %(prog)s --module spp_programs     # Check specific module
  %(prog)s --format json             # Output in JSON format
  %(prog)s --summary                 # Show summary statistics

Available checks:
  naming      - Module, model, and field naming conventions
  xml_ids     - XML ID naming patterns
  acl         - ACL file existence
  performance - Performance anti-patterns
  logger      - Logger setup and PII in logs
  ui          - UI patterns (list limits, sample data, XPath, statusbar, extension points)

See scripts/lint/README.md for documentation.
""",
    )
    parser.add_argument(
        "--check",
        nargs="+",
        choices=AVAILABLE_CHECKS,
        help=f"Specific checks to run (default: all). Choices: {', '.join(AVAILABLE_CHECKS)}",
    )
    parser.add_argument(
        "--module",
        help="Check only the specified module",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show detailed summary statistics",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to .openspp-lint.yaml config file",
    )
    parser.add_argument(
        "--severity",
        choices=["error", "warning", "info", "all"],
        default="all",
        help="Minimum severity to report (default: all)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report issues without failing (exit code 0)",
    )

    args = parser.parse_args()

    # Load config
    config = LintConfig.load(args.config) if args.config else LintConfig.load()

    # Run linter
    checks = args.check or AVAILABLE_CHECKS
    linter = UnifiedLinter(config=config, checks=checks)
    linter.run_all(root_dir=args.root, module=args.module)

    # Filter by severity if specified
    violations = linter.violations
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

        # Show breakdown by check
        print("\n--- By Check ---")
        for check_name, check_violations in linter.check_results.items():
            filtered = [v for v in check_violations if v in violations]
            if filtered:
                print(f"  {check_name}: {len(filtered)} violation(s)")

    # Determine exit code
    if args.check_only:
        return 0

    has_errors = any(v.severity == Severity.ERROR for v in violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
