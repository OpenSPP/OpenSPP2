# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Per-role access matrix for DRIMS (OP#974).

Verifies the role permission sweep end to end: group inheritance re-wire
(Phase 1), stock access for dispatch viewing (Phase 2), per-role model CRUD,
and record-rule scoping with fallbacks (Phase 3).
"""

from datetime import date, timedelta

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user

from .common import DrimsTestCommon


class TestDrimsAccessMatrix(DrimsTestCommon):
    """Role-by-role access checks for the core DRIMS models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)
        cls.alert_type = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:alert-types"), ("code", "=", "low_stock")],
            limit=1,
        )

        def role_user(login, group):
            return new_test_user(cls.env, login=login, groups=f"base.group_user,spp_drims.{group}")

        cls.u_viewer = role_user("drims_viewer_t", "group_drims_viewer")
        cls.u_officer = role_user("drims_officer_t", "group_drims_officer")
        cls.u_warehouse = role_user("drims_warehouse_t", "group_drims_warehouse_worker")
        cls.u_field = role_user("drims_field_t", "group_drims_field_officer")
        cls.u_coord = role_user("drims_coord_t", "group_drims_coordinator_supervisor")
        cls.u_approver = role_user("drims_approver_t", "group_drims_approver")
        cls.u_manager = role_user("drims_manager_t", "group_drims_manager")
        cls.all_users = [
            cls.u_viewer,
            cls.u_officer,
            cls.u_warehouse,
            cls.u_field,
            cls.u_coord,
            cls.u_approver,
            cls.u_manager,
        ]

        # A second warehouse + area for "out of scope" records.
        # stock.warehouse.code is capped at 5 chars; keep it distinct from the
        # base warehouse's code so the two do not collide after truncation.
        cls.warehouse2 = cls.env["stock.warehouse"].create(
            {"name": "Other Warehouse", "code": "OWH2", "is_drims_warehouse": True}
        )
        cls.area2 = cls.env["spp.area"].create({"name": "Other District", "draft_name": "Other District"})

        # Scope assignments so record-rule domains have something to match.
        cls.u_field.drims_warehouse_ids = cls.warehouse
        cls.u_warehouse.drims_warehouse_ids = cls.warehouse
        cls.u_coord.drims_area_ids = cls.area

        # Baseline records (as admin).
        cls.Donation = cls.env["spp.drims.donation"]
        cls.Request = cls.env["spp.drims.request"]
        cls.Alert = cls.env["spp.drims.alert"]

    def _donation_vals(self, warehouse=None):
        return {
            "incident_id": self.incident.id,
            "warehouse_id": (warehouse or self.warehouse).id,
            "donor_name": "Test Donor",
        }

    def _request_vals(self, area=None):
        return {
            "incident_id": self.incident.id,
            "destination_area_id": (area or self.area).id,
            "date_needed": self.future_date,
            "priority_id": self.priority_routine.id,
        }

    # ──────────────────────────────────────────────────────────────────
    # Phase 1 + 2 — group inheritance
    # ──────────────────────────────────────────────────────────────────
    def test_all_roles_can_access_stock_for_dispatches(self):
        """Every DRIMS role inherits stock_user so the Dispatches UI is visible."""
        for user in self.all_users:
            self.assertTrue(
                user.has_group("stock.group_stock_user"),
                f"{user.login} should have stock access for dispatch viewing",
            )

    def test_specialized_roles_do_not_inherit_create_group(self):
        """Field Officer / Coordinator / Warehouse inherit Viewer (read), not the
        broad Officer->create chain — they only get create where granted."""
        for user in (self.u_field, self.u_coord, self.u_warehouse):
            self.assertTrue(user.has_group("spp_drims.group_drims_read"))
            self.assertFalse(
                user.has_group("spp_drims.group_drims_create"),
                f"{user.login} must not inherit the blanket DRIMS create group",
            )

    # ──────────────────────────────────────────────────────────────────
    # Phase 1 — per-role model CRUD
    # ──────────────────────────────────────────────────────────────────
    def test_donation_create_gated(self):
        """Officer can create donations; Field Officer and Coordinator cannot."""
        self.Donation.with_user(self.u_officer).create(self._donation_vals())
        for user in (self.u_field, self.u_coord):
            with self.assertRaises(AccessError, msg=f"{user.login} must not create donations"):
                self.Donation.with_user(user).create(self._donation_vals())

    def test_request_create_gated(self):
        """Officer/Field Officer/Coordinator can create requests; Warehouse cannot."""
        for user in (self.u_officer, self.u_field, self.u_coord):
            self.Request.with_user(user).create(self._request_vals())
        with self.assertRaises(AccessError, msg="Warehouse Staff must not create requests"):
            self.Request.with_user(self.u_warehouse).create(self._request_vals())

    def test_alert_write_gated(self):
        """Officer/Warehouse/Field Officer can write alerts (acknowledge); Coordinator
        and Viewer are read-only."""
        if not self.alert_type:
            self.skipTest("alert type vocabulary code not present")
        alert = self.Alert.create(
            {
                "alert_type_id": self.alert_type.id,
                "title": "Scope Alert",
                "priority": "medium",
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "product_id": self.product.id,
            }
        )
        for user in (self.u_officer, self.u_warehouse, self.u_field):
            alert.with_user(user).write({"title": f"touched by {user.login}"})
        for user in (self.u_coord, self.u_viewer):
            with self.assertRaises(AccessError, msg=f"{user.login} must not write alerts"):
                alert.with_user(user).write({"title": "nope"})

    def test_only_manager_can_delete(self):
        """Deletion is Manager-only; an Officer cannot unlink a donation."""
        d1 = self.Donation.create(self._donation_vals())
        with self.assertRaises(AccessError):
            d1.with_user(self.u_officer).unlink()
        d2 = self.Donation.create(self._donation_vals())
        d2.with_user(self.u_manager).unlink()
        self.assertFalse(d2.exists())

    # ──────────────────────────────────────────────────────────────────
    # Phase 3 — record-rule scoping
    # ──────────────────────────────────────────────────────────────────
    def test_field_officer_donation_scope(self):
        """Field Officer sees donations for their warehouse, not others'."""
        in_scope = self.Donation.create(self._donation_vals(self.warehouse))
        out_scope = self.Donation.create(self._donation_vals(self.warehouse2))
        visible = self.Donation.with_user(self.u_field).search([])
        self.assertIn(in_scope, visible)
        self.assertNotIn(out_scope, visible)

    def test_coordinator_request_scope_with_own_fallback(self):
        """Coordinator sees requests in their area AND their own (own-record
        fallback added in Phase 3), but not unrelated requests."""
        in_area = self.Request.create(self._request_vals(self.area))
        other_area = self.Request.create(self._request_vals(self.area2))
        own_outside = self.Request.with_user(self.u_coord).create(self._request_vals(self.area2))
        visible = self.Request.with_user(self.u_coord).search([])
        self.assertIn(in_area, visible, "should see requests in assigned area")
        self.assertIn(own_outside, visible, "should see own requests even outside assigned area")
        self.assertNotIn(other_area, visible, "should not see unrelated out-of-area requests")
