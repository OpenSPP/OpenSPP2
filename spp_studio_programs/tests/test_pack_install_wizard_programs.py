# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The pack-install wizard's program_id and _get_pack_program_id hook."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPackInstallWizardPrograms(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["spp.studio.pack.install.wizard"]
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Pack Lookup Program",
                "target_type": "individual",
            }
        )

    def test_program_id_field_added(self):
        """The companion adds the optional program_id field to the wizard."""
        self.assertIn("program_id", self.Wizard._fields)
        self.assertEqual(self.Wizard._fields["program_id"].comodel_name, "spp.program")

    def test_get_pack_program_id_returns_selected_program(self):
        """_get_pack_program_id returns the selected program id."""
        wizard = self.Wizard.new({"program_id": self.program.id})
        self.assertEqual(wizard._get_pack_program_id(), self.program.id)

    def test_get_pack_program_id_none_when_unset(self):
        """_get_pack_program_id returns None when no program is selected."""
        wizard = self.Wizard.new({})
        self.assertIsNone(wizard._get_pack_program_id())
