#!/usr/bin/env python3
"""
OpenSPP Naming Conventions Checker

Validates OpenSPP naming conventions as defined in docs/principles/naming-conventions.md:
- Modules: spp_{domain} or spp_{domain}_{feature}
- Models: spp.{domain} or spp.{domain}.{entity}
- Fields: Boolean (is_*/has_*/can_*), Many2one (*_id), One2many/Many2many (*_ids)

Features:
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml
- Severity levels (error, warning, info)

Exit codes:
    0: No violations found
    1: Violations found
"""

import argparse
import ast
import logging
import os
import sys
from pathlib import Path

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

# Whitelist for modules that don't follow spp_* naming
MODULE_WHITELIST = {
    "base_user_role",
    "job_worker",
    "endpoint_route_handler",
    "extendable",
    "extendable_fastapi",
    "fastapi",
    "patches",
    "setup",
    "docs",
    "scripts",
    "theme_openspp_muk",
}

# Standard Odoo models that don't need to follow spp.* naming
STANDARD_MODEL_WHITELIST = {
    "res.partner",
    "res.users",
    "res.company",
    "res.config.settings",
    "ir.actions.server",
    "ir.cron",
    "ir.sequence",
    "mail.thread",
    "mail.activity.mixin",
}

# Third-party models that don't need to follow spp.* naming
# These are from external/third-party modules we depend on
THIRD_PARTY_MODEL_WHITELIST = {
    # job_worker module
    "queue.job",
    "queue.job.channel",
    "queue.job.function",
    "queue.job.lock",
    "queue.jobs.to.cancelled",
    "queue.jobs.to.done",
    "queue.limit",
    "queue.requeue.job",
    # fastapi module
    "fastapi.endpoint",
    # base_user_role module
    "res.users.role",
    "res.users.role.line",
    "wizard.create.role.from.user",
    "wizard.groups.into.role",
    # endpoint_route_handler module
    "endpoint.route.handler",
    "endpoint.route.handler.tool",
    "endpoint.route.sync.mixin",
    # extendable module
    "extendable.registry.loader",
}

# Many2one fields that are exceptions (don't need _id suffix)
# These are common Odoo conventions or fields where adding _id would be redundant
MANY2ONE_EXCEPTIONS = {
    # Standard Odoo conventions
    "parent",
    "company",
    "currency",
    "country",
    "state",
    "partner",
    "user",
    "categ",
    # Fields where the name already implies ID or type
    "id_type",  # spp.id.type - "id_type_id" would be redundant
    "source",
    "destination",  # Relationship endpoints
    "relation",  # Relationship type
    # Audit fields (who did what)
    "disabled_by",
    "created_by",
    "approved_by",
    "rejected_by",
    "create_uid",  # Standard Odoo audit field
    "write_uid",  # Standard Odoo audit field
    "printed_by",  # Common audit pattern
    "distributed_by",  # Common audit pattern
    "requested_by",  # Common audit pattern
    "generated_by",  # Common audit pattern
    "resolved_by",  # Common audit pattern
    # Geographic fields
    "district",
    "region",
    "province",
    "city",
    "village",
    # One2many inverse fields (standard Odoo pattern)
    "group",  # Inverse of group_membership_ids
    "individual",  # Inverse of individual_membership_ids
    # Field selection fields (selecting ir.model.fields)
    "multiplier_field",  # Selecting a field definition, not a typical record
    # Locale/origin fields (not typical ID relationships)
    "locale_origin",  # Selecting a country for locale, not a typical ID relationship
}

_logger = logging.getLogger(__name__)

# Domain-approved usages of the word "kind" for schema fields.
KIND_ALLOWED = {"in_kind"}


class NamingChecker:
    """Checks OpenSPP naming conventions with auto-fix support."""

    def __init__(self, root_dir: str = None, config: LintConfig = None):
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.config = config or LintConfig.load()
        self.violations: list[Violation] = []
        self.fixes_applied: list[tuple[str, int, str, str]] = []  # (file, line, old, new)

        # Load additional exceptions from config
        rule_config = self.config.get_rule_config("naming")
        self.boolean_exceptions = set(rule_config.get("boolean_exceptions", []))
        self.boolean_verb_prefixes = tuple(rule_config.get("boolean_verb_prefixes", []))
        self.many2one_exceptions = MANY2ONE_EXCEPTIONS | set(rule_config.get("many2one_exceptions", []))
        self.kind_allowed = KIND_ALLOWED | set(rule_config.get("kind_allowed", []))

        # Load namespace exceptions from config (models that don't need spp.* namespace)
        # Combine built-in third-party whitelist with config-based exceptions
        config_namespace_exceptions = set(rule_config.get("namespace_exceptions", []))
        self.namespace_exceptions = STANDARD_MODEL_WHITELIST | THIRD_PARTY_MODEL_WHITELIST | config_namespace_exceptions

    def check_module_names(self) -> list[Violation]:
        """Check that module directory names follow spp_* pattern."""
        violations = []

        for item in self.root_dir.iterdir():
            if not item.is_dir():
                continue

            module_name = item.name

            if module_name.startswith(".") or module_name.startswith("__"):
                continue

            manifest_path = item / "__manifest__.py"
            if not manifest_path.exists():
                continue

            if module_name not in MODULE_WHITELIST and not module_name.startswith("spp_"):
                violations.append(
                    Violation(
                        file_path=str(item.relative_to(self.root_dir)),
                        line=0,
                        message=f"Module '{module_name}' does not follow spp_* naming convention",
                        rule_id="naming.module_prefix",
                        severity=Severity.ERROR,
                        suggestion=f"Rename to 'spp_{module_name}'",
                        doc_link="docs/principles/naming-conventions.md#modules",
                    )
                )

        return violations

    def check_python_file(self, file_path: str, fix: bool = False) -> list[Violation]:
        """Check naming conventions in a Python file."""
        violations = []

        if self.config.should_ignore(file_path):
            return violations

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                original_content = content
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            _logger.warning("Syntax error in %s: %s", file_path, e)
            return violations
        except Exception as e:
            _logger.warning("Error parsing %s: %s", file_path, e)
            return violations

        # Check for deprecated g2p imports
        violations.extend(self._check_imports(file_path, tree))

        # Check model classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_violations = self._check_model_class(file_path, node, content)
                violations.extend(class_violations)

                # Apply fixes if requested
                if fix:
                    content = self._apply_fixes(content, class_violations)

        # Write fixed content if changes were made
        if fix and content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            _logger.info("Fixed %s", file_path)

        return violations

    def _check_imports(self, file_path: str, tree: ast.AST) -> list[Violation]:
        """Check for deprecated g2p imports."""
        violations = []
        severity = self.config.get_severity("naming.g2p_import", Severity.ERROR)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                line = node.lineno

                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("g2p") or "g2p_" in node.module:
                        new_module = node.module.replace("g2p_", "spp_").replace("g2p.", "spp.")
                        violations.append(
                            Violation(
                                file_path=file_path,
                                line=line,
                                message=f"Deprecated g2p import: 'from {node.module}'",
                                rule_id="naming.g2p_import",
                                severity=severity,
                                suggestion=f"Change to 'from {new_module}'",
                                doc_link="docs/principles/naming-conventions.md",
                            )
                        )

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("g2p") or "g2p_" in alias.name:
                            new_name = alias.name.replace("g2p_", "spp_").replace("g2p.", "spp.")
                            violations.append(
                                Violation(
                                    file_path=file_path,
                                    line=line,
                                    message=f"Deprecated g2p import: 'import {alias.name}'",
                                    rule_id="naming.g2p_import",
                                    severity=severity,
                                    suggestion=f"Change to 'import {new_name}'",
                                    doc_link="docs/principles/naming-conventions.md",
                                )
                            )

        return violations

    def _check_model_class(self, file_path: str, class_node: ast.ClassDef, content: str) -> list[Violation]:
        """Check naming conventions in a model class definition."""
        violations = []

        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_name":
                        if isinstance(node.value, ast.Constant):
                            model_name = node.value.value
                            line = node.lineno

                            if isinstance(model_name, str) and model_name.startswith("g2p."):
                                new_name = model_name.replace("g2p.", "spp.")
                                violations.append(
                                    Violation(
                                        file_path=file_path,
                                        line=line,
                                        message=f"Model uses deprecated 'g2p.*' namespace: '{model_name}'",
                                        rule_id="naming.g2p_model",
                                        severity=Severity.ERROR,
                                        suggestion=f"Change to '{new_name}'",
                                        doc_link="docs/principles/naming-conventions.md",
                                    )
                                )
                            elif (
                                isinstance(model_name, str)
                                and model_name not in self.namespace_exceptions
                                and not model_name.startswith("spp.")
                                and not model_name.startswith("spp_")
                                and "." in model_name
                            ):
                                violations.append(
                                    Violation(
                                        file_path=file_path,
                                        line=line,
                                        message=f"Model '{model_name}' should use 'spp.*' namespace",
                                        rule_id="naming.model_namespace",
                                        severity=Severity.WARNING,
                                        doc_link="docs/principles/naming-conventions.md",
                                    )
                                )

        violations.extend(self._check_fields(file_path, class_node, content))
        return violations

    def _check_fields(self, file_path: str, class_node: ast.ClassDef, content: str) -> list[Violation]:
        """Check field naming conventions."""
        violations = []

        # Default exceptions
        common_exceptions = {
            "active",
            "sequence",
            "closed",
            "done",
            "sent",
            "confirmed",
            "validated",
            "approved",
            "published",
            "archived",
            "locked",
            "cancelled",
            "required",
            "deprecated",
            "optional",
            "enabled",
            "disabled",
            "visible",
            "readonly",
            "hidden",
            "editable",
            "selectable",
            "unattended",
            "global_alias",
            "force_required",
            "warning_required",
            "function_apply_on_record",
            "fold",  # Standard Odoo field for stages (folded in Kanban)
        } | self.boolean_exceptions

        verb_prefixes = (
            "manage_",
            "validate_",
            "allow_",
            "enable_",
            "disable_",
            "show_",
            "hide_",
            "include_",
            "exclude_",
            "skip_",
            "auto_",
            "force_",
            "use_",
            "apply_",
            "check_",
            "can_",  # Permission/capability checks (e.g., can_approve, can_edit)
            # Action/behavior flags (these are action verbs, not state checks)
            "notify_on_",  # notify_on_submit, notify_on_reject, notify_on_pending, etc.
            "send_",  # send_notification, send_email, etc.
            "create_",  # create_case, create_batch, etc.
            "copy_",  # copy_description, copy_data, etc.
            "close_",  # close_ticket, close_case, etc.
            "assign_",  # assign_teams, assign_users, etc.
            "link_to_",  # link_to_beneficiaries, link_to_programs, etc.
            "overwrite_",  # overwrite_match, overwrite_data, etc.
            "enroll_",  # enroll_demo_stories, enroll_users, etc.
            "store_",  # store_sp_in_entitlements, store_data, etc.
            "topup_",  # topup_service_point, topup_account, etc.
            "track_",  # track_topics, track_attendance, etc.
        ) + self.boolean_verb_prefixes

        for node in class_node.body:
            if not isinstance(node, ast.Assign):
                continue

            field_name = None
            for target in node.targets:
                if isinstance(target, ast.Name):
                    field_name = target.id
                    break

            if not field_name or field_name.startswith("_"):
                continue

            if not isinstance(node.value, ast.Call):
                continue

            field_type = self._get_field_type(node.value)
            if not field_type:
                continue

            line = node.lineno
            severity = self.config.get_severity(f"naming.{field_type.lower()}_suffix", Severity.WARNING)

            # Warn on generic "kind" schema fields (V2 policy: prefer *_type / *_role)
            kind_violation = self._check_kind_term(file_path, field_name, field_type, line)
            if kind_violation:
                violations.append(kind_violation)

            if field_type == "Boolean":
                if not (field_name.startswith("is_") or field_name.startswith("has_")):
                    # Check for valid patterns: *_is_valid, *_not_exact, etc.
                    is_valid_pattern = field_name.endswith("_is_valid") or field_name.endswith("_not_exact")
                    # Check for fields with 'is_' embedded in the middle (e.g., z_ind_grp_is_*, grp_is_*, ind_is_*)
                    has_embedded_is = "_is_" in field_name and not field_name.startswith("is_")
                    if (
                        field_name not in common_exceptions
                        and not any(field_name.startswith(p) for p in verb_prefixes)
                        and not is_valid_pattern
                        and not has_embedded_is
                    ):
                        violations.append(
                            Violation(
                                file_path=file_path,
                                line=line,
                                message=f"Boolean field '{field_name}' should use 'is_' or 'has_' prefix",
                                rule_id="naming.boolean_prefix",
                                severity=severity,
                                suggestion=f"Rename to 'is_{field_name}'",
                                doc_link="docs/principles/naming-conventions.md#fields",
                            )
                        )

            elif field_type == "Many2one":
                if not field_name.endswith("_id") and field_name not in self.many2one_exceptions:
                    violations.append(
                        Violation(
                            file_path=file_path,
                            line=line,
                            message=f"Many2one field '{field_name}' should end with '_id'",
                            rule_id="naming.many2one_suffix",
                            severity=severity,
                            suggestion=f"Rename to '{field_name}_id'",
                            doc_link="docs/principles/naming-conventions.md#fields",
                        )
                    )

            elif field_type in ["One2many", "Many2many"]:
                if not field_name.endswith("_ids"):
                    violations.append(
                        Violation(
                            file_path=file_path,
                            line=line,
                            message=f"{field_type} field '{field_name}' should end with '_ids'",
                            rule_id=f"naming.{field_type.lower()}_suffix",
                            severity=severity,
                            suggestion=f"Rename to '{field_name}_ids'"
                            if not field_name.endswith("s")
                            else f"Rename to '{field_name[:-1]}_ids'",
                            doc_link="docs/principles/naming-conventions.md#fields",
                        )
                    )

            # Check for deprecated g2p.* in comodel_name
            violations.extend(self._check_comodel_name(file_path, node, line))

        return violations

    def _get_field_type(self, call_node: ast.Call) -> str | None:
        """Extract field type from a fields.Something() call."""
        if isinstance(call_node.func, ast.Attribute):
            if isinstance(call_node.func.value, ast.Name):
                if call_node.func.value.id == "fields":
                    return call_node.func.attr
        return None

    def _check_kind_term(self, file_path: str, field_name: str, field_type: str, line: int) -> Violation | None:
        """Warn when schema fields use the generic term 'kind' instead of type/role."""

        # Allowed domain usages
        if field_name in self.kind_allowed:
            return None

        # Patterns that indicate generic "kind" naming
        suspicious = (
            field_name == "kind"
            or field_name.endswith("_kind")
            or field_name.endswith("_kind_id")
            or field_name.endswith("_kind_ids")
            or field_name.endswith("_kinds")
        )

        if not suspicious:
            return None

        severity = self.config.get_severity("naming.kind_term", Severity.WARNING)
        return Violation(
            file_path=file_path,
            line=line,
            message=(f"Field '{field_name}' uses generic 'kind'; prefer '*_type' or '*_role' naming in V2"),
            rule_id="naming.kind_term",
            severity=severity,
            suggestion="Rename to the corresponding *_type or *_role field (see kind-to-type-renaming.md)",
            doc_link="docs/principles/kind-to-type-renaming.md",
        )

    def _check_comodel_name(self, file_path: str, node: ast.Assign, line: int) -> list[Violation]:
        """Check for deprecated g2p.* in comodel_name parameter."""
        violations = []

        if not isinstance(node.value, ast.Call):
            return violations

        for keyword in node.value.keywords:
            if keyword.arg == "comodel_name":
                if isinstance(keyword.value, ast.Constant):
                    comodel_name = keyword.value.value
                    if isinstance(comodel_name, str) and comodel_name.startswith("g2p."):
                        new_name = comodel_name.replace("g2p.", "spp.")
                        violations.append(
                            Violation(
                                file_path=file_path,
                                line=line,
                                message=f"comodel_name uses deprecated 'g2p.*': '{comodel_name}'",
                                rule_id="naming.g2p_comodel",
                                severity=Severity.ERROR,
                                suggestion=f"Change to '{new_name}'",
                                doc_link="docs/principles/naming-conventions.md",
                            )
                        )

        return violations

    def _apply_fixes(self, content: str, violations: list[Violation]) -> str:
        """Apply auto-fixes to content (placeholder for future implementation)."""
        # TODO: Implement actual fixes using AST transformation
        # For now, just log what would be fixed
        for v in violations:
            if v.suggestion:
                _logger.debug("Would fix: %s -> %s", v.message, v.suggestion)
        return content

    def check_files(self, file_paths: list[str], fix: bool = False) -> int:
        """Check naming conventions in the given files."""
        for file_path in file_paths:
            if not os.path.exists(file_path):
                _logger.warning("File not found: %s", file_path)
                continue

            if not file_path.endswith(".py"):
                continue

            violations = self.check_python_file(file_path, fix=fix)
            self.violations.extend(violations)

        return len(self.violations)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check OpenSPP naming conventions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Python files to check",
    )
    parser.add_argument(
        "--check-modules",
        action="store_true",
        help="Check module directory names",
    )
    parser.add_argument(
        "--root-dir",
        default=None,
        help="Root directory for module checks",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply auto-fixes when available (currently none for naming)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    # Add common arguments
    add_common_args(parser)

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(message)s")

    # Load config
    config = LintConfig.load(args.config) if args.config else LintConfig.load()

    checker = NamingChecker(root_dir=args.root_dir, config=config)

    # Check module names if requested
    if args.check_modules:
        module_violations = checker.check_module_names()
        checker.violations.extend(module_violations)

    # Check Python files
    if args.files:
        checker.check_files(args.files, fix=args.fix)

    # Filter by severity if specified
    if args.severity != "all":
        min_severity = Severity(args.severity)
        severity_order = [Severity.INFO, Severity.WARNING, Severity.ERROR]
        min_index = severity_order.index(min_severity)
        checker.violations = [v for v in checker.violations if severity_order.index(v.severity) >= min_index]

    # Output results
    formatter = OutputFormatter(args.format)
    output = formatter.format(checker.violations, show_summary=not args.summary)
    print(output)

    if args.summary:
        print_summary(checker.violations)

    # Return appropriate exit code
    has_errors = any(v.severity == Severity.ERROR for v in checker.violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
