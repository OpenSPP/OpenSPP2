from unittest.mock import MagicMock, patch

from odoo.tests.common import tagged

from .common import (
    BridgeTestBase,
    make_dr_empty_response,
    make_dr_search_response,
)


@tagged("post_install", "-at_install")
class TestAuditLogging(BridgeTestBase):
    """Verify one spp.dci.fetch.audit row is recorded per subject per fetch."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Audit = cls.env["spp.dci.fetch.audit"]

    def _audits_for_variable(self):
        return self.Audit.search([("variable_name", "=", self.variable.name)])

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_audit_row_on_success(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(True)
        mock_client_class.return_value = mock_client

        self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(self.variable, [self.partner_a.id], "current")

        rows = self._audits_for_variable()
        self.assertEqual(len(rows), 1)
        row = rows
        self.assertEqual(row.subject_id, self.partner_a.id)
        self.assertEqual(row.result, "ok")
        self.assertEqual(row.provider_code, self.provider.code)
        self.assertEqual(row.data_source_code, self.dci_source.code)
        self.assertEqual(row.registry_type, "DR")
        self.assertEqual(row.subject_model, "res.partner")
        self.assertGreaterEqual(row.elapsed_ms, 0)
        self.assertFalse(row.error_message)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_audit_row_on_not_found(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_empty_response()
        mock_client_class.return_value = mock_client

        self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(self.variable, [self.partner_a.id], "current")

        rows = self._audits_for_variable()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.result, "not_found")

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_audit_row_on_error(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = RuntimeError("simulated")
        mock_client_class.return_value = mock_client

        self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(self.variable, [self.partner_a.id], "current")

        rows = self._audits_for_variable()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.result, "error")
        self.assertIn("simulated", rows.error_message)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_one_audit_row_per_subject(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(True)
        mock_client_class.return_value = mock_client

        self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(
            self.variable,
            [self.partner_a.id, self.partner_b.id],
            "current",
        )

        rows = self._audits_for_variable()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r.subject_id for r in rows}, {self.partner_a.id, self.partner_b.id})
        self.assertTrue(all(r.result == "ok" for r in rows))

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_audit_records_user_id(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(True)
        mock_client_class.return_value = mock_client

        self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(self.variable, [self.partner_a.id], "current")

        rows = self._audits_for_variable()
        self.assertEqual(rows.user_id, self.env.user)
