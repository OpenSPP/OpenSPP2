# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Phase 9: Job concurrency, channel routing, and identity keys.

Verify that async dispatchers pass correct channel and identity_key to
delayable(), and that completion handlers route to statistics_refresh.
"""

import uuid
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.tests import TransactionCase


class TestCycleManagerChannelRouting(TransactionCase):
    """Test channel routing and identity_key in cycle manager async methods."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.cycle_manager = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": self.program.id,
            }
        )

    def test_check_eligibility_async_uses_identity_key(self):
        """_check_eligibility_async must pass identity_key to delayable."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(3)]
        )
        self.env["spp.cycle.membership"].create(
            [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "draft"} for p in partners]
        )

        delayable_calls = []
        original_delayable = type(self.cycle_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(self.cycle_manager), "delayable", mock_delayable):
            try:
                self.cycle_manager._check_eligibility_async(self.cycle, 3)
            except Exception:
                pass

        # Should have at least one call with identity_key containing "check_elig_"
        identity_keys = [c.get("identity_key", "") for c in delayable_calls]
        has_check_elig_key = any("check_elig_" in k for k in identity_keys)
        self.assertTrue(has_check_elig_key, f"Expected identity_key with 'check_elig_', got: {identity_keys}")

        # Completion handler should route to statistics_refresh
        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("statistics_refresh", channels)

    def test_prepare_entitlements_async_uses_identity_key(self):
        """_prepare_entitlements_async must pass identity_key to delayable."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(3)]
        )
        self.env["spp.cycle.membership"].create(
            [{"partner_id": p.id, "cycle_id": self.cycle.id, "state": "enrolled"} for p in partners]
        )

        delayable_calls = []
        original_delayable = type(self.cycle_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(self.cycle_manager), "delayable", mock_delayable):
            try:
                self.cycle_manager._prepare_entitlements_async(self.cycle, 3)
            except Exception:
                pass

        identity_keys = [c.get("identity_key", "") for c in delayable_calls]
        has_prepare_key = any("prepare_ent_" in k for k in identity_keys)
        self.assertTrue(has_prepare_key, f"Expected identity_key with 'prepare_ent_', got: {identity_keys}")

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("statistics_refresh", channels)

    def test_add_beneficiaries_async_uses_identity_key(self):
        """_add_beneficiaries_async must pass identity_key to delayable."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(3)]
        )

        delayable_calls = []
        original_delayable = type(self.cycle_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(self.cycle_manager), "delayable", mock_delayable):
            try:
                self.cycle_manager._add_beneficiaries_async(self.cycle, partners.ids, "draft")
            except Exception:
                pass

        identity_keys = [c.get("identity_key", "") for c in delayable_calls]
        has_add_key = any("add_benef_" in k for k in identity_keys)
        self.assertTrue(has_add_key, f"Expected identity_key with 'add_benef_', got: {identity_keys}")

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("statistics_refresh", channels)


class TestProgramManagerChannelRouting(TransactionCase):
    """Test channel routing and identity_key in program manager async methods."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.manager = self.env["spp.program.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
            }
        )

    def test_enroll_eligible_async_uses_identity_key(self):
        """_enroll_eligible_registrants_async must pass identity_key to delayable."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(3)]
        )
        self.env["spp.program.membership"].create(
            [{"partner_id": p.id, "program_id": self.program.id, "state": "draft"} for p in partners]
        )

        delayable_calls = []
        original_delayable = type(self.manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(self.manager), "delayable", mock_delayable):
            try:
                self.manager._enroll_eligible_registrants_async(["draft"], 3)
            except Exception:
                pass

        identity_keys = [c.get("identity_key", "") for c in delayable_calls]
        has_enroll_key = any("enroll_eligible_" in k for k in identity_keys)
        self.assertTrue(has_enroll_key, f"Expected identity_key with 'enroll_eligible_', got: {identity_keys}")

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("statistics_refresh", channels)


class TestEligibilityManagerChannelRouting(TransactionCase):
    """Test channel routing and identity_key in eligibility manager async methods."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.elig_manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Elig Manager",
                "program_id": self.program.id,
            }
        )

    def test_import_registrants_async_uses_identity_key(self):
        """_import_registrants_async must pass identity_key to delayable."""
        partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(3)]
        )

        delayable_calls = []
        original_delayable = type(self.elig_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(self.elig_manager), "delayable", mock_delayable):
            try:
                self.elig_manager._import_registrants_async(partners, "draft")
            except Exception:
                pass

        identity_keys = [c.get("identity_key", "") for c in delayable_calls]
        has_import_key = any("import_reg_" in k for k in identity_keys)
        self.assertTrue(has_import_key, f"Expected identity_key with 'import_reg_', got: {identity_keys}")

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("statistics_refresh", channels)


class TestEntitlementManagerChannelRouting(TransactionCase):
    """Test that entitlement async methods route to entitlement_approval channel."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

    def _get_entitlement_manager(self):
        """Get a cash entitlement manager for testing."""
        return self.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Test Entitlement Manager",
                "program_id": self.program.id,
            }
        )

    def test_set_pending_validation_async_routes_to_entitlement_approval(self):
        """_set_pending_validation_entitlements_async must use entitlement_approval channel."""
        ent_manager = self._get_entitlement_manager()
        mock_entitlements = MagicMock()
        mock_entitlements.__len__ = MagicMock(return_value=5)
        mock_entitlements.__getitem__ = MagicMock(return_value=mock_entitlements)

        delayable_calls = []
        original_delayable = type(ent_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(ent_manager), "delayable", mock_delayable):
            try:
                ent_manager._set_pending_validation_entitlements_async(self.cycle, mock_entitlements)
            except Exception:
                pass

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("entitlement_approval", channels)

    def test_validate_entitlements_async_routes_to_entitlement_approval(self):
        """_validate_entitlements_async must use entitlement_approval channel."""
        ent_manager = self._get_entitlement_manager()
        mock_entitlements = MagicMock()
        mock_entitlements.__len__ = MagicMock(return_value=5)
        mock_entitlements.__getitem__ = MagicMock(return_value=mock_entitlements)

        delayable_calls = []
        original_delayable = type(ent_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(ent_manager), "delayable", mock_delayable):
            try:
                ent_manager._validate_entitlements_async(self.cycle, mock_entitlements, 5)
            except Exception:
                pass

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("entitlement_approval", channels)

    def test_cancel_entitlements_async_routes_to_entitlement_approval(self):
        """_cancel_entitlements_async must use entitlement_approval channel."""
        ent_manager = self._get_entitlement_manager()
        mock_entitlements = MagicMock()
        mock_entitlements.__len__ = MagicMock(return_value=5)
        mock_entitlements.__getitem__ = MagicMock(return_value=mock_entitlements)

        delayable_calls = []
        original_delayable = type(ent_manager).delayable

        def mock_delayable(self_inner, **kwargs):
            delayable_calls.append(kwargs)
            return original_delayable(self_inner, **kwargs)

        with patch.object(type(ent_manager), "delayable", mock_delayable):
            try:
                ent_manager._cancel_entitlements_async(self.cycle, mock_entitlements, 5)
            except Exception:
                pass

        channels = [c.get("channel", "") for c in delayable_calls]
        self.assertIn("entitlement_approval", channels)
