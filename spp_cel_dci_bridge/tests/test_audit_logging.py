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
    def test_subject_ref_resolves_to_current_partner(self, mock_client_class):
        """Reference field gives auditors click-through to the partner."""
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(True)
        mock_client_class.return_value = mock_client

        self.env["spp.cel.dci.dispatcher"].fetch_values_for_variable(self.variable, [self.partner_a.id], "current")

        row = self._audits_for_variable()
        self.assertEqual(len(row), 1)
        self.assertEqual(row.subject_ref, self.partner_a)

    def test_subject_ref_falsy_when_partner_missing(self):
        """Reference is False when subject_id points to a deleted partner;
        the immutable subject_id snapshot is preserved in the audit log."""
        missing_id = 99999999
        # Make sure the id really doesn't exist
        self.assertFalse(self.env["res.partner"].browse(missing_id).exists())

        row = self.Audit.create(
            {
                "provider_code": "bridge_dr_provider",
                "data_source_code": "bridge_dr_source",
                "registry_type": "DR",
                "variable_name": self.variable.name,
                "subject_model": "res.partner",
                "subject_id": missing_id,
                "result": "ok",
            }
        )
        self.assertFalse(row.subject_ref)
        # Snapshot subject_id survives even when the partner no longer resolves
        self.assertEqual(row.subject_id, missing_id)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_audit_records_acting_user_not_root(self, mock_client_class):
        """Regression: audit must record the operator who triggered the
        fetch, not user_root. The user_id field default resolves to
        self.env.user, which gets overridden by sudo() to user_root unless
        we capture acting_user_id before escalating privileges.
        """
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_search_response(True)
        mock_client_class.return_value = mock_client

        # Create a non-admin internal user to act as the operator
        officer = self.env["res.users"].create(
            {
                "name": "DCI Officer",
                "login": "dci_officer_test",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

        # Drive the dispatcher as that user
        self.env["spp.cel.dci.dispatcher"].with_user(officer).fetch_values_for_variable(
            self.variable, [self.partner_a.id], "current"
        )

        rows = self._audits_for_variable()
        self.assertEqual(len(rows), 1)
        # The audit row must record the officer, not user_root
        self.assertEqual(rows.user_id, officer)
        self.assertNotEqual(rows.user_id, self.env.ref("base.user_root"))
