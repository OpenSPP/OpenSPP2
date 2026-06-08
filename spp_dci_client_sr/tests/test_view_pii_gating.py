# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""View-level PII gating for spp.dci.sr.record.

These tests pin the ``groups="spp_dci.group_dci_admin"`` attribute on
PII-bearing fields and pages. View gating is defence-in-depth on top of
model ACL; if it silently drops, sensitive cached SR data becomes visible
to anyone with read access to the model.
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged

GATING_GROUP = "spp_dci.group_dci_admin"


@tagged("post_install", "-at_install")
class TestSRRecordPIIGating(TransactionCase):
    def _arch(self, xml_id):
        view = self.env.ref(xml_id)
        return etree.fromstring(view.arch_db)

    def _assert_field_gated(self, arch, name):
        nodes = arch.xpath(f"//field[@name={name!r}]")
        self.assertTrue(nodes, f"field {name!r} not found in view")
        for node in nodes:
            self.assertIn(
                GATING_GROUP,
                node.get("groups", ""),
                f"field {name!r} must be gated by {GATING_GROUP}",
            )

    def _assert_node_gated(self, arch, tag, name):
        nodes = arch.xpath(f"//{tag}[@name={name!r}]")
        self.assertTrue(nodes, f"{tag} {name!r} not found in view")
        for node in nodes:
            self.assertIn(
                GATING_GROUP,
                node.get("groups", ""),
                f"{tag} {name!r} must be gated by {GATING_GROUP}",
            )

    def test_list_view_gates_sr_name(self):
        arch = self._arch("spp_dci_client_sr.view_sr_record_tree")
        self._assert_field_gated(arch, "sr_name")

    def test_form_view_gates_identifier_value(self):
        arch = self._arch("spp_dci_client_sr.view_sr_record_form")
        self._assert_field_gated(arch, "identifier_value")

    def test_form_view_gates_demographics_group(self):
        arch = self._arch("spp_dci_client_sr.view_sr_record_form")
        self._assert_node_gated(arch, "group", "demographics")

    def test_form_view_gates_raw_data_page(self):
        arch = self._arch("spp_dci_client_sr.view_sr_record_form")
        self._assert_node_gated(arch, "page", "raw_data")

    def test_form_view_gates_enrolled_programs_field(self):
        arch = self._arch("spp_dci_client_sr.view_sr_record_form")
        self._assert_field_gated(arch, "enrolled_programs")
