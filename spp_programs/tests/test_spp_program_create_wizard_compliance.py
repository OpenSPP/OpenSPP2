from odoo.exceptions import ValidationError

from . import common_compliance as common


class TestSppProgramCreateWiz(common.Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_create_program_without_compliance_manager(self):
        wizard = self.program_create_wizard({})
        wizard._check_compliance_manager_info()
        action = wizard.create_program()
        program = self.env["spp.program"].browse(action["params"]["program_id"])
        self.assertFalse(
            bool(program.compliance_manager_ids),
            "Should not create compliance manager for new program!",
        )

    def test_02_create_program_errors(self):
        wizard = self.program_create_wizard(
            {
                "enable_compliance_verification": True,
                "compliance_type": None,
            }
        )
        error = "^Not enough information for creating compliance manager!$"
        with self.assertRaisesRegex(ValidationError, error):
            wizard.create_program()

    def test_03_create_program_default_compliance_manager(self):
        wizard = self.program_create_wizard(
            {
                "enable_compliance_verification": True,
                "compliance_type": "spp.compliance.manager.default",
                "compliance_cel_expression": "r.id > 2",
            }
        )
        action = wizard.create_program()
        program = self.env["spp.program"].browse(action["params"]["program_id"])
        self.assertTrue(
            bool(program.compliance_manager_ids),
            "Should create compliance manager for new program!",
        )
        manager = program.compliance_manager_ids[0].manager_ref_id
        self.assertEqual(
            manager._name,
            "spp.compliance.manager.default",
            "Manager should be correct!",
        )
        self.assertEqual(manager.compliance_cel_expression, "r.id > 2", "Manager should be correct!")
        self.assertEqual(manager.program_id, program, "Manager should be correct!")
