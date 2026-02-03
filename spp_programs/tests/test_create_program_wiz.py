import uuid

from odoo import Command
from odoo.tests import TransactionCase


class TestCreateProgramWiz(TransactionCase):
    def setUp(self):
        super().setUp()
        self.areas = self.env["spp.area"].create(
            [
                {"draft_name": "Area 1 [TEST]"},
                {"draft_name": "Area 2 [TEST]"},
                {"draft_name": "Area 3 [TEST]"},
            ]
        )
        # Create a test product for in-kind entitlements
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product [TEST]",
                "type": "consu",
            }
        )
        self._program_create_wiz = self.env["spp.program.create.wizard"].create(
            {
                "name": f"Program {uuid.uuid4().hex[:8]} [TEST]",
                "rrule_type": "monthly",
                "eligibility_domain": "[]",
                "cycle_duration": 1,
                "currency_id": self.env.company.currency_id.id,
                "admin_area_ids": [Command.set(self.areas.ids)],
                "entitlement_type": "inkind",
                "entitlement_item_ids": [Command.create({"product_id": self.product.id, "quantity": 1})],
            }
        )

        self.program = self._program_create_wiz.create_program()
        # self.cycle_manager_default = (
        #     self._program_create_wiz.create_cycle_manager_default(self.program.id)
        # )

    def test_01_on_admin_area_ids_change(self):
        self.assertEqual(
            self._program_create_wiz.eligibility_domain,
            "[]",
            "Starting without eligibility domain!",
        )
        self._program_create_wiz.on_admin_area_ids_change()
        self.assertEqual(
            self._program_create_wiz.eligibility_domain,
            f"[('area_id', 'in', {tuple(self.areas.ids)})]",
            "Eligibility domain should be added!",
        )

    def test_02_create_program(self):
        # Create a new wizard with a fresh unique name for this test
        new_wiz = self.env["spp.program.create.wizard"].create(
            {
                "name": f"Program {uuid.uuid4().hex[:8]} [TEST]",
                "rrule_type": "monthly",
                "eligibility_domain": "[]",
                "cycle_duration": 1,
                "currency_id": self.env.company.currency_id.id,
                "admin_area_ids": [Command.set(self.areas.ids)],
                "entitlement_type": "inkind",
                "entitlement_item_ids": [Command.create({"product_id": self.product.id, "quantity": 1})],
                "import_beneficiaries": "yes",
            }
        )
        res = new_wiz.create_program()
        self.assertEqual(type(res), dict, "Action should be in json format!")
        for key in ("type", "res_model", "res_id"):
            self.assertIn(key, res.keys(), f"Key `{key}` is missing!")
        self.assertEqual(
            res["type"],
            "ir.actions.act_window",
            "Action for program should be returned!",
        )
        self.assertEqual(res["res_model"], "spp.program", "Action for program should be return!")
        self.assertTrue(res["res_id"], "New record for program should be existed!")

    def test_03_get_eligibility_manager(self):
        self._program_create_wiz.eligibility_type = "default_eligibility"
        res = self._program_create_wiz._get_eligibility_manager(self.program["res_id"])

        self.assertIn("eligibility_managers", res)

    # def test_04_create_cycle_manager(self):
    #     cycle_manager = self._program_create_wiz.create_cycle_manager(
    #         self.program.id, self.cycle_manager_default
    #     )

    #     self.assertEqual(cycle_manager._name, "spp.cycle.manager")
    #     self.assertIsNotNone(cycle_manager)

    # def test_05_create_cycle_manager_default(self):
    #     cycle_manager_default = self._program_create_wiz.create_cycle_manager_default(
    #         self.program.id
    #     )

    #     self.assertEqual(cycle_manager_default._name, "spp.cycle.manager.default")
    #     self.assertIsNotNone(cycle_manager_default)

    def test_06_create_program(self):
        # Create a new wizard with a fresh unique name for this test
        new_wiz = self.env["spp.program.create.wizard"].create(
            {
                "name": f"Program {uuid.uuid4().hex[:8]} [TEST]",
                "rrule_type": "monthly",
                "eligibility_domain": "[]",
                "cycle_duration": 1,
                "currency_id": self.env.company.currency_id.id,
                "admin_area_ids": [Command.set(self.areas.ids)],
                "entitlement_type": "inkind",
                "entitlement_item_ids": [Command.create({"product_id": self.product.id, "quantity": 1})],
            }
        )
        program = new_wiz.create_program()

        self.assertEqual(program["res_model"], "spp.program")
        self.assertIsNotNone(program)
