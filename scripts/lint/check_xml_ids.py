#!/usr/bin/env python3
"""
XML ID Naming Convention Checker for OpenSPP

Validates that XML IDs in Odoo XML files follow the naming conventions defined in
docs/principles/naming-conventions.md

Based on ADR-004 and OpenSPP naming standards:
- Views: view_{model}_form, view_{model}_list/tree
- Actions: action_{model}
- Menus: menu_{model}
- Security groups: group_{domain}_{level}
- Categories: category_spp_{domain}
- Privileges: privilege_{domain} or privilege_{domain}_{qualifier}
- Record rules: rule_{model}_{purpose}

Features:
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Severity levels (error, warning, info)

Usage:
    python scripts/lint/check_xml_ids.py [--strict] <file1.xml> [<file2.xml> ...]
    python scripts/lint/check_xml_ids.py [--strict] --module <module_name>

Exit codes:
    0 - No violations found
    1 - Violations found
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# Try to use lxml for accurate line numbers, fall back to ElementTree
try:
    from lxml import etree as ET

    USING_LXML = True
except ImportError:
    import xml.etree.ElementTree as ET

    USING_LXML = False

# Import common utilities
try:
    from .common import (
        LintConfig,
        OutputFormatter,
        Severity,
        Violation,
        add_common_args,
        print_summary,
    )
except ImportError:
    from common import (
        LintConfig,
        OutputFormatter,
        Severity,
        Violation,
        add_common_args,
        print_summary,
    )


# Model-based naming patterns
NAMING_RULES = {
    "ir.ui.view": {
        "patterns": [
            r"^view_[a-z0-9_]+_(form|list|tree|kanban|search|graph|pivot|calendar|gantt|activity|gis)$",
            r"^view_[a-z0-9_]+_(form|list|tree|kanban|search|graph|pivot|calendar|gantt|activity|gis)_[a-z0-9_]+$",
            r"^[a-z0-9_]+_(view_)?(form|list|tree|kanban|search|graph|pivot|calendar|gantt|activity|gis)$",  # noqa: E501 {model}_{type} or {model}_view_{type}
        ],
        "description": "View IDs should follow 'view_{model}_{type}' or '{model}_{type}' pattern",
        "examples": ["view_spp_program_form", "res_partner_tree", "ticket_view_form"],
    },
    "ir.actions.act_window": {
        "patterns": [
            r"^action_[a-z0-9_]+$",
            r"^action_[a-z0-9_]+_[a-z0-9_]+$",
            r"^[a-z0-9_]+_action$",  # Also accept {model}_action pattern
            r"^[a-z0-9_]+_action_[a-z0-9_]+$",  # Also accept {model}_action_{purpose}
        ],
        "description": "Action IDs should follow 'action_{model}' or '{model}_action' pattern",
        "examples": ["action_spp_program", "spp_grm_ticket_action"],
    },
    "ir.actions.act_window.view": {
        "patterns": [
            r"^action_[a-z0-9_]+_(form|list|tree|kanban|graph|pivot|calendar|gantt|activity|gis)_view$",
        ],
        "description": "Action view IDs should follow 'action_{model}_{type}_view' pattern",
        "examples": [
            "action_generate_program_form_view",
            "action_spp_program_list_view",
        ],
    },
    "ir.ui.menu": {
        "patterns": [
            r"^menu_[a-z0-9_]+$",
            r"^menu_[a-z0-9_]+_[a-z0-9_]+$",
        ],
        "description": "Menu IDs should follow 'menu_{model}' or 'menu_{model}_{purpose}' pattern",
        "examples": ["menu_spp_program", "menu_generate_program_data"],
    },
    "res.groups": {
        "patterns": [
            r"^group_[a-z0-9_]+_(viewer|officer|manager|admin|supervisor|approver|rejector|user|worker|requestor|validator|distributor|generator|registrar|reset|get|post|auditor|runner|editor|assessor|validator_hq)$",
            r"^group_[a-z0-9_]+_(read|write|create|delete|approve|reject)$",
            r"^group_[a-z0-9_]+_restrict_[a-z0-9_]+$",  # Technical restriction groups
            r"^group_spp_[a-z0-9_]+_(agent|validator|applicator|administrator|external_api|local_validator|hq_validator)$",  # noqa: E501 Module-specific roles
            r"^category_[a-z0-9_]+$",
        ],
        "description": "Group IDs should follow 'group_{domain}_{level}' or 'category_{domain}' pattern",
        "examples": [
            "group_registry_officer",
            "group_programs_approver",
            "category_spp_registry",
        ],
        "allowed_deprecated": True,  # Allow deprecated groups for backward compatibility
    },
    "ir.module.category": {
        "patterns": [
            r"^category_spp$",  # Main category
            r"^category_spp_[a-z0-9_]+$",
            r"^module_[a-z0-9_]+_category$",  # Alternate pattern: module_{name}_category
            r"^[a-z0-9_]+_category$",  # Generic {name}_category
        ],
        "description": "Category IDs should follow 'category_spp_{domain}' or '{module}_category' pattern",
        "examples": [
            "category_spp",
            "category_spp_registry",
            "module_openspp_grm_category",
        ],
    },
    "res.groups.privilege": {
        "patterns": [
            # Consolidated privilege: single privilege per domain (privilege_{domain})
            r"^privilege_[a-z0-9_]+$",
            # Qualified privilege: multi-category domains (privilege_{domain}_{qualifier})
            r"^privilege_[a-z0-9_]+_(viewer|officer|manager|admin|supervisor|approver|rejector|user|requestor|validator|distributor|generator|registrar|reset|get|post|auditor|runner|editor|specialized)$",
        ],
        "description": "Privilege IDs should follow 'privilege_{domain}' or 'privilege_{domain}_{qualifier}' pattern",
        "examples": ["privilege_registry", "privilege_programs_specialized"],
    },
    "ir.rule": {
        "patterns": [
            r"^rule_[a-z0-9_]+_[a-z0-9_]+$",
        ],
        "description": "Rule IDs should follow 'rule_{model}_{purpose}' pattern",
        "examples": ["rule_spp_grm_ticket_viewer", "rule_partner_company"],
    },
}

# Patterns that are exceptions (e.g., for menus, actions that don't correspond to models)
EXCEPTION_PATTERNS = [
    r"^.*_root$",  # Root menus
    r"^.*_menu_root$",  # Root menus
    r"^.*_configuration_menu.*$",  # Configuration menus
    r"^.*_main$",  # Main menus/actions
    r"^seq_.*$",  # Sequences
    r"^ir_cron_.*$",  # Cron jobs
    r"^mail_template_.*$",  # Mail templates
    r"^email_template_.*$",  # Email templates
    r"^paperformat_.*$",  # Paper formats
    r"^report_.*$",  # Reports
    r"^.*_paperformat$",  # Paper formats
    r"^decimal_.*$",  # Decimal precision
    r"^.*_filter$",  # Search filters
    r"^.*_filter_[a-z0-9_]+$",  # Search filters with suffix
    r"^.*_wizard$",  # Wizard views (simple)
    r"^.*_wizard_form$",  # Wizard form views
    r"^.*_wizard_form_view$",  # Wizard form views (alternate)
    r"^.*_wizard_form_view_[a-z0-9_]+$",  # Wizard form views with suffix
    r"^.*_wiz$",  # Wizard views (short)
    r"^inherit_.*$",  # Inherited views
]

# IDs that are known to be valid but don't follow standard patterns
KNOWN_VALID_IDS = {
    "base.group_user",
    "base.group_system",
    "base.group_erp_manager",
}


class XMLValidator:
    """Validates XML IDs in Odoo XML files."""

    def __init__(self, strict: bool = False, config: LintConfig = None):
        self.strict = strict
        self.config = config or LintConfig.load()
        self.violations: list[Violation] = []

    def is_exception(self, xml_id: str) -> bool:
        """Check if an ID matches exception patterns."""
        for pattern in EXCEPTION_PATTERNS:
            if re.match(pattern, xml_id):
                return True
        return False

    def is_known_valid(self, xml_id: str) -> bool:
        """Check if an ID is in the known valid list."""
        return xml_id in KNOWN_VALID_IDS

    def is_deprecated_group(self, record: ET.Element) -> bool:
        """Check if a group is marked as deprecated."""
        # Check for deprecated in comment field - must start with "deprecated:" or "deprecated."
        for field in record.findall(".//field[@name='comment']"):
            if field.text:
                text_lower = field.text.lower().strip()
                if text_lower.startswith("deprecated:") or text_lower.startswith("deprecated."):
                    return True

        # Check for deprecated in name field - must have "(deprecated)" or end with "deprecated"
        for field in record.findall(".//field[@name='name']"):
            if field.text:
                text_lower = field.text.lower().strip()
                if "(deprecated)" in text_lower or text_lower.endswith("deprecated"):
                    return True

        return False

    def extract_model_from_view(self, record: ET.Element) -> str | None:
        """Extract model name from a view record if possible."""
        for field in record.findall(".//field[@name='model']"):
            if field.text:
                return field.text.strip()
        return None

    def validate_id(self, xml_id: str, model: str, record: ET.Element, file_path: str, line_num: int) -> bool:
        """
        Validate a single XML ID against naming conventions.

        Returns True if valid, False otherwise.
        """
        # Skip external references (with module prefix)
        if "." in xml_id and not xml_id.startswith("."):
            return True

        # Remove leading dot if present
        xml_id = xml_id.lstrip(".")

        # Skip exceptions
        if self.is_exception(xml_id):
            return True

        # Skip known valid IDs
        if self.is_known_valid(xml_id):
            return True

        # Get rules for this model
        if model not in NAMING_RULES:
            # In non-strict mode, allow models we don't have rules for
            if not self.strict:
                return True
            # In strict mode, warn about unknown models
            self.violations.append(
                Violation(
                    file_path=file_path,
                    line=line_num,
                    message=f"Unknown model '{model}' (no naming rules defined)",
                    rule_id="xml_ids.unknown_model",
                    severity=Severity.INFO,
                )
            )
            return False

        rules = NAMING_RULES[model]

        # Special handling for deprecated groups
        if model == "res.groups" and rules.get("allowed_deprecated"):
            if self.is_deprecated_group(record):
                return True

        # Check if ID matches any pattern
        for pattern in rules["patterns"]:
            if re.match(pattern, xml_id):
                return True

        # ID doesn't match - record violation
        examples = ", ".join(rules["examples"][:2])
        severity = self.config.get_severity(f"xml_ids.{model.replace('.', '_')}", Severity.ERROR)
        self.violations.append(
            Violation(
                file_path=file_path,
                line=line_num,
                message=f"XML ID '{xml_id}' does not follow {rules['description']}",
                rule_id=f"xml_ids.{model.replace('.', '_')}",
                severity=severity,
                suggestion=f"Examples: {examples}",
                doc_link="docs/principles/naming-conventions.md",
            )
        )
        return False

    def get_line_number(self, element: Any) -> int:
        """Get line number for an element.

        Uses lxml's sourceline when available, otherwise returns 0.
        """
        if USING_LXML and hasattr(element, "sourceline"):
            return element.sourceline or 0
        return 0

    def parse_xml_file(self, file_path: Path) -> Any:
        """Parse an XML file, handling namespaces."""
        try:
            if USING_LXML:
                # lxml preserves line numbers
                parser = ET.XMLParser(remove_blank_text=False)  # nosec B314 — parsing local module XML for lint checks
                # nosemgrep: odoo-xxe-stdlib - Script file parsing internal XML, not user-facing
                tree = ET.parse(str(file_path), parser)  # nosec B314 — parsing local module XML for lint checks
            else:
                # ElementTree fallback
                ET.register_namespace("", "http://www.w3.org/2001/XMLSchema")
                # nosemgrep: odoo-xxe-stdlib - Script file parsing internal XML, not user-facing
                tree = ET.parse(file_path)  # nosec B314 — parsing local module XML for lint checks
            return tree
        except Exception as e:
            print(f"Error parsing {file_path}: {e}", file=sys.stderr)
            return None

    def find_line_number_fallback(self, file_path: Path, xml_id: str) -> int:
        """
        Find the line number where an XML ID is defined using text search.

        This is a fallback when lxml is not available or sourceline is missing.
        Note: This can be unreliable if ID appears in comments or is split across lines.
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if f'id="{xml_id}"' in line or f"id='{xml_id}'" in line:
                        return line_num
        except Exception:
            pass
        return 0

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate all XML IDs in a file.

        Returns True if all IDs are valid, False otherwise.
        """
        tree = self.parse_xml_file(file_path)
        if tree is None:
            return False

        root = tree.getroot()
        all_valid = True

        # Find all <record> elements
        for record in root.findall(".//record"):
            xml_id = record.get("id")
            model = record.get("model")

            if xml_id and model:
                # Use lxml's sourceline if available, otherwise fallback to text search
                line_num = self.get_line_number(record)
                if line_num == 0:
                    line_num = self.find_line_number_fallback(file_path, xml_id)

                if not self.validate_id(xml_id, model, record, str(file_path), line_num):
                    all_valid = False

        return all_valid

    def get_violation_count(self) -> int:
        """Get the number of violations found."""
        return len(self.violations)


def find_xml_files_in_module(module_name: str, base_path: Path = None) -> list[Path]:
    """Find all XML files in a module."""
    if base_path is None:
        base_path = Path.cwd()

    module_path = base_path / module_name
    if not module_path.exists() or not module_path.is_dir():
        print(f"Error: Module '{module_name}' not found in {base_path}", file=sys.stderr)
        return []

    xml_files = []
    # Look in common directories
    for subdir in ["views", "security", "data", "wizards", "report"]:
        subdir_path = module_path / subdir
        if subdir_path.exists():
            xml_files.extend(subdir_path.glob("*.xml"))

    return xml_files


def main():
    parser = argparse.ArgumentParser(
        description="Validate XML ID naming conventions in Odoo XML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check specific files
  %(prog)s spp_registry_base/views/partner_views.xml

  # Check all XML files in a module
  %(prog)s --module spp_registry_base

  # Check with strict mode (warns about unknown models)
  %(prog)s --strict --module spp_grm

  # Output in JSON format
  %(prog)s --format json --module spp_grm

Naming Conventions:
  - Views:       view_{model}_form, view_{model}_list/tree
  - Actions:     action_{model}
  - Menus:       menu_{model}
  - Groups:      group_{domain}_{level}
  - Categories:  category_spp_{domain}
  - Privileges:  privilege_{domain}_{level}
  - Rules:       rule_{model}_{purpose}

See docs/principles/naming-conventions.md for full details.
        """,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="XML files to check",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (warn about unknown models)",
    )
    parser.add_argument(
        "--module",
        help="Check all XML files in the specified module",
    )

    # Add common arguments
    add_common_args(parser)

    args = parser.parse_args()

    # Load config
    config = LintConfig.load(args.config) if args.config else LintConfig.load()

    # Collect files to check
    files_to_check = []

    if args.module:
        module_files = find_xml_files_in_module(args.module)
        if not module_files:
            return 1
        files_to_check.extend(module_files)

    if args.files:
        for file_path in args.files:
            path = Path(file_path)
            if not path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                return 1
            files_to_check.append(path)

    if not files_to_check:
        parser.print_help()
        return 1

    # Validate files
    validator = XMLValidator(strict=args.strict, config=config)

    for file_path in files_to_check:
        validator.validate_file(file_path)

    # Filter by severity if specified
    violations = validator.violations
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
