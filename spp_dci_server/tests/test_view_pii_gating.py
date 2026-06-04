# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""View-level PII gating for spp.dci.transaction payload tabs."""

from lxml import etree

from odoo.tests import TransactionCase, tagged

GATING_GROUP = "spp_dci.group_dci_admin"


@tagged("post_install", "-at_install")
class TestTransactionPIIGating(TransactionCase):
    def _arch(self, xml_id):
        return etree.fromstring(self.env.ref(xml_id).arch_db)

    def _assert_page_gated(self, arch, name):
        nodes = arch.xpath(f"//page[@name={name!r}]")
        self.assertTrue(nodes, f"page {name!r} not found")
        for node in nodes:
            self.assertIn(
                GATING_GROUP,
                node.get("groups", ""),
                f"page {name!r} must be gated by {GATING_GROUP}",
            )

    def test_form_view_gates_request_payload(self):
        """Raw DCI request envelopes carry PII; only DCI admins should see them."""
        arch = self._arch("spp_dci_server.view_spp_dci_transaction_form")
        self._assert_page_gated(arch, "request")

    def test_form_view_gates_response_payload(self):
        arch = self._arch("spp_dci_server.view_spp_dci_transaction_form")
        self._assert_page_gated(arch, "response")
