"""End-to-end test: bridge dispatcher routes vendor=openg2p sources to
the OpenG2P FR service, and the result populates spp.data.value such
that a CEL eligibility filter matches the right partners.
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


def make_fr_response_for_uin(uin_to_records):
    """Build a stateful client.search mock: response depends on the UIN
    inside the search envelope, so we can vary by partner.
    """

    def _search(**kwargs):
        # The OpenG2P client's search puts query_value as "TYPE:VALUE"
        qv = kwargs.get("query_value", "")
        _, _, value = qv.partition(":")
        records = uin_to_records.get(value, [])
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
                            "reg_type": "ns:org:RegistryType:Social",
                            "reg_record_type": "spdci-extensions-dci:Farmer",
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

        # Reuse the UIN vocab code seeded by the preset itself (data/openg2p_id_types.xml).
        # Creating a fresh `UIN` here would hit the spp.vocabulary.code uniqueness
        # constraint ("Code 'UIN' already exists in vocabulary 'ID Type'").
        cls.id_type_uin = cls.env.ref("spp_dci_openg2p.id_type_uin")
        cls.partner_in_fr = cls.env["res.partner"].create(
            {"name": "FR Partner", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_in_fr.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-FR-1",
            }
        )
        cls.partner_not_in_fr = cls.env["res.partner"].create(
            {"name": "Unknown Partner", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_not_in_fr.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-UNKNOWN",
            }
        )

        # The OpenG2P preset auto-creates this data source + provider +
        # variable. Confirm by reading via ref.
        cls.data_source = cls.env.ref("spp_dci_openg2p.openg2p_dr_source")
        cls.variable = cls.env.ref("spp_studio.var_has_disability")

    def test_data_source_has_vendor_openg2p(self):
        self.assertEqual(self.data_source.vendor, "openg2p")

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_fr_service.OpenG2PDCIClient")
    def test_openg2p_handler_returns_has_disability_true(self, mock_client_class):
        """Partner with a farmer record returns has_disability=True (the
        FR-as-DR pretense)."""
        mock_client = MagicMock()
        mock_client.search.side_effect = make_fr_response_for_uin({"UIN-FR-1": [{"farmer_id": "F-1"}]})
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_in_fr.id], "current"
        )

        self.assertEqual(result, {self.partner_in_fr.id: True})

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_fr_service.OpenG2PDCIClient")
    def test_openg2p_handler_records_not_found_for_unknown_partner(self, mock_client_class):
        """REG-ERR-001 / empty search_response → no entry in result
        dict, audit row says not_found."""
        mock_client = MagicMock()
        mock_client.search.side_effect = make_fr_response_for_uin({})
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_not_in_fr.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search(
            [("variable_name", "=", "has_disability"), ("subject_id", "=", self.partner_not_in_fr.id)]
        )
        self.assertEqual(audits.result, "not_found")

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_fr_service.OpenG2PDCIClient")
    def test_clearing_vendor_falls_back_to_standard_dr_handler(self, mock_client_class):
        """When vendor is cleared, the bridge's standard _handler_dr runs
        — using upstream DRService. This is the migration path: clear
        the vendor field on the data source and the bridge stops using
        the FR-as-DR adapter, no other changes required."""
        self.data_source.vendor = False

        # Patch DRService since the standard handler would invoke it
        with patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient") as mock_dci_client_class:
            mock_dci_client = MagicMock()
            mock_dci_client.search_by_id.return_value = {"message": {"search_response": []}}
            mock_dci_client_class.return_value = mock_dci_client

            # Should not call OpenG2P client at all
            self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
                self.variable, [self.partner_in_fr.id], "current"
            )

            mock_client_class.assert_not_called()
            mock_dci_client_class.assert_called_once()
