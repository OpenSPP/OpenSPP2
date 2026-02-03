import base64
import importlib.util
import logging
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)

# Check if claim169 library is available
CLAIM169_AVAILABLE = importlib.util.find_spec("claim169") is not None


class TestClaim169Base(TransactionCase):
    """Base test class for Claim 169 QR credential tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a simple test partner as an individual registrant
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "John Doe",
                "street": "123 Main St",
                "city": "Test City",
                "phone": "+1234567890",
                "email": "john.doe@example.com",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a second partner for multi-partner tests
        cls.partner2 = cls.env["res.partner"].create(
            {
                "name": "Jane Smith",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a test signing key with Ed25519 (supported by claim169)
        cls.signing_key = cls.env["spp.asymmetric.key"].create(
            {
                "name": "Test Signing Key",
                "key_type": "ed25519",
                "storage_mode": "local",
            }
        )
        # Generate the key pair
        cls.signing_key.generate_key_pair()

        # Create issuer configuration
        cls.issuer_config = cls.env["spp.claim169.issuer.config"].create(
            {
                "name": "Test Issuer",
                "issuer_id": "did:example:test-issuer",
                "signing_key_id": cls.signing_key.id,
                "default_validity_days": 365,
                "is_default": True,
            }
        )

        # Get service
        cls.service = cls.env["spp.claim169.service"]


class TestAttributeMapping(TestClaim169Base):
    """Test attribute mapping functionality."""

    def test_attribute_mapping_extraction(self):
        """Test attribute value extraction from partner."""
        # Use claim number 40 to avoid conflict with default mappings
        mapping = self.env["spp.claim169.attribute.mapping"].create(
            {
                "name": "Test Full Name",
                "claim_number": 40,  # Use unused claim number
                "claim_name": "full_name_test",
                "source_field": "name",
                "transform_type": "direct",
            }
        )

        value = mapping.get_value(self.partner)
        self.assertEqual(value, "John Doe")

    def test_address_combined_transformation(self):
        """Test combined address transformation."""
        # Use claim number 41 to avoid conflict with default mappings
        mapping = self.env["spp.claim169.attribute.mapping"].create(
            {
                "name": "Test Address",
                "claim_number": 41,  # Use unused claim number
                "claim_name": "address_test",
                "source_field": "street",
                "transform_type": "address_combined",
            }
        )

        value = mapping.get_value(self.partner)
        self.assertIn("123 Main St", value)
        self.assertIn("Test City", value)

    def test_claim_number_validation(self):
        """Test claim number must be in valid range."""
        with self.assertRaises(ValidationError):
            self.env["spp.claim169.attribute.mapping"].create(
                {
                    "name": "Invalid Claim",
                    "claim_number": 100,  # Out of range
                    "source_field": "name",
                    "transform_type": "direct",
                }
            )

    def test_unique_active_claim_number(self):
        """Test only one active mapping per claim number."""
        self.env["spp.claim169.attribute.mapping"].create(
            {
                "name": "First Mapping",
                "claim_number": 50,
                "source_field": "name",
                "transform_type": "direct",
                "is_active": True,
            }
        )

        with self.assertRaises(ValidationError):
            self.env["spp.claim169.attribute.mapping"].create(
                {
                    "name": "Second Mapping",
                    "claim_number": 50,
                    "source_field": "email",
                    "transform_type": "direct",
                    "is_active": True,
                }
            )


class TestClaim169LibraryIntegration(TestClaim169Base):
    """Test claim169 library integration."""

    def test_claim169_library_available(self):
        """Test that claim169 library is available."""
        try:
            import claim169

            self.assertTrue(hasattr(claim169, "Claim169Input"))
            self.assertTrue(hasattr(claim169, "CwtMetaInput"))
            self.assertTrue(hasattr(claim169, "encode_with_signer"))
            self.assertTrue(hasattr(claim169, "decode_unverified"))
        except ImportError:
            self.skipTest("claim169 library not installed")

    def test_build_claim169_input(self):
        """Test building Claim169Input from attribute mappings."""
        if not CLAIM169_AVAILABLE:
            self.skipTest("claim169 library not installed")

        claim_input = self.service._build_claim169_input(self.partner)

        # Check that full_name is set (from default mapping)
        self.assertEqual(claim_input.full_name, "John Doe")

    def test_build_cwt_meta_input(self):
        """Test building CwtMetaInput from issuer config."""
        if not CLAIM169_AVAILABLE:
            self.skipTest("claim169 library not installed")

        cwt_meta = self.service._build_cwt_meta_input(self.issuer_config)

        self.assertEqual(cwt_meta.issuer, "did:example:test-issuer")
        self.assertTrue(cwt_meta.expires_at > cwt_meta.issued_at)

    def test_get_signing_algorithm_ed25519(self):
        """Test algorithm detection for Ed25519 key."""
        algorithm = self.service._get_signing_algorithm(self.signing_key)
        self.assertEqual(algorithm, "EdDSA")

    def test_get_signing_algorithm_ec_p256(self):
        """Test algorithm detection for EC P-256 key."""
        ec_key = self.env["spp.asymmetric.key"].create(
            {
                "name": "Test EC Key",
                "key_type": "ec",
                "curve": "P-256",
                "storage_mode": "local",
            }
        )
        ec_key.generate_key_pair()

        algorithm = self.service._get_signing_algorithm(ec_key)
        self.assertEqual(algorithm, "ES256")

    def test_get_signing_algorithm_rsa_unsupported(self):
        """Test that RSA keys are not supported."""
        rsa_key = self.env["spp.asymmetric.key"].create(
            {
                "name": "Test RSA Key",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        rsa_key.generate_key_pair()

        with self.assertRaises(UserError) as context:
            self.service._get_signing_algorithm(rsa_key)

        self.assertIn("RSA", str(context.exception))


class TestIssuerConfig(TestClaim169Base):
    """Test issuer configuration."""

    def test_issuer_config_validation(self):
        """Test issuer configuration validation."""
        # Test validity days validation
        with self.assertRaises(ValidationError):
            self.env["spp.claim169.issuer.config"].create(
                {
                    "name": "Invalid Issuer",
                    "issuer_id": "did:example:invalid",
                    "signing_key_id": self.signing_key.id,
                    "default_validity_days": 0,  # Invalid
                }
            )

    def test_unique_default_issuer(self):
        """Test only one default issuer per company."""
        with self.assertRaises(ValidationError):
            self.env["spp.claim169.issuer.config"].create(
                {
                    "name": "Second Default",
                    "issuer_id": "did:example:second",
                    "signing_key_id": self.signing_key.id,
                    "is_default": True,  # Conflict with existing default
                }
            )


class TestCredential(TestClaim169Base):
    """Test credential functionality."""

    def test_credential_creation(self):
        """Test credential record creation."""
        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
            }
        )

        self.assertTrue(credential.name)
        self.assertNotEqual(credential.name, "New")
        self.assertEqual(credential.status, "active")

    def test_credential_expiration(self):
        """Test credential expiration status."""
        # Create expired credential
        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now() - timedelta(days=400),
                "expires_at": datetime.now() - timedelta(days=35),
            }
        )

        self.assertEqual(credential.status, "expired")

    def test_credential_revocation(self):
        """Test credential revocation."""
        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
            }
        )

        # Revoke
        credential.action_revoke()

        self.assertEqual(credential.status, "revoked")
        self.assertTrue(credential.revoked_at)
        self.assertTrue(credential.revoked_by_id)

    def test_credential_double_revocation(self):
        """Test that revoked credentials cannot be revoked again."""
        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
            }
        )

        credential.action_revoke()

        with self.assertRaises(UserError):
            credential.action_revoke()

    def test_credential_hash_from_cwt_bytes(self):
        """Test credential hash is computed from CWT bytes (legacy)."""
        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
                "cwt_bytes": base64.b64encode(b"test_cwt_data"),
            }
        )

        self.assertTrue(credential.credential_hash)
        self.assertEqual(len(credential.credential_hash), 64)  # SHA256 hex length

    def test_credential_hash_from_qr_data(self):
        """Test credential hash is computed from QR data (claim169 library)."""
        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
                "qr_data": "6BFA80630FFWGWG8CKFRDG80AF3MWEW9E0G7W",
            }
        )

        self.assertTrue(credential.credential_hash)
        self.assertEqual(len(credential.credential_hash), 64)  # SHA256 hex length

    def test_credential_validity_dates(self):
        """Test credential validity date constraints."""
        with self.assertRaises(ValidationError):
            self.env["spp.claim169.credential"].create(
                {
                    "partner_id": self.partner.id,
                    "issuer_config_id": self.issuer_config.id,
                    "issued_at": datetime.now(),
                    "expires_at": datetime.now() - timedelta(days=1),  # Before issuance
                }
            )


class TestCredentialGeneration(TestClaim169Base):
    """Test full credential generation flow with claim169 library."""

    def test_generate_cwt_for_partner(self):
        """Test generating a signed credential for a partner."""
        try:
            import claim169
        except ImportError:
            self.skipTest("claim169 library not installed")

        cwt_bytes, qr_data = self.service.generate_cwt_for_partner(
            self.partner.id, self.issuer_config.id
        )

        # cwt_bytes should be None (library handles encoding internally)
        self.assertIsNone(cwt_bytes)

        # qr_data should be a Base45-encoded string
        self.assertIsInstance(qr_data, str)
        self.assertGreater(len(qr_data), 0)

    def test_generate_credential_full_flow(self):
        """Test full credential generation and storage."""
        try:
            import claim169
        except ImportError:
            self.skipTest("claim169 library not installed")

        credential = self.env["spp.claim169.credential"].create(
            {
                "partner_id": self.partner.id,
                "issuer_config_id": self.issuer_config.id,
                "issued_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
            }
        )

        # Generate the credential
        credential.generate_credential()

        # Check that qr_data was populated
        self.assertTrue(credential.qr_data)
        self.assertGreater(len(credential.qr_data), 0)

        # Check that QR image was generated
        self.assertTrue(credential.qr_image)

        # Check that hash was computed
        self.assertTrue(credential.credential_hash)

    def test_decode_from_qr(self):
        """Test decoding QR data back to claims."""
        try:
            import claim169
        except ImportError:
            self.skipTest("claim169 library not installed")

        # Generate a credential
        cwt_bytes, qr_data = self.service.generate_cwt_for_partner(
            self.partner.id, self.issuer_config.id
        )

        # Decode the QR data (unverified)
        claims = self.service.decode_from_qr(qr_data)

        # Should return a dictionary with claim data
        self.assertIsInstance(claims, dict)
        # Should contain full_name from the partner
        self.assertEqual(claims.get("full_name"), "John Doe")

    def test_verify_credential(self):
        """Test credential verification with signature check."""
        try:
            import claim169
        except ImportError:
            self.skipTest("claim169 library not installed")

        # Generate a credential
        cwt_bytes, qr_data = self.service.generate_cwt_for_partner(
            self.partner.id, self.issuer_config.id
        )

        # Verify the credential using the same key
        result = self.service.verify_credential(qr_data, self.signing_key.id)

        # Should be valid
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])
        self.assertIsInstance(result["claims"], dict)

    def test_verify_credential_wrong_key(self):
        """Test credential verification fails with wrong key."""
        try:
            import claim169
        except ImportError:
            self.skipTest("claim169 library not installed")

        # Generate a credential
        cwt_bytes, qr_data = self.service.generate_cwt_for_partner(
            self.partner.id, self.issuer_config.id
        )

        # Create a different key for verification
        other_key = self.env["spp.asymmetric.key"].create(
            {
                "name": "Other Key",
                "key_type": "ed25519",
                "storage_mode": "local",
            }
        )
        other_key.generate_key_pair()

        # Verify with wrong key - should fail
        result = self.service.verify_credential(qr_data, other_key.id)

        # Should not be valid
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"])


class TestWizard(TestClaim169Base):
    """Test QR generation wizard."""

    def test_wizard_default_get(self):
        """Test wizard default values from context."""
        wizard = (
            self.env["spp.claim169.generate.qr.wizard"]
            .with_context(
                active_model="res.partner",
                active_ids=[self.partner.id],
            )
            .create({})
        )

        self.assertIn(self.partner, wizard.partner_ids)
        self.assertEqual(wizard.issuer_config_id, self.issuer_config)

    def test_wizard_partner_count(self):
        """Test wizard partner count computation."""
        wizard = self.env["spp.claim169.generate.qr.wizard"].create(
            {
                "partner_ids": [(6, 0, [self.partner.id, self.partner2.id])],
                "issuer_config_id": self.issuer_config.id,
            }
        )

        self.assertEqual(wizard.partner_count, 2)
