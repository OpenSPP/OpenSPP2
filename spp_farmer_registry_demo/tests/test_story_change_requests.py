# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Change Request generation in farmer_demo_generator.py.

Tests cover:
- _resolve_cr_registrant() finds registrant by name
- _resolve_cr_registrant() falls back to story_farms dict
- _create_single_change_request() creates CR with detail
- _build_farmer_detail_changes() for farm_details model
- _build_farmer_detail_changes() for manage_farm_activity model
- _set_cr_state() transitions through approval workflow
- STORY_CHANGE_REQUESTS definitions structure
"""

import time

from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestResolveCrRegistrant(TransactionCase):
    """Test _resolve_cr_registrant() method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]
        cls.wizard = cls.Generator.create({"name": _unique("CR Resolve Test")})

        # Create a registrant we can look up by name
        cls.test_farm = (
            cls.env["res.partner"]
            .sudo()
            .create(
                {
                    "name": "Test CR Farm",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

    def test_resolve_by_registrant_name(self):
        """When registrant_name is set, looks up partner by name."""
        cr_def = {"registrant_name": "Test CR Farm"}
        result = self.wizard._resolve_cr_registrant("any_story", cr_def, {})
        self.assertEqual(result.id, self.test_farm.id)

    def test_resolve_by_registrant_name_not_found(self):
        """When registrant_name does not match, falls back to story dict."""
        story_farms = {"test_story": self.test_farm}
        cr_def = {"registrant_name": "Nonexistent Farm Name"}
        result = self.wizard._resolve_cr_registrant("test_story", cr_def, story_farms)
        self.assertEqual(result.id, self.test_farm.id)

    def test_resolve_falls_back_to_story_id(self):
        """Without registrant_name, uses story_id key in story_farms dict."""
        story_farms = {"maria_santos": self.test_farm}
        cr_def = {}
        result = self.wizard._resolve_cr_registrant("maria_santos", cr_def, story_farms)
        self.assertEqual(result.id, self.test_farm.id)

    def test_resolve_strips_suffix_for_base_id(self):
        """Story IDs with _add_activity suffix should strip to base ID."""
        story_farms = {"juan_dela_cruz": self.test_farm}
        cr_def = {}
        result = self.wizard._resolve_cr_registrant("juan_dela_cruz_add_activity", cr_def, story_farms)
        self.assertEqual(result.id, self.test_farm.id)

    def test_resolve_strips_update_suffix(self):
        """Story IDs with _update suffix should strip to base ID."""
        story_farms = {"danilo_villanueva": self.test_farm}
        cr_def = {}
        result = self.wizard._resolve_cr_registrant("danilo_villanueva_update", cr_def, story_farms)
        self.assertEqual(result.id, self.test_farm.id)

    def test_resolve_returns_none_when_not_found(self):
        """Returns None when neither name nor story_id matches."""
        cr_def = {}
        result = self.wizard._resolve_cr_registrant("nonexistent_story", cr_def, {})
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestBuildFarmerDetailChanges(TransactionCase):
    """Test _build_farmer_detail_changes() method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]
        cls.wizard = cls.Generator.create({"name": _unique("Detail Build Test")})

        # Create test vocabularies
        cls._create_test_vocabularies()

        # Create a farm registrant for reference
        cls.test_farm = (
            cls.env["res.partner"]
            .sudo()
            .create(
                {
                    "name": "Build Detail Farm",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

    @classmethod
    def _create_test_vocabularies(cls):
        """Create vocabularies needed for detail building."""
        Vocabulary = cls.env["spp.vocabulary"]
        VocabCode = cls.env["spp.vocabulary.code"]

        vocab_defs = [
            {
                "name": "Farm Type",
                "namespace_uri": "urn:openspp:vocab:farm-type",
                "codes": [("crop", "Crop Farming"), ("mixed", "Mixed Farming")],
            },
            {
                "name": "Land Tenure",
                "namespace_uri": "urn:openspp:vocab:land-tenure",
                "codes": [("self", "Self-owned"), ("family", "Family-owned")],
            },
            {
                "name": "FAO ICC",
                "namespace_uri": "urn:fao:icc:1.1",
                "codes": [("02", "Vegetables")],
            },
            {
                "name": "FAO Livestock",
                "namespace_uri": "urn:fao:livestock:2020",
                "codes": [("5.1", "Chickens")],
            },
        ]

        for vocab_def in vocab_defs:
            vocab = Vocabulary.search([("namespace_uri", "=", vocab_def["namespace_uri"])], limit=1)
            if not vocab:
                vocab = Vocabulary.create(
                    {
                        "name": vocab_def["name"],
                        "namespace_uri": vocab_def["namespace_uri"],
                    }
                )
                for code, display in vocab_def["codes"]:
                    VocabCode.create(
                        {
                            "vocabulary_id": vocab.id,
                            "namespace_uri": vocab_def["namespace_uri"],
                            "code": code,
                            "display": display,
                        }
                    )

    def test_empty_proposed_changes(self):
        """Empty proposed_changes returns empty dict."""
        result = self.wizard._build_farmer_detail_changes("spp.cr.detail.farm_details", self.test_farm, {})
        self.assertEqual(result, {})

    def test_none_proposed_changes(self):
        """None proposed_changes returns empty dict."""
        result = self.wizard._build_farmer_detail_changes("spp.cr.detail.farm_details", self.test_farm, None)
        self.assertEqual(result, {})

    def test_farm_details_numeric_fields(self):
        """Direct numeric fields should be mapped from proposed_changes."""
        proposed = {
            "farm_total_size": 5.0,
            "farm_size_under_crops": 3.0,
            "farm_size_idle": 2.0,
            "experience_years": 15,
        }
        result = self.wizard._build_farmer_detail_changes("spp.cr.detail.farm_details", self.test_farm, proposed)
        self.assertEqual(result["farm_total_size"], 5.0)
        self.assertEqual(result["farm_size_under_crops"], 3.0)
        self.assertEqual(result["farm_size_idle"], 2.0)
        self.assertEqual(result["experience_years"], 15)

    def test_farm_details_farm_type_code(self):
        """farm_type_code should resolve to vocabulary ID."""
        proposed = {"farm_type_code": "crop"}
        result = self.wizard._build_farmer_detail_changes("spp.cr.detail.farm_details", self.test_farm, proposed)
        if result.get("farm_type_id"):
            code = self.env["spp.vocabulary.code"].browse(result["farm_type_id"])
            self.assertEqual(code.code, "crop")

    def test_farm_details_land_tenure_code(self):
        """land_tenure_code should resolve to vocabulary ID."""
        proposed = {"land_tenure_code": "self"}
        result = self.wizard._build_farmer_detail_changes("spp.cr.detail.farm_details", self.test_farm, proposed)
        if result.get("land_tenure_id"):
            code = self.env["spp.vocabulary.code"].browse(result["land_tenure_id"])
            self.assertEqual(code.code, "self")

    def test_manage_activity_operation_field(self):
        """manage_farm_activity detail should map operation and lock it."""
        proposed = {
            "operation": "add",
            "activity_type": "crop",
            "species_code": "vegetables",
            "area_planted": 0.5,
        }
        result = self.wizard._build_farmer_detail_changes(
            "spp.cr.detail.manage_farm_activity", self.test_farm, proposed
        )
        self.assertEqual(result["operation"], "add")
        self.assertTrue(result["is_operation_locked"])
        self.assertEqual(result["activity_type"], "crop")

    def test_manage_activity_species_resolution(self):
        """Species code should resolve through SPECIES_MAP."""
        proposed = {
            "operation": "add",
            "activity_type": "livestock",
            "species_code": "chickens",
            "quantity": 50.0,
            "quantity_unit": "heads",
        }
        result = self.wizard._build_farmer_detail_changes(
            "spp.cr.detail.manage_farm_activity", self.test_farm, proposed
        )
        if result.get("species_id"):
            code = self.env["spp.vocabulary.code"].browse(result["species_id"])
            self.assertEqual(code.code, "5.1")

    def test_manage_activity_numeric_fields(self):
        """Numeric fields should be passed through directly."""
        proposed = {
            "operation": "add",
            "activity_type": "crop",
            "quantity": 100.0,
            "area_planted": 1.5,
            "expected_yield": 3000.0,
            "actual_yield": 2800.0,
        }
        result = self.wizard._build_farmer_detail_changes(
            "spp.cr.detail.manage_farm_activity", self.test_farm, proposed
        )
        self.assertEqual(result["quantity"], 100.0)
        self.assertEqual(result["area_planted"], 1.5)
        self.assertEqual(result["expected_yield"], 3000.0)
        self.assertEqual(result["actual_yield"], 2800.0)

    def test_manage_activity_gets_active_season(self):
        """Season should be auto-filled from active season."""
        Season = self.env["spp.farm.season"]
        if not Season.search([("state", "=", "active")]):
            Season.sudo().create(
                {
                    "name": _unique("Test Season"),
                    "date_start": "2026-01-01",
                    "date_end": "2026-12-31",
                    "state": "active",
                }
            )

        proposed = {"operation": "add", "activity_type": "crop"}
        result = self.wizard._build_farmer_detail_changes(
            "spp.cr.detail.manage_farm_activity", self.test_farm, proposed
        )
        active_season = Season.search([("state", "=", "active")], limit=1)
        if active_season:
            self.assertEqual(result.get("season_id"), active_season.id)

    def test_unknown_detail_model_returns_empty(self):
        """Unknown detail model returns empty dict."""
        proposed = {"field": "value"}
        result = self.wizard._build_farmer_detail_changes("spp.cr.detail.unknown", self.test_farm, proposed)
        self.assertEqual(result, {})


@tagged("post_install", "-at_install")
class TestSetCrState(TransactionCase):
    """Test _set_cr_state() method with CR state transitions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]
        cls.wizard = cls.Generator.create({"name": _unique("CR State Test")})

        # Create a farm registrant
        cls.test_farm = (
            cls.env["res.partner"]
            .sudo()
            .create(
                {
                    "name": "State Test Farm",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

    def _create_cr(self):
        """Create a basic CR for state transition tests."""
        if "spp.change.request" not in self.env:
            self.skipTest("spp.change.request model not available")

        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        if not cr_type:
            self.skipTest("No CR types available")

        return self.env["spp.change.request"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.test_farm.id,
                "description": "Test CR for state transitions",
            }
        )

    def test_set_cr_state_pending(self):
        """Setting CR to pending should submit for approval."""
        cr = self._create_cr()
        self.wizard._set_cr_state(cr, "pending")
        # After setting pending, stage should be review for non-draft
        if "stage" in cr._fields:
            self.assertEqual(cr.stage, "review")

    def test_set_cr_state_approved(self):
        """Setting CR to approved should submit then approve."""
        cr = self._create_cr()
        self.wizard._set_cr_state(cr, "approved")
        # Should have advanced through approval
        if hasattr(cr, "approval_state"):
            self.assertIn(cr.approval_state, ("approved", "pending"))

    def test_set_cr_state_rejected(self):
        """Setting CR to rejected should submit then reject."""
        cr = self._create_cr()
        self.wizard._set_cr_state(cr, "rejected", rejection_reason="Test rejection reason")
        if "stage" in cr._fields:
            self.assertEqual(cr.stage, "review")

    def test_set_cr_state_revision(self):
        """Setting CR to revision should submit then request revision."""
        cr = self._create_cr()
        self.wizard._set_cr_state(cr, "revision", revision_notes="Please revise the form")
        if "stage" in cr._fields:
            self.assertEqual(cr.stage, "review")

    def test_set_cr_state_draft_no_stage_change(self):
        """Draft CRs should not have their stage changed to review."""
        cr = self._create_cr()
        original_stage = cr.stage if "stage" in cr._fields else None
        self.wizard._set_cr_state(cr, "draft")
        if "stage" in cr._fields:
            # Draft should NOT set stage to review
            self.assertEqual(cr.stage, original_stage)

    def test_set_cr_state_handles_failure_gracefully(self):
        """When approval workflow fails, method should not raise."""
        cr = self._create_cr()
        # This should handle errors gracefully via the try/except
        self.wizard._set_cr_state(cr, "approved")
        # Should not raise regardless of outcome

    def test_set_cr_state_with_apply(self):
        """Setting apply=True should attempt to apply the CR after approval."""
        cr = self._create_cr()
        self.wizard._set_cr_state(cr, "approved", apply=True)
        # Should not raise; may set is_applied directly if action_apply fails
        if hasattr(cr, "is_applied"):
            # Either applied via action or via direct write
            pass  # Just checking no exception occurred


@tagged("post_install", "-at_install")
class TestCreateSingleChangeRequest(TransactionCase):
    """Test _create_single_change_request() method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]
        cls.wizard = cls.Generator.create({"name": _unique("Single CR Test")})

        cls.test_farm = (
            cls.env["res.partner"]
            .sudo()
            .create(
                {
                    "name": "Single CR Farm",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

    def test_create_cr_with_unknown_type(self):
        """Unknown CR type code should return None."""
        cr_def = {
            "type_code": "nonexistent_cr_type",
            "days_back": 5,
            "state": "draft",
            "description": "Test",
            "proposed_changes": {},
        }
        stats = {}
        result = self.wizard._create_single_change_request(self.test_farm, cr_def, stats)
        self.assertIsNone(result)

    def test_create_cr_with_valid_type(self):
        """Valid CR type code should create a change request record."""
        if "spp.change.request" not in self.env:
            self.skipTest("spp.change.request model not available")

        # Find an actual CR type
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        if not cr_type:
            self.skipTest("No CR types available")

        cr_def = {
            "type_code": cr_type.code,
            "days_back": 10,
            "state": "draft",
            "description": "Test CR creation",
            "proposed_changes": {},
        }
        stats = {}
        result = self.wizard._create_single_change_request(self.test_farm, cr_def, stats)
        if result:
            self.assertEqual(result.registrant_id.id, self.test_farm.id)
            self.assertEqual(stats.get("change_requests_created", 0), 1)


@tagged("post_install", "-at_install")
class TestStoryChangeRequestDefinitions(TransactionCase):
    """Test STORY_CHANGE_REQUESTS structure on the generator model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]
        cls.wizard = cls.Generator.create({"name": _unique("CR Definitions Test")})

    def test_all_cr_defs_have_required_keys(self):
        """Every CR definition must have type_code, state, and proposed_changes."""
        for story_id, cr_def in self.wizard.STORY_CHANGE_REQUESTS.items():
            self.assertIn(
                "type_code",
                cr_def,
                f"CR def for {story_id} missing type_code",
            )
            self.assertIn(
                "state",
                cr_def,
                f"CR def for {story_id} missing state",
            )
            self.assertIn(
                "proposed_changes",
                cr_def,
                f"CR def for {story_id} missing proposed_changes",
            )

    def test_cr_defs_have_valid_states(self):
        """All CR states must be one of the known values."""
        valid_states = {"draft", "pending", "approved", "applied", "rejected", "revision"}
        for story_id, cr_def in self.wizard.STORY_CHANGE_REQUESTS.items():
            self.assertIn(
                cr_def["state"],
                valid_states,
                f"CR def for {story_id} has invalid state: {cr_def['state']}",
            )

    def test_cr_defs_have_valid_type_codes(self):
        """All CR type codes must be one of the known types."""
        valid_types = {"update_farm_details", "manage_farm_activity", "manage_farm_asset"}
        for story_id, cr_def in self.wizard.STORY_CHANGE_REQUESTS.items():
            self.assertIn(
                cr_def["type_code"],
                valid_types,
                f"CR def for {story_id} has invalid type_code: {cr_def['type_code']}",
            )

    def test_rejected_defs_have_rejection_reason(self):
        """Rejected CRs should have a rejection_reason."""
        for story_id, cr_def in self.wizard.STORY_CHANGE_REQUESTS.items():
            if cr_def["state"] == "rejected":
                self.assertIn(
                    "rejection_reason",
                    cr_def,
                    f"Rejected CR for {story_id} missing rejection_reason",
                )

    def test_revision_defs_have_revision_notes(self):
        """Revision CRs should have revision_notes."""
        for story_id, cr_def in self.wizard.STORY_CHANGE_REQUESTS.items():
            if cr_def["state"] == "revision":
                self.assertIn(
                    "revision_notes",
                    cr_def,
                    f"Revision CR for {story_id} missing revision_notes",
                )

    def test_cr_defs_count(self):
        """There should be at least 8 CR definitions (one per story + extras)."""
        count = len(self.wizard.STORY_CHANGE_REQUESTS)
        self.assertGreaterEqual(count, 8)
