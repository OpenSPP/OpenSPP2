# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for dynamic-approval-aware conflict and duplicate detection.

When a CR type has `use_dynamic_approval=True`, only the field selected via
`field_to_modify` represents a proposed change — all other fields are prefilled
snapshots from the registrant. Conflict and duplicate detection must account
for this to avoid false positives and inflated similarity scores.
"""

import logging

from odoo import Command, api
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestConflictDynamicApproval(TransactionCase):
    """Test conflict/duplicate detection integration with dynamic approval."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Patch _get_field_to_modify_selection so field_to_modify has valid options.
        DetailModel = type(cls.env["spp.cr.detail.edit_individual"])
        cls._orig_get_field_to_modify_selection = DetailModel._get_field_to_modify_selection

        @api.model
        def _test_field_to_modify_selection(self):
            return [
                ("given_name", "Given Name"),
                ("family_name", "Family Name"),
                ("phone", "Phone"),
            ]

        DetailModel._get_field_to_modify_selection = _test_field_to_modify_selection

        # Model shortcuts
        cls.CR = cls.env["spp.change.request"]
        cls.CRType = cls.env["spp.change.request.type"]
        cls.ApprovalDef = cls.env["spp.approval.definition"]

        cr_model = cls.env["ir.model"].search([("model", "=", "spp.change.request")], limit=1)

        # Create approver group + user
        cls.approver_group = cls.env["res.groups"].create({"name": "Conflict DA Test Approvers"})
        cls.approval_def = cls.ApprovalDef.create(
            {
                "name": "Conflict DA Test Approval",
                "model_id": cr_model.id,
                "approval_type": "group",
                "approval_group_id": cls.approver_group.id,
            }
        )

        # Dynamic CR type with conflict detection enabled
        cls.dynamic_cr_type = cls.CRType.create(
            {
                "name": "Dynamic Conflict Test",
                "code": "dyn_conflict_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "use_dynamic_approval": True,
                "candidate_definition_ids": [Command.link(cls.approval_def.id)],
                "enable_conflict_detection": True,
            }
        )
        # Field-mapping definitions: which detail fields map to which registrant
        # fields. Conflict/duplicate detection derives the "actually changed"
        # fields from these (detail value vs registrant), so a field_mapping
        # type needs them — same-named here (given_name -> given_name, etc.).
        cls.dynamic_cr_type.write(
            {
                "apply_mapping_ids": [
                    Command.create({"source_field": "given_name", "target_field": "given_name"}),
                    Command.create({"source_field": "family_name", "target_field": "family_name"}),
                    Command.create({"source_field": "phone", "target_field": "phone"}),
                ],
            }
        )

        # Field-scope conflict rule: checks given_name, family_name
        cls.field_rule = cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Field Conflict (name fields)",
                "cr_type_id": cls.dynamic_cr_type.id,
                "scope": "field",
                "action": "warn",
                "conflict_fields": "given_name, family_name",
            }
        )

        # Static CR type (no dynamic approval) for mixed-mode tests
        cls.static_cr_type = cls.CRType.create(
            {
                "name": "Static Conflict Test",
                "code": "static_conflict_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.approval_def.id,
                "use_dynamic_approval": False,
                "enable_conflict_detection": True,
            }
        )

        # Same field-scope rule for static type
        cls.env["spp.cr.conflict.rule"].create(
            {
                "name": "Field Conflict Static (name fields)",
                "cr_type_id": cls.static_cr_type.id,
                "scope": "field",
                "action": "warn",
                "conflict_fields": "given_name, family_name",
                "check_same_type_only": False,
                "conflict_type_ids": [Command.set([cls.dynamic_cr_type.id, cls.static_cr_type.id])],
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "DA Conflict Test Individual",
                "given_name": "OriginalGiven",
                "family_name": "OriginalFamily",
                "phone": "555-0100",
                "is_registrant": True,
                "is_group": False,
            }
        )

    @classmethod
    def tearDownClass(cls):
        DetailModel = type(cls.env["spp.cr.detail.edit_individual"])
        DetailModel._get_field_to_modify_selection = cls._orig_get_field_to_modify_selection
        super().tearDownClass()

    def _create_dynamic_cr(self, registrant=None):
        """Create a dynamic-approval CR for the given registrant."""
        return self.CR.create(
            {
                "request_type_id": self.dynamic_cr_type.id,
                "registrant_id": (registrant or self.registrant).id,
            }
        )

    def _create_static_cr(self, registrant=None):
        """Create a static CR for the given registrant."""
        return self.CR.create(
            {
                "request_type_id": self.static_cr_type.id,
                "registrant_id": (registrant or self.registrant).id,
            }
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 4a: Field Conflict Tests (dynamic approval)
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_cr_different_fields_no_conflict(self):
        """Two dynamic CRs modifying different fields should NOT conflict.

        CR-A selects given_name, CR-B selects family_name. Both are in the
        rule's conflict_fields list, but since they modify different fields,
        no conflict should be detected.
        """
        cr_a = self._create_dynamic_cr()
        detail_a = cr_a.get_detail()
        detail_a.write({"field_to_modify": "given_name", "given_name": "NewGivenA"})
        cr_a._run_conflict_checks()

        cr_b = self._create_dynamic_cr()
        detail_b = cr_b.get_detail()
        detail_b.write({"field_to_modify": "family_name", "family_name": "NewFamilyB"})
        cr_b._run_conflict_checks()

        self.assertEqual(
            cr_b.conflict_status,
            "none",
            "Different fields selected = no field-level conflict.",
        )
        self.assertNotIn(cr_a, cr_b.conflicting_cr_ids)

    def test_dynamic_cr_same_field_detects_conflict(self):
        """Two dynamic CRs modifying the same field SHOULD conflict.

        Both CR-A and CR-B select given_name for the same registrant.
        """
        cr_a = self._create_dynamic_cr()
        detail_a = cr_a.get_detail()
        detail_a.write({"field_to_modify": "given_name", "given_name": "NewGivenA"})
        cr_a._run_conflict_checks()

        cr_b = self._create_dynamic_cr()
        detail_b = cr_b.get_detail()
        detail_b.write({"field_to_modify": "given_name", "given_name": "NewGivenB"})
        cr_b._run_conflict_checks()

        self.assertEqual(
            cr_b.conflict_status,
            "warning",
            "Same field selected = conflict expected.",
        )
        self.assertIn(cr_a, cr_b.conflicting_cr_ids)

    def test_dynamic_cr_selected_field_not_in_rule_no_conflict(self):
        """Dynamic CR selecting a field NOT in the rule's conflict_fields should NOT conflict.

        CR selects phone, but rule only checks given_name and family_name.
        """
        cr_a = self._create_dynamic_cr()
        detail_a = cr_a.get_detail()
        detail_a.write({"field_to_modify": "phone", "phone": "555-0101"})
        cr_a._run_conflict_checks()

        cr_b = self._create_dynamic_cr()
        detail_b = cr_b.get_detail()
        detail_b.write({"field_to_modify": "phone", "phone": "555-0102"})
        cr_b._run_conflict_checks()

        self.assertEqual(
            cr_b.conflict_status,
            "none",
            "Selected field not in conflict_fields = no conflict.",
        )

    def test_dynamic_vs_static_cr_field_conflict(self):
        """A dynamic CR and a static CR modifying the same field SHOULD conflict.

        Dynamic CR selects given_name. Static CR has given_name populated.
        The static type's rule checks both types and has cross-type conflict_type_ids.
        """
        # Create static CR first with given_name set
        cr_static = self._create_static_cr()
        detail_static = cr_static.get_detail()
        detail_static.write({"given_name": "StaticNewGiven"})
        cr_static._run_conflict_checks()

        # Create dynamic CR that selects given_name
        cr_dynamic = self._create_dynamic_cr()
        detail_dynamic = cr_dynamic.get_detail()
        detail_dynamic.write({"field_to_modify": "given_name", "given_name": "DynamicNewGiven"})
        cr_dynamic._run_conflict_checks()

        # Dynamic CR should detect the static CR as conflicting
        self.assertIn(
            cr_static,
            cr_dynamic.conflicting_cr_ids,
            "Dynamic CR should detect conflict with static CR on same field.",
        )

    def test_dynamic_cr_field_conflict_before_selection_no_check(self):
        """Dynamic CR created without field_to_modify should skip conflict checks.

        At create time, field_to_modify is not set. Conflict checks should be
        skipped so conflict_detection_date stays empty.
        """
        cr = self._create_dynamic_cr()

        self.assertFalse(
            cr.conflict_detection_date,
            "Conflict checks must be skipped at create time for dynamic-approval types.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 4b: Duplicate Detection Tests (dynamic approval)
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_cr_different_fields_zero_similarity(self):
        """Two dynamic CRs selecting different fields should have 0% similarity."""
        # Enable duplicate detection
        dup_config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.dynamic_cr_type.id,
                "similarity_threshold": 50.0,
            }
        )
        self.dynamic_cr_type.write(
            {
                "enable_duplicate_detection": True,
                "duplicate_detection_config_id": dup_config.id,
            }
        )

        try:
            cr_a = self._create_dynamic_cr()
            detail_a = cr_a.get_detail()
            detail_a.write({"field_to_modify": "given_name", "given_name": "NewGivenA"})
            cr_a._run_conflict_checks()

            cr_b = self._create_dynamic_cr()
            detail_b = cr_b.get_detail()
            detail_b.write({"field_to_modify": "family_name", "family_name": "NewFamilyB"})

            similarity = cr_b._calculate_similarity(cr_a, dup_config)
            self.assertEqual(
                similarity,
                0.0,
                "Different fields selected = 0% similarity.",
            )
        finally:
            self.dynamic_cr_type.write(
                {
                    "enable_duplicate_detection": False,
                    "duplicate_detection_config_id": False,
                }
            )
            dup_config.unlink()

    def test_dynamic_cr_same_field_same_value_100_similarity(self):
        """Two dynamic CRs with same field and same value should have 100% similarity."""
        dup_config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.dynamic_cr_type.id,
                "similarity_threshold": 50.0,
            }
        )
        self.dynamic_cr_type.write(
            {
                "enable_duplicate_detection": True,
                "duplicate_detection_config_id": dup_config.id,
            }
        )

        try:
            cr_a = self._create_dynamic_cr()
            detail_a = cr_a.get_detail()
            detail_a.write({"field_to_modify": "given_name", "given_name": "SameValue"})
            cr_a._run_conflict_checks()

            cr_b = self._create_dynamic_cr()
            detail_b = cr_b.get_detail()
            detail_b.write({"field_to_modify": "given_name", "given_name": "SameValue"})

            similarity = cr_b._calculate_similarity(cr_a, dup_config)
            self.assertEqual(
                similarity,
                100.0,
                "Same field + same value = 100% similarity.",
            )
        finally:
            self.dynamic_cr_type.write(
                {
                    "enable_duplicate_detection": False,
                    "duplicate_detection_config_id": False,
                }
            )
            dup_config.unlink()

    def test_dynamic_cr_same_field_different_value_low_similarity(self):
        """Two dynamic CRs with same field but different values should have low similarity."""
        dup_config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.dynamic_cr_type.id,
                "similarity_threshold": 50.0,
            }
        )
        self.dynamic_cr_type.write(
            {
                "enable_duplicate_detection": True,
                "duplicate_detection_config_id": dup_config.id,
            }
        )

        try:
            cr_a = self._create_dynamic_cr()
            detail_a = cr_a.get_detail()
            detail_a.write({"field_to_modify": "given_name", "given_name": "AlphaValue"})
            cr_a._run_conflict_checks()

            cr_b = self._create_dynamic_cr()
            detail_b = cr_b.get_detail()
            detail_b.write({"field_to_modify": "given_name", "given_name": "ZetaValue"})

            similarity = cr_b._calculate_similarity(cr_a, dup_config)
            # Different values, no substring match → 0%
            self.assertEqual(
                similarity,
                0.0,
                "Same field + completely different value = 0% similarity.",
            )
        finally:
            self.dynamic_cr_type.write(
                {
                    "enable_duplicate_detection": False,
                    "duplicate_detection_config_id": False,
                }
            )
            dup_config.unlink()

    def test_dynamic_cr_prefilled_fields_not_inflating_score(self):
        """Two dynamic CRs for same registrant selecting different fields must have 0% similarity.

        Without the fix, all prefilled fields would be identical (from same registrant),
        inflating the score to ~80%+. With the fix, different fields = 0%.
        """
        dup_config = self.env["spp.cr.duplicate.config"].create(
            {
                "cr_type_id": self.dynamic_cr_type.id,
                "similarity_threshold": 50.0,
                # No check_fields configured — would compare ALL stored fields without fix
            }
        )
        self.dynamic_cr_type.write(
            {
                "enable_duplicate_detection": True,
                "duplicate_detection_config_id": dup_config.id,
            }
        )

        try:
            cr_a = self._create_dynamic_cr()
            detail_a = cr_a.get_detail()
            detail_a.write({"field_to_modify": "given_name", "given_name": "Changed"})
            cr_a._run_conflict_checks()

            cr_b = self._create_dynamic_cr()
            detail_b = cr_b.get_detail()
            detail_b.write({"field_to_modify": "family_name", "family_name": "Changed"})

            similarity = cr_b._calculate_similarity(cr_a, dup_config)
            self.assertEqual(
                similarity,
                0.0,
                "Prefilled fields must not inflate similarity. "
                "Different selected fields = 0% regardless of prefilled values.",
            )
        finally:
            self.dynamic_cr_type.write(
                {
                    "enable_duplicate_detection": False,
                    "duplicate_detection_config_id": False,
                }
            )
            dup_config.unlink()

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 4c: Timing Tests
    # ──────────────────────────────────────────────────────────────────────────

    def test_create_dynamic_cr_skips_conflict_check(self):
        """Creating a dynamic-approval CR must skip conflict checks at create time.

        field_to_modify is not set yet at create time, so running checks
        would produce meaningless results. conflict_detection_date stays False.
        """
        cr = self._create_dynamic_cr()
        self.assertFalse(
            cr.conflict_detection_date,
            "Dynamic CR must not run conflict checks at create time.",
        )

    def test_set_field_to_modify_triggers_conflict_check(self):
        """Setting field_to_modify on detail must trigger conflict checks via write().

        When _sync_field_to_modify() sets selected_field_name on the CR,
        the write() trigger should run _run_conflict_checks().
        """
        # Create a first CR so there's something to potentially conflict with
        cr_a = self._create_dynamic_cr()
        detail_a = cr_a.get_detail()
        detail_a.write({"field_to_modify": "given_name", "given_name": "ValueA"})

        # Create second CR — conflict_detection_date should be False at this point
        cr_b = self._create_dynamic_cr()
        self.assertFalse(cr_b.conflict_detection_date)

        # Set field_to_modify on cr_b's detail — should trigger conflict check
        detail_b = cr_b.get_detail()
        detail_b.write({"field_to_modify": "given_name", "given_name": "ValueB"})

        cr_b.invalidate_recordset()
        self.assertTrue(
            cr_b.conflict_detection_date,
            "Setting field_to_modify must trigger conflict checks.",
        )

    def test_static_cr_create_still_runs_conflict_check(self):
        """Creating a static CR must still run conflict checks at create time.

        This verifies the timing fix only affects dynamic-approval types.
        """
        # Create first static CR
        self._create_static_cr()

        # Create second static CR — should run checks at create time
        cr2 = self._create_static_cr()
        self.assertTrue(
            cr2.conflict_detection_date,
            "Static CR must run conflict checks at create time (existing behavior).",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Security: a user-writable selected_field_name must NOT bypass field-scoped
    # conflict/duplicate detection. selected_field_name is only view-readonly;
    # CR users have write on their own CRs, so the detection must derive the
    # effective changed field from the trusted detail.field_to_modify selection.
    # ──────────────────────────────────────────────────────────────────────────

    def test_writing_selected_field_name_cannot_bypass_field_conflict(self):
        """Writing selected_field_name to a field outside conflict_fields must
        not clear a real field-scoped conflict on a dynamic-approval CR."""
        cr_a = self._create_dynamic_cr()
        cr_a.get_detail().write({"field_to_modify": "given_name", "given_name": "NewGivenA"})
        cr_a._run_conflict_checks()

        cr_b = self._create_dynamic_cr()
        cr_b.get_detail().write({"field_to_modify": "given_name", "given_name": "NewGivenB"})
        cr_b._run_conflict_checks()
        self.assertEqual(cr_b.conflict_status, "warning", "Baseline: same field = conflict.")

        # Attack: re-point selected_field_name to a field NOT in conflict_fields
        # (phone). This re-triggers conflict detection via the write override.
        cr_b.write({"selected_field_name": "phone"})

        self.assertEqual(
            cr_b.conflict_status,
            "warning",
            "Writing selected_field_name must not bypass the field-scoped conflict.",
        )
        self.assertIn(cr_a, cr_b.conflicting_cr_ids)

    def test_writing_selected_field_name_on_static_cr_cannot_bypass(self):
        """On a non-dynamic-approval CR, selected_field_name must be ignored
        entirely — writing it cannot narrow the field-scoped conflict."""
        cr_a = self._create_static_cr()
        cr_a.get_detail().write({"given_name": "StaticGivenA"})
        cr_a._run_conflict_checks()

        cr_b = self._create_static_cr()
        cr_b.get_detail().write({"given_name": "StaticGivenB"})
        cr_b._run_conflict_checks()
        self.assertIn(cr_a, cr_b.conflicting_cr_ids, "Baseline: static CRs conflict on given_name.")

        cr_b.write({"selected_field_name": "phone"})

        self.assertIn(
            cr_a,
            cr_b.conflicting_cr_ids,
            "selected_field_name must not affect conflict detection for non-dynamic CR types.",
        )

    def test_mislabeled_field_to_modify_cannot_bypass_conflict(self):
        """Labelling field_to_modify as an unchanged field must not bypass the
        conflict on the field actually changed. field_to_modify is user-writable
        and does not constrain apply (field_mapping applies every changed field),
        so detection must scope to what actually differs from the registrant."""
        cr_a = self._create_dynamic_cr()
        cr_a.get_detail().write({"field_to_modify": "given_name", "given_name": "NewGivenA"})
        cr_a._run_conflict_checks()

        # cr_b really changes given_name (a conflict field) but labels the CR as
        # modifying phone (unchanged — still the registrant's prefilled value).
        cr_b = self._create_dynamic_cr()
        cr_b.get_detail().write({"field_to_modify": "phone", "given_name": "NewGivenB"})
        cr_b._run_conflict_checks()

        self.assertEqual(
            cr_b.conflict_status,
            "warning",
            "A real change to a conflict field must be detected regardless of field_to_modify.",
        )
        self.assertIn(cr_a, cr_b.conflicting_cr_ids)

    def test_mislabeled_candidate_still_detected_as_conflict(self):
        """A prior CR that mislabels field_to_modify while actually changing a
        conflict field must still be found as a conflicting candidate."""
        # cr_a really changes given_name but labels field_to_modify = phone.
        cr_a = self._create_dynamic_cr()
        cr_a.get_detail().write({"field_to_modify": "phone", "given_name": "MislabeledGivenA"})
        cr_a._run_conflict_checks()

        cr_b = self._create_dynamic_cr()
        cr_b.get_detail().write({"field_to_modify": "given_name", "given_name": "NewGivenB"})
        cr_b._run_conflict_checks()

        self.assertIn(
            cr_a,
            cr_b.conflicting_cr_ids,
            "A candidate that actually changed the conflict field must be detected even if mislabeled.",
        )

    def test_writing_selected_field_name_cannot_bypass_duplicate(self):
        """Writing selected_field_name must not drop duplicate similarity to 0."""
        dup_config = self.env["spp.cr.duplicate.config"].create(
            {"cr_type_id": self.dynamic_cr_type.id, "similarity_threshold": 50.0}
        )
        self.dynamic_cr_type.write({"enable_duplicate_detection": True, "duplicate_detection_config_id": dup_config.id})
        try:
            cr_a = self._create_dynamic_cr()
            cr_a.get_detail().write({"field_to_modify": "given_name", "given_name": "SameValue"})
            cr_a._run_conflict_checks()

            cr_b = self._create_dynamic_cr()
            cr_b.get_detail().write({"field_to_modify": "given_name", "given_name": "SameValue"})
            self.assertEqual(cr_b._calculate_similarity(cr_a, dup_config), 100.0, "Baseline duplicate.")

            # Attack: re-point selected_field_name away from the real field.
            cr_b.write({"selected_field_name": "phone"})

            self.assertEqual(
                cr_b._calculate_similarity(cr_a, dup_config),
                100.0,
                "Writing selected_field_name must not bypass duplicate detection.",
            )
        finally:
            self.dynamic_cr_type.write({"enable_duplicate_detection": False, "duplicate_detection_config_id": False})
            dup_config.unlink()

    def test_dynamic_custom_strategy_still_detects_conflicts(self):
        """A dynamic type whose strategy writes outside the mappings must not
        silently lose detection.

        The changed-field derivation reads apply_mapping_ids, which a custom
        apply strategy does not populate. Deriving from an empty mapping set
        would yield an empty "changed" set, which would make the field-scoped
        conflict filter match nothing and drive duplicate similarity to 0 —
        disabling both checks for that configuration. The derivation must fall
        back to the full configured field set instead.
        """
        custom_type = self.CRType.create(
            {
                "name": "Dynamic Custom Strategy",
                "code": "dyn_custom_strategy_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "custom",
                # A custom strategy requires an apply model (_check_apply_config).
                # The strategy is never executed here — the test only exercises
                # conflict detection — so any registered apply model will do.
                "apply_model": "spp.cr.apply.add_member",
                "approval_definition_id": self.approval_def.id,
                "use_dynamic_approval": True,
                "candidate_definition_ids": [Command.link(self.approval_def.id)],
                "enable_conflict_detection": True,
            }
        )
        self.env["spp.cr.conflict.rule"].create(
            {
                "name": "Field Conflict (custom strategy)",
                "cr_type_id": custom_type.id,
                "scope": "field",
                "action": "warn",
                "conflict_fields": "given_name, family_name",
            }
        )

        def _make():
            cr = self.CR.create({"request_type_id": custom_type.id, "registrant_id": self.registrant.id})
            cr.get_detail().write({"field_to_modify": "given_name", "given_name": "CollidingValue"})
            return cr

        cr_a = _make()
        cr_a._run_conflict_checks()
        cr_b = _make()

        # No mappings configured, so the derivation must return None (use the
        # full configured set) rather than an empty set.
        self.assertIsNone(
            cr_b._proposed_changed_fields(),
            "A dynamic type without field mappings must not derive an empty changed-field set.",
        )

        cr_b._run_conflict_checks()
        self.assertNotEqual(
            cr_b.conflict_status,
            "none",
            "Conflict detection must still fire for a dynamic custom-strategy type.",
        )
