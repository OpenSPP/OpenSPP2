from datetime import date
from unittest.mock import Mock, patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

from .common import Common


class TestEntitlement(Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = [
            Command.link(cls.env.ref("base.group_user").id),
            Command.link(cls.env.ref("spp_programs.group_programs_manager").id),
        ]
        cls.test_user_1 = cls.env["res.users"].create({
            "name": "test",
            "login": "test",
            "group_ids": group,
            "role_line_ids": [],  # Bypass default roles to test explicit group assignments
        })

        # User without access groups - should NOT have access to entitlement views
        cls.test_user_2 = cls.env["res.users"].create({
            "name": "test2",
            "login": "test2",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            "role_line_ids": [],  # Bypass default roles
        })

    def test_01_generate_code(self):
        self.assertIsNotNone(self.entitlement._generate_code())

    def test_02_get_view(self):
        # Test _get_view on spp.entitlement model (not inkind which has bypass logic)
        cash_entitlement = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
                "initial_amount": 100.0,
                "is_cash_entitlement": True,
            }
        )
        action_1 = cash_entitlement._get_view(view_type="form")
        action_2 = cash_entitlement.with_user(self.test_user_1.id)._get_view(view_type="form")
        action_3 = cash_entitlement.with_user(self.test_user_1.id)._get_view(view_type="search")

        self.assertTrue(all([action_1, action_2, action_3]))

        with self.assertRaisesRegex(ValidationError, "You have no access in the Entitlement List View"):
            cash_entitlement.with_user(self.test_user_2.id)._get_view(view_type="form")

    def test_03_compute_journal_id(self):
        self.entitlement._compute_journal_id()
        self.assertEqual(self.entitlement.journal_id.id, self.program.journal_id.id)

    def test_04_compute_name(self):
        self.entitlement._compute_name()

        self.assertEqual(self.entitlement.name, f"Entitlement: ({self.entitlement.product_id.name})")

    @patch("odoo.fields.Date.today")
    def test_05_gc_mark_expired_entitlement(self, mocked_today):
        mocked_today.__name__ = "today_mock"
        mocked_today.return_value = date(2023, 5, 20)
        entitlement_to_expired = self.env["spp.entitlement"].create(
            [
                {
                    "partner_id": self.registrant.id,
                    "initial_amount": 1.0,
                    "cycle_id": self.cycle.id,
                    "state": "approved",
                    "valid_until": fields.Date.add(fields.Date.today(), days=-1),
                },
                {
                    "partner_id": self.registrant.id,
                    "initial_amount": 1.0,
                    "cycle_id": self.cycle.id,
                    "state": "approved",
                    "valid_until": fields.Date.add(fields.Date.today(), days=-1),
                },
                {
                    "partner_id": self.registrant.id,
                    "initial_amount": 1.0,
                    "cycle_id": self.cycle.id,
                    "state": "approved",
                    "valid_until": fields.Date.add(fields.Date.today(), days=-1),
                },
            ]
        )
        entitlement_not_to_expired = self.env["spp.entitlement"].create(
            [
                {
                    "partner_id": self.registrant.id,
                    "initial_amount": 1.0,
                    "cycle_id": self.cycle.id,
                    "state": "approved",
                    "valid_until": fields.Date.add(fields.Date.today(), days=1),
                },
                {
                    "partner_id": self.registrant.id,
                    "initial_amount": 1.0,
                    "cycle_id": self.cycle.id,
                    "state": "approved",
                    "valid_until": fields.Date.add(fields.Date.today(), days=1),
                },
                {
                    "partner_id": self.registrant.id,
                    "initial_amount": 1.0,
                    "cycle_id": self.cycle.id,
                    "state": "approved",
                    "valid_until": fields.Date.add(fields.Date.today(), days=1),
                },
            ]
        )
        self.entitlement._gc_mark_expired_entitlement()
        for rec in entitlement_to_expired:
            self.assertEqual(
                rec.state,
                "expired",
                "To expired entitlement should be expired after garbage collector run!",
            )
        for rec in entitlement_not_to_expired:
            self.assertNotEqual(
                rec.state,
                "expired",
                "Not to expired entitlement should not be expired!",
            )

    @mute_logger("odoo.models.unlink")
    def test_06_unlink(self):
        self.entitlement.state = "pending_validation"

        with self.assertRaisesRegex(ValidationError, "Only draft entitlements are allowed to be deleted"):
            self.entitlement.unlink()

        self.entitlement.state = "draft"
        action = self.entitlement.unlink()
        self.assertIsNotNone(action)

    @patch("odoo.addons.spp_programs.models.programs.SPPProgram.get_manager")
    def test_07_approve_entitlement(self, mocker):
        mocker.__name__ = "mocker__get_manager"

        manager_mock = Mock()
        manager_mock.approve_entitlements.return_value = (1, "Error Message")

        mocker.return_value = manager_mock
        action = self.entitlement.approve_entitlement()

        self.assertEqual(
            [
                action.get("type"),
                action.get("tag"),
                action["params"].get("type"),
                action["params"].get("message"),
            ],
            ["ir.actions.client", "display_notification", "danger", "Error Message"],
        )

    @patch("odoo.addons.spp_programs.models.programs.SPPProgram.get_manager")
    def test_08_open_entitlement_form(self, mocker):
        mocker.__name__ = "mocker__get_manager"

        manager_mock = Mock()
        manager_mock.open_entitlement_form.return_value = True

        mocker.return_value = manager_mock

        self.assertTrue(self.entitlement.open_entitlement_form())

    def test_09_prepare_procurement_values(self):
        vals = self.entitlement._prepare_procurement_values()

        self.assertEqual(
            [vals.get("date_planned"), vals.get("date_deadline")],
            [self.cycle.start_date, self.cycle.end_date],
        )

    def test_10_get_qty_procurement(self):
        # Fallback category in case the standard one is not present (odoo 19 minimal install)
        try:
            categ_id = self.env.ref("product.product_category_all").id
        except ValueError:
            categ_id = self.env["product.category"].create({"name": "All Products"}).id

        product_vals = {
            "name": "Flour [TEST]",
            "categ_id": categ_id,
            "uom_id": self.env.ref("uom.product_uom_unit").id,
        }
        if "uom_po_id" in self.env["product.product"]._fields:
            product_vals["uom_po_id"] = self.env.ref("uom.product_uom_unit").id
        elif "purchase_uom_id" in self.env["product.product"]._fields:
            product_vals["purchase_uom_id"] = self.env.ref("uom.product_uom_unit").id
        # Use the field available in this Odoo version
        if "detailed_type" in self.env["product.product"]._fields:
            product_vals["detailed_type"] = "product"
        elif "type" in self.env["product.product"]._fields:
            type_field = self.env["product.product"]._fields["type"]
            selection_source = (
                type_field.selection(self.env["product.product"])
                if callable(type_field.selection)
                else type_field.selection
            )
            type_selection = dict(selection_source)
            # Odoo 19 renamed storable products to "consu" (Goods); fall back to first option if missing
            product_vals["type"] = "consu" if "consu" in type_selection else next(iter(type_selection))

        self.entitlement.product_id = self.env["product.product"].create(product_vals)
        self.entitlement.uom_id = self.env.ref("uom.product_uom_unit")
        self.assertEqual(
            self.entitlement._get_qty_procurement(),
            0.0,
            "Procurement Quantity should be 0 since no move in or out!",
        )
        self.env["stock.move"].create(
            {
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.env.ref("stock.stock_location_stock").id,
                "to_refund": True,
                "description_picking": "Test Move In - Flour [TEST]",
                "product_id": self.entitlement.product_id.id,
                "date": fields.Date.today(),
                "product_uom": self.env.ref("uom.product_uom_unit").id,
                "product_uom_qty": 1.0,
                "entitlement_id": self.entitlement.id,
            }
        )
        self.assertEqual(
            self.entitlement._get_qty_procurement(),
            -1.0,
            "Procurement Quantity should be -1 since there is a refund move in!",
        )
        self.env["stock.move"].create(
            {
                "location_id": self.env.ref("stock.stock_location_stock").id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "to_refund": True,
                "description_picking": "Test Move Out - Flour [TEST]",
                "product_id": self.entitlement.product_id.id,
                "date": fields.Date.today(),
                "product_uom": self.env.ref("uom.product_uom_unit").id,
                "product_uom_qty": 2.0,
                "entitlement_id": self.entitlement.id,
            }
        )
        self.assertEqual(
            self.entitlement._get_qty_procurement(),
            1.0,
            "Procurement Quantity should be 1 since there is a refund move out!",
        )

    def test_11_prepare_procurement_group_vals(self):
        vals = self.entitlement._prepare_procurement_group_vals()
        self.assertEqual(vals["name"], "Test Cycle", "Name should be cycle name!")
        self.assertEqual(
            vals["cycle_id"],
            self.entitlement.cycle_id.id,
            "Cycle should be entitlement cycle!",
        )

    def test_12_approve_entitlement(self):
        """Test that approve_entitlement raises error when no approval definition is configured."""
        entitlement_id = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "initial_amount": 1.0,
                "cycle_id": self.cycle.id,
                "state": "approved",
                "valid_until": fields.Date.add(fields.Date.today(), days=1),
            }
        )
        # Without an approval definition configured, approve should fail
        with self.assertRaisesRegex(UserError, "No approval definition configured"):
            entitlement_id.approve_entitlement()

    def test_13_reject_entitlement_wizard(self):
        """Test that `reject_entitlement` returns the correct wizard action."""
        entitlement_id = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "initial_amount": 1.0,
                "cycle_id": self.cycle.id,
                "state": "draft",
                "valid_until": fields.Date.add(fields.Date.today(), days=1),
            }
        )
        self.entitlement = entitlement_id
        action = self.entitlement.reject_entitlement()
        self.assertEqual(action["res_model"], "spp.reject.entitlement.wizard")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")
        self.assertIn("to_state", action["context"])
        self.assertEqual(action["context"]["to_state"], "reject")

    def test_14_internal_reject_entitlement(self):
        """Test the internal `_reject_entitlement` method."""
        # Test rejection from a valid state ('draft')
        entitlement_id = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "initial_amount": 1.0,
                "cycle_id": self.cycle.id,
                "state": "draft",
                "valid_until": fields.Date.add(fields.Date.today(), days=1),
            }
        )
        self.entitlement = entitlement_id
        self.entitlement.state = "draft"
        rejection_reason = "Invalid data provided."

        with patch("odoo.fields.Date.today", return_value=date(2024, 1, 1)):
            action = self.entitlement._reject_entitlement(to_state="reject", reject_reason=rejection_reason)

        self.assertEqual(self.entitlement.state, "reject")
        self.assertEqual(self.entitlement.rejected_reason, rejection_reason)
        self.assertEqual(self.entitlement.date_rejected, date(2024, 1, 1))

        # Check notification
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "danger")
        self.assertEqual(action["params"]["message"], "Entitlement Rejected")

        # Test rejection from an invalid state ('approved')
        self.entitlement.state = "approved"
        self.entitlement._reject_entitlement(to_state="reject", reject_reason="Should not work")
        self.assertEqual(self.entitlement.state, "approved", "Entitlement in 'approved' state should not be rejected.")

    def test_15_reset_to_pending_wizard(self):
        """Test that `reset_to_pending` returns the correct wizard action."""
        entitlement_id = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "initial_amount": 1.0,
                "cycle_id": self.cycle.id,
                "state": "draft",
                "valid_until": fields.Date.add(fields.Date.today(), days=1),
            }
        )
        self.entitlement = entitlement_id
        action = self.entitlement.reset_to_pending()
        self.assertEqual(action["res_model"], "spp.reset.pending.entitlement.wizard")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")

    def test_16_internal_reset_to_pending(self):
        """Test the internal `_reset_to_pending` method."""
        entitlement_id = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "initial_amount": 1.0,
                "cycle_id": self.cycle.id,
                "state": "draft",
                "valid_until": fields.Date.add(fields.Date.today(), days=1),
            }
        )
        self.entitlement = entitlement_id
        self.entitlement.state = "reject"
        action = self.entitlement._reset_to_pending()

        self.assertEqual(self.entitlement.state, "pending_validation")

        # Check notification
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(action["params"]["message"], "Entitlement Reset to Pending")
