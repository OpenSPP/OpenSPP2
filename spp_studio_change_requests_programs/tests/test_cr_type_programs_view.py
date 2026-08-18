# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""This companion re-adds program_ids to the change request type form."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrTypeProgramsView(TransactionCase):
    def test_program_ids_in_form_view(self):
        """The change request type form exposes program_ids when installed."""
        CrType = self.env["spp.studio.change.request.type"]
        # Field is provided by spp_studio_programs (a dependency)
        self.assertIn("program_ids", CrType._fields)
        # ...and this companion injects it back into the form arch
        arch = CrType.get_view(view_type="form")["arch"]
        self.assertIn("program_ids", arch)
