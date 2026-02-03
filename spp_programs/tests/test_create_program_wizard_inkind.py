from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestCreateProgramWiz(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            categ_id = cls.env.ref("product.product_category_all").id
        except ValueError:
            categ_id = cls.env["product.category"].create({"name": "All Products"}).id

        def _product_vals(name):
            vals = {
                "name": name,
                "categ_id": categ_id,
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
        cls._program_create_wiz = cls.env["spp.program.create.wizard"].create(
            {
                "name": "Program 1 [TEST]",
                "rrule_type": "monthly",
                "eligibility_domain": "[]",
                "cycle_duration": 1,
                "currency_id": cls.env.company.currency_id.id,
                "entitlement_type": "inkind",
            }
        )
        cls.journal_id = cls._program_create_wiz.create_journal(
            cls._program_create_wiz.name, cls._program_create_wiz.currency_id.id
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": cls._program_create_wiz.name,
                "journal_id": cls.journal_id,
                "target_type": cls._program_create_wiz.target_type,
            }
        )

    def _update_program_create_wiz(self):
        self._program_create_wiz.write(
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

    def test_01_check_required_fields(self):
        with self.assertRaisesRegex(
            UserError,
            "Items are required in the In-kind entitlement manager",
            msg="Missing entitlement items",
        ):
            self._program_create_wiz._check_required_fields()
        self._update_program_create_wiz()
        self._program_create_wiz.write(
            {
                "manage_inventory": True,
                "warehouse_id": None,
            }
        )
        with self.assertRaisesRegex(
            UserError,
            "^For inventory management, the warehouse is required.*$",
            msg="Missing warehouse when managing inventory",
        ):
            self._program_create_wiz._check_required_fields()

    def test_02_get_entitlement_manager(self):
        self._update_program_create_wiz()
        self.assertFalse(
            bool(self.env["spp.program.entitlement.manager.inkind"].search([])),
            "Start without entitlement manager",
        )
        self.assertFalse(
            bool(self.env["spp.program.entitlement.manager"].search([])),
            "Start without entitlement manager",
        )
        res = self._program_create_wiz._get_entitlement_manager(self.program.id)
        self.assertTrue(
            bool(self.env["spp.program.entitlement.manager.inkind"].search([])),
            "Finish with entitlement manager",
        )
        self.assertTrue(
            bool(self.env["spp.program.entitlement.manager"].search([])),
            "Finish with entitlement manager",
        )
        self.assertEqual(type(res), dict, "Correct return value")
        self.assertIn("entitlement_manager_ids", res.keys(), "Correct return value")
        self.assertEqual(type(res["entitlement_manager_ids"]), list, "Correct return value")
        self.assertEqual(len(res["entitlement_manager_ids"]), 1, "Correct return value")
        self.assertEqual(type(res["entitlement_manager_ids"][0]), tuple, "Correct return value")
        self.assertEqual(len(res["entitlement_manager_ids"][0]), 2, "Correct return value")
        self.assertEqual(res["entitlement_manager_ids"][0][0], 4, "Correct return value")
