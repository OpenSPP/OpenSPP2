#!/usr/bin/env python3
"""
Compliance Schema Definitions for OpenSPP Access Management.

This module defines the schema for compliance.yaml files that declare
expected access control configurations per module.

Schema version: 1.0
"""

from dataclasses import dataclass, field
from enum import Enum


class PermissionLevel(Enum):
    """Standard permission levels following ADR-004."""

    NONE = "none"
    READ = "read"
    WRITE = "write"  # implies read
    CREATE = "create"  # implies read
    FULL = "full"  # read + write + create + unlink


class DomainPattern(Enum):
    """
    Common domain patterns for record rules.

    These patterns can be automatically validated and tested.
    """

    # User can see all records (no filtering)
    ALL_RECORDS = "all_records"

    # User can only see records they created
    OWN_CREATED = "own_created"

    # User can only see their own record (e.g., res.partner linked to user)
    OWN_RECORD = "own_record"

    # User can see records assigned to them
    ASSIGNED_TO_ME = "assigned_to_me"

    # User can see records for their company only (multi-company)
    COMPANY_RECORDS = "company_records"

    # User can see records for their team/group
    TEAM_RECORDS = "team_records"

    # Custom domain - requires explicit domain expression
    CUSTOM = "custom"


@dataclass
class ModelAccess:
    """Expected CRUD permissions for a model per group."""

    model: str
    viewer: list[str] = field(default_factory=lambda: ["read"])
    officer: list[str] = field(default_factory=lambda: ["read", "write", "create"])
    manager: list[str] = field(default_factory=lambda: ["read", "write", "create", "unlink"])
    # Custom roles (optional)
    custom: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class RecordRule:
    """Expected record rule configuration."""

    rule_id: str
    model: str
    groups: list[str]
    domain_description: str  # Human-readable description of domain
    perm_read: bool = True
    perm_write: bool = False
    perm_create: bool = False
    perm_unlink: bool = False
    is_global: bool = False
    # Domain validation fields
    domain_pattern: str | None = None  # DomainPattern enum value as string
    domain: str | None = None  # Actual Odoo domain expression for validation
    # Field used in domain (for automatic test generation)
    domain_field: str | None = None  # e.g., "create_uid", "user_id", "assigned_to"


@dataclass
class MenuAccess:
    """Expected menu visibility per group."""

    menu_id: str
    name: str  # Human-readable name for documentation
    groups: list[str]  # Groups that should have access
    parent: str | None = None  # Parent menu ID if relevant


@dataclass
class FieldRestriction:
    """Expected field visibility restriction."""

    view_id: str
    field_name: str
    groups: list[str]  # Groups that can see this field
    reason: str | None = None  # Why this restriction exists


@dataclass
class ActionRestriction:
    """Expected action access restriction."""

    action_id: str
    action_type: str  # act_window, server, report, etc.
    name: str  # Human-readable name
    groups: list[str]  # Groups that can execute this action


@dataclass
class GroupDefinition:
    """Expected group configuration."""

    group_id: str
    tier: int  # 1=role, 2=functional, 3=technical
    privilege_id: str | None = None  # Required for tier 2
    implied_ids: list[str] = field(default_factory=list)
    comment: str | None = None


@dataclass
class ComplianceSpec:
    """Complete compliance specification for a module."""

    # Metadata
    module: str
    domain: str
    version: str = "1.0"

    # Group definitions
    groups: list[GroupDefinition] = field(default_factory=list)

    # Model access (ir.model.access.csv)
    model_access: list[ModelAccess] = field(default_factory=list)

    # Record rules (ir.rule)
    record_rules: list[RecordRule] = field(default_factory=list)

    # Menu visibility
    menus: list[MenuAccess] = field(default_factory=list)

    # Field restrictions in views
    field_restrictions: list[FieldRestriction] = field(default_factory=list)

    # Action restrictions
    actions: list[ActionRestriction] = field(default_factory=list)

    # Admin linkage - which manager group links to admin
    admin_link_group: str | None = None


# YAML schema documentation
COMPLIANCE_YAML_SCHEMA = """
# compliance.yaml Schema Documentation
# ====================================
#
# This file declares expected access control configuration for a module.
# The compliance checker validates actual configuration against this spec.
#
# Example:
# --------
# module: spp_registry_base
# domain: registry
# version: "1.0"
#
# groups:
#   # Tier 3: Technical groups
#   - id: group_registry_read
#     tier: 3
#     comment: "Read access to registry models"
#
#   - id: group_registry_write
#     tier: 3
#     implied_ids: [group_registry_read]
#     comment: "Write access (implies read)"
#
#   # Tier 2: User-facing groups
#   - id: group_registry_viewer
#     tier: 2
#     privilege_id: privilege_registry_viewer
#     implied_ids: [group_registry_read]
#     comment: "View-only access to registry"
#
#   - id: group_registry_officer
#     tier: 2
#     privilege_id: privilege_registry_officer
#     implied_ids: [group_registry_viewer, group_registry_write, group_registry_create]
#     comment: "Standard operational access"
#
#   - id: group_registry_manager
#     tier: 2
#     privilege_id: privilege_registry_manager
#     implied_ids: [group_registry_officer]
#     comment: "Full management access"
#
# admin_link_group: group_registry_manager
#
# model_access:
#   - model: res.partner
#     viewer: [read]
#     officer: [read, write, create]
#     manager: [read, write, create, unlink]
#
#   - model: spp.registry.relationship
#     viewer: [read]
#     officer: [read, write, create]
#     manager: [read, write, create, unlink]
#
# record_rules:
#   - id: rule_partner_company
#     model: res.partner
#     groups: []  # empty = global rule
#     domain_description: "Company isolation"
#     is_global: true
#     perm_read: true
#     perm_write: true
#     perm_create: true
#     perm_unlink: true
#     domain_pattern: company_records  # Pattern for auto-validation
#     domain: "[('company_id', 'in', company_ids)]"  # Actual domain to validate
#
#   - id: rule_partner_self_only
#     model: res.partner
#     groups: [group_registry_restrict_self]
#     domain_description: "User can only see own partner record"
#     perm_read: true
#     domain_pattern: own_created  # Validates: user only sees records they created
#     domain: "[('create_uid', '=', user.id)]"
#     domain_field: create_uid  # Field used for visibility test
#
# Domain patterns (for automatic test generation):
#   - all_records: No filtering, sees everything (domain = [(1,'=',1)])
#   - own_created: User sees only records they created (create_uid = user.id)
#   - own_record: User sees their own record (e.g., partner_id = user.partner_id)
#   - assigned_to_me: User sees records assigned to them (user_id/assigned_to = user.id)
#   - company_records: Multi-company isolation (company_id in company_ids)
#   - team_records: Team/group-based visibility
#   - custom: Custom domain, requires explicit domain field
#
# menus:
#   - id: menu_registry_root
#     name: "Registry"
#     groups: [group_registry_viewer, group_registry_officer, group_registry_manager]
#
#   - id: menu_registry_config
#     name: "Registry Configuration"
#     parent: menu_registry_root
#     groups: [group_registry_manager]
#
# field_restrictions:
#   - view_id: view_partner_form
#     field_name: company_id
#     groups: [base.group_multi_company]
#     reason: "Only show company field in multi-company setup"
#
# actions:
#   - id: action_partner_merge
#     action_type: act_window
#     name: "Merge Partners"
#     groups: [group_registry_manager]
"""
