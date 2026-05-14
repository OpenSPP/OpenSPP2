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

    @patch("odoo.addons.spp_dci_client_crvs.services.crvs_service.DCIClient")
    def test_crvs_handler_swallows_per_subject_error(self, mock_client_class):
        """Per-subject service exception must not fail the batch — logs +
        records an audit row with result='error' and continues."""
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = RuntimeError("crvs boom")
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search([("variable_name", "=", self.variable.name)])
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits.result, "error")
        self.assertIn("crvs boom", audits.error_message)

    @patch("odoo.addons.spp_dci_client_crvs.services.crvs_service.DCIClient")
    def test_crvs_handler_records_not_found_on_empty_response(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = {"message": {"search_response": []}}
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search([("variable_name", "=", self.variable.name)])
        self.assertEqual(audits.result, "not_found")

    @patch("odoo.addons.spp_dci_client_crvs.services.crvs_service.DCIClient")
    def test_crvs_handler_records_not_found_when_attribute_path_missing(self, mock_client_class):
        """Successful response but the configured dci_attribute_path doesn't
        resolve to anything — record not_found, not error."""
        self.variable.dci_attribute_path = "nonexistent.path"
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_crvs_birth_response()
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search([("variable_name", "=", self.variable.name)])
        self.assertEqual(audits.result, "not_found")


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

    def test_ibr_handler_swallows_per_subject_error(self):
        """If check_duplication itself raises (rare — the service swallows
        per-identifier failures internally), the dispatcher must record
        an error audit row and continue.
        """
        with patch(
            "odoo.addons.spp_dci_client_ibr.services.ibr_service.IBRService.check_duplication",
            side_effect=RuntimeError("ibr boom"),
        ):
            result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
                self.variable, [self.partner_a.id], "current"
            )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search([("variable_name", "=", self.variable.name)])
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits.result, "error")
        self.assertIn("ibr boom", audits.error_message)

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_ibr_handler_records_not_found_when_attribute_path_missing(self, mock_client_class):
        self.variable.dci_attribute_path = "nonexistent_key"
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_ibr_search_response()
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {})
        audits = self.env["spp.dci.fetch.audit"].search([("variable_name", "=", self.variable.name)])
        self.assertEqual(audits.result, "not_found")
