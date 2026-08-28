"""Extended tests for Change Request Conflict Detection and Duplicate Prevention.

This file contains additional test cases to achieve comprehensive coverage of:
- Group scope conflicts
- Field-level conflicts
- Cross-type conflicts
- Duplicate detection edge cases
- Wizard functionality
- Integration workflows
- Spec scenarios
"""

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestConflictRuleAdvanced(TransactionCase):
    """Advanced tests for conflict rule configuration and behavior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_type_1 = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Address",
                "code": "edit_address",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
            }
        )
        cls.cr_type_2 = cls.env["spp.change.request.type"].create(
            {
                "name": "Exit Program",
                "code": "exit_program",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
            }
        )

    def test_inactive_rule_ignored(self):
        """Test that inactive rules are not applied."""
        rule = self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Inactive Rule",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "block",
                "active": False,
            }
        )

        self.assertFalse(rule.active)
        # Rule should exist but not be applied in conflict detection
        self.cr_type_1.enable_conflict_detection = True

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create two CRs - should not conflict since rule is inactive
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )

        self.assertEqual(cr2.conflict_status, "none")

    def test_log_action_no_blocking(self):
        """Test that 'log' action doesn't block submission."""
        self.cr_type_1.enable_conflict_detection = True
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Log Only",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "log",
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )

        # Should detect conflict but status should be none (log only)
        self.assertEqual(cr2.conflict_status, "none")
        self.assertIn(cr1, cr2.conflicting_cr_ids)

    def test_conflict_type_ids_filtering(self):
        """Test conflict_type_ids filters to specific CR types."""
        self.cr_type_1.enable_conflict_detection = True

        # Rule that only checks for conflicts with cr_type_2
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Block Exit Type",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "block",
                "check_same_type_only": False,
                "conflict_type_ids": [(6, 0, [self.cr_type_2.id])],
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create CR of type 1
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )

        # Create another CR of type 1 - should NOT conflict
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )
        self.assertEqual(cr2.conflict_status, "none")

        # Create CR of type 2 - SHOULD conflict
        cr3 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_2.id,
                "registrant_id": registrant.id,
            }
        )

        # Re-check cr2 for conflicts with cr3
        cr2._run_conflict_checks()
        self.assertEqual(cr2.conflict_status, "blocked")
        self.assertIn(cr3, cr2.conflicting_cr_ids)

    def test_multiple_rules_block_takes_precedence(self):
        """Test that block action takes precedence over warn."""
        self.cr_type_1.enable_conflict_detection = True

        # Create two rules: warn and block
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Warn Rule",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "warn",
                "sequence": 10,
            }
        )
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Block Rule",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "block",
                "sequence": 20,
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )

        # Should be blocked, not just warned
        self.assertEqual(cr2.conflict_status, "blocked")

    def test_conflict_states_pending_only(self):
        """Test conflict_states='pending_only' filtering."""
        self.cr_type_1.enable_conflict_detection = True
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Pending Only",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "warn",
                "conflict_states": "pending_only",
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create draft CR
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )

        # Create another CR - should NOT conflict (cr1 is draft, not pending)
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )
        self.assertEqual(cr2.conflict_status, "none")

        # Change cr1 to pending
        cr1.write({"approval_state": "pending"})

        # Re-check cr2 - should now conflict
        cr2._run_conflict_checks()
        self.assertEqual(cr2.conflict_status, "warning")

    def test_get_conflict_message_custom(self):
        """Test custom conflict message."""
        rule = self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Custom Message Rule",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "block",
                "conflict_message": "Custom conflict detected!",
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_1.id,
                "registrant_id": registrant.id,
            }
        )

        message = rule.get_conflict_message(cr1)
        self.assertEqual(message, "Custom conflict detected!")

    def test_get_conflict_message_many_crs(self):
        """Test conflict message with many conflicting CRs (>5)."""
        rule = self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Test Rule",
                "cr_type_id": self.cr_type_1.id,
                "scope": "registrant",
                "action": "block",
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create 7 CRs
        crs = self.env["spp.change.request"]
        for _i in range(7):
            crs |= self.env["spp.change.request"].create(
                {
                    "request_type_id": self.cr_type_1.id,
                    "registrant_id": registrant.id,
                }
            )

        message = rule.get_conflict_message(crs)
        # Should show first 5 and "+2 more"
        self.assertIn("+2 more", message)


class TestFieldLevelConflicts(TransactionCase):
    """Test field-level conflict detection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Individual",
                "code": "edit_ind_field",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        cls.field_rule = cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Address Field Rule",
                "cr_type_id": cls.cr_type.id,
                "scope": "field",
                "action": "warn",
                "conflict_fields": "address_line1, city",
            }
        )

    def test_field_conflict_same_field(self):
        """Test field-level conflict when same field is modified."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create CR1 modifying street
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write({"address_line1": "123 Old Street"})

        # Create CR2 also modifying street
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write({"address_line1": "456 New Street"})

        # Re-run conflict check
        cr2._run_conflict_checks()

        # Should conflict (both modify street)
        self.assertEqual(cr2.conflict_status, "warning")
        self.assertIn(cr1, cr2.conflicting_cr_ids)

    def test_field_no_conflict_different_field(self):
        """Test no field conflict when different fields modified."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # CR1 modifies street
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write({"address_line1": "123 Old Street"})

        # CR2 modifies phone (not in conflict_fields)
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write({"phone": "555-1234"})

        cr2._run_conflict_checks()

        # Should NOT conflict (different fields)
        self.assertEqual(cr2.conflict_status, "none")

    def test_field_conflict_no_detail(self):
        """Test field conflict when CR has no detail."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create CRs without details
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Should not crash, no conflict detected
        self.assertEqual(cr2.conflict_status, "none")


class TestGroupScopeConflicts(TransactionCase):
    """Test group/household scope conflict detection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Member",
                "code": "edit_member_group",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        cls.group_rule = cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Group Scope Rule",
                "cr_type_id": cls.cr_type.id,
                "scope": "group",
                "action": "warn",
            }
        )

    def _create_household(self):
        """Create a household with two member individuals and return all three."""
        group = self.env["res.partner"].create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        individual1 = self.env["res.partner"].create(
            {
                "name": "Member 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        individual2 = self.env["res.partner"].create(
            {
                "name": "Member 2",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.env["spp.group.membership"].create(
            [
                {"group": group.id, "individual": individual1.id},
                {"group": group.id, "individual": individual2.id},
            ]
        )
        return group, individual1, individual2

    def test_group_scope_same_household_members(self):
        """Test group scope detects conflicts for household members."""
        group, individual1, individual2 = self._create_household()

        # Create CR for individual2 first, then for individual1: the group-scope
        # rule must flag the second CR because both registrants share a household.
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": individual2.id,
            }
        )
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": individual1.id,
            }
        )

        # _get_group_member_ids resolves the household and every co-member
        member_ids = cr1._get_group_member_ids()
        self.assertIn(individual1.id, member_ids)
        self.assertIn(group.id, member_ids)
        self.assertIn(individual2.id, member_ids)

        # The rule's action is "warn", so the second CR is flagged, not blocked
        self.assertEqual(cr1.conflict_status, "warning")

    def test_group_scope_group_registrant(self):
        """A CR whose registrant is the group itself resolves its members."""
        group, individual1, individual2 = self._create_household()

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": group.id,
            }
        )

        member_ids = cr._get_group_member_ids()
        self.assertIn(group.id, member_ids)
        self.assertIn(individual1.id, member_ids)
        self.assertIn(individual2.id, member_ids)

    def test_group_scope_ended_membership_excluded(self):
        """Members whose membership has ended are not conflict candidates."""
        group, individual1, individual2 = self._create_household()
        membership2 = self.env["spp.group.membership"].search(
            [("group", "=", group.id), ("individual", "=", individual2.id)]
        )
        membership2.ended_date = fields.Datetime.now()

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": individual1.id,
            }
        )

        member_ids = cr._get_group_member_ids()
        self.assertIn(individual1.id, member_ids)
        self.assertIn(group.id, member_ids)
        self.assertNotIn(individual2.id, member_ids)


class TestDuplicateDetectionAdvanced(TransactionCase):
    """Advanced duplicate detection tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Individual Dup",
                "code": "edit_ind_dup_adv",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_duplicate_detection": True,
            }
        )

        cls.config = cls.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": cls.cr_type.id,
                "time_window_hours": 48,
                "similarity_threshold": 80.0,
            }
        )
        cls.cr_type.duplicate_detection_config_id = cls.config.id

    def test_fuzzy_similarity_string_contains(self):
        """Test fuzzy similarity for strings (substring match)."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "given_name": "John",
                "family_name": "Doe",
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "Johnny",  # Similar but not exact
                "family_name": "Doe",
            }
        )

        cr2._run_conflict_checks()

        # Should detect as potential duplicate with partial similarity
        # Exact family_name + fuzzy given_name
        self.assertEqual(cr2.duplicate_status, "potential")

    def test_normalize_field_value_many2one(self):
        """Test field normalization for Many2one fields.

        _normalize_field_value returns a tuple of IDs for recordsets
        to allow proper comparison across different recordset sizes.
        """
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Test normalization - returns tuple of IDs for recordsets
        normalized = cr._normalize_field_value(registrant)
        self.assertEqual(normalized, (registrant.id,))

    def test_normalize_field_value_false(self):
        """Test that False is normalized to None."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        normalized = cr._normalize_field_value(False)
        self.assertIsNone(normalized)

    def test_auto_merge_states_list(self):
        """Test get_auto_merge_states_list method."""
        self.config.auto_merge_enabled = True
        self.config.auto_merge_states = "draft_only"

        states = self.config.get_auto_merge_states_list()
        self.assertEqual(states, ["draft"])

        self.config.auto_merge_states = "draft_pending"
        states = self.config.get_auto_merge_states_list()
        self.assertEqual(states, ["draft", "pending"])

        self.config.auto_merge_enabled = False
        states = self.config.get_auto_merge_states_list()
        self.assertEqual(states, [])

    def test_similarity_empty_check_fields(self):
        """Test similarity calculation with no check_fields (compare all)."""
        self.config.check_fields = False

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "given_name": "John",
                "family_name": "Doe",
                "phone": "555-1234",
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "John",
                "family_name": "Doe",
                "phone": "555-1234",
            }
        )

        # Calculate similarity
        similarity = cr2._calculate_similarity(cr1, self.config)

        # Should be high (all fields match)
        self.assertGreater(similarity, 90.0)


class TestIntegrationWorkflows(TransactionCase):
    """End-to-end integration workflow tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Individual Workflow",
                "code": "edit_ind_workflow",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        cls.conflict_rule = cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Block Same Registrant",
                "cr_type_id": cls.cr_type.id,
                "scope": "registrant",
                "action": "block",
            }
        )

        cls.override_group = cls.env.ref("spp_change_request_v2.group_cr_conflict_approver")
        cls.cr_manager_group = cls.env.ref("spp_change_request_v2.group_cr_manager")
        cls.approval_manager_group = cls.env.ref("spp_approval.group_approval_manager")
        cls.base_user_group = cls.env.ref("base.group_user")
        cls.override_user = cls.env["res.users"].create(
            {
                "name": "Override User",
                "login": "override_user_workflow",
                "group_ids": [
                    Command.link(cls.base_user_group.id),  # Internal user
                    Command.link(cls.override_group.id),
                    Command.link(cls.test_group.id),  # Approval group
                    Command.link(cls.cr_manager_group.id),  # CR manager for model access
                    Command.link(cls.approval_manager_group.id),  # Approval definitions access
                ],
            }
        )

    def test_full_workflow_create_conflict_override_submit(self):
        """Test full workflow: create → conflict → override → submit."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Step 1: Create first CR
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        self.assertEqual(cr1.conflict_status, "none")

        # Step 2: Create second CR - should detect conflict
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        self.assertEqual(cr2.conflict_status, "blocked")
        self.assertIn(cr1, cr2.conflicting_cr_ids)

        # Step 3: Try to submit - should fail with UserError due to blocking conflict
        with self.assertRaises(UserError):
            cr2.action_submit_for_approval()

        # Step 4: Override conflict
        reason = "Reviewed manually, safe to proceed with both changes"
        cr2.with_user(self.override_user).action_override_conflict(reason)

        self.assertEqual(cr2.conflict_status, "overridden")
        self.assertEqual(cr2.conflict_override_user_id, self.override_user)
        self.assertEqual(cr2.conflict_override_reason, reason)

        # Step 5: Now submission should succeed
        cr2.action_submit_for_approval()
        self.assertEqual(cr2.approval_state, "pending")

    def test_conflict_at_approval_time(self):
        """Test new conflict detected at approval time."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Temporarily disable conflict detection to create and submit both CRs
        self.cr_type.enable_conflict_detection = False

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Submit both CRs while detection is disabled
        cr1.action_submit_for_approval()
        self.assertEqual(cr1.approval_state, "pending")
        cr2.action_submit_for_approval()
        self.assertEqual(cr2.approval_state, "pending")

        # Re-enable conflict detection
        self.cr_type.enable_conflict_detection = True

        # Try to approve cr1 - should fail due to conflict with cr2
        # (use override_user who has approval permissions)
        with self.assertRaises(ValidationError):
            cr1.with_user(self.override_user).action_approve()

    def test_write_triggers_recheck(self):
        """Test that write() triggers conflict re-check."""
        registrant1 = self.env["res.partner"].create(
            {
                "name": "Person 1",
                "is_registrant": True,
            }
        )
        registrant2 = self.env["res.partner"].create(
            {
                "name": "Person 2",
                "is_registrant": True,
            }
        )

        # Create CR for registrant1
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant1.id,
            }
        )

        # Create CR for registrant2
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant2.id,
            }
        )

        # No conflict initially
        self.assertEqual(cr2.conflict_status, "none")

        # Change cr2's registrant to registrant1
        cr2.write({"registrant_id": registrant1.id})

        # Should now have conflict
        self.assertEqual(cr2.conflict_status, "blocked")


class TestConflictWizard(TransactionCase):
    """Test conflict resolution wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Individual Wizard",
                "code": "edit_ind_wizard",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Block Rule",
                "cr_type_id": cls.cr_type.id,
                "scope": "registrant",
                "action": "block",
            }
        )

        cls.override_group = cls.env.ref("spp_change_request_v2.group_cr_conflict_approver")
        cls.override_user = cls.env["res.users"].create(
            {
                "name": "Override User Wizard",
                "login": "override_user_wizard",
                "group_ids": [Command.link(cls.override_group.id)],
            }
        )

        cls.normal_group = cls.env.ref("spp_change_request_v2.group_cr_user")
        cls.normal_user = cls.env["res.users"].create(
            {
                "name": "Normal User Wizard",
                "login": "normal_user_wizard",
                "group_ids": [Command.link(cls.normal_group.id)],
            }
        )

    def test_wizard_creation(self):
        """Test wizard basic creation."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = self.env["spp.cr.conflict.wizard"].create(
            {
                "change_request_id": cr2.id,
            }
        )

        self.assertEqual(wizard.change_request_id, cr2)
        self.assertEqual(wizard.conflict_status, "blocked")
        self.assertEqual(wizard.conflict_count, 1)
        self.assertIn(cr1, wizard.conflicting_cr_ids)

    def test_wizard_can_override_permission(self):
        """Test can_override computed field."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Wizard with override user
        wizard_override = (
            self.env["spp.cr.conflict.wizard"]
            .with_user(self.override_user)
            .create(
                {
                    "change_request_id": cr2.id,
                }
            )
        )
        self.assertTrue(wizard_override.can_override)

        # Wizard with normal user
        wizard_normal = (
            self.env["spp.cr.conflict.wizard"]
            .with_user(self.normal_user)
            .create(
                {
                    "change_request_id": cr2.id,
                }
            )
        )
        self.assertFalse(wizard_normal.can_override)

    def test_wizard_override_action(self):
        """Test wizard override action."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = (
            self.env["spp.cr.conflict.wizard"]
            .with_user(self.override_user)
            .create(
                {
                    "change_request_id": cr2.id,
                    "resolution_action": "request_review",
                    "override_reason": "This is a valid override reason that is long enough",
                }
            )
        )

        result = wizard.action_resolve()

        # Check CR was overridden
        self.assertEqual(cr2.conflict_status, "overridden")
        self.assertEqual(result["type"], "ir.actions.client")

    def test_wizard_override_requires_reason(self):
        """Test wizard override requires justification."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = (
            self.env["spp.cr.conflict.wizard"]
            .with_user(self.override_user)
            .create(
                {
                    "change_request_id": cr2.id,
                    "resolution_action": "request_review",
                    "override_reason": "short",
                }
            )
        )

        with self.assertRaises(ValidationError):
            wizard.action_resolve()

    def test_wizard_cancel_conflicting(self):
        """Test wizard cancel conflicting CRs action."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = self.env["spp.cr.conflict.wizard"].create(
            {
                "change_request_id": cr2.id,
                "resolution_action": "cancel_conflicting",
                "crs_to_cancel": [(6, 0, [cr1.id])],
                "cancel_reason": "Canceling due to conflict",
            }
        )

        wizard.action_resolve()

        # cr1 should be deleted (was draft)
        self.assertFalse(cr1.exists())

    def test_wizard_cancel_this(self):
        """Test wizard cancel this CR action."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = self.env["spp.cr.conflict.wizard"].create(
            {
                "change_request_id": cr2.id,
                "resolution_action": "cancel_this",
                "cancel_reason": "Canceling this CR",
            }
        )

        wizard.action_resolve()

        # cr2 should be deleted
        self.assertFalse(cr2.exists())

    def test_wizard_wait_action(self):
        """Test wizard wait action (does nothing)."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = self.env["spp.cr.conflict.wizard"].create(
            {
                "change_request_id": cr2.id,
                "resolution_action": "wait",
            }
        )

        result = wizard.action_resolve()

        # Should just close the wizard
        self.assertEqual(result["type"], "ir.actions.act_window_close")
        self.assertEqual(cr2.conflict_status, "blocked")  # Unchanged

    def test_wizard_comparison_html(self):
        """Test wizard generates comparison HTML."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        wizard = self.env["spp.cr.conflict.wizard"].create(
            {
                "change_request_id": cr2.id,
            }
        )

        # Should have comparison HTML
        self.assertTrue(wizard.comparison_html)
        self.assertIn("<table", wizard.comparison_html)


class TestViewActionsAndHelpers(TransactionCase):
    """Test view actions and helper methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Individual Actions",
                "code": "edit_ind_actions",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Warn Rule",
                "cr_type_id": cls.cr_type.id,
                "scope": "registrant",
                "action": "warn",
            }
        )

    def test_action_view_conflicts(self):
        """Test action_view_conflicts returns correct action."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        action = cr2.action_view_conflicts()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.change.request")
        self.assertIn(cr1.id, action["domain"][0][2])

    def test_action_view_duplicates(self):
        """Test action_view_duplicates returns correct action."""
        self.cr_type.enable_duplicate_detection = True
        config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.cr_type.id,
                "similarity_threshold": 80.0,
            }
        )
        self.cr_type.duplicate_detection_config_id = config.id

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        action = cr2.action_view_duplicates()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.change.request")

    def test_action_open_conflict_wizard(self):
        """Test action_open_conflict_wizard creates wizard."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        action = cr2.action_open_conflict_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cr.conflict.wizard")
        self.assertTrue(action["res_id"])

    def test_action_recheck_conflicts(self):
        """Test action_recheck_conflicts re-runs detection."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        action = cr.action_recheck_conflicts()

        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")

    def test_get_conflict_summary(self):
        """Test get_conflict_summary returns correct data."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        summary = cr2.get_conflict_summary()

        self.assertTrue(summary["has_conflicts"])
        self.assertEqual(summary["conflict_status"], "warning")
        self.assertEqual(summary["conflict_count"], 1)
        self.assertFalse(summary["is_blocked"])

    def test_can_be_submitted(self):
        """Test can_be_submitted checks conflicts."""
        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        can_submit, msg = cr.can_be_submitted()
        self.assertTrue(can_submit)

        # Change to blocked
        cr.write({"conflict_status": "blocked"})
        can_submit, msg = cr.can_be_submitted()
        self.assertFalse(can_submit)


class TestSpecScenarios(TransactionCase):
    """Test specific scenarios from the specification."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        # CR type for address edits
        cls.cr_type_address = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Address",
                "code": "edit_address_spec",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        # CR type for exit
        cls.cr_type_exit = cls.env["spp.change.request.type"].create(
            {
                "name": "Exit Program",
                "code": "exit_program_spec",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

    def test_scenario_1_concurrent_field_updates(self):
        """Spec Scenario 1: Concurrent address updates to different values."""
        # Field-level conflict rule
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Address Field Conflict",
                "cr_type_id": self.cr_type_address.id,
                "scope": "field",
                "action": "warn",
                "conflict_fields": "address_line1",
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Worker A submits CR to change address to "New Street A"
        cr_a = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_address.id,
                "registrant_id": registrant.id,
            }
        )
        detail_a = cr_a.get_detail()
        detail_a.write({"address_line1": "New Street A"})

        # Worker B submits CR to change address to "New Street B"
        cr_b = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_address.id,
                "registrant_id": registrant.id,
            }
        )
        detail_b = cr_b.get_detail()
        detail_b.write({"address_line1": "New Street B"})

        cr_b._run_conflict_checks()

        # Should detect conflict (warning level)
        self.assertEqual(cr_b.conflict_status, "warning")
        self.assertIn(cr_a, cr_b.conflicting_cr_ids)

    def test_scenario_3_network_induced_duplicates(self):
        """Spec Scenario 3: Network-induced duplicates (double-click)."""
        self.cr_type_address.enable_duplicate_detection = True
        config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.cr_type_address.id,
                "time_window_hours": 1,  # Very short window
                "similarity_threshold": 95.0,
                "check_fields": "address_line1, city",  # Only check these fields
            }
        )
        self.cr_type_address.duplicate_detection_config_id = config

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # User clicks submit
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_address.id,
                "registrant_id": registrant.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "address_line1": "123 Main St",
                "city": "Testville",
            }
        )

        # User clicks submit again (slow network)
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_address.id,
                "registrant_id": registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "address_line1": "123 Main St",
                "city": "Testville",
            }
        )

        cr2._run_conflict_checks()

        # Should detect as duplicate
        self.assertEqual(cr2.duplicate_status, "potential")
        self.assertIn(cr1, cr2.potential_duplicate_ids)
        self.assertGreaterEqual(cr2.duplicate_similarity_score, 95.0)

    def test_scenario_4_cross_type_conflicts(self):
        """Spec Scenario 4: Cross-type conflicts (exit blocks other changes)."""
        # Rule: Exit CR blocks all other CR types
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Exit Blocks All",
                "cr_type_id": self.cr_type_exit.id,
                "scope": "registrant",
                "action": "block",
                "check_same_type_only": False,  # Check all types
            }
        )

        # Rule: Other CRs blocked by exit
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Blocked by Exit",
                "cr_type_id": self.cr_type_address.id,
                "scope": "registrant",
                "action": "block",
                "check_same_type_only": False,
                "conflict_type_ids": [(6, 0, [self.cr_type_exit.id])],
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        # Create exit CR
        cr_exit = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_exit.id,
                "registrant_id": registrant.id,
            }
        )

        # Try to create address change - should be blocked
        cr_address = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_address.id,
                "registrant_id": registrant.id,
            }
        )

        # Should detect blocking conflict
        self.assertEqual(cr_address.conflict_status, "blocked")
        self.assertIn(cr_exit, cr_address.conflicting_cr_ids)


class TestEdgeCases(TransactionCase):
    """Test edge cases and error conditions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create({"name": "Test Approval Group Ext"})
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Edit Individual Edge",
                "code": "edit_ind_edge",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
            }
        )

    def test_conflict_detection_disabled(self):
        """Test that conflict detection is skipped when disabled."""
        self.cr_type.enable_conflict_detection = False

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Should not detect conflicts
        self.assertEqual(cr2.conflict_status, "none")
        self.assertEqual(len(cr2.conflicting_cr_ids), 0)

    def test_duplicate_detection_disabled(self):
        """Test that duplicate detection is skipped when disabled."""
        self.cr_type.enable_duplicate_detection = False

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Should not detect duplicates
        self.assertEqual(cr2.duplicate_status, "none")

    def test_no_registrant(self):
        """Test conflict detection when CR has no registrant."""
        self.cr_type.enable_conflict_detection = True
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Test Rule",
                "cr_type_id": self.cr_type.id,
                "scope": "registrant",
                "action": "warn",
            }
        )

        # Create CR without registrant (if allowed by model)
        # This may raise an error if registrant is required
        # Test depends on actual model constraints

    def test_conflict_with_rejected_cr(self):
        """Test that rejected CRs don't cause conflicts."""
        self.cr_type.enable_conflict_detection = True
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Test Rule",
                "cr_type_id": self.cr_type.id,
                "scope": "registrant",
                "action": "warn",
                "conflict_states": "all_active",
            }
        )

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        # Reject cr1
        cr1.write({"approval_state": "rejected"})

        # Create cr2 - should NOT conflict with rejected cr1
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        self.assertEqual(cr2.conflict_status, "none")

    def test_empty_conflict_messages(self):
        """Test handling of empty conflict messages."""
        self.cr_type.enable_conflict_detection = True

        registrant = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
            }
        )

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant.id,
            }
        )

        summary = cr.get_conflict_summary()
        self.assertEqual(summary["messages"], [])
