# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The individuals form renders ID numbers through the masked widget."""

from lxml import etree

from odoo import Command
from odoo.tests.common import TransactionCase


class TestMaskedIdWiring(TransactionCase):
    def test_individuals_form_masks_id_value(self):
        """Both Identity tabs (individual and group) render reg_ids.value
        with the masked_char widget and the PII reveal gate. get_view also
        validates the inherited arch, so this fails fast if view validation
        rejects the widget attributes."""
        user = self.env["res.users"].create(
            {
                "name": "Registry Viewer",
                "login": "registry_viewer_masked",
                "group_ids": [Command.link(self.env.ref("base.group_user").id)],
            }
        )
        view = self.env.ref("spp_registry.view_individuals_form")
        arch = self.env["res.partner"].with_user(user).get_view(view_id=view.id)["arch"]
        tree = etree.fromstring(arch)

        value_fields = tree.xpath("//field[@name='reg_ids']/list/field[@name='value']")
        self.assertEqual(len(value_fields), 2, "both Identity tabs must be wired")
        for node in value_fields:
            self.assertEqual(node.get("widget"), "masked_char")
            self.assertEqual(node.get("mask_pattern"), "****-****-####")
            self.assertEqual(
                node.get("reveal_group"),
                "spp_data_classification.group_pii_full_access_admin",
            )

    def test_reveal_group_exists(self):
        """Guards against a rename of the PR2 group this module gates on."""
        self.assertTrue(self.env.ref("spp_data_classification.group_pii_full_access_admin"))
