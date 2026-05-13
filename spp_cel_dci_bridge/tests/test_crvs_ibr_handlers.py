"""Smoke tests for CRVS and IBR handlers.

These confirm the dispatcher routes correctly and the handlers wire to the
real service surfaces; they do NOT exhaustively exercise CRVS/IBR semantics
(which are the responsibility of those modules' own test suites).
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import tagged

from .common import BridgeTestBase


def make_crvs_birth_response(birth_date="2000-01-15"):
    return {
        "message": {
            "search_response": [
                {
                    "reference_id": "crvs-ref",
                    "status": "succ",
                    "data": [
                        {
                            "identifier_type": "UIN",
                            "birth_date": birth_date,
                            "person_name": "Test Person",
                        }
                    ],
                }
            ]
        }
    }


def make_ibr_search_response():
    return {
        "message": {
            "search_response": [
                {
                    "reference_id": "ibr-ref",
                    "status": "succ",
                    "data": [
                        {
                            "programs": ["program-a", "program-b"],
                            "first_name": "Test",
                            "last_name": "Person",
                        }
                    ],
                }
            ]
        }
    }


@tagged("post_install", "-at_install")
class TestCRVSHandler(BridgeTestBase):
    """Verify CRVS dispatcher routing via mocked DCIClient.

    CRVS service requires registry_type = the SPDCI URI; the bridge
    dispatcher normalizes both URI and short forms to the canonical key.
    """

    def setUp(self):
        super().setUp()
        # CRVS service validates against the SPDCI URI specifically
        self.dci_source.registry_type = "ns:org:RegistryType:Civil"
        self.variable.dci_attribute_path = "birth_date"

    @patch("odoo.addons.spp_dci_client_crvs.services.crvs_service.DCIClient")
    def test_crvs_handler_extracts_attribute(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_crvs_birth_response("2005-05-12")
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {self.partner_a.id: "2005-05-12"})

    @patch("odoo.addons.spp_dci_client_crvs.services.crvs_service.DCIClient")
    def test_crvs_handler_omits_subject_without_identifier(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_crvs_birth_response()
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_no_id.id], "current"
        )

        self.assertEqual(result, {})


@tagged("post_install", "-at_install")
class TestIBRHandler(BridgeTestBase):
    """Verify IBR dispatcher routing via mocked DCIClient.

    IBR service validates registry_type == "ibr" (lowercase). The bridge
    dispatcher normalizes this to the canonical "IBR" key.
    """

    def setUp(self):
        super().setUp()
        self.dci_source.registry_type = "ibr"
        self.variable.dci_attribute_path = "is_duplicate"

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_ibr_handler_extracts_attribute(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_ibr_search_response()
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        # check_duplication finds 2 matched programs → is_duplicate=True
        self.assertEqual(result, {self.partner_a.id: True})
