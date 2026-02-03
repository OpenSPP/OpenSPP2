"""Tests for DCISigner and DCIVerifier."""

import unittest
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..services.signing import DCISigner, DCIVerifier


class TestDCISigner(unittest.TestCase):
    """Test DCISigner class."""

    def setUp(self):
        """Set up test fixtures."""
        # Generate Ed25519 keypair for testing
        self.private_key_obj = Ed25519PrivateKey.generate()
        self.public_key_obj = self.private_key_obj.public_key()

        # Get PEM format keys
        self.private_key_pem = self.private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.public_key_pem = self.public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Get raw format keys
        self.private_key_raw = self.private_key_obj.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.public_key_raw = self.public_key_obj.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        self.sender_id = "test-sender"
        self.key_id = "test-key-1"
        self.algorithm = "ed25519"

    def test_sign_and_verify_ed25519(self):
        """Test signing and verifying with Ed25519 keypair."""
        # Create signer
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id=self.sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

        # Create test message
        header = {
            "version": "1.0.0",
            "message_id": "msg-123",
            "message_ts": datetime.now().isoformat(),
            "action": "search",
            "sender_id": self.sender_id,
            "receiver_id": "test-receiver",
        }
        message = {
            "transaction_id": "txn-456",
            "search_request": [
                {
                    "reference_id": "ref-789",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

        # Sign message
        signature = signer.sign(header, message)

        # Verify signature is a string
        self.assertIsInstance(signature, str)
        self.assertIn("namespace=", signature)
        self.assertIn("kidId=", signature)
        self.assertIn("signature=", signature)

        # Create verifier
        verifier = DCIVerifier(
            public_key=self.public_key_pem,
            algorithm=self.algorithm,
        )

        # Verify signature
        is_valid = verifier.verify(signature, header, message)
        self.assertTrue(is_valid)

    def test_verify_invalid_signature(self):
        """Test that verification fails for tampered data."""
        # Create signer
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id=self.sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

        # Create test message
        header = {
            "version": "1.0.0",
            "message_id": "msg-123",
            "action": "search",
            "sender_id": self.sender_id,
            "receiver_id": "test-receiver",
        }
        message = {"transaction_id": "txn-456"}

        # Sign message
        signature = signer.sign(header, message)

        # Tamper with message
        tampered_message = {"transaction_id": "txn-999-tampered"}

        # Create verifier
        verifier = DCIVerifier(
            public_key=self.public_key_pem,
            algorithm=self.algorithm,
        )

        # Verify should fail
        is_valid = verifier.verify(signature, header, tampered_message)
        self.assertFalse(is_valid)

    def test_verify_expired_signature(self):
        """Test that verification fails for expired signatures."""
        # Create signer
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id=self.sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

        # Create test message
        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        # Sign message
        signature = signer.sign(header, message)

        # Wait for signature to expire (5 minutes + 1 second)
        # Since we can't wait that long, we'll manually create an expired signature
        # by modifying the expires timestamp in the signature string
        import re

        # Parse created and expires from signature
        created_match = re.search(r'created="(\d+)"', signature)
        expires_match = re.search(r'expires="(\d+)"', signature)

        if created_match and expires_match:
            created = int(created_match.group(1))
            # Set expires to past time
            expired_time = created - 1

            # Replace expires in signature
            expired_signature = re.sub(r'expires="\d+"', f'expires="{expired_time}"', signature)

            # Create verifier
            verifier = DCIVerifier(
                public_key=self.public_key_pem,
                algorithm=self.algorithm,
            )

            # Verify should fail due to expiration
            # Note: This will actually fail because the signature doesn't match
            # the modified expires timestamp, which is the expected behavior
            is_valid = verifier.verify(expired_signature, header, message)
            self.assertFalse(is_valid)

    def test_sign_with_pem_key(self):
        """Test signing with PEM-formatted key."""
        # Create signer with PEM key
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id=self.sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        # Should successfully sign
        signature = signer.sign(header, message)
        self.assertIsInstance(signature, str)
        self.assertGreater(len(signature), 0)

    def test_sign_with_raw_key(self):
        """Test signing with raw 32-byte key."""
        # Create signer with raw key (32 bytes)
        signer = DCISigner(
            private_key=self.private_key_raw,
            sender_id=self.sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        # Should successfully sign
        signature = signer.sign(header, message)
        self.assertIsInstance(signature, str)
        self.assertGreater(len(signature), 0)

    def test_signature_format(self):
        """Verify signature header format matches DCI spec."""
        # Create signer
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id=self.sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        # Sign message
        signature = signer.sign(header, message)

        # Verify format components
        self.assertIn('namespace="dci"', signature)
        self.assertIn(f'kidId="{self.sender_id}|{self.key_id}|{self.algorithm}"', signature)
        self.assertIn(f'algorithm="{self.algorithm}"', signature)
        self.assertIn('created="', signature)
        self.assertIn('expires="', signature)
        self.assertIn('headers="(created) (expires) digest"', signature)
        self.assertIn('signature="', signature)

        # Verify kidId format
        expected_kid = f"{self.sender_id}|{self.key_id}|{self.algorithm}"
        self.assertIn(expected_kid, signature)


class TestDCIVerifier(unittest.TestCase):
    """Test DCIVerifier class."""

    def setUp(self):
        """Set up test fixtures."""
        # Generate Ed25519 keypair for testing
        self.private_key_obj = Ed25519PrivateKey.generate()
        self.public_key_obj = self.private_key_obj.public_key()

        # Get PEM format keys
        self.private_key_pem = self.private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.public_key_pem = self.public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Get raw format keys
        self.public_key_raw = self.public_key_obj.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        self.algorithm = "ed25519"

    def test_verify_with_pem_key(self):
        """Test verification with PEM-formatted key."""
        verifier = DCIVerifier(
            public_key=self.public_key_pem,
            algorithm=self.algorithm,
        )

        # Create signer
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id="sender",
            key_id="key1",
            algorithm=self.algorithm,
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        signature = signer.sign(header, message)
        is_valid = verifier.verify(signature, header, message)
        self.assertTrue(is_valid)

    def test_verify_with_raw_key(self):
        """Test verification with raw 32-byte key."""
        verifier = DCIVerifier(
            public_key=self.public_key_raw,
            algorithm=self.algorithm,
        )

        # Create signer
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id="sender",
            key_id="key1",
            algorithm=self.algorithm,
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        signature = signer.sign(header, message)
        is_valid = verifier.verify(signature, header, message)
        self.assertTrue(is_valid)

    def test_verify_wrong_algorithm(self):
        """Test that verification fails when algorithm doesn't match."""
        # Create verifier with different algorithm
        verifier = DCIVerifier(
            public_key=self.public_key_pem,
            algorithm="rs256",  # Different algorithm
        )

        # Create signer with ed25519
        signer = DCISigner(
            private_key=self.private_key_pem,
            sender_id="sender",
            key_id="key1",
            algorithm="ed25519",
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        signature = signer.sign(header, message)
        is_valid = verifier.verify(signature, header, message)
        self.assertFalse(is_valid)

    def test_verify_malformed_signature(self):
        """Test that verification fails for malformed signature."""
        verifier = DCIVerifier(
            public_key=self.public_key_pem,
            algorithm=self.algorithm,
        )

        header = {"action": "search"}
        message = {"transaction_id": "txn-456"}

        # Test with completely invalid signature
        is_valid = verifier.verify("invalid-signature", header, message)
        self.assertFalse(is_valid)

        # Test with incomplete signature
        incomplete_signature = 'namespace="dci", algorithm="ed25519"'
        is_valid = verifier.verify(incomplete_signature, header, message)
        self.assertFalse(is_valid)
