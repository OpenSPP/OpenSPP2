"""Tests for Change Request Conflict Detection and Duplicate Prevention."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestConflictRule(TransactionCase):
    """Test spp.cr.conflict.rule model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Test Edit Individual",
                "code": "test_edit_individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
            }
        )

    def test_conflict_rule_creation(self):
        """Test basic conflict rule creation."""
        rule = self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Test Conflict Rule",
                "cr_type_id": self.cr_type.id,
                "scope": "registrant",
                "action": "warn",
            }
        )
        self.assertTrue(rule.id)
        self.assertEqual(rule.scope, "registrant")
        self.assertEqual(rule.action, "warn")
        self.assertEqual(rule.conflict_states, "all_active")

    def test_conflict_rule_field_scope_requires_fields(self):
        """Test that field scope requires conflict_fields to be set."""
        with self.assertRaises(ValidationError):
            self.env["spp.cr.conflict.rule"].create(
                {
                    "name": "Field Scope Rule",
                    "cr_type_id": self.cr_type.id,
                    "scope": "field",
                    "action": "warn",
                    # Missing conflict_fields
                }
            )

    def test_conflict_rule_field_scope_with_fields(self):
        """Test field scope with conflict_fields set."""
        rule = self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Field Scope Rule",
                "cr_type_id": self.cr_type.id,
                "scope": "field",
                "action": "warn",
                "conflict_fields": "given_name, family_name",
            }
        )
        self.assertEqual(rule.get_conflict_fields_list(), ["given_name", "family_name"])

    def test_conflict_states_list(self):
        """Test get_conflict_states_list method."""
        rule = self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Test Rule",
                "cr_type_id": self.cr_type.id,
                "scope": "registrant",
                "action": "block",
                "conflict_states": "pending_only",
            }
        )
        self.assertEqual(rule.get_conflict_states_list(), ["pending"])

        rule.conflict_states = "approved_only"
        self.assertEqual(rule.get_conflict_states_list(), ["approved"])

        rule.conflict_states = "pending_approved"
        self.assertEqual(rule.get_conflict_states_list(), ["pending", "approved"])

        rule.conflict_states = "all_active"
        self.assertEqual(rule.get_conflict_states_list(), ["draft", "pending", "approved"])


class TestDuplicateConfig(TransactionCase):
    """Test spp.cr.duplicate.config model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Test Edit Individual",
                "code": "test_edit_ind_dup",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
            }
        )

    def test_duplicate_config_creation(self):
        """Test basic duplicate config creation."""
        config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.cr_type.id,
                "time_window_hours": 48,
                "similarity_threshold": 85.0,
            }
        )
        self.assertTrue(config.id)
        self.assertEqual(config.time_window_hours, 48)
        self.assertEqual(config.similarity_threshold, 85.0)

    def test_duplicate_config_unique_per_type(self):
        """Test that only one duplicate config per CR type is allowed."""
        self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.cr_type.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["spp.cr.duplicate.config"].create(
                {
                    "cr_type_id": self.cr_type.id,
                }
            )

    def test_similarity_threshold_validation(self):
        """Test similarity threshold must be between 0 and 100."""
        with self.assertRaises(ValidationError):
            self.env["spp.cr.duplicate.config"].create(
                {
                    "cr_type_id": self.cr_type.id,
                    "similarity_threshold": 150.0,
                }
            )

        with self.assertRaises(ValidationError):
            self.env["spp.cr.duplicate.config"].create(
                {
                    "cr_type_id": self.cr_type.id,
                    "similarity_threshold": -10.0,
                }
            )

    def test_time_window_validation(self):
        """Test time window must be non-negative."""
        with self.assertRaises(ValidationError):
            self.env["spp.cr.duplicate.config"].create(
                {
                    "cr_type_id": self.cr_type.id,
                    "time_window_hours": -5,
                }
            )

    def test_check_fields_list(self):
        """Test get_check_fields_list method."""
        config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.cr_type.id,
                "check_fields": "given_name, family_name, phone",
            }
        )
        self.assertEqual(config.get_check_fields_list(), ["given_name", "family_name", "phone"])


class TestConflictDetection(TransactionCase):
    """Test conflict detection logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test approval group
        cls.test_group = cls.env["res.groups"].create(
            {
                "name": "Test Approval Group",
            }
        )
        # Create approval definition
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.env.ref("spp_change_request_v2.model_spp_change_request").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        # Create CR type with conflict detection enabled
        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Test Edit Individual",
                "code": "test_edit_ind_conflict",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        # Create conflict rule - warn on same registrant
        cls.conflict_rule = cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Warn Same Registrant",
                "cr_type_id": cls.cr_type.id,
                "scope": "registrant",
                "action": "warn",
                "conflict_states": "all_active",
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_conflict_detection_same_registrant(self):
        """Test conflict detection for same registrant."""
        # Create first CR
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Create second CR for same registrant
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Second CR should detect conflict with first
        self.assertEqual(cr2.conflict_status, "warning")
        self.assertIn(cr1, cr2.conflicting_cr_ids)

    def test_no_conflict_different_registrant(self):
        """Test no conflict for different registrants."""
        registrant2 = self.env["res.partner"].create(
            {
                "name": "Test Individual 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": registrant2.id,
            }
        )

        # No conflict expected
        self.assertEqual(cr2.conflict_status, "none")
        self.assertNotIn(cr1, cr2.conflicting_cr_ids)

    def test_blocking_conflict(self):
        """Test blocking conflict prevents submission."""
        # Create blocking rule
        self.conflict_rule.action = "block"

        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        self.assertEqual(cr2.conflict_status, "blocked")

        # Submission should fail
        with self.assertRaises(ValidationError):
            cr2.action_submit_for_approval()

    def test_time_window_filtering(self):
        """Test time window filtering for conflicts."""
        # Set time window to 1 hour
        self.conflict_rule.time_window_hours = 1

        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Backdate cr1 to 2 hours ago
        old_date = fields.Datetime.now() - timedelta(hours=2)
        self.env.cr.execute("UPDATE spp_change_request SET create_date = %s WHERE id = %s", (old_date, cr1.id))
        cr1.invalidate_recordset()

        # Create second CR
        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Should not detect conflict (outside time window)
        self.assertEqual(cr2.conflict_status, "none")

    def test_applied_cr_not_conflicting(self):
        """Test that applied CRs don't cause conflicts."""
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Mark cr1 as applied
        cr1.write(
            {
                "approval_state": "approved",
                "is_applied": True,
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Applied CR should not be in conflicts
        self.assertNotIn(cr1, cr2.conflicting_cr_ids)


class TestConflictOverride(TransactionCase):
    """Test conflict override mechanism."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create(
            {
                "name": "Test Approval Group Override",
            }
        )
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
                "name": "Test Edit Individual",
                "code": "test_edit_ind_override",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_conflict_detection": True,
            }
        )

        cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Block Same Registrant",
                "cr_type_id": cls.cr_type.id,
                "scope": "registrant",
                "action": "block",
            }
        )

        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create user with override permission
        cls.override_group = cls.env.ref("spp_change_request_v2.group_cr_conflict_approver")
        cls.override_user = cls.env["res.users"].create(
            {
                "name": "Override User",
                "login": "override_user",
                "group_ids": [Command.link(cls.override_group.id)],
            }
        )

        # Create user without override permission
        cls.normal_group = cls.env.ref("spp_change_request_v2.group_cr_user")
        cls.normal_user = cls.env["res.users"].create(
            {
                "name": "Normal User",
                "login": "normal_user",
                "group_ids": [Command.link(cls.normal_group.id)],
            }
        )

    def test_override_requires_permission(self):
        """Test that override requires special permission."""
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        self.assertEqual(cr2.conflict_status, "blocked")

        # Normal user cannot override
        with self.assertRaises(UserError):
            cr2.with_user(self.normal_user).action_override_conflict("I need to override this conflict")

    def test_override_with_permission(self):
        """Test successful override with permission."""
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        self.assertEqual(cr2.conflict_status, "blocked")

        # Override with permission
        reason = "Urgent update required, conflicts reviewed manually"
        cr2.with_user(self.override_user).action_override_conflict(reason)

        self.assertEqual(cr2.conflict_status, "overridden")
        self.assertEqual(cr2.conflict_override_user_id, self.override_user)
        self.assertEqual(cr2.conflict_override_reason, reason)
        self.assertTrue(cr2.conflict_override_date)

    def test_override_requires_reason(self):
        """Test that override requires justification."""
        self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Short reason should fail
        with self.assertRaises(ValidationError):
            cr2.with_user(self.override_user).action_override_conflict("short")

        # Empty reason should fail
        with self.assertRaises(ValidationError):
            cr2.with_user(self.override_user).action_override_conflict("")


class TestDuplicateDetection(TransactionCase):
    """Test duplicate detection logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_group = cls.env["res.groups"].create(
            {
                "name": "Test Approval Group Dup",
            }
        )
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
                "name": "Test Edit Individual",
                "code": "test_edit_ind_dup_det",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "enable_duplicate_detection": True,
            }
        )

        cls.duplicate_config = cls.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": cls.cr_type.id,
                "time_window_hours": 48,
                "similarity_threshold": 80.0,
                "check_fields": "given_name, family_name",
            }
        )
        cls.cr_type.duplicate_detection_config_id = cls.duplicate_config.id

        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_duplicate_detection_same_details(self):
        """Test duplicate detection with same details."""
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
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
                "registrant_id": self.registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "John",
                "family_name": "Doe",
            }
        )

        # Re-run duplicate detection
        cr2._run_conflict_checks()

        self.assertEqual(cr2.duplicate_status, "potential")
        self.assertIn(cr1, cr2.potential_duplicate_ids)
        self.assertGreaterEqual(cr2.duplicate_similarity_score, 80.0)

    def test_no_duplicate_different_details(self):
        """Test no duplicate detection with different details."""
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
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
                "registrant_id": self.registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "Jane",
                "family_name": "Smith",
            }
        )

        # Re-run duplicate detection
        cr2._run_conflict_checks()

        self.assertEqual(cr2.duplicate_status, "none")

    def test_duplicate_time_window(self):
        """Test duplicate detection respects time window."""
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail1 = cr1.get_detail()
        detail1.write(
            {
                "given_name": "John",
                "family_name": "Doe",
            }
        )

        # Backdate cr1 to outside time window
        old_date = fields.Datetime.now() - timedelta(hours=72)
        self.env.cr.execute("UPDATE spp_change_request SET create_date = %s WHERE id = %s", (old_date, cr1.id))
        cr1.invalidate_recordset()

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail2 = cr2.get_detail()
        detail2.write(
            {
                "given_name": "John",
                "family_name": "Doe",
            }
        )

        # Re-run duplicate detection
        cr2._run_conflict_checks()

        # Should not detect duplicate (outside time window)
        self.assertEqual(cr2.duplicate_status, "none")


class TestCRTypeConflictConfiguration(TransactionCase):
    """Test CR type conflict configuration fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_type = cls.env["spp.change.request.type"].create(
            {
                "name": "Test Type Config",
                "code": "test_type_config",
                "detail_model": "spp.cr.detail.edit_individual",
                "target_type": "individual",
                "apply_strategy": "field_mapping",
            }
        )

    def test_enable_conflict_detection(self):
        """Test enabling conflict detection on CR type."""
        self.assertFalse(self.cr_type.enable_conflict_detection)

        self.cr_type.enable_conflict_detection = True
        self.assertTrue(self.cr_type.enable_conflict_detection)

    def test_conflict_rule_count(self):
        """Test conflict rule count computation."""
        self.assertEqual(self.cr_type.conflict_rule_count, 0)

        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Rule 1",
                "cr_type_id": self.cr_type.id,
                "scope": "registrant",
                "action": "warn",
            }
        )

        self.assertEqual(self.cr_type.conflict_rule_count, 1)

        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Rule 2",
                "cr_type_id": self.cr_type.id,
                "scope": "field",
                "action": "block",
                "conflict_fields": "phone",
            }
        )

        self.assertEqual(self.cr_type.conflict_rule_count, 2)

    def test_configure_duplicate_detection_action(self):
        """Test action to configure duplicate detection."""
        self.cr_type.enable_duplicate_detection = True
        self.assertFalse(self.cr_type.duplicate_detection_config_id)

        # Call action - should create config
        action = self.cr_type.action_configure_duplicate_detection()

        self.assertTrue(self.cr_type.duplicate_detection_config_id)
        self.assertEqual(action["res_model"], "spp.cr.duplicate.config")
        self.assertEqual(action["res_id"], self.cr_type.duplicate_detection_config_id.id)
