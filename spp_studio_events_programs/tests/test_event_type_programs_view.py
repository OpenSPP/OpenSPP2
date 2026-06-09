# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""This companion re-adds program_ids to the event type form."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEventTypeProgramsView(TransactionCase):
    def test_program_ids_in_form_view(self):
        """The event type form exposes program_ids when installed."""
        EventType = self.env["spp.studio.event.type"]
        # Field is provided by spp_studio_programs (a dependency)
        self.assertIn("program_ids", EventType._fields)
        # ...and this companion injects it back into the form arch
        arch = EventType.get_view(view_type="form")["arch"]
        self.assertIn("program_ids", arch)
