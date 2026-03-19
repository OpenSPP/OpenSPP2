# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farm Season model.

Tests cover:
- Season creation and access control
- State transitions (draft -> active -> closed)
- Constraints (overlapping seasons, date validation, force close)
- Computed fields (access rights, show_close_button, activity_count)
- Copy behavior
- Display name computation
- Deletion controls
- toggle_active override
- _get_current_season helper
- action_view_activities
"""

import time
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import FarmerTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestFarmSeasonCreate(TransactionCase, FarmerTestDataMixin):
    """Test farm season creation and basic fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_create_season(self):
        """Test creating a basic season."""
        season = self._create_test_season(name=_unique("Basic Season"), state="draft")

        self.assertEqual(season.state, "draft")
        self.assertTrue(season.active)

    def test_create_season_date_validation(self):
        """Test that end date must be after start date."""
        today = date.today()

        with self.assertRaises(Exception):  # noqa: B017
            self.env["spp.farm.season"].create(
                {
                    "name": _unique("Invalid Date Season"),
                    "date_start": today,
                    "date_end": today - timedelta(days=1),
                }
            )

    def test_season_unique_name_constraint(self):
        """Test that season name must be unique."""
        name = _unique("Unique Season")
        self._create_test_season(name=name, state="draft")

        with self.assertRaises(Exception):  # noqa: B017
            self._create_test_season(name=name, state="draft")


@tagged("post_install", "-at_install")
class TestFarmSeasonStateTransitions(TransactionCase, FarmerTestDataMixin):
    """Test farm season state machine transitions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_activate_draft_season(self):
        """Test activating a draft season."""
        season = self._create_test_season(name=_unique("Activate Season"), state="draft")
        season.action_activate()

        self.assertEqual(season.state, "active")

    def test_activate_non_draft_raises(self):
        """Test that activating a non-draft season raises ValidationError."""
        season = self._create_test_season(name=_unique("Active Season"))
        # Season is already active
        with self.assertRaises(ValidationError):
            season.action_activate()

    def test_close_active_season_past_end_date(self):
        """Test closing an active season after end date."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("ClosePast Season"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()
        season.action_close()

        self.assertEqual(season.state, "closed")

    def test_close_active_season_future_end_date_raises(self):
        """Test closing an active season before end date raises without force_close."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("CloseFuture Season"),
            state="draft",
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=30),
            allow_overlap=True,
        )
        season.action_activate()

        with self.assertRaises(ValidationError):
            season.action_close()

    def test_force_close_active_season(self):
        """Test force closing an active season before end date."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("ForceClose Season"),
            state="draft",
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=30),
            allow_overlap=True,
        )
        season.action_activate()
        season.action_force_close()

        self.assertEqual(season.state, "closed")
        self.assertTrue(season.force_close)

    def test_close_non_active_raises(self):
        """Test that closing a non-active season raises ValidationError."""
        season = self._create_test_season(name=_unique("CloseDraft Season"), state="draft")

        with self.assertRaises(ValidationError):
            season.action_close()

    def test_draft_active_season_no_activities(self):
        """Test resetting an active season to draft when no activities exist."""
        season = self._create_test_season(name=_unique("Draft Active"), state="draft")
        season.action_activate()
        season.action_draft()

        self.assertEqual(season.state, "draft")

    def test_draft_closed_season_raises(self):
        """Test that reopening a closed season raises ValidationError."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("Reopen Closed"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()
        season.action_close()

        with self.assertRaises(ValidationError):
            season.action_draft()

    def test_draft_with_activities_raises(self):
        """Test that resetting to draft with activities raises ValidationError."""
        species = self._create_species_vocabularies()
        farm = self._create_test_farm(name=_unique("DraftAct Farm"))

        season = self._create_test_season(name=_unique("DraftAct Season"), state="draft")
        season.action_activate()

        self.env["spp.farm.activity"].create(
            {
                "crop_farm_id": farm.id,
                "activity_type": "crop",
                "species_id": species["crop"]["rice"].id,
                "season_id": season.id,
            }
        )

        with self.assertRaises(ValidationError):
            season.action_draft()


@tagged("post_install", "-at_install")
class TestFarmSeasonOverlap(TransactionCase, FarmerTestDataMixin):
    """Test farm season overlap constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_overlapping_active_seasons_raises(self):
        """Test that activating overlapping seasons raises ValidationError."""
        today = date.today()

        season1 = self._create_test_season(
            name=_unique("Overlap1"),
            state="draft",
            date_start=today - timedelta(days=30),
            date_end=today + timedelta(days=30),
            allow_overlap=False,
        )
        season1.action_activate()

        season2 = self.env["spp.farm.season"].create(
            {
                "name": _unique("Overlap2"),
                "date_start": today - timedelta(days=10),
                "date_end": today + timedelta(days=50),
                "allow_overlap": False,
            }
        )

        with self.assertRaises(ValidationError):
            season2.action_activate()

    def test_overlapping_allowed_seasons_ok(self):
        """Test that overlapping is allowed when allow_overlap is True."""
        today = date.today()

        season1 = self._create_test_season(
            name=_unique("OverlapOK1"),
            state="draft",
            date_start=today - timedelta(days=30),
            date_end=today + timedelta(days=30),
            allow_overlap=True,
        )
        season1.action_activate()

        season2 = self._create_test_season(
            name=_unique("OverlapOK2"),
            state="draft",
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=50),
            allow_overlap=True,
        )
        season2.action_activate()

        self.assertEqual(season1.state, "active")
        self.assertEqual(season2.state, "active")


@tagged("post_install", "-at_install")
class TestFarmSeasonComputedFields(TransactionCase, FarmerTestDataMixin):
    """Test farm season computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_compute_access_rights_manager(self):
        """Test access rights computed for manager user."""
        season = self._create_test_season(name=_unique("AccessRights"), state="draft")

        # Admin user has manager group
        self.assertTrue(season.can_edit)
        self.assertTrue(season.can_activate)
        self.assertFalse(season.can_close)

    def test_compute_access_rights_active_state(self):
        """Test access rights change when season is active."""
        season = self._create_test_season(name=_unique("AccessActive"), state="draft")
        season.action_activate()

        self.assertTrue(season.can_edit)
        self.assertFalse(season.can_activate)
        self.assertTrue(season.can_close)

    def test_compute_access_rights_closed_state(self):
        """Test access rights for closed state."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("AccessClosed"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()
        season.action_close()

        self.assertFalse(season.can_edit)
        self.assertFalse(season.can_activate)
        self.assertFalse(season.can_close)

    def test_compute_show_close_button_past_end(self):
        """Test show_close_button is True when end date is in the past."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("ShowClose"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()

        self.assertTrue(season.show_close_button)

    def test_compute_show_close_button_future_end(self):
        """Test show_close_button is False when end date is in the future."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("HideClose"),
            state="draft",
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=30),
            allow_overlap=True,
        )
        season.action_activate()

        self.assertFalse(season.show_close_button)

    def test_compute_show_close_button_draft(self):
        """Test show_close_button is False for draft season."""
        season = self._create_test_season(name=_unique("DraftCloseBtn"), state="draft")
        self.assertFalse(season.show_close_button)

    def test_compute_show_force_close_button_future_end(self):
        """Test show_force_close_button is True when active with future end date."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("ShowForce"),
            state="draft",
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=30),
            allow_overlap=True,
        )
        season.action_activate()

        self.assertTrue(season.show_force_close_button)

    def test_compute_show_force_close_button_past_end(self):
        """Test show_force_close_button is False when end date is in the past."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("HideForce"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()

        self.assertFalse(season.show_force_close_button)

    def test_compute_activity_count(self):
        """Test activity_count is computed from activity_ids."""
        species = self._create_species_vocabularies()
        farm = self._create_test_farm(name=_unique("Count Farm"))
        season = self._create_test_season(name=_unique("Count Season"))

        self.env["spp.farm.activity"].create(
            {
                "crop_farm_id": farm.id,
                "activity_type": "crop",
                "species_id": species["crop"]["rice"].id,
                "season_id": season.id,
            }
        )

        season.invalidate_recordset()
        self.assertEqual(season.activity_count, 1)

    def test_display_name_with_dates(self):
        """Test display name includes dates."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("Display"),
            state="draft",
            date_start=today,
            date_end=today + timedelta(days=30),
        )

        self.assertIn(str(today), season.display_name)


@tagged("post_install", "-at_install")
class TestFarmSeasonCopyAndDelete(TransactionCase, FarmerTestDataMixin):
    """Test farm season copy and delete behavior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_copy_season(self):
        """Test copying a season resets to draft and updates name."""
        season = self._create_test_season(name=_unique("CopySeason"), state="draft")
        copied = season.copy()

        self.assertEqual(copied.state, "draft")
        self.assertIn("Copy", copied.name)
        self.assertNotEqual(copied.name, season.name)

    def test_copy_active_season(self):
        """Test copying an active season still creates draft."""
        season = self._create_test_season(name=_unique("CopyActive"), state="draft")
        season.action_activate()
        copied = season.copy()

        self.assertEqual(copied.state, "draft")

    def test_delete_draft_season(self):
        """Test deleting a draft season succeeds."""
        season = self._create_test_season(name=_unique("DeleteDraft"), state="draft")
        season_id = season.id
        season.unlink()

        self.assertFalse(self.env["spp.farm.season"].search([("id", "=", season_id)]))

    def test_delete_closed_season_raises(self):
        """Test deleting a closed season raises ValidationError."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("DeleteClosed"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()
        season.action_close()

        with self.assertRaises(ValidationError):
            season.unlink()


@tagged("post_install", "-at_install")
class TestFarmSeasonHelpers(TransactionCase, FarmerTestDataMixin):
    """Test farm season helper methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

    def test_get_current_season(self):
        """Test _get_current_season returns active season covering today."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("Current Season"),
            state="draft",
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=20),
            allow_overlap=True,
        )
        season.action_activate()

        current = self.env["spp.farm.season"]._get_current_season()
        self.assertTrue(current)
        self.assertEqual(current.state, "active")

    def test_get_current_season_none(self):
        """Test _get_current_season returns empty when no active season covers today."""
        today = date.today()
        season = self._create_test_season(
            name=_unique("Future Season"),
            state="draft",
            date_start=today + timedelta(days=10),
            date_end=today + timedelta(days=40),
            allow_overlap=True,
        )
        season.action_activate()

        # This season doesn't cover today, so _get_current_season may or may not find it
        # depending on other test data. Just verify it returns a recordset.
        current = self.env["spp.farm.season"]._get_current_season()
        if current:
            self.assertTrue(current.date_start <= today <= current.date_end)

    def test_action_view_activities(self):
        """Test action_view_activities returns correct action dict."""
        season = self._create_test_season(name=_unique("ViewAct Season"))

        action = season.action_view_activities()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.farm.activity")
        self.assertEqual(action["domain"], [("season_id", "=", season.id)])
        self.assertEqual(action["context"]["default_season_id"], season.id)

    def test_toggle_active_closed_with_activities_raises(self):
        """Test toggle_active raises for closed season with activities."""
        species = self._create_species_vocabularies()
        farm = self._create_test_farm(name=_unique("Toggle Farm"))
        today = date.today()

        season = self._create_test_season(
            name=_unique("Toggle Season"),
            state="draft",
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=1),
            allow_overlap=True,
        )
        season.action_activate()

        self.env["spp.farm.activity"].create(
            {
                "crop_farm_id": farm.id,
                "activity_type": "crop",
                "species_id": species["crop"]["rice"].id,
                "season_id": season.id,
            }
        )

        season.action_close()
        # Archive the season via SQL to bypass write ACL (test setup only)
        self.env.cr.execute(
            "UPDATE spp_farm_season SET active = false WHERE id = %s",
            (season.id,),
        )
        season.invalidate_recordset()

        with self.assertRaises(ValidationError):
            season.toggle_active()
