# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for DCI Client DR module."""

from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas import DCIMessageHeader
from odoo.addons.spp_dci.services.signing import DCISigner


@tagged("post_install", "-at_install")
class DRClientCommon(TransactionCase):
    """Base test class with shared utilities for DR Client tests."""

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()

        # Create test keypair for DR sender (registry side)
        cls.test_private_key = Ed25519PrivateKey.generate()
        cls.test_public_key_pem = (
            cls.test_private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
        cls.test_private_key_pem = cls.test_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Test DR sender configuration
        cls.test_sender_id = "dr.national.gov"
        cls.test_key_id = "2024-test-key"
        cls.test_algorithm = "ed25519"

        # Models
        cls.DRSender = cls.env["spp.dci.dr.sender"]

    @classmethod
    def create_test_dr_sender(
        cls,
        sender_id=None,
        name=None,
        public_key=None,
        algorithm=None,
        active=True,
        jwks_url=None,
    ):
        """Helper to create a test DR sender registry entry.

        Args:
            sender_id: Sender ID (defaults to cls.test_sender_id)
            name: Friendly name (defaults to auto-generated)
            public_key: Public key PEM (defaults to cls.test_public_key_pem)
            algorithm: Algorithm (defaults to cls.test_algorithm)
            active: Whether sender is active (default: True)
            jwks_url: Optional JWKS URL

        Returns:
            spp.dci.dr.sender: Created sender record
        """
        sender_id = sender_id or cls.test_sender_id
        return cls.DRSender.create(
            {
                "name": name or f"Test DR Sender {sender_id}",
                "sender_id": sender_id,
                "public_key": public_key or cls.test_public_key_pem,
                "algorithm": algorithm or cls.test_algorithm,
                "active": active,
                "jwks_url": jwks_url,
            }
        )

    @classmethod
    def create_signed_envelope(
        cls,
        sender_id=None,
        receiver_id="dr.client.openspp",
        action="notify",
        message=None,
    ):
        """Helper to create a signed DCI envelope for testing DR callbacks.

        Args:
            sender_id: Sender ID (defaults to cls.test_sender_id)
            receiver_id: Receiver ID
            action: DCI action (default: 'notify' for callbacks)
            message: Message payload (defaults to DR birth event)

        Returns:
            dict: DCI envelope with signature, header, and message
        """
        if message is None:
            message = {
                "event_type": "birth",
                "event_id": "BRN-2024-001",
                "event_date": "2024-01-15",
                "child": {
                    "name": "John Doe Jr",
                    "national_id": "NID-123456",
                },
            }

        sender_id = sender_id or cls.test_sender_id

        # Create message header using Pydantic model to ensure consistent serialization
        # This ensures the header format matches what verification expects
        header_model = DCIMessageHeader(
            version="1.0.0",
            message_id="dr-callback-001",
            message_ts=datetime.now(UTC),
            action=action,
            sender_id=sender_id,
            sender_uri="https://dr.national.gov/api/v1",
            receiver_id=receiver_id,
            total_count=1,
            is_msg_encrypted=False,
        )
        # Serialize with mode="json" to match verification serialization
        header = header_model.model_dump(mode="json")

        # Sign the message using DR sender's private key
        signer = DCISigner(
            private_key=cls.test_private_key_pem,
            sender_id=sender_id,
            key_id=cls.test_key_id,
            algorithm=cls.test_algorithm,
        )
        signature = signer.sign(header, message)

        return {
            "signature": signature,
            "header": header,
            "message": message,
        }

    @classmethod
    def create_unsigned_envelope(
        cls,
        sender_id=None,
        receiver_id="dr.client.openspp",
        action="notify",
        message=None,
    ):
        """Helper to create an unsigned DCI envelope for testing.

        Args:
            sender_id: Sender ID (defaults to cls.test_sender_id)
            receiver_id: Receiver ID
            action: DCI action
            message: Message payload (defaults to DR birth event)

        Returns:
            dict: DCI envelope with unsigned-stub signature, header, and message
        """
        if message is None:
            message = {
                "event_type": "birth",
                "event_id": "BRN-2024-001",
                "event_date": "2024-01-15",
                "child": {
                    "name": "John Doe Jr",
                    "national_id": "NID-123456",
                },
            }

        sender_id = sender_id or cls.test_sender_id

        # Create message header using Pydantic model to ensure consistent serialization
        header_model = DCIMessageHeader(
            version="1.0.0",
            message_id="dr-callback-001",
            message_ts=datetime.now(UTC),
            action=action,
            sender_id=sender_id,
            sender_uri="https://dr.national.gov/api/v1",
            receiver_id=receiver_id,
            total_count=1,
            is_msg_encrypted=False,
        )
        header = header_model.model_dump(mode="json")

        return {
            "signature": "unsigned-stub",
            "header": header,
            "message": message,
        }
