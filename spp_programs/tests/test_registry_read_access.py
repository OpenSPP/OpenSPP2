# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tier-3 ``group_registry_read`` must cover this module's registrant-form models.

``spp_registry.group_registry_viewer`` (Tier-2) implies ``group_registry_read``
(Tier-3), so any ACL granted only to the viewer tier disappears for a role
scoped to the read tier. ``spp_programs/views/registrant_view.xml`` renders ``cycle_id`` in the
entitlement lists on the registrant form,
so a read-tier role that opens a registrant hits an AccessError unless the
Tier-3 group carries these models too.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged

_MODELS = [
    "spp.cycle",
    "spp.cycle.membership",
]


@tagged("post_install", "-at_install")
class TestRegistryReadAccess(TransactionCase):
    def test_tier3_registry_read_covers_registrant_form_models(self):
        user = self.env["res.users"].create(
            {
                "name": "Tier3 Reader",
                "login": "tier3_reader_spp_programs",
                "email": "tier3_reader_spp_programs@example.com",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("spp_registry.group_registry_read").id),
                ],
            }
        )
        Access = self.env["ir.model.access"].with_user(user)
        missing = sorted(m for m in _MODELS if not Access.check(m, "read", raise_exception=False))
        self.assertFalse(
            missing,
            "Tier-3 group_registry_read cannot read registrant-form models: " + ", ".join(missing),
        )
