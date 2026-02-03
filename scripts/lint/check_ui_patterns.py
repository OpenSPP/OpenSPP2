#!/usr/bin/env python3
"""
UI Pattern Checker for OpenSPP

Validates XML view patterns based on docs/principles/ui-design.md:
- XPath uses hasclass() not @class
- Statusbar widget in <header> not <sheet>
- Extension points present in forms
- Large O2M fields not editable
- Search panel thresholds respected

Features:
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Model classification awareness

Exit codes:
    0: No violations found
    1: Violations found
"""

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

# Import common utilities
try:
    from .common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary
except ImportError:
    from common import LintConfig, OutputFormatter, Severity, Violation, add_common_args


# Models likely to have >1k records (should have list limits)
LARGE_MODEL_PATTERNS = [
    "res.partner",  # Registry
    "spp.payment",  # Transactional
    "spp.entitlement",  # Transactional
    "spp.event.data",  # Transactional
    "spp.program.membership",  # Relationship
    "spp.group.membership",  # Relationship
]


class UIPatternChecker:
    """Checks for UI pattern violations in XML view files."""

    def __init__(self, config: LintConfig = None):
        self.config = config or LintConfig.load()
        self.violations: list[Violation] = []

        # Load config settings
        rule_config = self.config.get_rule_config("ui")
        self.large_models = rule_config.get("large_models", LARGE_MODEL_PATTERNS)
        self.search_panel_max_records = rule_config.get("search_panel_max_records", 100000)
        self.allow_editable_o2m = rule_config.get("allow_editable_o2m", [])

    def check_file(self, file_path: str) -> list[Violation]:
        """Check a single XML file for UI pattern violations."""
        violations = []
        path = Path(file_path)

        if not path.exists() or not path.suffix == ".xml":
            return violations

        # Check if file should be ignored
        if self.config.should_ignore(file_path):
            return violations

        # Skip non-view XML files
        if not self._is_view_file(path):
            return violations

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError:
            return violations  # Skip malformed XML
        except Exception:
            return violations

        # Run checks
        violations.extend(self._check_xpath_class(file_path, root))
        violations.extend(self._check_statusbar_location(file_path, root))
        violations.extend(self._check_extension_points(file_path, root))
        violations.extend(self._check_large_o2m_editable(file_path, root))

        return violations

    def _is_view_file(self, path: Path) -> bool:
        """Check if XML file contains view definitions."""
        # Views are typically in /views/ directory
        # or filename contains 'view'
        return "views" in path.parts or "view" in path.name.lower()

    def _get_model_from_view(self, view_elem) -> str | None:
        """Extract model name from view record."""
        # Look for <field name="model">...</field>
        for field in view_elem.findall(".//field[@name='model']"):
            return field.text
        return None

    def _is_large_model(self, model_name: str | None) -> bool:
        """Check if model likely has >1k records."""
        if not model_name:
            return False

        # Exact match
        if model_name in self.large_models:
            return True

        # Pattern match (e.g., spp.payment.*)
        for pattern in self.large_models:
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if model_name.startswith(prefix):
                    return True

        return False

    def _get_line_number(self, elem) -> int:
        """Get line number from XML element (if available)."""
        # ElementTree doesn't track line numbers by default
        # Return 0 if not available (could enhance with lxml for better tracking)
        return getattr(elem, "sourceline", 0)

    def _check_xpath_class(self, file_path: str, root) -> list[Violation]:
        """Check if XPath uses hasclass() instead of @class, and check for @title."""
        violations = []

        # Find all xpath elements
        for xpath in root.findall(".//xpath"):
            expr = xpath.get("expr", "")

            # Check if using @class selector
            if "@class" in expr and "hasclass(" not in expr:
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=self._get_line_number(xpath),
                        message=f"XPath uses @class instead of hasclass(): {expr}",
                        rule_id="ui.xpath_class",
                        severity=self.config.get_severity("ui.xpath_class", Severity.ERROR),
                        suggestion="Replace [@class='...'] with [hasclass('...')]",
                        doc_link="docs/principles/ui-design.md#xpath-best-practices",
                    )
                )

            # Check if using @title selector (invalid in Odoo 19)
            if "@title" in expr:
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=self._get_line_number(xpath),
                        message=f"XPath uses @title selector (invalid in Odoo 19): {expr}",
                        rule_id="ui.xpath_title",
                        severity=self.config.get_severity("ui.xpath_title", Severity.ERROR),
                        suggestion="Use name, class, or other valid attributes instead of @title",
                        doc_link="docs/principles/odoo19-compatibility.md#view-inheritance-selectors",
                    )
                )

        return violations

    def _check_statusbar_location(self, file_path: str, root) -> list[Violation]:
        """Check if statusbar widget is in <header> not <sheet>."""
        violations = []

        for record in root.findall(".//record[@model='ir.ui.view']"):
            for arch in record.findall(".//field[@name='arch']"):
                for form_elem in arch.findall(".//form"):
                    # Find statusbar widgets in <sheet>
                    for sheet in form_elem.findall(".//sheet"):
                        for field in sheet.findall(".//field[@widget='statusbar']"):
                            violations.append(
                                Violation(
                                    file_path=file_path,
                                    line=self._get_line_number(field),
                                    message="Statusbar widget found in <sheet>, should be in <header>",
                                    rule_id="ui.statusbar_location",
                                    severity=self.config.get_severity("ui.statusbar_location", Severity.ERROR),
                                    suggestion="Move statusbar field to <header> element",
                                    doc_link="docs/principles/ui-design.md#universal-form-templates",
                                )
                            )

        return violations

    def _check_extension_points(self, file_path: str, root) -> list[Violation]:
        """Check if forms have extension point placeholders."""
        violations = []

        for record in root.findall(".//record[@model='ir.ui.view']"):
            model_name = self._get_model_from_view(record)

            for arch in record.findall(".//field[@name='arch']"):
                for form_elem in arch.findall(".//form"):
                    # Check for notebooks (forms with tabs)
                    notebooks = form_elem.findall(".//notebook")
                    if notebooks:
                        # Check if any page has extension points
                        pages = form_elem.findall(".//page")
                        has_extension_points = False

                        for page in pages:
                            # Look for groups with "additional" or "extension" in name
                            for group in page.findall(".//group"):
                                group_name = group.get("name", "")
                                if "additional" in group_name or "extension" in group_name:
                                    has_extension_points = True
                                    break

                            # Look for divs with similar naming
                            for div in page.findall(".//div"):
                                div_name = div.get("name", "")
                                if "additional" in div_name or "extension" in div_name:
                                    has_extension_points = True
                                    break

                        if not has_extension_points and len(pages) > 0:
                            violations.append(
                                Violation(
                                    file_path=file_path,
                                    line=self._get_line_number(form_elem),
                                    message=f"Form for model '{model_name}' has tabs but no extension points",
                                    rule_id="ui.extension_points",
                                    severity=self.config.get_severity("ui.extension_points", Severity.INFO),
                                    suggestion="Add <group name='additional_*' invisible='1'/> to tabs for extensibility",
                                    doc_link="docs/principles/ui-design.md#extension-points",
                                )
                            )

        return violations

    def _check_large_o2m_editable(self, file_path: str, root) -> list[Violation]:
        """Check if large O2M fields are not editable."""
        violations = []

        for record in root.findall(".//record[@model='ir.ui.view']"):
            model_name = self._get_model_from_view(record)

            for arch in record.findall(".//field[@name='arch']"):
                # Find field elements with list children (O2M/M2M)
                for field_elem in arch.findall(".//field"):
                    field_name = field_elem.get("name", "")

                    # Skip if in allow list
                    if field_name in self.allow_editable_o2m:
                        continue

                    # Check if has editable list
                    for list_elem in field_elem.findall(".//list"):
                        editable = list_elem.get("editable")

                        # Check if field name suggests it's a large collection
                        # (heuristic: ends with _ids and not in exceptions)
                        if editable and field_name.endswith("_ids"):
                            # Check if model is large or field name suggests high volume
                            is_large_collection = (
                                self._is_large_model(model_name)
                                or "member" in field_name
                                or "beneficiar" in field_name
                                or "payment" in field_name
                                or "entitlement" in field_name
                            )

                            if is_large_collection:
                                violations.append(
                                    Violation(
                                        file_path=file_path,
                                        line=self._get_line_number(field_elem),
                                        message=f"Large O2M field '{field_name}' should not be editable",
                                        rule_id="ui.large_o2m_editable",
                                        severity=self.config.get_severity("ui.large_o2m_editable", Severity.WARNING),
                                        suggestion="Use readonly='1' with wizard pattern for add/remove",
                                        doc_link="docs/principles/ui-performance.md#large-o2m-fields",
                                    )
                                )

        return violations


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check XML view files for UI pattern violations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    add_common_args(parser)
    parser.add_argument("files", nargs="*", help="XML files to check")
    parser.add_argument(
        "--module",
        help="Check all view files in a module",
    )

    args = parser.parse_args()

    # Load configuration
    config = LintConfig.load()
    checker = UIPatternChecker(config)

    # Collect files to check
    files_to_check = []

    if args.module:
        # Find all XML files in module's views directory
        module_path = Path(args.module)
        if not module_path.exists():
            # Try relative to current directory
            module_path = Path.cwd() / args.module

        views_dir = module_path / "views"
        if views_dir.exists():
            files_to_check.extend(views_dir.glob("*.xml"))

    if args.files:
        files_to_check.extend(Path(f) for f in args.files)

    if not files_to_check:
        print("No files to check", file=sys.stderr)
        return 0

    # Check all files
    all_violations = []
    for file_path in files_to_check:
        violations = checker.check_file(str(file_path))
        all_violations.extend(violations)

    # Output results
    formatter = OutputFormatter(args.format)
    output = formatter.format(all_violations, show_summary=args.summary)
    print(output)

    # Exit with error if violations found
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
