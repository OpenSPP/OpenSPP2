# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""spp.program.membership gains source tracking via this companion (OP#1084)."""

import uuid

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProgramMembershipSourceTracking(TransactionCase):
    def test_program_membership_has_source_tracking(self):
        """spp.program.membership inherits the source-tracking mixin."""
        program = self.env["spp.program"].create(
            {"name": f"Test Program {uuid.uuid4().hex[:8]}", "target_type": "individual"}
        )
        partner = self.env["res.partner"].create({"name": "ST Partner", "is_registrant": True})
        membership = (
            self.env["spp.program.membership"]
            .with_context(source_system="enrollment-api")
            .create({"partner_id": partner.id, "program_id": program.id})
        )
        self.assertEqual(membership.source_system, "enrollment-api")
