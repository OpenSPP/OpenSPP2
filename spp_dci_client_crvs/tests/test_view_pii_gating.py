# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""View-level PII gating for spp.dci.crvs.event."""

from lxml import etree

from odoo.tests import TransactionCase, tagged

GATING_GROUP = "spp_dci.group_dci_admin"


@tagged("post_install", "-at_install")
class TestCRVSEventPIIGating(TransactionCase):
    def _arch(self, xml_id):
        return etree.fromstring(self.env.ref(xml_id).arch_db)

    def _assert_field_gated(self, arch, name):
        nodes = arch.xpath(f"//field[@name={name!r}]")
        self.assertTrue(nodes, f"field {name!r} not found")
        for node in nodes:
            self.assertIn(
                GATING_GROUP,
                node.get("groups", ""),
                f"field {name!r} must be gated by {GATING_GROUP}",
            )

    def _assert_page_gated(self, arch, name):
        nodes = arch.xpath(f"//page[@name={name!r}]")
        self.assertTrue(nodes, f"page {name!r} not found")
        for node in nodes:
            self.assertIn(
                GATING_GROUP,
                node.get("groups", ""),
                f"page {name!r} must be gated by {GATING_GROUP}",
            )

    def test_list_view_gates_person_id(self):
        arch = self._arch("spp_dci_client_crvs.view_spp_dci_crvs_event_tree")
        self._assert_field_gated(arch, "person_id")

    def test_list_view_gates_identifier_value(self):
        arch = self._arch("spp_dci_client_crvs.view_spp_dci_crvs_event_tree")
        self._assert_field_gated(arch, "identifier_value")

    def test_form_view_gates_person_id(self):
        arch = self._arch("spp_dci_client_crvs.view_spp_dci_crvs_event_form")
        self._assert_field_gated(arch, "person_id")

    def test_form_view_gates_identifier_value(self):
        arch = self._arch("spp_dci_client_crvs.view_spp_dci_crvs_event_form")
        self._assert_field_gated(arch, "identifier_value")

    def test_form_view_gates_raw_data_page(self):
        arch = self._arch("spp_dci_client_crvs.view_spp_dci_crvs_event_form")
        self._assert_page_gated(arch, "raw_data")
