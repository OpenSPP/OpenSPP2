"""End-to-end test: bridge dispatcher routes vendor=openg2p sources
(registry_type=SR) to the OpenG2P Social service, and the result
populates the dispatcher's return dict for attribute-path extraction.
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_cel_dci_bridge.exceptions import DCIConfigurationError


def make_sr_response_for_search_text(search_text_to_records):
    """Build a stateful client.search mock: response depends on the
    ``search_text`` value passed in ``query_value``, so a single mock can
    distinguish between matching and non-matching partners.
    """

    def _search(**kwargs):
        # OpenG2PSocialService passes the partner identifier value as
        # query_value (the search_text). No type prefix; the client
        # wraps it into the expression query shape.
        search_text = kwargs.get("query_value", "")
        records = search_text_to_records.get(search_text, [])
        if not records:
            return {"message": {"search_response": []}}
        return {
            "message": {
                "search_response": [
                    {
                        "reference_id": "r1",
                        "timestamp": "2026-05-14T00:00:00Z",
                        "status": "succ",
                        "data": {
                            "reg_type": "Individual",
                            "reg_record_type": "Individual",
                            "reg_records": records,
                        },
                    }
                ]
            }
        }

    return _search


@tagged("post_install", "-at_install")
class TestDispatcherRoutesOpenG2P(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Reuse the UIN vocab code seeded by the preset itself
        # (data/openg2p_id_types.xml). Creating a fresh UIN here would hit
        # the spp.vocabulary.code uniqueness constraint.
        cls.id_type_uin = cls.env.ref("spp_dci_openg2p.id_type_uin")
        cls.partner_in_sr = cls.env["res.partner"].create(
            {"name": "SR Partner", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_in_sr.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "IND-NSR-0001",
            }
        )
        cls.partner_not_in_sr = cls.env["res.partner"].create(
            {"name": "Unknown Partner", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_not_in_sr.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "IND-UNKNOWN",
            }
        )

        # The OpenG2P preset auto-creates this data source + provider +
        # variable. Confirm by reading via ref.
        cls.data_source = cls.env.ref("spp_dci_openg2p.openg2p_dr_source")
        cls.variable = cls.env.ref("spp_studio.var_has_disability")

    def test_data_source_has_vendor_openg2p_and_registry_type_sr(self):
        self.assertEqual(self.data_source.vendor, "openg2p")
        self.assertEqual(self.data_source.registry_type, "SR")

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_openg2p_handler_extracts_attribute_path_from_reg_record(self, mock_client_class):
        """Partner with a matching OpenG2P record returns the value at
        ``dci_attribute_path`` from the raw reg_record (no synthesis)."""
        mock_client = MagicMock()
        mock_client.search.side_effect = make_sr_response_for_search_text(
            {"IND-NSR-0001": [{"has_disability": True}]}
        )
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_in_sr.id], "current"
        )

        self.assertEqual(result, {self.partner_in_sr.id: True})

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_openg2p_handler_records_not_found_for_unknown_partner(self, mock_client_class):
        """REG-ERR-001 / empty search_response → no entry in result dict,
        audit row says ``not_found``."""
        mock_client = MagicMock()
        mock_client.search.side_effect = make_sr_response_for_search_text({})
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_not_in_sr.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search(
            [("variable_name", "=", "has_disability"), ("subject_id", "=", self.partner_not_in_sr.id)]
        )
        self.assertEqual(audits.result, "not_found")

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_clearing_vendor_falls_back_to_bridge_sr_stub(self, mock_client_class):
        """When vendor is cleared, the bridge's not-implemented SR handler
        runs and raises DCIConfigurationError — ADR-023 Critical #2's
        silent-failure guard. The OpenG2P client must not be invoked.

        This is the migration test: setting vendor on a data source is
        what opts into the vendor-specific adapter; clearing it returns
        the variable to the bridge's default behaviour (which, for SR,
        is "no handler installed").
        """
        self.data_source.vendor = False

        with self.assertRaises(DCIConfigurationError):
            self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
                self.variable, [self.partner_in_sr.id], "current"
            )

        mock_client_class.assert_not_called()
