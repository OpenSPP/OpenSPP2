# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for dynamic approval routing on Change Request types.

When a CR type has `use_dynamic_approval=True`, the user selects a single field
to modify from a dropdown on the detail form. The selected field name, together
with the old and new values, is exposed on `spp.change.request` as
`selected_field_name`, `selected_field_old_value`, and
`selected_field_new_value`. The approval workflow is then resolved by evaluating
a list of candidate `spp.approval.definition` records (sorted by sequence) using
their CEL conditions. The first definition whose condition evaluates to True wins;
definitions without a CEL condition act as catch-all fallbacks.
"""

import logging

from odoo import Command, api
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestDynamicApproval(TransactionCase):
    """Test suite for the dynamic approval routing feature.

    Most tests exercise `_get_approval_definition()` directly because that is
    the hook that drives routing.  One end-to-end test (test 13) exercises the
    full submission/approval/apply cycle to verify the complete flow.
    """

    # ──────────────────────────────────────────────────────────────────────────
    # CLASS-LEVEL SETUP
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disable tracking to avoid sending e-mail notifications during setup.
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Patch the _get_field_to_modify_selection method on the concrete model
        # so field_to_modify has valid options for our tests. The base method
        # returns [] and concrete models override it. We save the original and
        # restore in tearDownClass.
        DetailModel = type(cls.env["spp.cr.detail.edit_individual"])
        cls._orig_get_field_to_modify_selection = DetailModel._get_field_to_modify_selection

        @api.model
        def _test_field_to_modify_selection(self):
            return [
                ("given_name", "Given Name"),
                ("family_name", "Family Name"),
                ("phone", "Phone"),
                ("gender_id", "Gender"),
                ("birthdate", "Birthdate"),
            ]

        DetailModel._get_field_to_modify_selection = _test_field_to_modify_selection

        # Model shortcuts
        cls.CR = cls.env["spp.change.request"]
        cls.CRType = cls.env["spp.change.request.type"]
        cls.ApprovalDef = cls.env["spp.approval.definition"]

        # Get the ir.model record for spp.change.request (required by approval defs)
        cls.cr_model_record = cls.env["ir.model"].search([("model", "=", "spp.change.request")], limit=1)

        # Create a dedicated approver user (SUPERUSER/OdooBot doesn't work with
        # normal group membership lookups in tier approvals).
        cls.approver_user = cls.env["res.users"].create(
            {
                "name": "Dynamic Approval Approver",
                "login": "dynamic_approval_approver",
                "email": "approver@test.com",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_approval.group_approval_approver").id,
                        ]
                    )
                ],
            }
        )
        # Create a security group with the approver user as member.
        cls.approver_group = cls.env["res.groups"].create(
            {
                "name": "Dynamic Approval Test Approvers",
                "user_ids": [Command.set([cls.approver_user.id])],
            }
        )

        # Create a registrant with known field values so old-value assertions are
        # deterministic.
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Dynamic Test Individual",
                "given_name": "Original Given",
                "family_name": "Original Family",
                "phone": "111-222",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # ── Approval definitions ──────────────────────────────────────────────

        # escalated_def (sequence=10): matches name-change fields via CEL.
        cls.escalated_def = cls.ApprovalDef.create(
            {
                "name": "Escalated Approvals (name fields)",
                "model_id": cls.cr_model_record.id,
                "sequence": 10,
                "approval_type": "group",
                "approval_group_id": cls.approver_group.id,
                "use_cel_condition": True,
                "cel_condition": ('record.selected_field_name in ["given_name", "family_name"]'),
            }
        )

        # fallback_def (sequence=20): no CEL condition — acts as catch-all.
        cls.fallback_def = cls.ApprovalDef.create(
            {
                "name": "Fallback Approvals (catch-all)",
                "model_id": cls.cr_model_record.id,
                "sequence": 20,
                "approval_type": "group",
                "approval_group_id": cls.approver_group.id,
            }
        )

        # static_def: used by the non-dynamic CR type as its sole definition.
        cls.static_def = cls.ApprovalDef.create(
            {
                "name": "Static Approval Definition",
                "model_id": cls.cr_model_record.id,
                "approval_type": "group",
                "approval_group_id": cls.approver_group.id,
            }
        )

        # ── CR types ─────────────────────────────────────────────────────────

        # Shared apply mappings for the field_mapping strategy.  These map
        # detail fields to identically-named registrant fields for the simple
        # scalar fields used in our tests.
        _common_mappings = [
            Command.create({"source_field": "given_name", "target_field": "given_name", "sequence": 10}),
            Command.create({"source_field": "family_name", "target_field": "family_name", "sequence": 20}),
            Command.create({"source_field": "phone", "target_field": "phone", "sequence": 30}),
            Command.create({"source_field": "gender_id", "target_field": "gender_id", "sequence": 40}),
            Command.create({"source_field": "birthdate", "target_field": "birthdate", "sequence": 50}),
        ]

        cls.dynamic_cr_type = cls.CRType.create(
            {
                "name": "Dynamic Approval Test Type",
                "code": "dyn_approval_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.static_def.id,
                "use_dynamic_approval": True,
                "candidate_definition_ids": [
                    Command.link(cls.escalated_def.id),
                    Command.link(cls.fallback_def.id),
                ],
                "apply_mapping_ids": _common_mappings,
                "auto_apply_on_approve": True,
            }
        )

        cls.non_dynamic_cr_type = cls.CRType.create(
            {
                "name": "Non-Dynamic Approval Test Type",
                "code": "non_dyn_approval_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": cls.static_def.id,
                "use_dynamic_approval": False,
                "auto_apply_on_approve": True,
            }
        )

    @classmethod
    def tearDownClass(cls):
        # Revert the monkey-patched method so other test modules are not affected.
        DetailModel = type(cls.env["spp.cr.detail.edit_individual"])
        DetailModel._get_field_to_modify_selection = cls._orig_get_field_to_modify_selection
        super().tearDownClass()

    # ──────────────────────────────────────────────────────────────────────────
    # HELPER
    # ──────────────────────────────────────────────────────────────────────────

    def _create_cr(self, cr_type=None, registrant=None):
        """Create a CR with the given type, defaulting to the dynamic type."""
        return self.CR.create(
            {
                "request_type_id": (cr_type or self.dynamic_cr_type).id,
                "registrant_id": (registrant or self.registrant).id,
            }
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 1 – Static approval when dynamic is disabled
    # ──────────────────────────────────────────────────────────────────────────

    def test_static_approval_when_dynamic_disabled(self):
        """CR types with use_dynamic_approval=False return their static definition.

        _get_approval_definition() should return the `approval_definition_id`
        configured on the CR type without consulting any candidate definitions.
        """
        cr = self._create_cr(cr_type=self.non_dynamic_cr_type)
        result = cr._get_approval_definition()
        self.assertEqual(
            result,
            self.static_def,
            "Non-dynamic CR type must return its static approval_definition_id.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 2 – Dynamic routing: field matches escalated definition
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_approval_field_matches_escalated_definition(self):
        """Selecting a name field routes to escalated_def via CEL.

        The CEL condition on escalated_def checks:
        ``record.selected_field_name in ["given_name", "family_name"]``
        Writing given_name on the detail should make selected_field_name sync to
        "given_name" and the routing should pick escalated_def (sequence=10).
        """
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "given_name", "given_name": "New Name"})

        self.assertEqual(
            cr.selected_field_name,
            "given_name",
            "selected_field_name must sync from detail.field_to_modify.",
        )

        result = cr._get_approval_definition()
        self.assertEqual(
            result,
            self.escalated_def,
            "given_name field must route to escalated_def whose CEL matches name fields.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 3 – Dynamic routing: unmatched field falls through to fallback
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_approval_unmatched_field_uses_fallback(self):
        """A field not covered by any CEL condition falls back to catch-all.

        ``phone`` is not in escalated_def's CEL list, so the engine skips
        escalated_def and returns fallback_def (no CEL condition = always True).
        """
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "phone", "phone": "999-888"})

        result = cr._get_approval_definition()
        self.assertEqual(
            result,
            self.fallback_def,
            "A field not matched by any CEL condition must use the catch-all fallback.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 4 – Validation error when no field selected before submission
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_approval_no_field_selected_raises_validation_error(self):
        """Submitting a dynamic CR without selecting field_to_modify raises ValidationError.

        _check_can_submit() (or equivalent pre-submission validation) must reject
        the submission when field_to_modify is empty and use_dynamic_approval=True.
        """
        cr = self._create_cr()
        # Do NOT write field_to_modify — leave it blank.
        with self.assertRaises(ValidationError):
            cr._check_can_submit()

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 5 – Broken CEL is skipped with a warning
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_approval_cel_failure_skips_candidate(self):
        """A candidate with invalid CEL is skipped and a warning is logged.

        A third definition with sequence=5 (evaluated first) has intentionally
        broken CEL syntax.  The engine must catch the error, log a warning, and
        continue to escalated_def (sequence=10) which matches given_name.
        """
        # Use an expression that is syntactically valid (passes the parser)
        # but will fail at evaluation time due to referencing a nonexistent
        # attribute. This bypasses the @api.constrains CEL validator while
        # still triggering a runtime error in _resolve_dynamic_approval.
        broken_def = self.ApprovalDef.create(
            {
                "name": "Broken CEL Candidate",
                "model_id": self.cr_model_record.id,
                "sequence": 5,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
                "use_cel_condition": True,
                "cel_condition": "record.nonexistent_xyz_field > 999",
            }
        )

        # Temporarily add broken_def at the front of candidates.
        self.dynamic_cr_type.write({"candidate_definition_ids": [Command.link(broken_def.id)]})

        try:
            cr = self._create_cr()
            detail = cr.get_detail()
            detail.write({"field_to_modify": "given_name", "given_name": "Tested"})

            # Despite the broken candidate at seq=5, routing must still work and
            # return the first *valid* matching definition.
            result = cr._get_approval_definition()
            self.assertEqual(
                result,
                self.escalated_def,
                "Broken CEL candidate must be skipped; escalated_def should be returned.",
            )
        finally:
            # Clean up so broken_def does not affect other tests.
            self.dynamic_cr_type.write({"candidate_definition_ids": [Command.unlink(broken_def.id)]})
            broken_def.unlink()

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 6 – First matching candidate wins (sequence ordering)
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_approval_first_match_wins(self):
        """When multiple candidates match, the one with the lowest sequence wins.

        We add a third definition with sequence=5 that also matches given_name.
        That definition should be returned before escalated_def (sequence=10).
        """
        early_def = self.ApprovalDef.create(
            {
                "name": "Early Match Definition (seq=5)",
                "model_id": self.cr_model_record.id,
                "sequence": 5,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
                "use_cel_condition": True,
                "cel_condition": ('record.selected_field_name in ["given_name", "family_name", "phone"]'),
            }
        )

        self.dynamic_cr_type.write({"candidate_definition_ids": [Command.link(early_def.id)]})

        try:
            cr = self._create_cr()
            detail = cr.get_detail()
            detail.write({"field_to_modify": "given_name", "given_name": "First Match"})

            result = cr._get_approval_definition()
            self.assertEqual(
                result,
                early_def,
                "The candidate with the lowest sequence that matches must be returned first.",
            )
        finally:
            self.dynamic_cr_type.write({"candidate_definition_ids": [Command.unlink(early_def.id)]})
            early_def.unlink()

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 7 – field_to_modify syncs to CR on detail write
    # ──────────────────────────────────────────────────────────────────────────

    def test_field_to_modify_syncs_on_detail_write(self):
        """Writing field_to_modify on the detail record must sync to the parent CR.

        The detail's write() override calls _sync_field_to_modify() which
        updates `selected_field_name` on the parent `spp.change.request`.
        """
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "given_name"})

        cr.invalidate_recordset()
        self.assertEqual(
            cr.selected_field_name,
            "given_name",
            "selected_field_name on the CR must be updated when detail.field_to_modify changes.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 8 – field_to_modify syncs to CR when set on detail create
    # ──────────────────────────────────────────────────────────────────────────

    def test_field_to_modify_syncs_on_detail_create(self):
        """Creating a detail record with field_to_modify set must sync to the CR.

        _ensure_detail() creates the auto-detail without field_to_modify.  When a
        second (or explicit) detail is created with field_to_modify in the create
        vals, the create() override must call _sync_field_to_modify() so the
        parent CR's selected_field_name is updated.
        """
        cr = self._create_cr()

        # Create an additional detail record with field_to_modify already set.
        # The CR model links to the *first* auto-created detail, but the sync
        # must still occur for any detail linked to this CR.
        new_detail = self.env["spp.cr.detail.edit_individual"].create(
            {
                "change_request_id": cr.id,
                "field_to_modify": "family_name",
                "family_name": "Created Family",
            }
        )

        # The most recently created detail set field_to_modify; CR must reflect it.
        cr.invalidate_recordset()
        self.assertEqual(
            cr.selected_field_name,
            "family_name",
            "Creating a detail with field_to_modify set must sync selected_field_name on the CR.",
        )
        self.assertTrue(new_detail.id, "Detail record must have been created successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 9 – Old and new values synced on save
    # ──────────────────────────────────────────────────────────────────────────

    def test_old_new_values_synced_on_save(self):
        """Writing field_to_modify and the new value syncs old/new to the CR.

        The registrant was created with given_name="Original Given".  After the
        detail is saved with given_name="New Given Name", the CR must expose:
        - selected_field_old_value == "Original Given"
        - selected_field_new_value == "New Given Name"
        """
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "given_name", "given_name": "New Given Name"})

        cr.invalidate_recordset()
        self.assertEqual(
            cr.selected_field_old_value,
            "Original Given",
            "selected_field_old_value must reflect the registrant's current field value.",
        )
        self.assertEqual(
            cr.selected_field_new_value,
            "New Given Name",
            "selected_field_new_value must reflect the value written to the detail.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 10 – Old/new values for Many2one fields use display names
    # ──────────────────────────────────────────────────────────────────────────

    def test_old_new_value_for_many2one_field(self):
        """Old and new values for Many2one fields must be human-readable display names.

        For Many2one fields the raw value is a recordset; the implementation
        should store the display_name (or name) string, not the integer ID.
        """
        gender_codes = self.env["spp.vocabulary.code"].search([("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=2)
        if len(gender_codes) < 2:
            self.skipTest("Need at least 2 gender vocabulary codes (urn:iso:std:iso:5218) to run this test.")

        gender_old, gender_new = gender_codes[0], gender_codes[1]

        # Set the registrant's current gender so we have a known old value.
        self.registrant.write({"gender_id": gender_old.id})

        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "gender_id", "gender_id": gender_new.id})

        cr.invalidate_recordset()
        # Values must be strings (display names), not integer IDs.
        self.assertNotEqual(
            cr.selected_field_old_value,
            str(gender_old.id),
            "selected_field_old_value must not be a raw database ID.",
        )
        self.assertNotEqual(
            cr.selected_field_new_value,
            str(gender_new.id),
            "selected_field_new_value must not be a raw database ID.",
        )
        self.assertIn(
            gender_old.display_name,
            cr.selected_field_old_value or "",
            "selected_field_old_value must contain the old gender's display name.",
        )
        self.assertIn(
            gender_new.display_name,
            cr.selected_field_new_value or "",
            "selected_field_new_value must contain the new gender's display name.",
        )

        # Restore the registrant to a neutral state.
        self.registrant.write({"gender_id": False})

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 11 – CEL condition can access new_value for scalar comparison
    # ──────────────────────────────────────────────────────────────────────────

    def test_cel_condition_with_old_new_values(self):
        """CEL condition can use new_value to match a specific string value.

        A candidate definition with CEL:
        ``record.selected_field_name == "given_name" and new_value == "SpecificName"``
        should only match when the new value is exactly "SpecificName".
        """
        specific_def = self.ApprovalDef.create(
            {
                "name": "Specific Name Approvals",
                "model_id": self.cr_model_record.id,
                "sequence": 5,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
                "use_cel_condition": True,
                "cel_condition": (
                    'record.selected_field_name == "given_name" and record.selected_field_new_value == "SpecificName"'
                ),
            }
        )
        self.dynamic_cr_type.write({"candidate_definition_ids": [Command.link(specific_def.id)]})

        try:
            # Case A: new value IS "SpecificName" — specific_def must match.
            cr_match = self._create_cr()
            detail_match = cr_match.get_detail()
            detail_match.write({"field_to_modify": "given_name", "given_name": "SpecificName"})
            result_match = cr_match._get_approval_definition()
            self.assertEqual(
                result_match,
                specific_def,
                "CEL condition matching on new_value must route to specific_def.",
            )

            # Case B: new value is something else — specific_def must NOT match.
            cr_no_match = self._create_cr()
            detail_no_match = cr_no_match.get_detail()
            detail_no_match.write({"field_to_modify": "given_name", "given_name": "OtherName"})
            result_no_match = cr_no_match._get_approval_definition()
            self.assertNotEqual(
                result_no_match,
                specific_def,
                "CEL condition must not match when new_value differs from 'SpecificName'.",
            )
            # Should fall through to escalated_def (given_name is in its list).
            self.assertEqual(
                result_no_match,
                self.escalated_def,
                "After specific_def is skipped, escalated_def must be returned for given_name.",
            )
        finally:
            self.dynamic_cr_type.write({"candidate_definition_ids": [Command.unlink(specific_def.id)]})
            specific_def.unlink()

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 12 – CEL condition with Many2one value comparison
    # ──────────────────────────────────────────────────────────────────────────

    def test_cel_condition_with_many2one_values(self):
        """CEL condition can match on the display name of a Many2one new value.

        A candidate definition with:
        ``record.selected_field_name == "gender_id" and record.selected_field_new_value == "<name>"``
        should route to the correct definition only for the specified gender.
        """
        gender_codes = self.env["spp.vocabulary.code"].search([("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=2)
        if len(gender_codes) < 2:
            self.skipTest("Need at least 2 gender vocabulary codes (urn:iso:std:iso:5218) to run this test.")

        target_gender = gender_codes[0]
        other_gender = gender_codes[1]
        target_display = target_gender.display_name

        gender_specific_def = self.ApprovalDef.create(
            {
                "name": "Gender-Specific Approvals",
                "model_id": self.cr_model_record.id,
                "sequence": 5,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
                "use_cel_condition": True,
                "cel_condition": (
                    f'record.selected_field_name == "gender_id" '
                    f'and record.selected_field_new_value == "{target_display}"'
                ),
            }
        )
        self.dynamic_cr_type.write({"candidate_definition_ids": [Command.link(gender_specific_def.id)]})

        try:
            # Case A: new gender matches target — gender_specific_def must match.
            cr_match = self._create_cr()
            detail_match = cr_match.get_detail()
            detail_match.write({"field_to_modify": "gender_id", "gender_id": target_gender.id})
            result_match = cr_match._get_approval_definition()
            self.assertEqual(
                result_match,
                gender_specific_def,
                "CEL must match when the new Many2one display name equals the expected value.",
            )

            # Case B: new gender is different — gender_specific_def must NOT match.
            cr_no_match = self._create_cr()
            detail_no_match = cr_no_match.get_detail()
            detail_no_match.write({"field_to_modify": "gender_id", "gender_id": other_gender.id})
            result_no_match = cr_no_match._get_approval_definition()
            self.assertNotEqual(
                result_no_match,
                gender_specific_def,
                "CEL must not match when the new Many2one display name differs.",
            )
        finally:
            self.dynamic_cr_type.write({"candidate_definition_ids": [Command.unlink(gender_specific_def.id)]})
            gender_specific_def.unlink()
            # Reset registrant gender for cleanliness.
            self.registrant.write({"gender_id": False})

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 13 – End-to-end: multi-tier dynamic approval submit → approve → apply
    # ──────────────────────────────────────────────────────────────────────────

    def test_dynamic_approval_end_to_end_multitier(self):
        """Full lifecycle: field selection → submission → tier-by-tier approval → apply.

        We create a multi-tier escalated definition with two tiers.  Both tiers
        use our test approver_group so the current (admin) user can approve both.
        After the second tier is approved the CR is auto-applied and the
        registrant's field is updated.
        """
        # ── Build a multi-tier definition ────────────────────────────────────
        # Per the project memory: create the definition WITHOUT use_multitier
        # first, create tiers, then enable use_multitier.
        multitier_def = self.ApprovalDef.create(
            {
                "name": "Multi-Tier Dynamic Approval",
                "model_id": self.cr_model_record.id,
                "sequence": 5,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
                "use_cel_condition": True,
                "cel_condition": ('record.selected_field_name in ["given_name", "family_name"]'),
            }
        )

        # Create tiers before enabling use_multitier (constraint requires tiers).
        tier1 = self.env["spp.approval.tier"].create(
            {
                "definition_id": multitier_def.id,
                "name": "Tier 1 – Initial Review",
                "sequence": 10,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
            }
        )
        tier2 = self.env["spp.approval.tier"].create(
            {
                "definition_id": multitier_def.id,
                "name": "Tier 2 – Final Approval",
                "sequence": 20,
                "approval_type": "group",
                "approval_group_id": self.approver_group.id,
            }
        )

        # Enable multi-tier now that tiers exist.
        multitier_def.write({"use_multitier": True})

        # Create an isolated registrant for this test to avoid cross-test state.
        e2e_registrant = self.env["res.partner"].create(
            {
                "name": "E2E Multitier Test",
                "given_name": "BeforeApproval",
                "family_name": "Original",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # CR type for this test: multitier_def as candidate, with field mappings.
        e2e_cr_type = self.CRType.create(
            {
                "name": "E2E Multi-Tier CR Type",
                "code": "e2e_multitier_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": self.static_def.id,
                "use_dynamic_approval": True,
                "candidate_definition_ids": [Command.link(multitier_def.id)],
                "apply_mapping_ids": [
                    Command.create(
                        {
                            "source_field": "given_name",
                            "target_field": "given_name",
                            "sequence": 10,
                        }
                    ),
                ],
                "auto_apply_on_approve": True,
            }
        )

        try:
            cr = self.CR.create(
                {
                    "request_type_id": e2e_cr_type.id,
                    "registrant_id": e2e_registrant.id,
                }
            )
            detail = cr.get_detail()
            detail.write({"field_to_modify": "given_name", "given_name": "AfterApproval"})

            # ── Submit for approval ───────────────────────────────────────────
            cr.action_submit_for_approval()
            cr.invalidate_recordset()
            self.assertEqual(
                cr.approval_state,
                "pending",
                "CR must be in pending state after submission.",
            )

            # Verify a review was created for the multi-tier definition.
            review = cr.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
            self.assertTrue(review, "A pending review must exist after submission.")
            self.assertEqual(
                review.definition_id,
                multitier_def,
                "The review must reference the dynamic multitier_def.",
            )
            self.assertTrue(
                review.is_multitier,
                "The review must be flagged as multi-tier.",
            )

            # Tier 1 must be pending; Tier 2 must be waiting.
            tier1_review = review.tier_review_ids.filtered(lambda t: t.tier_id.id == tier1.id)
            tier2_review = review.tier_review_ids.filtered(lambda t: t.tier_id.id == tier2.id)
            self.assertTrue(tier1_review, "Tier 1 review record must exist.")
            self.assertTrue(tier2_review, "Tier 2 review record must exist.")
            self.assertEqual(
                tier1_review.status,
                "pending",
                "Tier 1 must be pending (active) immediately after submission.",
            )
            self.assertEqual(
                tier2_review.status,
                "waiting",
                "Tier 2 must be waiting until Tier 1 is approved.",
            )

            # ── Approve Tier 1 ────────────────────────────────────────────────
            review.with_user(self.approver_user).action_approve_tier()
            review.invalidate_recordset()

            tier1_review.invalidate_recordset()
            tier2_review.invalidate_recordset()
            self.assertEqual(
                tier1_review.status,
                "approved",
                "Tier 1 must be approved after action_approve_tier().",
            )
            self.assertEqual(
                tier2_review.status,
                "pending",
                "Tier 2 must become pending after Tier 1 is approved.",
            )

            # CR must still be pending (Tier 2 not yet approved).
            cr.invalidate_recordset()
            self.assertEqual(
                cr.approval_state,
                "pending",
                "CR must remain pending while Tier 2 is still outstanding.",
            )

            # ── Approve Tier 2 ────────────────────────────────────────────────
            review.with_user(self.approver_user).action_approve_tier()
            review.invalidate_recordset()

            # All tiers approved → review must be approved.
            self.assertEqual(
                review.status,
                "approved",
                "Review must be approved after all tiers are approved.",
            )

            # The multitier review system approves the review but does not
            # propagate back to the CR's stored approval_state (existing gap
            # in spp_approval).  Trigger the CR-level approval explicitly.
            cr._do_approve(auto=True)
            cr.invalidate_recordset()

            self.assertEqual(
                cr.approval_state,
                "approved",
                "CR must reach approved state after _do_approve().",
            )

            # auto_apply_on_approve=True means _on_approve() calls action_apply().
            self.assertTrue(
                cr.is_applied,
                "CR must be marked as applied when auto_apply_on_approve is True.",
            )

            # Verify the registrant's field was updated by the apply strategy.
            e2e_registrant.invalidate_recordset()
            self.assertEqual(
                e2e_registrant.given_name,
                "AfterApproval",
                "Registrant's given_name must be updated after the CR is applied.",
            )
        finally:
            # Delete in FK-safe order: reviews → CRs → CR type → definition.
            reviews = self.env["spp.approval.review"].search([("definition_id", "=", multitier_def.id)])
            reviews.unlink()
            self.CR.search([("request_type_id", "=", e2e_cr_type.id)]).unlink()
            e2e_cr_type.unlink()
            multitier_def.unlink()

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 14 – Non-dynamic type ignores field_to_modify
    # ──────────────────────────────────────────────────────────────────────────

    def test_non_dynamic_cr_type_ignores_field_to_modify(self):
        """Setting field_to_modify on a non-dynamic CR type's detail has no effect on routing.

        _get_approval_definition() must return the static approval_definition_id
        regardless of what field_to_modify is set to on the detail.
        """
        cr = self._create_cr(cr_type=self.non_dynamic_cr_type)
        detail = cr.get_detail()
        # Write a field that WOULD trigger escalated_def in a dynamic CR.
        detail.write({"field_to_modify": "given_name", "given_name": "Changed"})

        result = cr._get_approval_definition()
        self.assertEqual(
            result,
            self.static_def,
            "Non-dynamic CR types must always return their static approval_definition_id.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 15 – New value syncs when only the target field is updated
    # ──────────────────────────────────────────────────────────────────────────

    def test_value_sync_on_selected_field_edit(self):
        """Updating the target field without changing field_to_modify must re-sync new_value.

        After the initial write of field_to_modify + given_name, a subsequent
        write that only changes given_name (not field_to_modify) must still
        update selected_field_new_value so it reflects the latest value.
        """
        cr = self._create_cr()
        detail = cr.get_detail()

        # Initial write: set both the selector and the initial new value.
        detail.write({"field_to_modify": "given_name", "given_name": "First Value"})
        cr.invalidate_recordset()
        self.assertEqual(
            cr.selected_field_new_value,
            "First Value",
            "selected_field_new_value must be 'First Value' after the initial write.",
        )

        # Second write: update only the field value, not field_to_modify.
        detail.write({"given_name": "Second Value"})
        cr.invalidate_recordset()
        self.assertEqual(
            cr.selected_field_new_value,
            "Second Value",
            "selected_field_new_value must be updated to 'Second Value' after the detail field changes.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 16 – Many2one normalization includes code and parent for vocabulary
    # ──────────────────────────────────────────────────────────────────────────

    def test_normalize_value_includes_code_for_vocabulary(self):
        """_normalize_value_for_cel() enriches vocabulary Many2one with code and parent.

        For models with a ``code`` field (like spp.vocabulary.code), the normalized
        dict must include a ``code`` key. If the record has a ``parent_id`` with
        its own ``code``, a ``parent`` dict must also be present.
        """
        gender_codes = self.env["spp.vocabulary.code"].search([("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=1)
        if not gender_codes:
            self.skipTest("Need gender vocabulary codes (urn:iso:std:iso:5218) to run this test.")

        gender = gender_codes[0]

        # Set the registrant's gender so we can get old_value from it.
        self.registrant.write({"gender_id": gender.id})

        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "gender_id", "gender_id": gender.id})

        # Call the internal normalization directly.
        normalized = cr._normalize_value_for_cel(gender, detail, "gender_id")

        self.assertIsInstance(normalized, dict, "Many2one must normalize to a dict.")
        self.assertEqual(normalized["name"], gender.display_name, "name must be display_name.")
        self.assertIn("code", normalized, "Vocabulary codes must include a 'code' key.")
        self.assertEqual(normalized["code"], gender.code, "code must match the record's code.")

        # If gender has a parent, verify parent dict
        if gender.parent_id:
            self.assertIn("parent", normalized, "Hierarchical vocab must include parent dict.")
            self.assertEqual(normalized["parent"]["code"], gender.parent_id.code)

        # Restore registrant
        self.registrant.write({"gender_id": False})

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 17 – _normalize_value_for_cel covers all field types
    # ──────────────────────────────────────────────────────────────────────────

    def test_normalize_value_char_field(self):
        """_normalize_value_for_cel returns string for char/text/selection fields."""
        cr = self._create_cr()
        detail = cr.get_detail()
        # given_name is a Char field on the detail model
        result = cr._normalize_value_for_cel("hello", detail, "given_name")
        self.assertEqual(result, "hello")

    def test_normalize_value_date_field(self):
        """_normalize_value_for_cel passes through date values."""
        cr = self._create_cr()
        detail = cr.get_detail()
        # birthdate is a Date field on the detail model
        from datetime import date

        test_date = date(2000, 1, 15)
        result = cr._normalize_value_for_cel(test_date, detail, "birthdate")
        self.assertEqual(result, test_date)

    def test_normalize_value_falsy_boolean_returns_false(self):
        """_normalize_value_for_cel returns False (not None) for falsy boolean fields."""
        cr = self._create_cr()
        # Use a known boolean field from the detail base model
        detail = cr.get_detail()
        result = cr._normalize_value_for_cel(False, detail, "is_applied")
        self.assertIs(result, False, "Falsy boolean must return False, not None.")

    def test_normalize_value_falsy_integer_returns_zero(self):
        """_normalize_value_for_cel returns 0 for falsy integer/float/monetary fields."""
        cr = self._create_cr()
        registrant = cr.registrant_id
        # res.partner has 'color' as an Integer field
        result = cr._normalize_value_for_cel(False, registrant, "color")
        self.assertEqual(result, 0, "Falsy integer must return 0, not None.")

    def test_normalize_value_truthy_boolean(self):
        """_normalize_value_for_cel returns bool for boolean fields."""
        cr = self._create_cr()
        detail = cr.get_detail()
        result = cr._normalize_value_for_cel(True, detail, "is_applied")
        self.assertIs(result, True)

    def test_normalize_value_truthy_integer(self):
        """_normalize_value_for_cel returns numeric value for integer fields."""
        cr = self._create_cr()
        registrant = cr.registrant_id
        result = cr._normalize_value_for_cel(42, registrant, "color")
        self.assertEqual(result, 42)

    def test_normalize_value_many2many_field(self):
        """_normalize_value_for_cel returns dict with ids and count for x2many fields."""
        cr = self._create_cr()
        registrant = cr.registrant_id
        # category_id is a Many2many field on res.partner
        result = cr._normalize_value_for_cel(registrant.category_id, registrant, "category_id")
        self.assertIsInstance(result, dict)
        self.assertIn("ids", result)
        self.assertIn("count", result)
        self.assertIsInstance(result["ids"], list)

    def test_normalize_value_none_without_record(self):
        """_normalize_value_for_cel returns None when record is None."""
        cr = self._create_cr()
        result = cr._normalize_value_for_cel(None, None, None)
        self.assertIsNone(result)

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 18 – _compute_field_values_for_cel with no field selected
    # ──────────────────────────────────────────────────────────────────────────

    def test_compute_field_values_no_field_selected(self):
        """_compute_field_values_for_cel returns None values when no field is selected."""
        cr = self._create_cr()
        # Don't set field_to_modify — selected_field_name stays empty
        result = cr._compute_field_values_for_cel()
        self.assertIsNone(result["old_value"])
        self.assertIsNone(result["new_value"])

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 19 – _resolve_dynamic_approval with no selected field
    # ──────────────────────────────────────────────────────────────────────────

    def test_resolve_dynamic_approval_no_field_returns_none(self):
        """_resolve_dynamic_approval returns None when selected_field_name is not set."""
        cr = self._create_cr()
        result = cr._resolve_dynamic_approval()
        self.assertIsNone(result, "Must return None when no field is selected.")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 20 – _check_can_submit validates dynamic field selection
    # ──────────────────────────────────────────────────────────────────────────

    def test_check_can_submit_rejects_without_field_selection(self):
        """_check_can_submit raises ValidationError for dynamic CR without field selection."""
        cr = self._create_cr()
        # CR is dynamic but no field_to_modify set
        with self.assertRaises(ValidationError):
            cr._check_can_submit()

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 21 – Many2one normalization with hierarchical parent
    # ──────────────────────────────────────────────────────────────────────────

    def test_normalize_many2one_with_parent(self):
        """_normalize_value_for_cel includes parent dict for hierarchical records."""
        # Find a vocabulary code with a parent, or create one
        VocabCode = self.env["spp.vocabulary.code"]
        parent = VocabCode.search([("parent_id", "!=", False)], limit=1)
        if not parent:
            # Try to find any vocab code and check if the model supports parent
            any_code = VocabCode.search([], limit=1)
            if not any_code or "parent_id" not in any_code._fields:
                self.skipTest("Need hierarchical vocabulary codes with parent_id.")
            # Create parent-child pair
            vocab = any_code.vocabulary_id
            parent_rec = VocabCode.create({"name": "Test Parent", "code": "TEST_PARENT", "vocabulary_id": vocab.id})
            child_rec = VocabCode.create(
                {"name": "Test Child", "code": "TEST_CHILD", "vocabulary_id": vocab.id, "parent_id": parent_rec.id}
            )
            parent = child_rec

        cr = self._create_cr()
        detail = cr.get_detail()
        normalized = cr._normalize_value_for_cel(parent, detail, "gender_id")

        self.assertIsInstance(normalized, dict)
        self.assertIn("parent", normalized, "Hierarchical vocab must include parent dict.")
        self.assertIn("id", normalized["parent"])
        self.assertIn("name", normalized["parent"])
        self.assertIn("code", normalized["parent"])

    # ──────────────────────────────────────────────────────────────────────────
    # APPLY RESTRICTION — a dynamic-approval CR must apply ONLY the selected
    # field, even if other mapped detail fields were also changed. Otherwise a
    # user could route a low-risk field to a weak workflow and smuggle changes
    # to other (higher-risk) mapped fields through the same weak approval.
    # ──────────────────────────────────────────────────────────────────────────

    def _field_mapping_strategy(self):
        return self.env["spp.cr.strategy.field_mapping"]

    def test_dynamic_apply_writes_only_selected_field(self):
        cr = self._create_cr()
        detail = cr.get_detail()
        # Select the low-risk field (phone) but ALSO change a high-risk field.
        detail.write({"field_to_modify": "phone", "phone": "999-000", "given_name": "HACKED"})
        self.assertEqual(cr.selected_field_name, "phone")

        self._field_mapping_strategy().apply(cr)

        self.assertEqual(self.registrant.phone, "999-000", "the selected field must be applied")
        self.assertEqual(
            self.registrant.given_name,
            "Original Given",
            "a non-selected mapped field must NOT be applied for a dynamic-approval CR",
        )

    def test_dynamic_preview_shows_only_selected_field(self):
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "phone", "phone": "999-000", "given_name": "HACKED"})

        changes = self._field_mapping_strategy().preview(cr)

        self.assertEqual(len(changes), 1, "preview must show only the selected field for a dynamic CR")
        self.assertEqual(next(iter(changes.values()))["new"], "999-000")

    def test_dynamic_apply_unmapped_selected_field_writes_nothing(self):
        """Fail-closed: a dynamic CR whose selected field has no mapping writes nothing,
        even if another mapped detail field was changed.

        Applying is additionally rejected outright rather than reporting success.
        Returning success wrote nothing but still stamped the request applied,
        hiding a dropped change from operators; see
        ``test_apply_effective_mappings``. The fail-closed guarantee this test
        exists for is unchanged -- nothing is written either way.
        """
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"phone": "999-000"})
        # Force a selected field that is not present in apply_mapping_ids.
        cr.selected_field_name = "email"

        with self.assertRaises(UserError):
            self._field_mapping_strategy().apply(cr)

        self.assertEqual(self.registrant.phone, "111-222", "nothing may be applied for an unmapped selection")

    def test_non_dynamic_apply_still_writes_all_changed_fields(self):
        """Regression: non-dynamic CR types keep applying every changed mapping."""
        nd_type = self.CRType.create(
            {
                "name": "Non-Dynamic With Mappings",
                "code": "nd_with_mappings_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "approval_definition_id": self.static_def.id,
                "use_dynamic_approval": False,
                "apply_mapping_ids": [
                    Command.create({"source_field": "phone", "target_field": "phone", "sequence": 10}),
                    Command.create({"source_field": "given_name", "target_field": "given_name", "sequence": 20}),
                ],
            }
        )
        reg = self.env["res.partner"].create(
            {
                "name": "ND Registrant",
                "given_name": "OldGiven",
                "phone": "000-000",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cr = self.CR.create({"request_type_id": nd_type.id, "registrant_id": reg.id})
        detail = cr.get_detail()
        detail.write({"phone": "555-555", "given_name": "NewGiven"})

        self._field_mapping_strategy().apply(cr)

        self.assertEqual(reg.phone, "555-555")
        self.assertEqual(reg.given_name, "NewGiven", "non-dynamic CR must apply all changed mappings")

    # ──────────────────────────────────────────────────────────────────────────
    # POST-SUBMIT FREEZE — once routed, the proposed change (selected field and
    # the mapped values) is frozen. This closes the desync where a user routes on
    # a low-risk field, then swaps the field or its value before apply.
    # ──────────────────────────────────────────────────────────────────────────

    def _submit_dynamic_cr(self, selected="phone", **detail_vals):
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": selected, selected: detail_vals.get(selected, "999-000"), **detail_vals})
        cr.action_submit_for_approval()
        cr.invalidate_recordset()
        self.assertEqual(cr.approval_state, "pending")
        return cr, detail

    def test_cannot_change_field_to_modify_after_submit(self):
        _cr, detail = self._submit_dynamic_cr(selected="phone")
        with self.assertRaises(UserError):
            detail.write({"field_to_modify": "given_name", "given_name": "HACKED"})

    def test_cannot_change_selected_field_name_directly_after_submit(self):
        cr, _detail = self._submit_dynamic_cr(selected="phone")
        with self.assertRaises(UserError):
            cr.write({"selected_field_name": "given_name"})

    def test_cannot_change_selected_field_value_after_submit(self):
        """Value-swap: even the same (selected) field's value is frozen post-submit,
        because the value was what the approval was routed on."""
        _cr, detail = self._submit_dynamic_cr(selected="phone", phone="111-orig")
        with self.assertRaises(UserError):
            detail.write({"phone": "222-swapped"})

    def test_cannot_repoint_detail_after_submit(self):
        """Substitution bypass: create a second detail and repoint detail_res_id
        to it. get_detail() resolves strictly by detail_res_id, so this would
        otherwise apply the substituted values under the original routing."""
        cr, _detail = self._submit_dynamic_cr(selected="phone", phone="111-orig")
        substitute = self.env["spp.cr.detail.edit_individual"].create(
            {"change_request_id": cr.id, "phone": "999-SUBSTITUTED"}
        )
        with self.assertRaises(UserError):
            cr.write({"detail_res_id": substitute.id})

    def test_no_op_write_of_unset_protected_field_is_allowed(self):
        """Regression (false-positive lockout): writing None to a protected source
        field that is already unset must not raise post-submit. Odoo stores unset
        fields as False while a JSON-RPC payload may send None for the same field;
        the freeze must treat them as equal (no change), not lock the user out."""
        _cr, detail = self._submit_dynamic_cr(selected="phone")
        self.assertFalse(detail.birthdate)  # a protected (mapped) field, unset
        # None vs the stored False is a no-op, not a change — must not raise.
        detail.write({"birthdate": None})

    def test_can_change_selection_while_draft(self):
        """The freeze must not over-block: while still in draft the user can
        freely change the selected field (which re-routes on submission)."""
        cr = self._create_cr()
        detail = cr.get_detail()
        detail.write({"field_to_modify": "phone", "phone": "111-222-draft"})
        # Still draft — switching the selected field is allowed.
        detail.write({"field_to_modify": "given_name", "given_name": "Draft Edit"})
        self.assertEqual(cr.approval_state, "draft")
        self.assertEqual(cr.selected_field_name, "given_name")
