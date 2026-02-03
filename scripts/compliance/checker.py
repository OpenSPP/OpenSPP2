#!/usr/bin/env python3
"""
OpenSPP Access Management Compliance Checker.

Validates actual module configurations against compliance.yaml specifications.

Checks performed:
1. Group definitions (hierarchy, naming, privileges)
2. Model access (ir.model.access.csv completeness)
3. Record rules (domain patterns, group assignments)
4. Menu visibility (group restrictions)
5. Field restrictions in views
6. Action restrictions

Usage:
    python -m scripts.compliance.checker spp_registry_base
    python -m scripts.compliance.checker --all
    python -m scripts.compliance.checker --all --report --format markdown
"""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from .loader import ComplianceLoadError, load_compliance_yaml
from .schema import ComplianceSpec


@dataclass
class ComplianceIssue:
    """A compliance violation or warning."""

    severity: str  # ERROR, WARNING, INFO
    category: str  # GROUP, ACL, RULE, MENU, VIEW, ACTION
    message: str
    expected: str | None = None
    actual: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    suggestion: str | None = None


@dataclass
class ComplianceResult:
    """Result of compliance check for a module."""

    module: str
    spec_path: Path | None
    issues: list[ComplianceIssue] = field(default_factory=list)
    groups_checked: int = 0
    models_checked: int = 0
    rules_checked: int = 0
    menus_checked: int = 0
    fields_checked: int = 0
    actions_checked: int = 0

    @property
    def is_compliant(self) -> bool:
        """Check if module is compliant (no ERROR-level issues)."""
        return not any(i.severity == "ERROR" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")


class ComplianceChecker:
    """Validates module configuration against compliance spec."""

    def __init__(self, module_path: Path, spec: ComplianceSpec):
        self.module_path = module_path
        self.spec = spec
        self.result = ComplianceResult(module=spec.module, spec_path=module_path / "security" / "compliance.yaml")

        # Cache loaded data
        self._groups_xml: dict[str, ET.Element] = {}
        self._acl_entries: dict[str, dict] = {}
        self._rules_xml: dict[str, ET.Element] = {}
        self._menus_xml: dict[str, ET.Element] = {}
        self._views_xml: dict[str, ET.Element] = {}
        self._actions_xml: dict[str, ET.Element] = {}

    def check_all(self) -> ComplianceResult:
        """Run all compliance checks."""
        self._load_module_data()

        self._check_groups()
        self._check_model_access()
        self._check_record_rules()
        self._check_menus()
        self._check_field_restrictions()
        self._check_actions()
        self._check_admin_link()

        return self.result

    def _load_module_data(self):
        """Load all security-related data from the module."""
        security_dir = self.module_path / "security"
        views_dir = self.module_path / "views"

        # Load groups from security/*.xml
        if security_dir.exists():
            for xml_file in security_dir.glob("*.xml"):
                self._parse_security_xml(xml_file)

            # Load ACL entries
            acl_file = security_dir / "ir.model.access.csv"
            if acl_file.exists():
                self._load_acl_file(acl_file)

        # Load views and menus (including subdirectories)
        if views_dir.exists():
            for xml_file in views_dir.glob("**/*.xml"):
                self._parse_views_xml(xml_file)

    def _parse_security_xml(self, file_path: Path):
        """Parse security XML file for groups, rules, etc."""
        try:
            content = file_path.read_text(encoding="utf-8")
            # Add XML declaration if missing
            if not content.strip().startswith("<?xml"):
                content = '<?xml version="1.0" encoding="utf-8"?>\n' + content
            root = ET.fromstring(content)

            for record in root.iter("record"):
                model = record.get("model", "")
                xml_id = record.get("id", "")

                if model == "res.groups":
                    self._groups_xml[xml_id] = record
                elif model == "ir.rule":
                    self._rules_xml[xml_id] = record
                elif model in ("ir.actions.act_window", "ir.actions.server", "ir.actions.report"):
                    self._actions_xml[xml_id] = record

        except ET.ParseError:
            self.result.issues.append(
                ComplianceIssue(
                    severity="WARNING",
                    category="PARSE",
                    message="Could not parse XML file",
                    file_path=str(file_path.relative_to(self.module_path)),
                )
            )

    def _parse_views_xml(self, file_path: Path):
        """Parse view XML files for menus, views, and actions."""
        try:
            content = file_path.read_text(encoding="utf-8")
            if not content.strip().startswith("<?xml"):
                content = '<?xml version="1.0" encoding="utf-8"?>\n' + content
            root = ET.fromstring(content)

            # Find menuitem elements
            for menuitem in root.iter("menuitem"):
                menu_id = menuitem.get("id", "")
                if menu_id:
                    self._menus_xml[menu_id] = menuitem

            # Find record-based menus
            for record in root.iter("record"):
                model = record.get("model", "")
                xml_id = record.get("id", "")

                if model == "ir.ui.menu":
                    self._menus_xml[xml_id] = record
                elif model == "ir.ui.view":
                    self._views_xml[xml_id] = record
                elif model in ("ir.actions.act_window", "ir.actions.server", "ir.actions.report"):
                    self._actions_xml[xml_id] = record

        except ET.ParseError:
            pass  # Skip unparseable files

    def _load_acl_file(self, file_path: Path):
        """Load ir.model.access.csv file."""
        try:
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entry_id = row.get("id", "")
                    if entry_id:
                        self._acl_entries[entry_id] = row
        except Exception as e:
            self.result.issues.append(
                ComplianceIssue(
                    severity="ERROR",
                    category="ACL",
                    message=f"Could not parse ACL file: {e}",
                    file_path="security/ir.model.access.csv",
                )
            )

    def _check_groups(self):
        """Check group definitions against spec."""
        for group_spec in self.spec.groups:
            self.result.groups_checked += 1
            group_id = group_spec.group_id

            # Check if group exists
            if group_id not in self._groups_xml:
                self.result.issues.append(
                    ComplianceIssue(
                        severity="ERROR",
                        category="GROUP",
                        message=f"Expected group '{group_id}' not found",
                        expected=group_id,
                        suggestion=f"Define group '{group_id}' in security/groups.xml",
                    )
                )
                continue

            record = self._groups_xml[group_id]

            # Check tier 2 groups have privilege_id
            if group_spec.tier == 2 and group_spec.privilege_id:
                has_privilege = any(f.get("name") == "privilege_id" for f in record.findall("field"))
                if not has_privilege:
                    self.result.issues.append(
                        ComplianceIssue(
                            severity="WARNING",
                            category="GROUP",
                            message=f"Tier 2 group '{group_id}' should have privilege_id",
                            expected=f"privilege_id ref='{group_spec.privilege_id}'",
                            suggestion="Add privilege_id for Odoo 19 user settings UI",
                        )
                    )

            # Check implied_ids
            if group_spec.implied_ids:
                implied_field = None
                for f in record.findall("field"):
                    if f.get("name") == "implied_ids":
                        implied_field = f
                        break

                if implied_field is None:
                    self.result.issues.append(
                        ComplianceIssue(
                            severity="WARNING",
                            category="GROUP",
                            message=f"Group '{group_id}' missing implied_ids",
                            expected=str(group_spec.implied_ids),
                            suggestion="Add implied_ids to establish group hierarchy",
                        )
                    )

            # Check comment field
            has_comment = any(f.get("name") == "comment" for f in record.findall("field"))
            if not has_comment and group_spec.comment:
                self.result.issues.append(
                    ComplianceIssue(
                        severity="INFO",
                        category="GROUP",
                        message=f"Group '{group_id}' missing documentation comment",
                        suggestion="Add comment field to document group purpose",
                    )
                )

    def _check_model_access(self):
        """Check model access (ACL) against spec."""
        for access_spec in self.spec.model_access:
            self.result.models_checked += 1
            model = access_spec.model
            model_underscore = model.replace(".", "_")

            # Check viewer access (skip if empty - means module uses custom roles)
            if access_spec.viewer:
                self._check_acl_entry(model, model_underscore, "viewer", access_spec.viewer)

            # Check officer access (skip if empty - means module uses custom roles)
            if access_spec.officer:
                self._check_acl_entry(model, model_underscore, "officer", access_spec.officer)

            # Check manager access
            if access_spec.manager:
                self._check_acl_entry(model, model_underscore, "manager", access_spec.manager)

            # Check custom roles
            for role, perms in access_spec.custom.items():
                self._check_acl_entry(model, model_underscore, role, perms)

    def _check_acl_entry(self, model: str, model_underscore: str, role: str, expected_perms: list[str]):
        """Check a single ACL entry."""
        # Look for matching entry - try common patterns
        possible_ids = [
            f"access_{model_underscore}_{role}",
            f"access_{model_underscore}_{self.spec.domain}_{role}",
        ]

        found_entry = None
        for entry_id in possible_ids:
            if entry_id in self._acl_entries:
                found_entry = self._acl_entries[entry_id]
                break

        # Also search by model_id:id reference and group
        if not found_entry:
            for _entry_id, entry in self._acl_entries.items():
                model_ref = entry.get("model_id:id", "")
                group_ref = entry.get("group_id:id", "")
                # Try both dot notation and underscore notation
                # model_ref format: "module.model_model_name"
                model_in_ref = model_underscore in model_ref or f"model_{model_underscore}" in model_ref
                role_in_ref = role in group_ref.lower()
                if model_in_ref and role_in_ref:
                    found_entry = entry
                    break

        if not found_entry:
            self.result.issues.append(
                ComplianceIssue(
                    severity="ERROR",
                    category="ACL",
                    message=f"Missing ACL entry for {model} / {role}",
                    expected=f"access_{model_underscore}_{role}",
                    file_path="security/ir.model.access.csv",
                    suggestion=f"Add ACL entry for {model} with {role} permissions: {expected_perms}",
                )
            )
            return

        # Check permissions match
        actual_perms = []
        if found_entry.get("perm_read") == "1":
            actual_perms.append("read")
        if found_entry.get("perm_write") == "1":
            actual_perms.append("write")
        if found_entry.get("perm_create") == "1":
            actual_perms.append("create")
        if found_entry.get("perm_unlink") == "1":
            actual_perms.append("unlink")

        if set(actual_perms) != set(expected_perms):
            self.result.issues.append(
                ComplianceIssue(
                    severity="WARNING",
                    category="ACL",
                    message=f"ACL permissions mismatch for {model} / {role}",
                    expected=str(expected_perms),
                    actual=str(actual_perms),
                    file_path="security/ir.model.access.csv",
                )
            )

    def _check_record_rules(self):
        """Check record rules against spec."""
        for rule_spec in self.spec.record_rules:
            self.result.rules_checked += 1
            rule_id = rule_spec.rule_id

            if rule_id not in self._rules_xml:
                self.result.issues.append(
                    ComplianceIssue(
                        severity="ERROR",
                        category="RULE",
                        message=f"Expected record rule '{rule_id}' not found",
                        expected=rule_id,
                        suggestion=f"Define rule '{rule_id}' in security/rules.xml",
                    )
                )
                continue

            record = self._rules_xml[rule_id]

            # Check for empty domain_force with write permissions (anti-pattern)
            actual_domain = None
            for f in record.findall("field"):
                if f.get("name") == "domain_force":
                    actual_domain = f.text or ""
                    if actual_domain.strip() in ("[]", ""):
                        # Check if rule has write permissions
                        has_write = False
                        for perm_field in record.findall("field"):
                            if perm_field.get("name") in ("perm_write", "perm_create", "perm_unlink"):
                                if perm_field.text == "1" or perm_field.get("eval") in ("True", "1"):
                                    has_write = True
                                    break

                        if has_write:
                            self.result.issues.append(
                                ComplianceIssue(
                                    severity="ERROR",
                                    category="RULE",
                                    message=f"Rule '{rule_id}' has empty domain with write permissions",
                                    actual="domain_force=[]",
                                    suggestion="Use [(1, '=', 1)] for 'see all' pattern, never empty []",
                                )
                            )

            # Validate domain pattern if specified
            if rule_spec.domain_pattern and rule_spec.domain and actual_domain:
                self._validate_domain_pattern(rule_id, rule_spec, actual_domain)

    def _validate_domain_pattern(self, rule_id: str, rule_spec, actual_domain: str):
        """Validate that actual domain matches expected pattern."""
        expected_domain = rule_spec.domain.strip()
        actual_domain = actual_domain.strip()

        # Normalize domains for comparison (remove whitespace variations)
        def normalize_domain(d):
            # Remove extra whitespace
            d = re.sub(r"\s+", " ", d)
            # Normalize quotes
            d = d.replace("'", '"')
            return d.strip()

        normalized_expected = normalize_domain(expected_domain)
        normalized_actual = normalize_domain(actual_domain)

        # Check if domains match (exact or semantic match)
        if normalized_expected != normalized_actual:
            # Try pattern-based validation
            pattern_matches = self._check_domain_pattern_match(
                rule_spec.domain_pattern, actual_domain, rule_spec.domain_field
            )

            if not pattern_matches:
                self.result.issues.append(
                    ComplianceIssue(
                        severity="WARNING",
                        category="RULE",
                        message=f"Rule '{rule_id}' domain doesn't match expected pattern",
                        expected=f"Pattern: {rule_spec.domain_pattern}, Domain: {expected_domain}",
                        actual=actual_domain,
                        suggestion="Verify domain_force matches the expected security pattern",
                    )
                )

    def _check_domain_pattern_match(self, pattern: str, actual_domain: str, domain_field: str = None) -> bool:
        """Check if actual domain matches the expected pattern semantically."""
        actual_lower = actual_domain.lower()

        if pattern == "all_records":
            # Should be [(1, '=', 1)] or similar "see all" pattern
            return "(1" in actual_domain and "'='" in actual_lower or '"="' in actual_lower

        elif pattern == "own_created":
            # Should reference create_uid
            field = domain_field or "create_uid"
            return field in actual_lower and "user" in actual_lower

        elif pattern == "own_record":
            # Should reference user's partner_id or similar
            return "user" in actual_lower and ("partner" in actual_lower or "id" in actual_lower)

        elif pattern == "assigned_to_me":
            # Should reference user_id, assigned_to, or similar
            field = domain_field or "user_id"
            return field in actual_lower and "user" in actual_lower

        elif pattern == "company_records":
            # Should reference company_id and company_ids
            return "company_id" in actual_lower and "company_ids" in actual_lower

        elif pattern == "team_records":
            # Should reference team or group
            return "team" in actual_lower or "group" in actual_lower

        elif pattern == "custom":
            # Custom pattern - can't auto-validate, just check domain is not empty
            return len(actual_domain.strip()) > 2  # More than "[]"

        return False

    def _check_menus(self):
        """Check menu visibility against spec."""
        for menu_spec in self.spec.menus:
            self.result.menus_checked += 1
            menu_id = menu_spec.menu_id

            if menu_id not in self._menus_xml:
                # Menu might be defined with module prefix
                full_id = f"{self.spec.module}.{menu_id}"
                if full_id not in self._menus_xml:
                    self.result.issues.append(
                        ComplianceIssue(
                            severity="WARNING",
                            category="MENU",
                            message=f"Expected menu '{menu_id}' not found in module",
                            expected=menu_id,
                            suggestion="Verify menu ID or check if defined in another module",
                        )
                    )
                    continue
                menu_id = full_id

            element = self._menus_xml[menu_id]

            # Get actual groups from element
            actual_groups = []
            if element.tag == "menuitem":
                groups_attr = element.get("groups", "")
                if groups_attr:
                    actual_groups = [g.strip() for g in groups_attr.split(",")]
            else:
                # Record-style menu
                for f in element.findall("field"):
                    if f.get("name") in ("groups", "group_ids"):
                        # Parse eval attribute or text
                        eval_attr = f.get("eval", "")
                        if eval_attr:
                            # Extract refs from eval
                            refs = re.findall(r"ref\(['\"]([^'\"]+)['\"]\)", eval_attr)
                            actual_groups = refs

            # Check if expected groups are present
            if menu_spec.groups and not actual_groups:
                self.result.issues.append(
                    ComplianceIssue(
                        severity="WARNING",
                        category="MENU",
                        message=f"Menu '{menu_spec.menu_id}' has no group restrictions",
                        expected=str(menu_spec.groups),
                        actual="No groups defined",
                        suggestion="Add groups attribute to restrict menu visibility",
                    )
                )

    def _check_field_restrictions(self):
        """Check field-level restrictions in views."""
        for field_spec in self.spec.field_restrictions:
            self.result.fields_checked += 1
            view_id = field_spec.view_id

            if view_id not in self._views_xml:
                # Skip if view not found (might be inherited)
                continue

            view_record = self._views_xml[view_id]

            # Find arch field and parse it
            for f in view_record.findall("field"):
                if f.get("name") == "arch":
                    # Check for field with groups attribute
                    arch_text = ET.tostring(f, encoding="unicode")
                    pattern = rf'<field[^>]+name=["\']{ field_spec.field_name}["\'][^>]*groups=["\']([^"\']+)["\']'
                    match = re.search(pattern, arch_text)

                    if match:
                        actual_groups = [g.strip() for g in match.group(1).split(",")]
                        expected_groups = field_spec.groups

                        if set(actual_groups) != set(expected_groups):
                            self.result.issues.append(
                                ComplianceIssue(
                                    severity="INFO",
                                    category="VIEW",
                                    message=f"Field '{field_spec.field_name}' groups mismatch in '{view_id}'",
                                    expected=str(expected_groups),
                                    actual=str(actual_groups),
                                )
                            )
                    elif field_spec.groups:
                        # Field exists but no groups restriction
                        field_in_arch = (
                            f'name="{field_spec.field_name}"' in arch_text
                            or f"name='{field_spec.field_name}'" in arch_text
                        )
                        if field_in_arch:
                            self.result.issues.append(
                                ComplianceIssue(
                                    severity="INFO",
                                    category="VIEW",
                                    message=(
                                        f"Field '{field_spec.field_name}' missing " f"groups restriction in '{view_id}'"
                                    ),
                                    expected=str(field_spec.groups),
                                    suggestion=(f"Add groups=\"{','.join(field_spec.groups)}\" " "to field"),
                                )
                            )

    def _check_actions(self):
        """Check action restrictions against spec."""
        for action_spec in self.spec.actions:
            self.result.actions_checked += 1
            action_id = action_spec.action_id

            if action_id not in self._actions_xml:
                # Try with module prefix
                full_id = f"{self.spec.module}.{action_id}"
                if full_id not in self._actions_xml:
                    self.result.issues.append(
                        ComplianceIssue(
                            severity="WARNING",
                            category="ACTION",
                            message=f"Expected action '{action_id}' not found",
                            expected=action_id,
                        )
                    )
                    continue
                action_id = full_id

            record = self._actions_xml[action_id]

            # Check for groups_id or group_ids field (Odoo uses groups_id)
            actual_groups = []
            for f in record.findall("field"):
                if f.get("name") in ("groups_id", "group_ids"):
                    eval_attr = f.get("eval", "")
                    if eval_attr:
                        refs = re.findall(r"ref\(['\"]([^'\"]+)['\"]\)", eval_attr)
                        actual_groups = refs

            if action_spec.groups and not actual_groups:
                self.result.issues.append(
                    ComplianceIssue(
                        severity="WARNING",
                        category="ACTION",
                        message=f"Action '{action_spec.action_id}' has no group restrictions",
                        expected=str(action_spec.groups),
                        actual="No groups defined",
                        suggestion="Add group_ids field to restrict action access",
                    )
                )

    def _check_admin_link(self):
        """Check if manager group is linked to admin."""
        if not self.spec.admin_link_group:
            return

        # Look for the admin extension record
        admin_ext_id = "spp_security.group_spp_admin"
        found_link = False

        for xml_id, record in self._groups_xml.items():
            if admin_ext_id in xml_id or xml_id == admin_ext_id:
                # Check if it links to our manager group
                for f in record.findall("field"):
                    if f.get("name") == "implied_ids":
                        eval_attr = f.get("eval", "")
                        if self.spec.admin_link_group in eval_attr:
                            found_link = True
                            break

        if not found_link:
            admin_link_suggestion = (
                f'Add: <record id="spp_security.group_spp_admin">'
                f'<field name="implied_ids" '
                f"eval=\"[Command.link(ref('{self.spec.admin_link_group}'))]\"/>"
                f"</record>"
            )
            self.result.issues.append(
                ComplianceIssue(
                    severity="WARNING",
                    category="GROUP",
                    message=(f"Manager group '{self.spec.admin_link_group}' " "not linked to admin"),
                    suggestion=admin_link_suggestion,
                )
            )


def check_module(module_path: Path) -> ComplianceResult:
    """
    Check a module for compliance.

    Args:
        module_path: Path to the module directory

    Returns:
        ComplianceResult with findings
    """
    spec_file = module_path / "security" / "compliance.yaml"

    if not spec_file.exists():
        # No compliance spec - return empty result
        result = ComplianceResult(module=module_path.name, spec_path=None)
        result.issues.append(
            ComplianceIssue(
                severity="INFO",
                category="SPEC",
                message="No compliance.yaml found",
                suggestion="Create security/compliance.yaml to enable compliance checking",
            )
        )
        return result

    try:
        spec = load_compliance_yaml(spec_file)
    except ComplianceLoadError as e:
        result = ComplianceResult(module=module_path.name, spec_path=spec_file)
        result.issues.append(
            ComplianceIssue(
                severity="ERROR",
                category="SPEC",
                message=f"Could not load compliance spec: {e}",
            )
        )
        return result

    checker = ComplianceChecker(module_path, spec)
    return checker.check_all()


def find_modules(base_path: Path) -> list[Path]:
    """Find all OpenSPP modules."""
    modules = []
    for item in base_path.iterdir():
        if item.is_dir() and (item / "__manifest__.py").exists():
            if item.name.startswith("spp_"):
                modules.append(item)
    return sorted(modules)


def generate_report(results: list[ComplianceResult], format: str = "markdown") -> str:
    """Generate compliance report."""
    if format == "json":
        return _generate_json_report(results)
    elif format == "text":
        return _generate_text_report(results)
    else:
        return _generate_markdown_report(results)


def _generate_markdown_report(results: list[ComplianceResult]) -> str:
    """Generate markdown compliance report."""
    lines = [
        "# OpenSPP Access Management Compliance Report",
        "",
        f"**Generated:** {__import__('datetime').datetime.now().isoformat()}",
        f"**Modules Checked:** {len(results)}",
        "",
        "## Summary",
        "",
        "| Module | Groups | Models | Rules | Menus | Actions | Errors | Warnings |",
        "|--------|--------|--------|-------|-------|---------|--------|----------|",
    ]

    total_errors = 0
    total_warnings = 0
    compliant_count = 0

    for result in results:
        total_errors += result.error_count
        total_warnings += result.warning_count
        if result.is_compliant:
            compliant_count += 1

        lines.append(
            f"| {result.module} | {result.groups_checked} | {result.models_checked} | "
            f"{result.rules_checked} | {result.menus_checked} | {result.actions_checked} | "
            f"{result.error_count} | {result.warning_count} |"
        )

    lines.extend(
        [
            "",
            f"**Compliant:** {compliant_count}/{len(results)}",
            f"**Total Errors:** {total_errors}",
            f"**Total Warnings:** {total_warnings}",
            "",
        ]
    )

    # Detailed issues
    modules_with_issues = [r for r in results if r.issues]
    if modules_with_issues:
        lines.extend(["## Issues", ""])

        for result in modules_with_issues:
            if not any(i.severity in ("ERROR", "WARNING") for i in result.issues):
                continue

            lines.extend([f"### {result.module}", ""])

            for severity in ["ERROR", "WARNING"]:
                issues = [i for i in result.issues if i.severity == severity]
                if not issues:
                    continue

                lines.append(f"**{severity}S:**")
                for issue in issues:
                    lines.append(f"- **[{issue.category}]** {issue.message}")
                    if issue.expected:
                        lines.append(f"  - Expected: `{issue.expected}`")
                    if issue.actual:
                        lines.append(f"  - Actual: `{issue.actual}`")
                    if issue.suggestion:
                        lines.append(f"  - Suggestion: {issue.suggestion}")
                lines.append("")

    return "\n".join(lines)


def _generate_json_report(results: list[ComplianceResult]) -> str:
    """Generate JSON compliance report."""
    data = {
        "generated": __import__("datetime").datetime.now().isoformat(),
        "summary": {
            "modules_checked": len(results),
            "compliant": sum(1 for r in results if r.is_compliant),
            "total_errors": sum(r.error_count for r in results),
            "total_warnings": sum(r.warning_count for r in results),
        },
        "modules": [],
    }

    for result in results:
        module_data = {
            "name": result.module,
            "compliant": result.is_compliant,
            "checked": {
                "groups": result.groups_checked,
                "models": result.models_checked,
                "rules": result.rules_checked,
                "menus": result.menus_checked,
                "actions": result.actions_checked,
            },
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "expected": i.expected,
                    "actual": i.actual,
                    "suggestion": i.suggestion,
                }
                for i in result.issues
            ],
        }
        data["modules"].append(module_data)

    return json.dumps(data, indent=2)


def _generate_text_report(results: list[ComplianceResult]) -> str:
    """Generate plain text compliance report."""
    lines = []

    for result in results:
        status = "PASS" if result.is_compliant else "FAIL"
        lines.append(f"[{status}] {result.module}: {result.error_count} errors, {result.warning_count} warnings")

        for issue in result.issues:
            if issue.severity in ("ERROR", "WARNING"):
                icon = "X" if issue.severity == "ERROR" else "!"
                lines.append(f"  [{icon}] {issue.category}: {issue.message}")

    total_pass = sum(1 for r in results if r.is_compliant)
    lines.append(f"\nTotal: {total_pass}/{len(results)} compliant")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check OpenSPP modules for access management compliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s spp_registry_base          # Check single module
  %(prog)s --all                       # Check all modules with compliance.yaml
  %(prog)s --all --report              # Generate detailed report
  %(prog)s --all --format json         # JSON output for CI

Exit codes:
  0 - All modules compliant
  1 - One or more compliance errors
""",
    )
    parser.add_argument("module", nargs="?", help="Module name to check")
    parser.add_argument("--all", "-a", action="store_true", help="Check all modules")
    parser.add_argument("--report", "-r", action="store_true", help="Generate report")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json", "text"],
        default="markdown",
        help="Output format",
    )
    parser.add_argument("--base-path", type=Path, default=Path("."), help="Base path")
    parser.add_argument("--errors-only", "-e", action="store_true", help="Only show modules with errors")

    args = parser.parse_args()
    base_path = args.base_path.resolve()

    results = []

    if args.all:
        modules = find_modules(base_path)
        for module_path in modules:
            result = check_module(module_path)
            # Only include modules with compliance.yaml or issues
            if result.spec_path or any(i.severity == "ERROR" for i in result.issues):
                results.append(result)
    elif args.module:
        module_path = base_path / args.module
        if not module_path.exists():
            print(f"Module not found: {module_path}", file=sys.stderr)
            sys.exit(1)
        results.append(check_module(module_path))
    else:
        parser.print_help()
        sys.exit(1)

    if args.errors_only:
        results = [r for r in results if not r.is_compliant]

    if args.report or args.format != "text":
        print(generate_report(results, args.format))
    else:
        # Quick summary
        for result in results:
            status = "PASS" if result.is_compliant else "FAIL"
            print(f"[{status}] {result.module}: {result.error_count} errors, {result.warning_count} warnings")

        total_pass = sum(1 for r in results if r.is_compliant)
        print(f"\nTotal: {total_pass}/{len(results)} compliant")

    # Exit code
    has_errors = any(not r.is_compliant for r in results)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
