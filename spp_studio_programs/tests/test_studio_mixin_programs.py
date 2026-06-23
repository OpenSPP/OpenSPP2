# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The program_ids scoping field is added to Studio configs by this companion."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStudioMixinPrograms(TransactionCase):
    def test_program_ids_field(self):
        """program_ids many2many is present on Studio configurations."""
        StudioField = self.env["spp.studio.field"]
        self.assertIn("program_ids", StudioField._fields)
        self.assertEqual(StudioField._fields["program_ids"].type, "many2many")
