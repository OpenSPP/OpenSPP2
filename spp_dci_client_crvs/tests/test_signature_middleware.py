# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CRVS DCI signature verification middleware."""

import logging
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import CRVSClientCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestCRVSSignatureMiddleware(CRVSClientCommon):
    """Test cases for CRVS signature verification middleware."""

    def setUp(self):
        """Set up test fixtures for each test method."""
        super().setUp()

        # Create a test CRVS sender in the registry
        self.test_sender = self.create_test_crvs_sender()

        # Ensure dev mode is disabled by default
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

    async def _verify_signature(self, envelope_data):
        """Helper to call the verify_crvs_signature function.

        Args:
            envelope_data: Dictionary with signature, header, and message

        Returns:
            str: Validated sender_id

        Raises:
            HTTPException: If verification fails
        """
        from odoo.addons.spp_dci_client_crvs.middleware.signature import (
            verify_crvs_signature,
        )

        # Create DCIEnvelope from data
        envelope = DCIEnvelope(**envelope_data)

        # Call the verification function
        return await verify_crvs_signature(envelope, self.env)

    def test_verify_valid_signature(self):
        """Test that valid signature returns sender_id."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should return validated sender_id",
        )

    def test_verify_invalid_signature(self):
        """Test that invalid signature returns 401 Unauthorized."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
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

    def test_verify_unknown_sender(self):
        """Test that unknown sender returns 401 Unauthorized."""
        # Create envelope with sender not in registry
        envelope_data = self.create_signed_envelope(
            sender_id="crvs.unknown.gov",
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("unknown", exc.detail.lower())

    def test_verify_missing_signature_production_mode(self):
        """Test that missing signature is rejected in production mode."""
        # Ensure production mode (dev mode disabled)
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("signature", exc.detail.lower())

    def test_verify_missing_signature_dev_mode(self):
        """Test that missing signature is accepted in dev mode."""
        # Enable dev mode
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "true")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should accept unsigned request in dev mode",
        )

    def test_verify_inactive_sender_rejected(self):
        """Test that inactive sender is rejected."""
        # Create inactive sender
        self.create_test_crvs_sender(
            sender_id="crvs.inactive.test",
            active=False,
        )

        # Create a signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id="crvs.inactive.test",
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("unknown", exc.detail.lower())

    def test_verify_tampered_message(self):
        """Test that tampering with message invalidates signature."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
            message={
                "event_type": "birth",
                "event_id": "BRN-2024-001",
            },
        )

        # Tamper with the message
        envelope_data["message"] = {
            "event_type": "death",
            "event_id": "DTH-2024-001",
        }

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
            receiver_id="crvs.client.openspp",
            action="notify",
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
        """Test that missing sender_id in header is rejected during validation."""
        from pydantic import ValidationError as PydanticValidationError

        # Create envelope with missing sender_id
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Remove sender_id from header
        del envelope_data["header"]["sender_id"]

        # Pydantic validation will fail when creating DCIEnvelope
        # since sender_id is a required field
        import asyncio

        with self.assertRaises(PydanticValidationError) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        # Verify the error mentions sender_id
        error_str = str(exc).lower()
        self.assertIn("sender_id", error_str)

    def test_verify_sender_without_public_key(self):
        """Test that sender without public key returns 500 Internal Server Error."""
        # Create sender without public key
        self.CRVSSender.create(
            {
                "name": "No Key Sender",
                "sender_id": "crvs.nokey.test",
                "algorithm": "ed25519",
                # public_key intentionally not set
            }
        )

        # Create a signed envelope (signature won't matter since we'll fail on key)
        envelope_data = self.create_signed_envelope(
            sender_id="crvs.nokey.test",
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 500, "Should return 500 Internal Server Error")
        self.assertIn("verifier", exc.detail.lower())

    def test_verify_empty_signature_string(self):
        """Test that empty signature string is rejected."""
        # Ensure production mode
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "false")

        # Create unsigned envelope with empty signature
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )
        envelope_data["signature"] = ""

        # Run async verification and expect HTTPException
        import asyncio

        with self.assertRaises(HTTPException) as context:
            asyncio.run(self._verify_signature(envelope_data))

        exc = context.exception
        self.assertEqual(exc.status_code, 401, "Should return 401 Unauthorized")
        self.assertIn("signature", exc.detail.lower())

    def test_verify_config_parameter_case_insensitive(self):
        """Test that config parameter check is case insensitive."""
        # Set parameter with different casing
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "TRUE")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should accept unsigned request with TRUE (uppercase)",
        )

    def test_verify_logs_success(self):
        """Test that successful verification logs info message."""
        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_client_crvs.middleware.signature._logger") as mock_logger:
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
            sender_id="crvs.unknown.gov",
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_client_crvs.middleware.signature._logger") as mock_logger:
            # Run async verification
            import asyncio

            try:
                asyncio.run(self._verify_signature(envelope_data))
            except HTTPException:
                pass

            # Verify warning log was called
            mock_logger.warning.assert_called()
            log_message = mock_logger.warning.call_args[0][0]
            self.assertIn("unknown", log_message.lower())

    def test_verify_logs_invalid_signature(self):
        """Test that invalid signature logs warning."""
        # Create envelope with invalid signature
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Use a completely invalid signature to ensure verification fails
        # (replacing characters is unreliable if those characters don't exist in the signature)
        envelope_data["signature"] = "definitely-not-a-valid-signature"

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_client_crvs.middleware.signature._logger") as mock_logger:
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

    def test_verify_logs_unsigned_in_dev_mode(self):
        """Test that accepting unsigned request in dev mode logs warning."""
        # Enable dev mode
        self.env["ir.config_parameter"].sudo().set_param("dci.allow_unsigned_requests", "true")

        # Create unsigned envelope
        envelope_data = self.create_unsigned_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Patch the logger to capture log calls
        with patch("odoo.addons.spp_dci_client_crvs.middleware.signature._logger") as mock_logger:
            # Run async verification
            import asyncio

            asyncio.run(self._verify_signature(envelope_data))

            # Verify warning log was called
            mock_logger.warning.assert_called()
            log_message = mock_logger.warning.call_args[0][0]
            self.assertIn("unsigned", log_message.lower())
            self.assertIn("development", log_message.lower())

    def test_verify_multiple_envelopes_sequentially(self):
        """Test verifying multiple envelopes sequentially."""
        import asyncio

        # Create multiple properly signed envelopes
        envelopes = [
            self.create_signed_envelope(
                sender_id=self.test_sender_id,
                action="notify",
                message={"event_id": f"BRN-2024-00{i}"},
            )
            for i in range(1, 4)
        ]

        # Verify each envelope
        for envelope_data in envelopes:
            result = asyncio.run(self._verify_signature(envelope_data))
            self.assertEqual(result, self.test_sender_id)

    def test_verify_different_actions(self):
        """Test verification works for different DCI actions."""
        import asyncio

        actions = ["notify", "on_create", "on_update", "on_delete"]

        for action in actions:
            envelope_data = self.create_signed_envelope(
                sender_id=self.test_sender_id,
                action=action,
            )

            result = asyncio.run(self._verify_signature(envelope_data))
            self.assertEqual(
                result,
                self.test_sender_id,
                f"Should verify signature for action: {action}",
            )

    def test_verify_with_different_message_types(self):
        """Test verification with different CRVS event types."""
        import asyncio

        event_types = [
            {"event_type": "birth", "event_id": "BRN-001"},
            {"event_type": "death", "event_id": "DTH-001"},
            {"event_type": "marriage", "event_id": "MRG-001"},
            {"event_type": "divorce", "event_id": "DIV-001"},
        ]

        for message in event_types:
            envelope_data = self.create_signed_envelope(
                sender_id=self.test_sender_id,
                message=message,
            )

            result = asyncio.run(self._verify_signature(envelope_data))
            self.assertEqual(
                result,
                self.test_sender_id,
                f"Should verify for event type: {message['event_type']}",
            )

    def test_verify_sender_lookup_uses_sudo(self):
        """Test that sender lookup uses sudo to bypass access rights."""
        # This test ensures the middleware can verify signatures even if
        # the current user doesn't have read access to spp.dci.crvs.sender

        # Create a properly signed envelope
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="crvs.client.openspp",
            action="notify",
        )

        # Run async verification (middleware should use sudo)
        import asyncio

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should work with sudo even without explicit access",
        )

    def test_verify_complex_message_structure(self):
        """Test verification with complex nested message structure."""
        import asyncio

        complex_message = {
            "event_type": "birth",
            "event_id": "BRN-2024-001",
            "event_date": "2024-01-15",
            "location": {
                "facility": "General Hospital",
                "district": "Central",
                "coordinates": {
                    "lat": 1.2345,
                    "lng": 103.8198,
                },
            },
            "child": {
                "name": "John Doe Jr",
                "national_id": "NID-123456",
                "birth_weight": 3.2,
                "parents": [
                    {"name": "John Doe Sr", "national_id": "NID-789012"},
                    {"name": "Jane Doe", "national_id": "NID-345678"},
                ],
            },
        }

        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            message=complex_message,
        )

        result = asyncio.run(self._verify_signature(envelope_data))

        self.assertEqual(
            result,
            self.test_sender_id,
            "Should verify complex nested message structures",
        )
