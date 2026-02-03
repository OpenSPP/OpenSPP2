import base64
import hashlib
import json
import re
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class DCISigner:
    """
    DCI HTTP Signature signer following draft-cavage specification.
    """

    def __init__(self, private_key: bytes, sender_id: str, key_id: str, algorithm: str = "ed25519"):
        """
        Initialize DCI signer.

        Args:
            private_key: Ed25519 private key in PEM or raw bytes format
            sender_id: Sender identifier
            key_id: Key identifier
            algorithm: Signing algorithm (default: "ed25519")
        """
        self.sender_id = sender_id
        self.key_id = key_id
        self.algorithm = algorithm

        # Load private key
        try:
            # Try loading as PEM format first
            self.private_key = serialization.load_pem_private_key(private_key, password=None)
        except Exception:
            # If that fails, assume it's raw 32-byte key
            if len(private_key) == 32:
                self.private_key = Ed25519PrivateKey.from_private_bytes(private_key)
            else:
                raise ValueError("Invalid private key format") from None

    def _compute_digest(self, content: dict) -> str:
        """
        Compute SHA-256 digest of content.

        Args:
            content: Dictionary to hash

        Returns:
            Base64 encoded SHA-256 digest
        """
        # Convert dict to JSON string (canonical, sorted keys)
        json_str = json.dumps(content, sort_keys=True, separators=(",", ":"))
        # Compute SHA-256 hash
        digest = hashlib.sha256(json_str.encode("utf-8")).digest()
        # Return base64 encoded
        return base64.b64encode(digest).decode("ascii")

    def _create_signing_string(self, created: int, expires: int, digest: str) -> str:
        """
        Create the signing string per HTTP Signature spec.

        Args:
            created: Unix timestamp when signature was created
            expires: Unix timestamp when signature expires
            digest: Base64 encoded digest

        Returns:
            Signing string
        """
        return f"(created): {created}\n(expires): {expires}\ndigest: {digest}"

    def sign(self, header: dict, message: dict) -> str:
        """
        Create HTTP signature for DCI message.

        Args:
            header: Message header
            message: Message body

        Returns:
            Signature header string
        """
        # Create timestamps
        created = int(time.time())
        expires = created + 300  # 5 minutes validity

        # Compute digest of entire message (header + message)
        full_message = {"header": header, "message": message}
        digest = self._compute_digest(full_message)

        # Create signing string
        signing_string = self._create_signing_string(created, expires, digest)

        # Sign with Ed25519
        signature_bytes = self.private_key.sign(signing_string.encode("utf-8"))
        signature_b64 = base64.b64encode(signature_bytes).decode("ascii")

        # Format signature header
        kid_id = f"{self.sender_id}|{self.key_id}|{self.algorithm}"
        signature_header = (
            f'namespace="dci", '
            f'kidId="{kid_id}", '
            f'algorithm="{self.algorithm}", '
            f'created="{created}", '
            f'expires="{expires}", '
            f'headers="(created) (expires) digest", '
            f'signature="{signature_b64}"'
        )

        return signature_header


class DCIVerifier:
    """
    DCI HTTP Signature verifier following draft-cavage specification.
    """

    def __init__(self, public_key: bytes, algorithm: str = "ed25519"):
        """
        Initialize DCI verifier.

        Args:
            public_key: Ed25519 public key in PEM or raw bytes format
            algorithm: Signing algorithm (default: "ed25519")
        """
        self.algorithm = algorithm

        # Load public key
        try:
            # Try loading as PEM format first
            self.public_key = serialization.load_pem_public_key(public_key)
        except Exception:
            # If that fails, assume it's raw 32-byte key
            if len(public_key) == 32:
                self.public_key = Ed25519PublicKey.from_public_bytes(public_key)
            else:
                raise ValueError("Invalid public key format") from None

    def _parse_signature_header(self, signature_header: str) -> dict:
        """
        Parse HTTP signature header into components.

        Args:
            signature_header: Signature header string

        Returns:
            Dictionary of signature components
        """
        components = {}

        # Parse key-value pairs
        # Pattern matches: key="value" or key=value
        pattern = r'(\w+)="([^"]+)"|(\w+)=([^\s,]+)'
        matches = re.findall(pattern, signature_header)

        for match in matches:
            if match[0]:  # Quoted value
                key, value = match[0], match[1]
            else:  # Unquoted value
                key, value = match[2], match[3]
            components[key] = value

        return components

    def verify(self, signature_header: str, header: dict, message: dict) -> bool:
        """
        Verify HTTP signature for DCI message.

        Args:
            signature_header: Signature header string
            header: Message header
            message: Message body

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Parse signature header
            sig_components = self._parse_signature_header(signature_header)

            # Validate required fields
            required_fields = ["created", "expires", "signature", "algorithm"]
            for field in required_fields:
                if field not in sig_components:
                    return False

            # Check algorithm matches
            if sig_components["algorithm"] != self.algorithm:
                return False

            # Check signature hasn't expired
            created = int(sig_components["created"])
            expires = int(sig_components["expires"])
            now = int(time.time())

            if now > expires:
                return False

            if created > now + 60:  # Allow 60 second clock skew
                return False

            # Recompute digest
            full_message = {"header": header, "message": message}
            digest = self._compute_digest(full_message)

            # Recreate signing string
            signing_string = self._create_signing_string(created, expires, digest)

            # Verify signature
            signature_bytes = base64.b64decode(sig_components["signature"])
            self.public_key.verify(signature_bytes, signing_string.encode("utf-8"))

            return True

        except Exception:
            return False

    def _compute_digest(self, content: dict) -> str:
        """
        Compute SHA-256 digest of content.

        Args:
            content: Dictionary to hash

        Returns:
            Base64 encoded SHA-256 digest
        """
        # Convert dict to JSON string (canonical, sorted keys)
        json_str = json.dumps(content, sort_keys=True, separators=(",", ":"))
        # Compute SHA-256 hash
        digest = hashlib.sha256(json_str.encode("utf-8")).digest()
        # Return base64 encoded
        return base64.b64encode(digest).decode("ascii")

    def _create_signing_string(self, created: int, expires: int, digest: str) -> str:
        """
        Create the signing string per HTTP Signature spec.

        Args:
            created: Unix timestamp when signature was created
            expires: Unix timestamp when signature expires
            digest: Base64 encoded digest

        Returns:
            Signing string
        """
        return f"(created): {created}\n(expires): {expires}\ndigest: {digest}"
