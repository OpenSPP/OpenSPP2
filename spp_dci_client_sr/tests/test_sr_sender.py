# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.sr.sender model."""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSRSender(TransactionCase):
    """Test cases for SR Sender model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRSender = cls.env["spp.dci.sr.sender"]

    def test_create_sr_sender(self):
        """Test creating SR sender record."""
        sender = self.SRSender.create(
            {
                "name": "Test Social Registry",
                "sender_id": "SR001",
                "algorithm": "ed25519",
            }
        )
        self.assertEqual(sender.name, "Test Social Registry")
        self.assertEqual(sender.sender_id, "SR001")
        self.assertEqual(sender.algorithm, "ed25519")
        self.assertTrue(sender.active)

    def test_create_sr_sender_with_public_key(self):
        """Test creating SR sender with PEM public key."""
        public_key_pem = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAGb9F2CMM8wnM7wQTmPTo2HKrVsc0YwXPKQMKLX5rJ6g=
-----END PUBLIC KEY-----"""

        sender = self.SRSender.create(
            {
                "name": "Test SR with Key",
                "sender_id": "SR002",
                "algorithm": "ed25519",
                "public_key": public_key_pem,
            }
        )
        self.assertIn("-----BEGIN PUBLIC KEY-----", sender.public_key)

    def test_get_verifier_without_public_key(self):
        """Test get_verifier raises ValidationError when no public key configured."""
        sender = self.SRSender.create(
            {
                "name": "No Key SR",
                "sender_id": "SR003",
                "algorithm": "ed25519",
            }
        )
        with self.assertRaises(ValidationError):
            sender.get_verifier()

    def test_get_verifier_returns_real_verifier(self):
        """get_verifier() must successfully import DCIVerifier and return an instance.

        Regression: sr_sender previously imported from a non-existent
        ``odoo.addons.spp_dci.crypto`` path, so this method always raised
        ImportError. Exercising the real code path (no mock) catches that.
        """
        from odoo.addons.spp_dci.services.signing import DCIVerifier

        public_key_pem = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAGb9F2CMM8wnM7wQTmPTo2HKrVsc0YwXPKQMKLX5rJ6g=
-----END PUBLIC KEY-----"""

        sender = self.SRSender.create(
            {
                "name": "Real Verifier SR",
                "sender_id": "SR004",
                "algorithm": "ed25519",
                "public_key": public_key_pem,
            }
        )
        verifier = sender.get_verifier()
        self.assertIsInstance(verifier, DCIVerifier)
        self.assertEqual(verifier.algorithm, "ed25519")

    def test_get_verifier_with_valid_key(self):
        """get_verifier() instantiates DCIVerifier with the configured algorithm."""
        public_key_pem = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAGb9F2CMM8wnM7wQTmPTo2HKrVsc0YwXPKQMKLX5rJ6g=
-----END PUBLIC KEY-----"""

        sender = self.SRSender.create(
            {
                "name": "Valid Key SR",
                "sender_id": "SR004a",
                "algorithm": "ed25519",
                "public_key": public_key_pem,
            }
        )
        with patch("odoo.addons.spp_dci.services.signing.DCIVerifier") as mock_verifier:
            sender.get_verifier()
            mock_verifier.assert_called_once_with(
                algorithm="ed25519",
                public_key=public_key_pem.encode("utf-8"),
            )

    def test_algorithm_enum_matches_sibling_senders(self):
        """Algorithm selection must match crvs/dr/ibr/server senders.

        Regression: sr_sender shipped with capitalized keys ('Ed25519',
        'RSA-SHA256', 'ES256') incompatible with DCIVerifier (lowercase
        'ed25519') and with the algorithm strings used by all other senders.
        """
        field = self.SRSender._fields["algorithm"]
        keys = sorted(k for k, _label in field.selection)
        self.assertEqual(keys, ["ed25519", "rs256"])

    def test_public_key_validation(self):
        """Test that non-PEM public key raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.SRSender.create(
                {
                    "name": "Invalid Key SR",
                    "sender_id": "SR005",
                    "algorithm": "ed25519",
                    "public_key": "not_a_valid_key",
                }
            )

    def test_sender_id_unique(self):
        """Test sender_id uniqueness constraint."""
        self.SRSender.create(
            {
                "name": "First SR",
                "sender_id": "SR_UNIQUE",
            }
        )
        with self.assertRaises(Exception):
            self.SRSender.create(
                {
                    "name": "Second SR",
                    "sender_id": "SR_UNIQUE",
                }
            )

    def test_toggle_active(self):
        """Test archiving/unarchiving sender."""
        sender = self.SRSender.create(
            {
                "name": "Toggle Test SR",
                "sender_id": "SR006",
            }
        )
        self.assertTrue(sender.active)

        sender.toggle_active()
        self.assertFalse(sender.active)

        sender.toggle_active()
        self.assertTrue(sender.active)

    def test_action_test_connection_no_url(self):
        """Test connection test with no URL configured."""
        sender = self.SRSender.create(
            {
                "name": "No URL SR",
                "sender_id": "SR007",
            }
        )

        result = sender.action_test_connection()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "warning")

    @patch("odoo.addons.spp_dci_client_sr.services.SRService")
    def test_action_test_connection_success(self, mock_service_class):
        """Test successful connection test."""
        mock_service = mock_service_class.return_value
        mock_service.check_connection.return_value = True

        sender = self.SRSender.create(
            {
                "name": "Connection Test SR",
                "sender_id": "SR008",
                "base_url": "https://sr.example.org",
            }
        )

        result = sender.action_test_connection()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "success")

    @patch("odoo.addons.spp_dci_client_sr.services.SRService")
    def test_action_test_connection_failure(self, mock_service_class):
        """Test failed connection test."""
        mock_service_class.side_effect = Exception("Connection failed")

        sender = self.SRSender.create(
            {
                "name": "Fail Connection SR",
                "sender_id": "SR009",
                "base_url": "https://sr.invalid.org",
            }
        )

        result = sender.action_test_connection()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "danger")
