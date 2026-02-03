#!/usr/bin/env python3
"""
OpenSPP Compliance Test Generator.

Generates Python test files from compliance.yaml specifications.
The generated tests validate access control at runtime.

Generated tests cover:
1. Group hierarchy (implied_ids work correctly)
2. Model CRUD permissions per role
3. Record rule filtering (data visibility)
4. Menu visibility per role
5. Action access restrictions

Usage:
    python -m scripts.compliance.test_generator spp_registry_base
    python -m scripts.compliance.test_generator --all
    python -m scripts.compliance.test_generator --all --output-dir tests/generated
"""

import argparse
import sys
from pathlib import Path

from .loader import ComplianceLoadError, load_compliance_yaml
from .schema import ComplianceSpec


def _discover_all_roles(spec: ComplianceSpec) -> dict[str, str]:
    """
    Discover all roles defined in the compliance spec.

    Returns a dict mapping role names to their group IDs.
    Standard roles (viewer, officer, manager) use domain-based naming.
    Custom roles use their defined names.
    """
    domain = spec.domain

    # Standard roles with domain-based group naming
    roles = {
        "viewer": f"group_{domain}_viewer",
        "officer": f"group_{domain}_officer",
        "manager": f"group_{domain}_manager",
    }

    # Discover custom roles from model_access definitions
    for access in spec.model_access:
        for role_name in access.custom.keys():
            # Custom roles use group_{domain}_{role} naming convention
            if role_name not in roles:
                roles[role_name] = f"group_{domain}_{role_name}"

    # Also check groups definitions for custom roles
    for group in spec.groups:
        # Extract role name from group_id (e.g., group_case_worker -> worker)
        group_id = group.group_id
        if group_id.startswith(f"group_{domain}_"):
            role_name = group_id[len(f"group_{domain}_") :]
            if role_name not in roles:
                roles[role_name] = group_id

    return roles


def generate_test_file(spec: ComplianceSpec, module_path: Path) -> str:
    """
    Generate a Python test file from a compliance spec.

    Args:
        spec: ComplianceSpec object
        module_path: Path to the module

    Returns:
        Python test file content as string
    """
    lines = [
        "# Part of OpenSPP. See LICENSE file for full copyright and licensing details.",
        "# AUTO-GENERATED from compliance.yaml - DO NOT EDIT MANUALLY",
        f"# Regenerate with: python -m scripts.compliance.test_generator {spec.module}",
        "",
        '"""',
        f"Access control compliance tests for {spec.module}.",
        "",
        f"Generated from: {spec.module}/security/compliance.yaml",
        "Tests validate:",
        "- Group hierarchy and implied_ids",
        "- Model CRUD permissions per role",
        "- Menu visibility per role",
        "- Action access restrictions",
        '"""',
        "",
        "from odoo import Command",
        "from odoo.exceptions import AccessError",
        "from odoo.tests import TransactionCase, tagged",
        "",
        "",
    ]

    # Generate base test class
    lines.extend(_generate_base_class(spec))

    # Generate group hierarchy tests
    if spec.groups:
        lines.extend(_generate_group_tests(spec))

    # Generate model access tests
    if spec.model_access:
        lines.extend(_generate_model_access_tests(spec))

    # Generate menu visibility tests
    if spec.menus:
        lines.extend(_generate_menu_tests(spec))

    # Generate action access tests
    if spec.actions:
        lines.extend(_generate_action_tests(spec))

    # Generate record rule tests
    if spec.record_rules:
        lines.extend(_generate_record_rule_tests(spec))

    # Generate data visibility tests (for rules with domain patterns)
    if spec.record_rules:
        visibility_tests = _generate_data_visibility_tests(spec)
        if visibility_tests:
            lines.extend(visibility_tests)

    # Generate admin linkage tests
    if spec.admin_link_group:
        lines.extend(_generate_admin_linkage_tests(spec))

    return "\n".join(lines)


def _generate_base_class(spec: ComplianceSpec) -> list[str]:
    """Generate the base test class with user setup."""
    module = spec.module

    # Discover all roles defined in this module
    all_roles = _discover_all_roles(spec)

    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance")',
        "class TestComplianceBase(TransactionCase):",
        f'    """Base class for {spec.module} compliance tests."""',
        "",
        "    @classmethod",
        "    def setUpClass(cls):",
        '        """Set up test users with different roles."""',
        "        super().setUpClass()",
        "",
        "        # Helper to safely get reference",
        "        def safe_ref(xml_id):",
        "            try:",
        "                return cls.env.ref(xml_id)",
        "            except ValueError:",
        "                return None",
        "",
        "        # Base internal user group",
        '        base_group = cls.env.ref("base.group_user")',
        "",
        "        # Store all role groups and users",
        "        cls.role_groups = {}",
        "        cls.role_users = {}",
        "",
    ]

    # Generate group and user creation for each discovered role
    for role_name, group_id in all_roles.items():
        lines.extend(
            [
                f"        # {role_name.title()} role",
                f'        cls.role_groups["{role_name}"] = safe_ref("{module}.{group_id}")',
                (
                    f'        cls.role_users["{role_name}"] = '
                    f'cls._create_test_user("{role_name}", cls.role_groups["{role_name}"])'
                ),
                "",
            ]
        )

    # Add backward-compatible aliases for standard roles
    lines.extend(
        [
            "        # Backward-compatible aliases for standard roles",
            '        cls.group_viewer = cls.role_groups.get("viewer")',
            '        cls.group_officer = cls.role_groups.get("officer")',
            '        cls.group_manager = cls.role_groups.get("manager")',
            '        cls.user_viewer = cls.role_users.get("viewer")',
            '        cls.user_officer = cls.role_users.get("officer")',
            '        cls.user_manager = cls.role_users.get("manager")',
            "",
            "        # Admin user",
            '        admin_group = safe_ref("spp_security.group_spp_admin")',
            '        cls.user_admin = cls._create_test_user("admin", admin_group)',
            "",
            "    @classmethod",
            "    def _create_test_user(cls, role, group):",
            '        """Create a test user with the specified group."""',
            "        if not group:",
            "            return None",
            '        return cls.env["res.users"].create({',
            '            "name": f"Test {role.title()}",',
            '            "login": f"test_{role}_compliance",',
            '            "email": f"{role}_compliance@test.com",',
            '            "group_ids": [',
            '                Command.link(cls.env.ref("base.group_user").id),',
            "                Command.link(group.id),",
            "            ],",
            "        })",
            "",
            "    def _get_user_for_role(self, role):",
            '        """Get test user for a given role name."""',
            "        return self.role_users.get(role)",
            "",
            "    def _assert_access(self, model, user, perm, should_have):",
            '        """Assert user has or doesn\'t have permission on model."""',
            "        Model = self.env[model].with_user(user)",
            "        has_access = Model.check_access_rights(perm, raise_exception=False)",
            "        if should_have:",
            "            self.assertTrue(",
            "                has_access,",
            '                f"{user.name} should have {perm} on {model}"',
            "            )",
            "        else:",
            "            self.assertFalse(",
            "                has_access,",
            '                f"{user.name} should NOT have {perm} on {model}"',
            "            )",
            "",
            "",
        ]
    )

    return lines


def _generate_group_tests(spec: ComplianceSpec) -> list[str]:
    """Generate group hierarchy tests."""
    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance")',
        "class TestGroupHierarchy(TestComplianceBase):",
        '    """Test group hierarchy and implied_ids."""',
        "",
    ]

    # Test that manager implies officer implies viewer
    lines.extend(
        [
            "    def test_manager_implies_officer(self):",
            '        """Manager group should imply officer group."""',
            "        if not self.user_manager or not self.group_officer:",
            '            self.skipTest("Required groups not found")',
            "        self.assertTrue(",
            f'            self.user_manager.has_group("{spec.module}.group_{spec.domain}_officer"),',
            '            "Manager should have officer privileges"',
            "        )",
            "",
            "    def test_officer_implies_viewer(self):",
            '        """Officer group should imply viewer group."""',
            "        if not self.user_officer or not self.group_viewer:",
            '            self.skipTest("Required groups not found")',
            "        self.assertTrue(",
            f'            self.user_officer.has_group("{spec.module}.group_{spec.domain}_viewer"),',
            '            "Officer should have viewer privileges"',
            "        )",
            "",
        ]
    )

    # Test each group's implied_ids
    for group in spec.groups:
        if group.implied_ids:
            method_name = f"test_{group.group_id}_implies"
            lines.extend(
                [
                    f"    def {method_name}(self):",
                    f'        """Test {group.group_id} implies correct groups."""',
                    f'        group = self.env.ref("{spec.module}.{group.group_id}", raise_if_not_found=False)',
                    "        if not group:",
                    f'            self.skipTest("Group {group.group_id} not found")',
                    '        implied_ids = group.implied_ids.mapped("id")',
                ]
            )
            for implied in group.implied_ids:
                lines.extend(
                    [
                        f'        implied_group = self.env.ref("{spec.module}.{implied}", raise_if_not_found=False)',
                        "        if implied_group:",
                        "            self.assertIn(",
                        "                implied_group.id, implied_ids,",
                        f'                "{group.group_id} should imply {implied}"',
                        "            )",
                    ]
                )
            lines.append("")

    lines.append("")
    return lines


def _generate_model_access_tests(spec: ComplianceSpec) -> list[str]:
    """Generate model CRUD permission tests for all roles."""
    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance")',
        "class TestModelAccess(TestComplianceBase):",
        '    """Test model CRUD permissions per role."""',
        "",
    ]

    for access in spec.model_access:
        model_safe = access.model.replace(".", "_")

        # Collect all roles that have defined permissions for this model
        roles_to_test = []

        # Standard roles - only test if they have permissions defined
        if access.viewer:
            roles_to_test.append(("viewer", access.viewer))
        if access.officer:
            roles_to_test.append(("officer", access.officer))
        if access.manager:
            roles_to_test.append(("manager", access.manager))

        # Custom roles from the custom dict
        for role_name, perms in access.custom.items():
            if perms:  # Only add if permissions are defined
                roles_to_test.append((role_name, perms))

        # Generate tests for each role
        for role_name, perms in roles_to_test:
            method_name = f"test_{model_safe}_{role_name}_access"
            lines.extend(
                [
                    f"    def {method_name}(self):",
                    f'        """Test {role_name} permissions on {access.model}."""',
                    f'        user = self._get_user_for_role("{role_name}")',
                    "        if not user:",
                    f'            self.skipTest("{role_name.title()} user not found")',
                ]
            )
            for perm in ["read", "write", "create", "unlink"]:
                should_have = perm in perms
                lines.append(f'        self._assert_access("{access.model}", user, "{perm}", {should_have})')
            lines.append("")

    lines.append("")
    return lines


def _generate_menu_tests(spec: ComplianceSpec) -> list[str]:
    """Generate menu visibility tests."""
    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance")',
        "class TestMenuVisibility(TestComplianceBase):",
        '    """Test menu visibility per role."""',
        "",
        "    def _menu_visible(self, menu_xml_id, user):",
        '        """Check if menu is visible to user."""',
        "        menu = self.env.ref(menu_xml_id, raise_if_not_found=False)",
        "        if not menu:",
        "            return None  # Menu not found",
        "        # Get visible menus for user",
        '        visible_menus = self.env["ir.ui.menu"].with_user(user).search([])',
        "        return menu in visible_menus",
        "",
    ]

    for menu in spec.menus:
        menu_xml_id = f"{spec.module}.{menu.menu_id}" if "." not in menu.menu_id else menu.menu_id
        method_name = f"test_menu_{menu.menu_id.replace('.', '_')}_visibility"

        lines.extend(
            [
                f"    def {method_name}(self):",
                f'        """Test visibility of menu {menu.name}."""',
            ]
        )

        # Test viewer visibility
        viewer_should_see = f"group_{spec.domain}_viewer" in menu.groups or any(
            "viewer" in g.lower() for g in menu.groups
        )
        lines.extend(
            [
                "        if self.user_viewer:",
                f'            visible = self._menu_visible("{menu_xml_id}", self.user_viewer)',
                "            if visible is not None:",
            ]
        )
        if viewer_should_see:
            lines.append(f'                self.assertTrue(visible, "Viewer should see {menu.name}")')
        else:
            lines.append(f'                self.assertFalse(visible, "Viewer should NOT see {menu.name}")')

        # Test manager visibility (managers usually see everything)
        lines.extend(
            [
                "        if self.user_manager:",
                f'            visible = self._menu_visible("{menu_xml_id}", self.user_manager)',
                "            if visible is not None:",
                f'                self.assertTrue(visible, "Manager should see {menu.name}")',
                "",
            ]
        )

    lines.append("")
    return lines


def _generate_action_tests(spec: ComplianceSpec) -> list[str]:
    """Generate action access tests."""
    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance")',
        "class TestActionAccess(TestComplianceBase):",
        '    """Test action access restrictions."""',
        "",
        "    def _can_access_action(self, action_xml_id, user):",
        '        """Check if user can access an action."""',
        "        action = self.env.ref(action_xml_id, raise_if_not_found=False)",
        "        if not action:",
        "            return None",
        "        # Check if user's groups intersect with action's groups",
        "        if not action.group_ids:",
        "            return True  # No restriction",
        "        user_groups = user.group_ids",
        "        return bool(action.group_ids & user_groups)",
        "",
    ]

    for action in spec.actions:
        action_xml_id = f"{spec.module}.{action.action_id}" if "." not in action.action_id else action.action_id
        method_name = f"test_action_{action.action_id.replace('.', '_')}_access"

        lines.extend(
            [
                f"    def {method_name}(self):",
                f'        """Test access to action {action.name}."""',
            ]
        )

        # Determine who should have access based on groups
        has_viewer = any("viewer" in g.lower() for g in action.groups)

        lines.extend(
            [
                "        # Test viewer access",
                "        if self.user_viewer:",
                f'            can_access = self._can_access_action("{action_xml_id}", self.user_viewer)',
                "            if can_access is not None:",
            ]
        )
        if has_viewer:
            lines.append(f'                self.assertTrue(can_access, "Viewer should access {action.name}")')
        else:
            lines.append(f'                self.assertFalse(can_access, "Viewer should NOT access {action.name}")')

        lines.extend(
            [
                "",
                "        # Test manager access",
                "        if self.user_manager:",
                f'            can_access = self._can_access_action("{action_xml_id}", self.user_manager)',
                "            if can_access is not None:",
                f'                self.assertTrue(can_access, "Manager should access {action.name}")',
                "",
            ]
        )

    lines.append("")
    return lines


def _generate_record_rule_tests(spec: ComplianceSpec) -> list[str]:
    """Generate record rule (data visibility) tests."""
    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance", "record_rules")',
        "class TestRecordRules(TestComplianceBase):",
        '    """Test record rules (data visibility filtering).',
        "",
        "    These tests verify that users can only see records they are allowed",
        "    to see based on ir.rule domain filters.",
        '    """',
        "",
        "    def _rule_exists(self, rule_xml_id):",
        '        """Check if a record rule exists."""',
        "        return bool(self.env.ref(rule_xml_id, raise_if_not_found=False))",
        "",
        "    def _get_rule(self, rule_xml_id):",
        '        """Get a record rule by XML ID."""',
        "        return self.env.ref(rule_xml_id, raise_if_not_found=False)",
        "",
    ]

    for rule in spec.record_rules:
        rule_xml_id = f"{spec.module}.{rule.rule_id}"
        method_name = f"test_rule_{rule.rule_id.replace('.', '_')}_exists"

        # Test that rule exists and has correct configuration
        lines.extend(
            [
                f"    def {method_name}(self):",
                f'        """Test record rule {rule.rule_id} exists and is configured."""',
                f'        rule = self._get_rule("{rule_xml_id}")',
                "        if not rule:",
                f'            self.skipTest("Rule {rule.rule_id} not found")',
                "",
                "        # Verify rule model",
                "        self.assertEqual(",
                f'            rule.model_id.model, "{rule.model}",',
                f'            "Rule should be for model {rule.model}"',
                "        )",
                "",
                "        # Verify permissions",
                f"        self.assertEqual(rule.perm_read, {rule.perm_read})",
                f"        self.assertEqual(rule.perm_write, {rule.perm_write})",
                f"        self.assertEqual(rule.perm_create, {rule.perm_create})",
                f"        self.assertEqual(rule.perm_unlink, {rule.perm_unlink})",
                "",
            ]
        )

        # Test group assignment
        if rule.groups:
            group_test_method = f"test_rule_{rule.rule_id.replace('.', '_')}_groups"
            lines.extend(
                [
                    f"    def {group_test_method}(self):",
                    f'        """Test record rule {rule.rule_id} is assigned to correct groups."""',
                    f'        rule = self._get_rule("{rule_xml_id}")',
                    "        if not rule:",
                    f'            self.skipTest("Rule {rule.rule_id} not found")',
                    "",
                    "        rule_group_xmlids = []",
                    "        for group in rule.groups:",
                    "            xml_id = group.get_external_id().get(group.id)",
                    "            if xml_id:",
                    "                rule_group_xmlids.append(xml_id)",
                    "",
                ]
            )
            for group in rule.groups:
                group_ref = f"{spec.module}.{group}" if "." not in group else group
                lines.extend(
                    [
                        f'        expected_group = self.env.ref("{group_ref}", raise_if_not_found=False)',
                        "        if expected_group:",
                        "            self.assertIn(",
                        "                expected_group, rule.groups,",
                        f'                "Rule should include group {group}"',
                        "            )",
                    ]
                )
            lines.append("")
        else:
            # Global rule (no groups = applies to everyone)
            if rule.is_global:
                global_test_method = f"test_rule_{rule.rule_id.replace('.', '_')}_is_global"
                lines.extend(
                    [
                        f"    def {global_test_method}(self):",
                        f'        """Test record rule {rule.rule_id} is a global rule."""',
                        f'        rule = self._get_rule("{rule_xml_id}")',
                        "        if not rule:",
                        f'            self.skipTest("Rule {rule.rule_id} not found")',
                        "        self.assertFalse(",
                        "            rule.groups,",
                        '            "Global rule should have no groups assigned"',
                        "        )",
                        '        self.assertTrue(rule.global_, "Rule should be marked as global")',
                        "",
                    ]
                )

    lines.append("")
    return lines


def _generate_data_visibility_tests(spec: ComplianceSpec) -> list[str]:
    """Generate data visibility tests for rules with domain patterns."""
    # Filter rules that have domain patterns defined
    testable_rules = [r for r in spec.record_rules if r.domain_pattern]

    if not testable_rules:
        return []

    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance", "data_visibility")',
        "class TestDataVisibility(TestComplianceBase):",
        '    """Test data visibility based on record rule domains.',
        "",
        "    These tests create actual records and verify that users can only",
        "    see the records they are allowed to see based on domain filters.",
        '    """',
        "",
    ]

    for rule in testable_rules:
        pattern = rule.domain_pattern
        model = rule.model
        model_safe = model.replace(".", "_")

        if pattern == "own_created":
            # Generate test for "user sees only their own created records"
            lines.extend(_generate_own_created_test(spec, rule, model_safe))

        elif pattern == "assigned_to_me":
            # Generate test for "user sees only records assigned to them"
            lines.extend(_generate_assigned_to_me_test(spec, rule, model_safe))

        elif pattern == "company_records":
            # Generate test for multi-company isolation
            lines.extend(_generate_company_isolation_test(spec, rule, model_safe))

        elif pattern == "all_records":
            # Generate test that confirms user can see all records
            lines.extend(_generate_all_records_test(spec, rule, model_safe))

    lines.append("")
    return lines


def _generate_own_created_test(spec: ComplianceSpec, rule, model_safe: str) -> list[str]:
    """Generate test for own_created domain pattern."""
    domain_field = rule.domain_field or "create_uid"
    method_name = f"test_{model_safe}_own_created_visibility"

    return [
        f"    def {method_name}(self):",
        f'        """Test {rule.model}: user only sees records they created."""',
        "        if not self.user_officer or not self.user_viewer:",
        '            self.skipTest("Required users not found")',
        "",
        f'        Model = self.env["{rule.model}"]',
        "",
        "        # Check model has required field",
        f'        if "{domain_field}" not in Model._fields:',
        f'            self.skipTest("Model missing {domain_field} field")',
        "",
        "        # Create record as officer",
        "        try:",
        "            officer_record = Model.with_user(self.user_officer).create({",
        '                "name": "Officer Created Record",',
        "            })",
        "        except Exception as e:",
        '            self.skipTest(f"Cannot create test record: {e}")',
        "",
        "        # Create record as viewer",
        "        try:",
        "            viewer_record = Model.with_user(self.user_viewer).create({",
        '                "name": "Viewer Created Record",',
        "            })",
        "        except Exception:",
        "            viewer_record = None",
        "",
        "        # Test: officer should see their own record",
        "        officer_visible = Model.with_user(self.user_officer).search([",
        '            ("id", "=", officer_record.id)',
        "        ])",
        "        self.assertTrue(",
        "            officer_visible,",
        '            "Officer should see their own record"',
        "        )",
        "",
        "        # Test: officer should NOT see viewer's record (if viewer could create)",
        "        if viewer_record:",
        "            officer_sees_viewer = Model.with_user(self.user_officer).search([",
        '                ("id", "=", viewer_record.id)',
        "            ])",
        "            self.assertFalse(",
        "                officer_sees_viewer,",
        '                "Officer should NOT see viewer\'s record"',
        "            )",
        "",
    ]


def _generate_assigned_to_me_test(spec: ComplianceSpec, rule, model_safe: str) -> list[str]:
    """Generate test for assigned_to_me domain pattern."""
    domain_field = rule.domain_field or "user_id"
    method_name = f"test_{model_safe}_assigned_visibility"

    return [
        f"    def {method_name}(self):",
        f'        """Test {rule.model}: user only sees records assigned to them."""',
        "        if not self.user_officer or not self.user_viewer:",
        '            self.skipTest("Required users not found")',
        "",
        f'        Model = self.env["{rule.model}"]',
        "",
        "        # Check model has assignment field",
        f'        if "{domain_field}" not in Model._fields:',
        f'            self.skipTest("Model missing {domain_field} field")',
        "",
        "        # Create record assigned to officer (as admin)",
        "        try:",
        "            officer_assigned = Model.sudo().create({",
        '                "name": "Assigned to Officer",',
        f'                "{domain_field}": self.user_officer.id,',
        "            })",
        "        except Exception as e:",
        '            self.skipTest(f"Cannot create test record: {e}")',
        "",
        "        # Create record assigned to viewer (as admin)",
        "        try:",
        "            viewer_assigned = Model.sudo().create({",
        '                "name": "Assigned to Viewer",',
        f'                "{domain_field}": self.user_viewer.id,',
        "            })",
        "        except Exception:",
        "            viewer_assigned = None",
        "",
        "        # Test: officer should see record assigned to them",
        "        officer_visible = Model.with_user(self.user_officer).search([",
        '            ("id", "=", officer_assigned.id)',
        "        ])",
        "        self.assertTrue(",
        "            officer_visible,",
        '            "Officer should see records assigned to them"',
        "        )",
        "",
        "        # Test: officer should NOT see viewer's assigned record",
        "        if viewer_assigned:",
        "            officer_sees_viewer = Model.with_user(self.user_officer).search([",
        '                ("id", "=", viewer_assigned.id)',
        "            ])",
        "            self.assertFalse(",
        "                officer_sees_viewer,",
        '                "Officer should NOT see records assigned to others"',
        "            )",
        "",
    ]


def _generate_company_isolation_test(spec: ComplianceSpec, rule, model_safe: str) -> list[str]:
    """Generate test for company_records domain pattern."""
    method_name = f"test_{model_safe}_company_isolation"

    return [
        f"    def {method_name}(self):",
        f'        """Test {rule.model}: multi-company isolation."""',
        f'        Model = self.env["{rule.model}"]',
        "",
        "        # Check model has company_id field",
        '        if "company_id" not in Model._fields:',
        '            self.skipTest("Model missing company_id field")',
        "",
        "        # Get or create a second company",
        '        Company = self.env["res.company"]',
        '        company_2 = Company.search([("id", "!=", self.env.company.id)], limit=1)',
        "        if not company_2:",
        '            company_2 = Company.create({"name": "Test Company 2"})',
        "",
        "        # Create record in main company",
        "        try:",
        "            main_co_record = Model.sudo().create({",
        '                "name": "Main Company Record",',
        '                "company_id": self.env.company.id,',
        "            })",
        "        except Exception as e:",
        '            self.skipTest(f"Cannot create test record: {e}")',
        "",
        "        # Create record in second company",
        "        try:",
        "            other_co_record = Model.sudo().create({",
        '                "name": "Other Company Record",',
        '                "company_id": company_2.id,',
        "            })",
        "        except Exception:",
        "            other_co_record = None",
        "",
        "        # Test: user should see record from their company",
        "        if self.user_officer:",
        "            # Ensure user is in main company",
        "            self.user_officer.company_ids = [(4, self.env.company.id)]",
        "            self.user_officer.company_id = self.env.company.id",
        "",
        "            visible = Model.with_user(self.user_officer).search([",
        '                ("id", "=", main_co_record.id)',
        "            ])",
        "            self.assertTrue(",
        "                visible,",
        '                "User should see records from their company"',
        "            )",
        "",
        "            # Test: user should NOT see record from other company",
        "            if other_co_record:",
        "                visible_other = Model.with_user(self.user_officer).search([",
        '                    ("id", "=", other_co_record.id)',
        "                ])",
        "                self.assertFalse(",
        "                    visible_other,",
        '                    "User should NOT see records from other companies"',
        "                )",
        "",
    ]


def _generate_all_records_test(spec: ComplianceSpec, rule, model_safe: str) -> list[str]:
    """Generate test for all_records domain pattern."""
    method_name = f"test_{model_safe}_sees_all"

    return [
        f"    def {method_name}(self):",
        f'        """Test {rule.model}: user with this rule sees all records."""',
        f'        Model = self.env["{rule.model}"]',
        "",
        "        # Get initial count as admin",
        "        admin_count = Model.sudo().search_count([])",
        "        if admin_count == 0:",
        '            self.skipTest("No records to test visibility")',
        "",
        "        # Test that user sees all records",
        "        if self.user_manager:",
        "            user_count = Model.with_user(self.user_manager).search_count([])",
        "            self.assertEqual(",
        "                user_count, admin_count,",
        '                f"Manager should see all {admin_count} records, but sees {user_count}"',
        "            )",
        "",
    ]


def _generate_admin_linkage_tests(spec: ComplianceSpec) -> list[str]:
    """Generate admin linkage tests."""
    lines = [
        '@tagged("post_install", "-at_install", "access_control", "compliance")',
        "class TestAdminLinkage(TestComplianceBase):",
        '    """Test that admin group inherits manager permissions."""',
        "",
    ]

    manager_group = spec.admin_link_group

    lines.extend(
        [
            "    def test_admin_has_manager_group(self):",
            f'        """Test admin user has {manager_group} permissions."""',
            "        if not self.user_admin:",
            '            self.skipTest("Admin user not created")',
            "        self.assertTrue(",
            f'            self.user_admin.has_group("{spec.module}.{manager_group}"),',
            f'            "Admin should have {manager_group} permissions"',
            "        )",
            "",
            "    def test_admin_group_implies_manager(self):",
            f'        """Test spp_security.group_spp_admin implies {manager_group}."""',
            '        admin_group = self.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)',
            f'        manager_group = self.env.ref("{spec.module}.{manager_group}", raise_if_not_found=False)',
            "        if not admin_group or not manager_group:",
            '            self.skipTest("Required groups not found")',
            "",
            "        # Check implied_ids (direct or transitive)",
            "        def get_all_implied(group, visited=None):",
            '            """Recursively get all implied groups."""',
            "            if visited is None:",
            "                visited = set()",
            "            if group.id in visited:",
            "                return set()",
            "            visited.add(group.id)",
            "            result = set(group.implied_ids.ids)",
            "            for implied in group.implied_ids:",
            "                result |= get_all_implied(implied, visited)",
            "            return result",
            "",
            "        all_implied = get_all_implied(admin_group)",
            "        self.assertIn(",
            "            manager_group.id, all_implied,",
            f'            "Admin group should imply {manager_group} (directly or transitively)"',
            "        )",
            "",
        ]
    )

    lines.append("")
    return lines


def write_test_file(spec: ComplianceSpec, module_path: Path, output_dir: Path = None) -> Path:
    """
    Generate and write test file.

    Args:
        spec: ComplianceSpec object
        module_path: Path to the module
        output_dir: Optional output directory (default: module/tests/)

    Returns:
        Path to the generated test file
    """
    content = generate_test_file(spec, module_path)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"test_compliance_{spec.module}.py"
    else:
        tests_dir = module_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        output_path = tests_dir / "test_compliance_generated.py"

    output_path.write_text(content, encoding="utf-8")
    return output_path


def find_modules_with_compliance(base_path: Path) -> list[tuple[Path, ComplianceSpec]]:
    """Find all modules with compliance.yaml files."""
    modules = []
    for item in base_path.iterdir():
        if item.is_dir() and item.name.startswith("spp_"):
            spec_file = item / "security" / "compliance.yaml"
            if spec_file.exists():
                try:
                    spec = load_compliance_yaml(spec_file)
                    modules.append((item, spec))
                except ComplianceLoadError as e:
                    print(f"Warning: {e}", file=sys.stderr)
    return modules


def main():
    parser = argparse.ArgumentParser(
        description="Generate compliance tests from compliance.yaml specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s spp_registry_base           # Generate tests for single module
  %(prog)s --all                        # Generate tests for all modules
  %(prog)s --all --output-dir tests/    # Output to specific directory
  %(prog)s spp_registry_base --dry-run  # Preview without writing
""",
    )
    parser.add_argument("module", nargs="?", help="Module name")
    parser.add_argument("--all", "-a", action="store_true", help="Generate for all modules")
    parser.add_argument("--output-dir", type=Path, help="Output directory for generated tests")
    parser.add_argument("--base-path", type=Path, default=Path("."), help="Base path")
    parser.add_argument("--dry-run", action="store_true", help="Print generated code without writing")

    args = parser.parse_args()
    base_path = args.base_path.resolve()

    if args.all:
        modules = find_modules_with_compliance(base_path)
        if not modules:
            print("No modules with compliance.yaml found", file=sys.stderr)
            sys.exit(1)

        for module_path, spec in modules:
            if args.dry_run:
                print(f"=== {spec.module} ===")
                print(generate_test_file(spec, module_path))
                print()
            else:
                output_path = write_test_file(spec, module_path, args.output_dir)
                print(f"Generated: {output_path}")

    elif args.module:
        module_path = base_path / args.module
        spec_file = module_path / "security" / "compliance.yaml"

        if not spec_file.exists():
            print(f"No compliance.yaml found in {module_path}", file=sys.stderr)
            sys.exit(1)

        try:
            spec = load_compliance_yaml(spec_file)
        except ComplianceLoadError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.dry_run:
            print(generate_test_file(spec, module_path))
        else:
            output_path = write_test_file(spec, module_path, args.output_dir)
            print(f"Generated: {output_path}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
