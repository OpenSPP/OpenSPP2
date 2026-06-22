# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCIConsentAdapter.

The adapter bridges DCI search to the spp_api_v2 consent infrastructure.
Tests cover:

- legal-basis bypass logic
- per-registrant access check with bypass / no-consent-required / consent
  lookup / no-consent paths
- DCI response filtering with bypass metadata vs delegate vs fallback paths
- domain-building for bulk search filtering
- access logging side-effect
"""

from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .common import DCIServerCommon


@tagged("post_install", "-at_install")
class TestConsentAdapter(DCIServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.services.consent_adapter import (
            DCIConsentAdapter,
        )

        self.DCIConsentAdapter = DCIConsentAdapter
        self.sender = self.create_test_sender()

    # --- has_legal_basis_bypass ----------------------------------------------

    def test_legal_basis_bypass_true_for_each_non_consent_basis(self):
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        for basis in self.DCIConsentAdapter.NON_CONSENT_LEGAL_BASES:
            with self.subTest(basis=basis):
                self.sender.write({"legal_basis": basis})
                self.assertTrue(adapter.has_legal_basis_bypass())

    def test_legal_basis_bypass_false_for_consent(self):
        self.sender.write({"legal_basis": "consent"})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        self.assertFalse(adapter.has_legal_basis_bypass())

    def test_legal_basis_bypass_false_when_no_sender(self):
        adapter = self.DCIConsentAdapter(self.env)
        self.assertFalse(adapter.has_legal_basis_bypass())

    # --- set_sender ----------------------------------------------------------

    def test_set_sender(self):
        adapter = self.DCIConsentAdapter(self.env)
        self.assertIsNone(adapter.sender)
        adapter.set_sender(self.sender)
        self.assertEqual(adapter.sender, self.sender)

    # --- can_access_registrant -----------------------------------------------

    def test_can_access_returns_false_without_sender(self):
        adapter = self.DCIConsentAdapter(self.env)
        self.assertFalse(adapter.can_access_registrant(1))

    def test_can_access_true_when_legal_basis_bypass(self):
        self.sender.write({"legal_basis": "legal_obligation"})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        self.assertTrue(adapter.can_access_registrant(1))

    def test_can_access_true_when_consent_not_required(self):
        self.sender.write({"legal_basis": "consent", "is_require_consent": False})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        self.assertTrue(adapter.can_access_registrant(1))

    def test_can_access_consent_path_returns_true_when_consent_found(self):
        self.sender.write({"legal_basis": "consent", "is_require_consent": True})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        with patch.object(
            type(self.env["spp.consent"]),
            "check_api_consent",
            return_value=MagicMock(),
        ):
            self.assertTrue(adapter.can_access_registrant(1))

    def test_can_access_consent_path_returns_false_when_no_consent(self):
        self.sender.write({"legal_basis": "consent", "is_require_consent": True})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        with patch.object(
            type(self.env["spp.consent"]),
            "check_api_consent",
            return_value=False,
        ):
            self.assertFalse(adapter.can_access_registrant(1))

    # --- filter_dci_response -------------------------------------------------

    def test_filter_returns_unfiltered_without_sender(self):
        adapter = self.DCIConsentAdapter(self.env)
        data = {"name": "Test"}
        self.assertEqual(adapter.filter_dci_response(1, data), data)

    def test_filter_adds_legal_basis_metadata_on_bypass(self):
        self.sender.write({"legal_basis": "legal_obligation"})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        result = adapter.filter_dci_response(1, {"name": "Test"})
        self.assertEqual(result["_consent"]["status"], "legal_basis")
        self.assertEqual(result["_consent"]["basis"], "legal_obligation")

    def test_filter_uses_consent_service_when_available(self):
        self.sender.write({"legal_basis": "consent", "is_require_consent": True})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        # Inject a mock consent_service so the lazy load short-circuits.
        mock_service = MagicMock()
        mock_service.filter_response.return_value = {"filtered": True}
        adapter._consent_service = mock_service

        result = adapter.filter_dci_response(1, {"name": "Test"})
        self.assertEqual(result, {"filtered": True})
        mock_service.filter_response.assert_called_once()

    def test_filter_fallback_path_with_access(self):
        """No ConsentService + can_access_registrant=True returns data
        with an _consent='active' marker."""
        self.sender.write({"legal_basis": "consent", "is_require_consent": False})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        adapter._consent_service = None  # force fallback
        # Force the lazy property to skip the ImportError branch
        with patch.object(self.DCIConsentAdapter, "consent_service", None):
            result = adapter.filter_dci_response(1, {"name": "Test"})
        self.assertEqual(result["_consent"]["status"], "active")

    def test_filter_fallback_path_without_access(self):
        """No ConsentService + can_access_registrant=False returns minimal
        data with no_consent metadata."""
        self.sender.write({"legal_basis": "consent", "is_require_consent": True})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        adapter._consent_service = None
        with patch.object(self.DCIConsentAdapter, "consent_service", None):
            with patch.object(
                type(self.env["spp.consent"]),
                "check_api_consent",
                return_value=False,
            ):
                result = adapter.filter_dci_response(
                    1,
                    {"name": "Test", "identifier": [{"value": "X"}]},
                )
        self.assertEqual(result["_consent"]["status"], "no_consent")
        # Identifier is preserved per docstring; everything else dropped.
        self.assertEqual(result["identifier"], [{"value": "X"}])
        self.assertNotIn("name", result)

    # --- build_consented_domain ----------------------------------------------

    def test_build_domain_no_sender_returns_base(self):
        adapter = self.DCIConsentAdapter(self.env)
        self.assertEqual(adapter.build_consented_domain([("a", "=", 1)]), [("a", "=", 1)])

    def test_build_domain_with_bypass_returns_base(self):
        self.sender.write({"legal_basis": "public_interest"})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        base = [("is_registrant", "=", True)]
        self.assertEqual(adapter.build_consented_domain(base), base)

    def test_build_domain_appends_consent_filter_when_required(self):
        self.sender.write({"legal_basis": "consent", "is_require_consent": True})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        result = adapter.build_consented_domain([("a", "=", 1)])
        self.assertIn(("consent_ids.status", "=", "active"), result)

    def test_build_domain_when_consent_not_required(self):
        self.sender.write({"legal_basis": "consent", "is_require_consent": False})
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        base = [("a", "=", 1)]
        self.assertEqual(adapter.build_consented_domain(base), base)

    # --- log_dci_access ------------------------------------------------------

    def test_log_access_noop_without_sender(self):
        adapter = self.DCIConsentAdapter(self.env)
        # Just must not raise.
        adapter.log_dci_access(1, "individual")

    def test_log_access_calls_log_method_when_consent_exists(self):
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        if "spp.consent.access.log" not in self.env:
            self.skipTest("spp.consent.access.log model not installed")

        consent_mock = MagicMock()
        with (
            patch.object(
                type(self.env["spp.consent"]),
                "check_api_consent",
                return_value=consent_mock,
            ),
            patch.object(
                type(self.env["spp.consent.access.log"]),
                "log_access",
            ) as log,
        ):
            adapter.log_dci_access(1, "individual", action="read", fields_accessed=["name"])
        log.assert_called_once()

    def test_log_access_tolerates_log_failure(self):
        adapter = self.DCIConsentAdapter(self.env, self.sender)
        if "spp.consent.access.log" not in self.env:
            self.skipTest("spp.consent.access.log model not installed")
        consent_mock = MagicMock()
        with (
            patch.object(
                type(self.env["spp.consent"]),
                "check_api_consent",
                return_value=consent_mock,
            ),
            patch.object(
                type(self.env["spp.consent.access.log"]),
                "log_access",
                side_effect=RuntimeError("broken"),
            ),
        ):
            # Must not raise.
            adapter.log_dci_access(1, "individual")
