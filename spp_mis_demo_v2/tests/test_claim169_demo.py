# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Claim 169 demo data generation."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestClaim169Demo(TransactionCase):
    """Test Claim 169 demo data generation in MIS Demo Generator.

    Note: Master key is auto-derived from database UUID, so no explicit
    key configuration is needed for tests.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up default provider for key manager (required for encryption)
        existing_default = cls.env["spp.key.provider.registry"].search(
            [("is_default", "=", True)]
        )
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

        # Create test country for locale
        cls.test_country = cls.env.ref("base.us")

        # Create a demo story registrant
        cls.demo_registrant = cls.env["res.partner"].create(
            {
                "name": "Maria Santos",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_claim169_demo_fields_exist(self):
        """Test that Claim 169 fields are added to the generator."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Claim169 Fields",
            }
        )

        # Fields should exist with default values
        self.assertTrue(hasattr(generator, "generate_claim169_demo"))
        self.assertTrue(hasattr(generator, "generate_credentials_for_stories"))
        self.assertTrue(generator.generate_claim169_demo)
        self.assertTrue(generator.generate_credentials_for_stories)

    def test_claim169_mode_defaults(self):
        """Test that demo mode presets include Claim 169 settings."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Mode Defaults",
                "demo_mode": "sales",
            }
        )
        generator._onchange_demo_mode()
        self.assertTrue(generator.generate_claim169_demo)
        self.assertTrue(generator.generate_credentials_for_stories)

        generator.demo_mode = "complete"
        generator._onchange_demo_mode()
        self.assertTrue(generator.generate_claim169_demo)
        self.assertTrue(generator.generate_credentials_for_stories)

    def test_claim169_key_and_issuer_creation(self):
        """Test that signing key and issuer config are created."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Claim169 Key/Issuer",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_change_requests": False,
                "create_fairness_analysis": False,
                "generate_grm_demo": False,
                "generate_case_demo": False,
                "generate_claim169_demo": True,
                "generate_credentials_for_stories": False,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Check signing key was created
        signing_key = self.env["spp.asymmetric.key"].search(
            [("name", "=", "Demo Claim 169 Signing Key")],
            limit=1,
        )
        self.assertTrue(signing_key, "Signing key should be created")
        self.assertEqual(signing_key.key_type, "ed25519")
        self.assertTrue(signing_key.kid, "Key ID should be generated")
        self.assertTrue(signing_key.public_key_jwk, "Public key should be stored")

        # Check issuer config was created
        issuer = self.env["spp.claim169.issuer.config"].search(
            [("name", "=", "Demo National ID")],
            limit=1,
        )
        self.assertTrue(issuer, "Issuer config should be created")
        self.assertEqual(issuer.issuer_id, "did:openspp:demo:national-id")
        self.assertEqual(issuer.signing_key_id.id, signing_key.id)
        self.assertTrue(issuer.is_default)

    def test_claim169_credential_generation(self):
        """Test that credentials are generated for demo story personas."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Claim169 Credentials",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_change_requests": False,
                "create_fairness_analysis": False,
                "generate_grm_demo": False,
                "generate_case_demo": False,
                "generate_claim169_demo": True,
                "generate_credentials_for_stories": True,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Check credential was created for demo registrant
        credential = self.env["spp.claim169.credential"].search(
            [("partner_id", "=", self.demo_registrant.id)],
            limit=1,
        )
        self.assertTrue(credential, "Credential should be created for Maria Santos")
        self.assertEqual(credential.status, "active")
        self.assertTrue(credential.qr_data, "QR data should be generated")
        # Note: cwt_bytes is None when using claim169 library (encoding is internal)
        # The credential_hash is computed from qr_data instead
        self.assertTrue(credential.credential_hash, "Credential hash should be generated")
        self.assertTrue(credential.qr_image, "QR image should be generated")

    def test_claim169_idempotent(self):
        """Test that re-running does not duplicate keys, issuers, or credentials."""
        generator_params = {
            "create_demo_programs": False,
            "enroll_demo_stories": False,
            "generate_volume": False,
            "create_cycles": False,
            "create_event_data": False,
            "create_change_requests": False,
            "create_fairness_analysis": False,
            "generate_grm_demo": False,
            "generate_case_demo": False,
            "generate_claim169_demo": True,
            "generate_credentials_for_stories": True,
            "locale_origin": self.test_country.id,
        }

        # Run twice
        generator1 = self.env["spp.mis.demo.generator"].create(
            {"name": "Idempotent Test 1", **generator_params}
        )
        generator1.action_generate()

        generator2 = self.env["spp.mis.demo.generator"].create(
            {"name": "Idempotent Test 2", **generator_params}
        )
        generator2.action_generate()

        # Should only have one signing key
        signing_keys = self.env["spp.asymmetric.key"].search(
            [("name", "=", "Demo Claim 169 Signing Key")]
        )
        self.assertEqual(len(signing_keys), 1, "Should not duplicate signing key")

        # Should only have one issuer
        issuers = self.env["spp.claim169.issuer.config"].search(
            [("name", "=", "Demo National ID")]
        )
        self.assertEqual(len(issuers), 1, "Should not duplicate issuer config")

        # Should only have one active credential per registrant
        credentials = self.env["spp.claim169.credential"].search(
            [
                ("partner_id", "=", self.demo_registrant.id),
                ("status", "=", "active"),
            ]
        )
        self.assertEqual(len(credentials), 1, "Should not duplicate credentials")

    def test_claim169_disabled(self):
        """Test that no Claim 169 data is created when disabled."""
        # Clean up any existing demo data first
        self.env["spp.asymmetric.key"].search(
            [("name", "=", "Demo Claim 169 Signing Key")]
        ).unlink()
        self.env["spp.claim169.issuer.config"].search(
            [("name", "=", "Demo National ID")]
        ).unlink()

        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Claim169 Disabled",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_change_requests": False,
                "create_fairness_analysis": False,
                "generate_grm_demo": False,
                "generate_case_demo": False,
                "generate_claim169_demo": False,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # No signing key should be created
        signing_key = self.env["spp.asymmetric.key"].search(
            [("name", "=", "Demo Claim 169 Signing Key")],
            limit=1,
        )
        self.assertFalse(signing_key, "No signing key when claim169 disabled")

        # No issuer should be created
        issuer = self.env["spp.claim169.issuer.config"].search(
            [("name", "=", "Demo National ID")],
            limit=1,
        )
        self.assertFalse(issuer, "No issuer when claim169 disabled")
