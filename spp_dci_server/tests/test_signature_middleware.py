# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI signature verification middleware."""

import logging
from unittest.mock import patch

from pydantic import ValidationError

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import DCIServerCommon

_logger = logging.getLogger(__name__)


class TestSignatureMiddleware(DCIServerCommon):
    """Test cases for DCI signature verification middleware."""

    def setUp(self):
        """Set up test fixtures for each test method."""
        super().setUp()

        # Create a test sender in the registry
        self.test_sender = self.create_test_sender()

    async def _verify_signature(self, envelope_data):
        """Helper to call the verify_dci_signature function.

        Args:
            envelope_data: Dictionary with signature, header, and message

        Returns:
            str: Validated sender_id

        Raises:
            HTTPException: If verification fails
        """
        from odoo.addons.spp_dci_server.middleware.signature import (
            verify_dci_signature,
        )

        # Create DCIEnvelope from data
        envelope = DCIEnvelope(**envelope_data)

        # Call the verification function
        return await verify_dci_signature(envelope, self.env)

    def test_verify_valid_signature(self):
        """Test that valid signature returns sender_id."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should return validated sender_id",
        )

    def test_verify_missing_sender(self):
        """Test that unknown sender returns 401 Unauthorized."""
        # Create envelope with sender not in registry
        envelope_data = self.create_signed_envelope(
            sender_id="unknown.sender.gov",
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("unknown sender", exc.detail.lower())

    def test_verify_inactive_sender_rejected(self):
        """A deactivated sender must not authenticate, even with a valid
        signature (the registry lookup requires active=True)."""
        self.test_sender.active = False
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(context.exception.status_code, 401, "Inactive sender should be rejected")

    def test_verify_invalid_signature(self):
        """Test that bad signature returns 401 Unauthorized."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Tamper with the signature to make it invalid
        # Use a completely invalid signature value to ensure verification fails
        envelope_data["signature"] = "definitely-not-a-valid-signature"

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("invalid signature", exc.detail.lower())

    def test_verify_tampered_message(self):
        """Test that tampering with message invalidates signature."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
            message={"query": {"name": "John Doe"}},
        )

        # Tamper with the message
        envelope_data["message"] = {"query": {"name": "Jane Doe"}}

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("invalid signature", exc.detail.lower())

    def test_verify_tampered_header(self):
        """Test that tampering with header invalidates signature."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Tamper with the header
        envelope_data["header"]["action"] = "subscribe"

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("invalid signature", exc.detail.lower())

    def test_verify_missing_sender_id_in_header(self):
        """Test that missing sender_id in header raises ValidationError.

        Since sender_id is required by the DCIEnvelope schema, Pydantic
        raises ValidationError before our middleware code runs.
        """
        # Create envelope with missing sender_id
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Remove sender_id from header
        del envelope_data["header"]["sender_id"]

        # Run async verification and expect ValidationError from Pydantic
        import asyncio

        with self.assertRaises(ValidationError) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        # Check that the error mentions sender_id
        self.assertIn("sender_id", str(exc).lower())

    def test_allow_unsigned_dev_mode_enabled(self):
        """Test that unsigned requests are allowed when dev mode is enabled."""
        # Enable dev mode
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "true")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should accept unsigned request in dev mode",
        )

        # Clean up - disable dev mode
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

    def test_reject_unsigned_dev_mode_disabled(self):
        """Test that unsigned requests are rejected when dev mode is disabled."""
        # Ensure dev mode is disabled
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("signature", exc.detail.lower())

    def test_verify_missing_signature(self):
        """Test that missing signature field returns 401 Unauthorized."""
        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Remove signature entirely (set to empty string)
        envelope_data["signature"] = ""

        # Ensure dev mode is disabled
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("signature", exc.detail.lower())

    def test_verify_sender_without_public_key(self):
        """Test that sender without public key returns 401 Unauthorized.

        Per DCI spec, authentication/authorization failures return 401.
        """
        # Create sender without public key
        self.SenderRegistry.create(
            {
                "name": "No Key Sender",
                "sender_id": "crvs.nokey.test",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
                # public_key intentionally not set
            }
        )

        # Create a signed envelope (signature won't matter since we'll fail on key)
        envelope_data = self.create_signed_envelope(
            sender_id="crvs.nokey.test",
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        # Error message indicates signature verification is not configured
        self.assertIn("verification not configured", exc.detail.lower())

    def test_verify_inactive_sender(self):
        """Test that inactive sender is treated as unknown."""
        # Create inactive sender
        self.create_test_sender(
            sender_id="crvs.inactive.test",
            active=False,
        )

        # Create a signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id="crvs.inactive.test",
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("unknown sender", exc.detail.lower())

    def test_verify_multiple_senders_returns_first(self):
        """Test that when multiple active senders exist, first one is used."""
        # This shouldn't happen due to unique constraint, but test the lookup behavior
        # We can't actually create duplicates due to SQL constraint, so we test
        # that get_by_sender_id with limit=1 works correctly

        self.create_test_sender(sender_id="crvs.multi.test1")

        # Create a signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id="crvs.multi.test1",
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            "crvs.multi.test1",
            "Should return sender_id from first match",
        )

    def test_verify_with_different_algorithm(self):
        """Test verification with RS256 algorithm."""
        # For now, we only test ed25519, but this is a placeholder for future
        # RSA support testing. This test documents the intent.
        # TODO: Add RSA key generation and testing when rs256 support is fully implemented
        pass

    def test_config_parameter_case_insensitive(self):
        """Test that config parameter check is case insensitive."""
        # Set parameter with different casing
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "TRUE")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should accept unsigned request with TRUE (uppercase)",
        )

        # Clean up
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

    def test_verify_logs_success(self):
        """Test that successful verification logs info message."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_server.middleware.signature._logger") as mock_logger:
            # Run async verification
            import asyncio

            asyncio.run(self._verify_signature(envelope_data))

            # Verify info log was called
            mock_logger.info.assert_called()
            log_message = mock_logger.info.call_args[0][0]
            self.assertIn("verified successfully", log_message.lower())

    def test_verify_logs_unknown_sender(self):
        """Test that unknown sender logs warning."""
        # Create envelope with unknown sender
        envelope_data = self.create_signed_envelope(
            sender_id="unknown.sender.gov",
            receiver_id="registry.test.gov",
            action="search",
        )

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_server.middleware.signature._logger") as mock_logger:
            # Run async verification
            import asyncio

            try:
                asyncio.run(self._verify_signature(envelope_data))
            except HTTPException:
                pass

            # Verify warning log was called
            mock_logger.warning.assert_called()
            log_message = mock_logger.warning.call_args[0][0]
            self.assertIn("unknown sender", log_message.lower())

    def test_verify_logs_invalid_signature(self):
        """Test that invalid signature logs warning."""
        # Create envelope with invalid signature
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="registry.test.gov",
            action="search",
        )

        # Tamper with signature - use a completely invalid value to ensure verification fails
        envelope_data["signature"] = "definitely-not-a-valid-signature"

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_server.middleware.signature._logger") as mock_logger:
            # Run async verification
            import asyncio

            try:
                asyncio.run(self._verify_signature(envelope_data))
            except HTTPException:
                pass

            # Verify warning log was called for invalid signature
            # Extract the first argument (format string) from each warning call
            warning_messages = []
            for call in mock_logger.warning.call_args_list:
                if call.args:
                    # Format the message with its arguments if any
                    try:
                        msg = call.args[0] % call.args[1:] if len(call.args) > 1 else call.args[0]
                        warning_messages.append(str(msg).lower())
                    except (TypeError, IndexError):
                        warning_messages.append(str(call.args[0]).lower())
            self.assertTrue(
                any("invalid signature" in msg for msg in warning_messages),
                f"Should log warning about invalid signature. Got: {warning_messages}",
            )
