from unittest.mock import MagicMock, patch

from odoo.tests.common import tagged

from .common import (
    BridgeTestBase,
    make_dr_empty_response,
    make_dr_search_response,
)


@tagged("post_install", "-at_install")
class TestDRHandler(BridgeTestBase):
    """Verify the dispatcher's DR handler against a mocked DCIClient."""

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_returns_attribute_value(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(has_disability=True)
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {self.partner_a.id: True})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_returns_false_when_no_disability(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(has_disability=False)
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {self.partner_a.id: False})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_extracts_nested_attribute(self, mock_client_class):
        # Reconfigure the variable to read a nested path
        self.variable.dci_attribute_path = "functional_scores.Vision"

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(
            functional_scores={"Vision": 4, "Mobility": 2, "Cognition": 1}
        )
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {self.partner_a.id: 4})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_omits_subject_with_empty_response(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_empty_response()
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        self.assertEqual(result, {})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_omits_subject_without_identifier(self, mock_client_class):
        # DRService.get_disability_status returns None when partner has no
        # matching identifier; the bridge must treat that as "skip subject",
        # not "error the whole batch".
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(has_disability=True)
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable,
            [self.partner_a.id, self.partner_no_id.id],
            "current",
        )

        # partner_no_id has no identifier; only partner_a is in the result
        self.assertEqual(result, {self.partner_a.id: True})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_batches_multiple_subjects(self, mock_client_class):
        # Per-subject loop in v1; verify both subjects appear in the result.
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(has_disability=True)
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable,
            [self.partner_a.id, self.partner_b.id],
            "current",
        )

        self.assertEqual(
            result,
            {self.partner_a.id: True, self.partner_b.id: True},
        )

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_dr_handler_swallows_per_subject_errors(self, mock_client_class):
        """One subject erroring out must not fail the batch."""
        responses = iter(
            [
                make_dr_search_response(has_disability=True),
                Exception("simulated network error"),
            ]
        )

        def side_effect(**_kwargs):
            r = next(responses)
            if isinstance(r, Exception):
                raise r
            return r

        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = side_effect
        mock_client_class.return_value = mock_client

        result = self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable,
            [self.partner_a.id, self.partner_b.id],
            "current",
        )

        # First subject succeeded; second errored and is omitted
        self.assertEqual(result, {self.partner_a.id: True})
