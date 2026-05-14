"""End-to-end test: bridge dispatcher routes vendor=openspp DR sources to
the OpenSPP-DR service, and the result populates the dispatcher's return
dict for attribute-path extraction.
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


def make_dr_response_for_uin(uin_to_records):
    """Stateful search_by_id mock: response depends on the identifier_value."""

    def _search_by_id(**kwargs):
        value = kwargs.get("identifier_value", "")
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
                            "reg_type": "DR",
                            "reg_record_type": "PWD_PERSON",
                            "reg_records": records,
                        },
                    }
                ]
            }
        }

    return _search_by_id


@tagged("post_install", "-at_install")
class TestDispatcherRoutesOpenSPPDR(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.id_type_uin = cls.env.ref("spp_dci_openspp_dr.id_type_uin_sp")
        cls.partner_pwd = cls.env["res.partner"].create(
            {"name": "DR Partner", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_pwd.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-DR-1",
            }
        )
        cls.partner_unknown = cls.env["res.partner"].create(
            {"name": "Unknown Partner", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_unknown.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-UNKNOWN",
            }
        )

        cls.data_source = cls.env.ref("spp_dci_openspp_dr.openspp_dr_source")
        cls.variable = cls.env.ref("spp_studio.var_has_disability")

    def test_data_source_has_vendor_openspp_and_registry_type_dr(self):
        self.assertEqual(self.data_source.vendor, "openspp")
        self.assertEqual(self.data_source.registry_type, "DR")

    @patch("odoo.addons.spp_dci_openspp_dr.services.openspp_dr_service.DCIClient")
    def test_openspp_dr_handler_extracts_has_disability(self, mock_client_class):
        """Partner with a matching DR record returns has_disability=True."""
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = make_dr_response_for_uin(
            {"UIN-DR-1": [{"has_disability": True}]}
        )
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_pwd.id], "current"
        )

        self.assertEqual(result, {self.partner_pwd.id: True})

    @patch("odoo.addons.spp_dci_openspp_dr.services.openspp_dr_service.DCIClient")
    def test_openspp_dr_handler_records_not_found_for_unknown_partner(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = make_dr_response_for_uin({})
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_unknown.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search(
            [
                ("variable_name", "=", "has_disability"),
                ("subject_id", "=", self.partner_unknown.id),
            ]
        )
        self.assertEqual(audits.result, "not_found")

    @patch("odoo.addons.spp_dci_openspp_dr.services.openspp_dr_service.DCIClient")
    def test_clearing_vendor_falls_back_to_upstream_dr_handler(self, mock_client_class):
        """When vendor is cleared, the bridge's standard _handler_dr runs
        — using upstream DRService. This is the migration test: vendor
        opt-in / fall-back contract."""
        self.data_source.vendor = False

        # Patch upstream DCIClient used by DRService so we can verify it
        # was called (and our adapter was not).
        with patch(
            "odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient"
        ) as mock_upstream_class:
            mock_upstream_client = MagicMock()
            mock_upstream_client.search_by_id.return_value = {
                "message": {"search_response": []}
            }
            mock_upstream_class.return_value = mock_upstream_client

            self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
                self.variable, [self.partner_pwd.id], "current"
            )

            # Our adapter must NOT have been used
            mock_client_class.assert_not_called()
            # Upstream WAS used
            mock_upstream_class.assert_called_once()
