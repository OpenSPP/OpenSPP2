from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestEntitlementManager(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure a usable product category exists; Odoo 19 environments may not
        # always provide ``product.product_category_all`` depending on modules.
        try:
            product_category = cls.env.ref("product.product_category_all")
        except ValueError:
            product_category = cls.env["product.category"].create({"name": "All Products [TEST]"})

        def _product_vals(name):
            vals = {
                "name": name,
                "categ_id": product_category.id,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
            }
            if "uom_po_id" in cls.env["product.product"]._fields:
                vals["uom_po_id"] = cls.env.ref("uom.product_uom_unit").id
            elif "purchase_uom_id" in cls.env["product.product"]._fields:
                vals["purchase_uom_id"] = cls.env.ref("uom.product_uom_unit").id
            if "detailed_type" in cls.env["product.product"]._fields:
                vals["detailed_type"] = "product"
            elif "type" in cls.env["product.product"]._fields:
                type_field = cls.env["product.product"]._fields["type"]
                selection_source = (
                    type_field.selection(cls.env["product.product"])
                    if callable(type_field.selection)
                    else type_field.selection
                )
                type_selection = dict(selection_source)
                vals["type"] = "consu" if "consu" in type_selection else next(iter(type_selection))
            return vals

        cls._test_products = cls.env["product.product"].create(
            [_product_vals("Flour [TEST]"), _product_vals("Food [TEST]")]
        )
        country = cls.env.ref("base.iq")
        cls.service_points = cls.env["spp.service.point"].create(
            [
                {
                    "name": "Correct Phone Number",
                    "country_id": country.id,
                    "phone_no": "+9647001234567",
                    "is_disabled": False,
                },
                {
                    "name": "In-correct Phone Number",
                    "country_id": country.id,
                    "phone_no": "+964700123456",
                    "is_disabled": True,
                    "disabled_reason": "Wrong phone number format!",
                },
            ]
        )
        cls.registrants = cls.env["res.partner"].create(
            [
                {
                    "name": "Registrant 1 [TEST]",
                    "is_registrant": True,
                    "is_group": True,
                    "service_point_ids": [(6, 0, cls.service_points.ids)],
                },
                {
                    "name": "Registrant 2 [TEST]",
                    "is_registrant": True,
                    "is_group": True,
                    "service_point_ids": [(6, 0, cls.service_points.ids)],
                },
            ]
        )
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Program Inkind 1 [TEST]",
                "program_membership_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.registrants[0].id,
                            "state": "enrolled",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.registrants[-1].id,
                            "state": "enrolled",
                        },
                    ),
                ],
            }
        )
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Cycle 1 [TEST]",
                "program_id": cls.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        inkind_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement.inkind")], limit=1)
        cls._approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Inkind Entitlement Approval [TEST]",
                "model_id": inkind_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )
        cls._inkind_entitlement_manager = cls.env["spp.program.entitlement.manager.inkind"].create(
            {
                "name": "Entitlement Manager Inkind 1 [TEST]",
                "program_id": cls.program.id,
                "warehouse_id": cls.env.ref("stock.warehouse0").id,
                "approval_definition_id": cls._approval_definition.id,
            }
        )
        # Create the junction record and link it to the program so that
        # entitlements can resolve the approval definition via get_manager()
        entitlement_manager_junction = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"spp.program.entitlement.manager.inkind,{cls._inkind_entitlement_manager.id}",
            }
        )
        cls.program.write({"entitlement_manager_ids": [(4, entitlement_manager_junction.id)]})

    def create_entitlement_inkind(self):
        return self.env["spp.entitlement.inkind"].create(
            {
                "partner_id": self.registrants[0].id,
                "cycle_id": self.cycle.id,
                "product_id": self._test_products[0].id,
                "valid_from": fields.Date.today(),
            }
        )

    def test_01_prepare_entitlements(self):
        with self.assertRaisesRegex(UserError, "no items entered for this"):
            self._inkind_entitlement_manager.prepare_entitlements(self.cycle, self.program.program_membership_ids)
        self._inkind_entitlement_manager.write(
            {
                "entitlement_item_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self._test_products[0].id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self._test_products[-1].id,
                        },
                    ),
                ],
            }
        )
        before_entitlement_inkind = self.env["spp.entitlement.inkind"].search([])
        self.assertFalse(before_entitlement_inkind.ids, "Start without entitlement inkind!")
        self._inkind_entitlement_manager.prepare_entitlements(self.cycle, self.program.program_membership_ids)
        after_entitlement_inkind = self.env["spp.entitlement.inkind"].search([])
        self.assertTrue(bool(after_entitlement_inkind.ids), "Entitlement Inkind should be created!")

    def test_02_set_pending_validation_entitlements(self):
        entitlement = self.create_entitlement_inkind()
        entitlement.state = "draft"
        self._inkind_entitlement_manager.set_pending_validation_entitlements(self.cycle)
        self.assertEqual(
            entitlement.state,
            "pending_validation",
            "Entitlement now should be pending validation!",
        )

    @patch("odoo.fields.Date.today")
    def test_03_validate_entitlements(self, mock_today):
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2023, 5, 23)
        entitlement = self.create_entitlement_inkind()
        # The approval system requires entitlements to be in pending_validation
        # state (approval_state='pending') before they can be approved.
        self._inkind_entitlement_manager.set_pending_validation_entitlements(self.cycle)
        res = self._inkind_entitlement_manager.validate_entitlements(self.cycle)
        self.assertEqual(res["params"]["type"], "success", "Should display success notification!")
        self.assertEqual(entitlement.state, "approved", "Entitlement should now approved!")
        self.assertEqual(
            entitlement.date_approved,
            date(2023, 5, 23),
            "Entitlement approving date should be today!",
        )

    def test_04_cancel_entitlements(self):
        entitlement = self.create_entitlement_inkind()
        self._inkind_entitlement_manager.cancel_entitlements(self.cycle)
        self.assertEqual(entitlement.state, "cancelled", "Entitlement should now cancelled!")

    def test_05_open_entitlements_form(self):
        res = self._inkind_entitlement_manager.open_entitlements_form(self.cycle)
        for key in ["res_model", "type", "domain"]:
            self.assertIn(key, res.keys(), f"Key `{key}` is missing from return action!")
        self.assertEqual(res["res_model"], "spp.entitlement.inkind")
        self.assertEqual(res["type"], "ir.actions.act_window")
        self.assertEqual(res["domain"], [("cycle_id", "=", self.cycle.id)])

    def test_06_open_entitlement_form(self):
        entitlement = self.create_entitlement_inkind()
        res = self._inkind_entitlement_manager.open_entitlement_form(entitlement)
        for key in ["res_model", "type", "target", "res_id", "view_mode"]:
            self.assertIn(key, res.keys(), f"Key `{key}` is missing from return action!")
        self.assertEqual(res["res_model"], "spp.entitlement.inkind")
        self.assertEqual(res["type"], "ir.actions.act_window")
        self.assertEqual(res["target"], "new")
        self.assertEqual(res["res_id"], entitlement.id)
        self.assertEqual(res["view_mode"], "form")
