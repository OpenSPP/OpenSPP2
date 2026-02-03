#!/usr/bin/env python3
"""
Check that all Odoo modules have required ir.model.access.csv files.

This script scans for Odoo modules (directories with __manifest__.py) and
verifies that each installable module has a security/ir.model.access.csv file.

Features:
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Severity levels (error for regular modules, warning for demo modules)
"""

import argparse
import ast
import sys
from pathlib import Path

# Import common utilities
try:
    from .common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary
except ImportError:
    from common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary


def is_installable_module(manifest_path):
    """
    Check if module is installable by parsing its manifest.

    Args:
        manifest_path: Path to __manifest__.py file

    Returns:
        bool: True if module is installable, False otherwise
    """
    try:
        with open(manifest_path, encoding="utf-8") as f:
            content = f.read()
            # Parse the manifest as Python dict
            manifest = ast.literal_eval(content)
            # Default is installable: True if not specified
            return manifest.get("installable", True)
    except Exception as e:
        print(f"WARNING: Could not parse manifest {manifest_path}: {e}", file=sys.stderr)
        return True  # Assume installable if we can't parse


def is_demo_module(module_path):
    """
    Check if module is a demo module (ends with _demo).

    Args:
        module_path: Path object for the module directory

    Returns:
        bool: True if module is a demo module
    """
    return module_path.name.endswith("_demo")


class ACLChecker:
    """Checks that Odoo modules have ACL files."""

    def __init__(self, root_dir: str = ".", config: LintConfig = None):
        self.root = Path(root_dir)
        self.config = config or LintConfig.load()
        self.violations: list[Violation] = []

    def check_all_modules(self) -> list[Violation]:
        """
        Check all Odoo modules for ir.model.access.csv files.

        Returns:
            List of violations found
        """
        # Find all modules (directories with __manifest__.py)
        manifest_files = list(self.root.glob("**/__manifest__.py"))

        if not manifest_files:
            return []

        for manifest_path in manifest_files:
            module_path = manifest_path.parent

            # Skip non-installable modules
            if not is_installable_module(manifest_path):
                continue

            # Skip ignored files
            try:
                relative_path = str(module_path.relative_to(self.root))
            except ValueError:
                relative_path = str(module_path)

            if self.config.should_ignore(relative_path):
                continue

            # Check for ACL file
            acl_path = module_path / "security" / "ir.model.access.csv"

            if not acl_path.exists():
                module_name = module_path.name

                # Demo modules get warnings, others get errors
                if is_demo_module(module_path):
                    severity = Severity.WARNING
                else:
                    severity = self.config.get_severity("acl.missing_file", Severity.ERROR)

                self.violations.append(
                    Violation(
                        file_path=relative_path,
                        line=0,
                        message=f"Missing ir.model.access.csv in module '{module_name}'",
                        rule_id="acl.missing_file",
                        severity=severity,
                        suggestion=f"Create security/ir.model.access.csv for {module_name}",
                        doc_link="docs/principles/access-rights.md",
                    )
                )

        return self.violations


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Check that all Odoo modules have required ir.model.access.csv files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Check current directory
  %(prog)s --root /path/to/modules
  %(prog)s --check-only       # Report only, don't fail
  %(prog)s --format json      # Output in JSON format

Exit codes:
  0 - All modules have ACL files (or --check-only)
  1 - One or more modules missing ACL files
""",
    )
    parser.add_argument("--check-only", action="store_true", help="Only report issues without failing (exit code 0)")
    parser.add_argument("--root", default=".", help="Root directory to scan (default: current directory)")

    # Add common arguments
    add_common_args(parser)

    args = parser.parse_args()

    # Load config
    config = LintConfig.load(args.config) if args.config else LintConfig.load()

    # Run checker
    checker = ACLChecker(args.root, config)
    checker.check_all_modules()

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
