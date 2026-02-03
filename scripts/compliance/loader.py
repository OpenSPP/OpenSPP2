#!/usr/bin/env python3
"""
YAML loader for compliance specifications.

Loads and validates compliance.yaml files against the schema.
"""

from pathlib import Path
from typing import Any

import yaml

from .schema import (
    ActionRestriction,
    ComplianceSpec,
    FieldRestriction,
    GroupDefinition,
    MenuAccess,
    ModelAccess,
    RecordRule,
)


class ComplianceLoadError(Exception):
    """Error loading or parsing compliance spec."""

    pass


def load_compliance_yaml(file_path: Path) -> ComplianceSpec:
    """
    Load a compliance.yaml file and return a ComplianceSpec object.

    Args:
        file_path: Path to the compliance.yaml file

    Returns:
        ComplianceSpec object

    Raises:
        ComplianceLoadError: If file cannot be loaded or parsed
    """
    if not file_path.exists():
        raise ComplianceLoadError(f"File not found: {file_path}")

    try:
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ComplianceLoadError(f"YAML parse error in {file_path}: {e}") from e

    if not data:
        raise ComplianceLoadError(f"Empty compliance file: {file_path}")

    return _parse_compliance_data(data, file_path)


def _parse_compliance_data(data: dict[str, Any], source: Path) -> ComplianceSpec:
    """Parse raw YAML data into ComplianceSpec."""

    # Required fields
    if "module" not in data:
        raise ComplianceLoadError(f"Missing required field 'module' in {source}")
    if "domain" not in data:
        raise ComplianceLoadError(f"Missing required field 'domain' in {source}")

    spec = ComplianceSpec(
        module=data["module"],
        domain=data["domain"],
        version=data.get("version", "1.0"),
        admin_link_group=data.get("admin_link_group"),
    )

    # Parse groups
    for group_data in data.get("groups", []):
        spec.groups.append(_parse_group(group_data, source))

    # Parse model access
    for access_data in data.get("model_access", []):
        spec.model_access.append(_parse_model_access(access_data, source))

    # Parse record rules
    for rule_data in data.get("record_rules", []):
        spec.record_rules.append(_parse_record_rule(rule_data, source))

    # Parse menus
    for menu_data in data.get("menus", []):
        spec.menus.append(_parse_menu(menu_data, source))

    # Parse field restrictions
    for field_data in data.get("field_restrictions", []):
        spec.field_restrictions.append(_parse_field_restriction(field_data, source))

    # Parse actions
    for action_data in data.get("actions", []):
        spec.actions.append(_parse_action(action_data, source))

    return spec


def _parse_group(data: dict[str, Any], source: Path) -> GroupDefinition:
    """Parse group definition."""
    if "id" not in data:
        raise ComplianceLoadError(f"Group missing 'id' in {source}")
    if "tier" not in data:
        raise ComplianceLoadError(f"Group '{data['id']}' missing 'tier' in {source}")

    return GroupDefinition(
        group_id=data["id"],
        tier=data["tier"],
        privilege_id=data.get("privilege_id"),
        implied_ids=data.get("implied_ids", []),
        comment=data.get("comment"),
    )


def _parse_model_access(data: dict[str, Any], source: Path) -> ModelAccess:
    """Parse model access definition."""
    if "model" not in data:
        raise ComplianceLoadError(f"Model access missing 'model' in {source}")

    # Build custom roles from any non-standard keys
    custom = data.get("custom", {})

    # Also look for alternative role names (user instead of viewer, etc.)
    for alt_name in ["user", "validator", "approver", "supervisor", "worker"]:
        if alt_name in data:
            custom[alt_name] = data[alt_name]

    # Only use defaults if no custom roles are defined AND the standard role is missing
    has_custom_roles = bool(custom)

    return ModelAccess(
        model=data["model"],
        # If custom roles exist, only use explicitly defined standard roles (empty list = skip check)
        viewer=data.get("viewer", [] if has_custom_roles else ["read"]),
        officer=data.get("officer", [] if has_custom_roles else ["read", "write", "create"]),
        manager=data.get("manager", ["read", "write", "create", "unlink"]),
        custom=custom,
    )


def _parse_record_rule(data: dict[str, Any], source: Path) -> RecordRule:
    """Parse record rule definition."""
    if "id" not in data:
        raise ComplianceLoadError(f"Record rule missing 'id' in {source}")
    if "model" not in data:
        raise ComplianceLoadError(f"Record rule '{data['id']}' missing 'model' in {source}")

    return RecordRule(
        rule_id=data["id"],
        model=data["model"],
        groups=data.get("groups", []),
        domain_description=data.get("domain_description", ""),
        perm_read=data.get("perm_read", True),
        perm_write=data.get("perm_write", False),
        perm_create=data.get("perm_create", False),
        perm_unlink=data.get("perm_unlink", False),
        is_global=data.get("is_global", False),
        domain_pattern=data.get("domain_pattern"),
        domain=data.get("domain"),
        domain_field=data.get("domain_field"),
    )


def _parse_menu(data: dict[str, Any], source: Path) -> MenuAccess:
    """Parse menu access definition."""
    if "id" not in data:
        raise ComplianceLoadError(f"Menu missing 'id' in {source}")

    return MenuAccess(
        menu_id=data["id"],
        name=data.get("name", data["id"]),
        groups=data.get("groups", []),
        parent=data.get("parent"),
    )


def _parse_field_restriction(data: dict[str, Any], source: Path) -> FieldRestriction:
    """Parse field restriction definition."""
    # Accept either view_id or model as the target
    view_id = data.get("view_id") or data.get("model", "")
    if not view_id:
        raise ComplianceLoadError(f"Field restriction missing 'view_id' or 'model' in {source}")
    if "field_name" not in data:
        raise ComplianceLoadError(f"Field restriction missing 'field_name' in {source}")

    return FieldRestriction(
        view_id=view_id,  # Can be either a view_id or model name
        field_name=data["field_name"],
        groups=data.get("groups", []),
        reason=data.get("reason"),
    )


def _parse_action(data: dict[str, Any], source: Path) -> ActionRestriction:
    """Parse action restriction definition."""
    if "id" not in data:
        raise ComplianceLoadError(f"Action missing 'id' in {source}")

    return ActionRestriction(
        action_id=data["id"],
        action_type=data.get("action_type", "act_window"),
        name=data.get("name", data["id"]),
        groups=data.get("groups", []),
    )


def find_compliance_files(base_path: Path) -> list[Path]:
    """
    Find all compliance.yaml files in the codebase.

    Args:
        base_path: Root directory to search

    Returns:
        List of paths to compliance.yaml files
    """
    return list(base_path.glob("**/compliance.yaml"))


def load_all_compliance_specs(base_path: Path) -> dict[str, ComplianceSpec]:
    """
    Load all compliance specs from the codebase.

    Args:
        base_path: Root directory to search

    Returns:
        Dict mapping module name to ComplianceSpec
    """
    specs = {}
    for file_path in find_compliance_files(base_path):
        try:
            spec = load_compliance_yaml(file_path)
            specs[spec.module] = spec
        except ComplianceLoadError as e:
            print(f"Warning: {e}")
    return specs
