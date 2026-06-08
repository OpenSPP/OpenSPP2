# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI Administrator security group."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDCIAdminGroup(TransactionCase):
    """The DCI admin group is consumed by every spp_dci_* view that gates
    raw payloads or PII. If the xml_id disappears or the group is replaced
    silently, those view gates degrade to "visible to everyone" - this
    pinning test catches that.
    """

    def test_dci_admin_group_exists(self):
        group = self.env.ref("spp_dci.group_dci_admin", raise_if_not_found=False)
        self.assertTrue(group, "spp_dci.group_dci_admin must exist")
        self.assertEqual(group.name, "DCI Administrator")

    def test_dci_admin_group_implies_system(self):
        """Members must already be system administrators."""
        group = self.env.ref("spp_dci.group_dci_admin")
        system = self.env.ref("base.group_system")
        self.assertIn(system, group.implied_ids)
