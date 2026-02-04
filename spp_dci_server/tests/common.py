# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for DCI Server module."""

from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from odoo.tests import TransactionCase

from odoo.addons.spp_dci.schemas.envelope import DCIMessageHeader
from odoo.addons.spp_dci.services.signing import DCISigner


class DCIServerCommon(TransactionCase):
    """Base test class with shared utilities for DCI Server tests."""

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()

        # Create test keypair
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

        # Test sender configuration
        cls.test_sender_id = "crvs.test.gov"
        cls.test_key_id = "2024-test-key"
        cls.test_algorithm = "ed25519"

        # Models
        cls.SenderRegistry = cls.env["spp.dci.sender.registry"]

        # Create test partner for sender registry (required by spp.api.client)
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Test DCI Sender Organization",
                "is_company": True,
            }
        )

        # Lookup organization type (required by spp.api.client)
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

    @classmethod
    def create_test_sender(
        cls,
        sender_id=None,
        public_key=None,
        algorithm=None,
        active=True,
        partner_id=None,
    ):
        """Helper to create a test sender registry entry.

        Args:
            sender_id: Sender ID (defaults to cls.test_sender_id)
            public_key: Public key PEM (defaults to cls.test_public_key_pem)
            algorithm: Algorithm (defaults to cls.test_algorithm)
            active: Whether sender is active (default: True)
            partner_id: Partner ID (defaults to cls.test_partner.id)

        Returns:
            spp.dci.sender.registry: Created sender record
        """
        return cls.SenderRegistry.create(
            {
                "name": f"Test Sender {sender_id or cls.test_sender_id}",
                "sender_id": sender_id or cls.test_sender_id,
                "public_key": public_key or cls.test_public_key_pem,
                "algorithm": algorithm or cls.test_algorithm,
                "active": active,
                "partner_id": partner_id or cls.test_partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )

    @classmethod
    def create_signed_envelope(
        cls,
        sender_id=None,
        receiver_id="registry.test.gov",
        action="search",
        message=None,
    ):
        """Helper to create a signed DCI envelope for testing.

        Args:
            sender_id: Sender ID (defaults to cls.test_sender_id)
            receiver_id: Receiver ID
            action: DCI action
            message: Message payload (defaults to empty dict)

        Returns:
            dict: DCI envelope with signature, header, and message
        """
        if message is None:
            message = {"query": {"name": "John Doe"}}

        sender_id = sender_id or cls.test_sender_id

        # Create message header using Pydantic model to ensure consistent serialization
        # This ensures the header format matches what verification expects
        header_model = DCIMessageHeader(
            version="1.0.0",
            message_id="test-msg-001",
            message_ts=datetime.now(UTC),
            action=action,
            sender_id=sender_id,
            sender_uri="https://crvs.test.gov/callback",
            receiver_id=receiver_id,
            total_count=1,
            is_msg_encrypted=False,
        )
        # Serialize with mode="json" to match verification serialization
        header = header_model.model_dump(mode="json")

        # Sign the message
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
        receiver_id="registry.test.gov",
        action="search",
        message=None,
    ):
        """Helper to create an unsigned DCI envelope for testing.

        Args:
            sender_id: Sender ID (defaults to cls.test_sender_id)
            receiver_id: Receiver ID
            action: DCI action
            message: Message payload (defaults to empty dict)

        Returns:
            dict: DCI envelope with unsigned-stub signature, header, and message
        """
        if message is None:
            message = {"query": {"name": "John Doe"}}

        sender_id = sender_id or cls.test_sender_id

        # Create message header using Pydantic model to ensure consistent serialization
        header_model = DCIMessageHeader(
            version="1.0.0",
            message_id="test-msg-001",
            message_ts=datetime.now(UTC),
            action=action,
            sender_id=sender_id,
            sender_uri="https://crvs.test.gov/callback",
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
