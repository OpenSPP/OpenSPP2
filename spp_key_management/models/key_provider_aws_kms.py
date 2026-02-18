"""AWS KMS Key Provider.

This provider integrates with AWS Key Management Service for enterprise-grade
key management in AWS environments.

Configuration (odoo.conf):
    spp_aws_region = us-east-1
    spp_aws_access_key_id = AKIAXXXXXXXX
    spp_aws_secret_access_key = xxxxx
    spp_aws_kms_key_alias = alias/spp-encryption-key

Environment variables (alternative - recommended for AWS):
    AWS_REGION = us-east-1
    AWS_ACCESS_KEY_ID = AKIAXXXXXXXX
    AWS_SECRET_ACCESS_KEY = xxxxx
    # Or use IAM roles (EC2/ECS/Lambda) - no credentials needed
"""

import base64
import logging
import os

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import config

from ..utils.signature import der_to_raw_ecdsa, raw_to_der_ecdsa

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    _logger.warning("boto3 library not installed. AWS KMS key provider will not work.")


class AWSKMSKeyProvider(models.AbstractModel):
    """Key provider using AWS Key Management Service.

    Supports:
    - Envelope encryption (generate data keys)
    - Direct encryption/decryption via KMS
    - Automatic key rotation (managed by AWS)
    - IAM role-based authentication
    """

    _name = "spp.key.provider.aws.kms"
    _inherit = "spp.key.provider"
    _description = "AWS KMS Key Provider"

    def _get_kms_client(self):
        """Get an AWS KMS client.

        Returns:
            boto3.client: KMS client

        Raises:
            UserError: If AWS is not configured
        """
        if not BOTO3_AVAILABLE:
            raise UserError("AWS KMS integration requires the 'boto3' library. Install it with: pip install boto3")

        # Get configuration from odoo.conf or environment
        region = config.get("spp_aws_region") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

        if not region:
            raise UserError(
                "AWS region not configured. Set spp_aws_region in odoo.conf or AWS_REGION environment variable."
            )

        # Check for explicit credentials (odoo.conf takes precedence)
        access_key = config.get("spp_aws_access_key_id") or os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = config.get("spp_aws_secret_access_key") or os.environ.get("AWS_SECRET_ACCESS_KEY")

        if access_key and secret_key:
            # Use explicit credentials
            client = boto3.client(
                "kms",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Use default credential chain (IAM role, instance profile, etc.)
            client = boto3.client("kms", region_name=region)

        return client

    def _get_key_id(self, key_id):
        """Get the AWS KMS key ID or alias.

        Args:
            key_id: The logical key identifier

        Returns:
            str: The AWS KMS key ID or alias
        """
        # Check if a specific alias is configured
        alias = config.get(f"spp_aws_kms_key_{key_id}")
        if alias:
            return alias

        # Use default alias pattern
        default_alias = config.get("spp_aws_kms_key_alias", "alias/spp-encryption")
        return f"{default_alias}-{key_id}"

    def get_data_key(self, key_id, version=None):
        """Generate a data encryption key using AWS KMS.

        Uses envelope encryption: KMS generates a data key and returns
        both plaintext and encrypted versions.

        Args:
            key_id: The key identifier
            version: Ignored (AWS manages versions)

        Returns:
            bytes: The plaintext data key
        """
        client = self._get_kms_client()
        kms_key_id = self._get_key_id(key_id)

        try:
            response = client.generate_data_key(
                KeyId=kms_key_id,
                KeySpec="AES_256",
            )

            # Store the encrypted key for later re-retrieval
            self._cache_encrypted_key(key_id, response["CiphertextBlob"], kms_key_id)

            return response["Plaintext"]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NotFoundException":
                raise UserError(f"AWS KMS key not found: {kms_key_id}. Create the key in AWS KMS first.") from e
            raise UserError(f"AWS KMS error: {e}") from e

    def _cache_encrypted_key(self, key_id, encrypted_key, kms_key_id):
        """Cache the encrypted data key for later retrieval.

        Args:
            key_id: The logical key identifier
            encrypted_key: The encrypted data key (bytes)
            kms_key_id: The AWS KMS key used
        """
        EncryptionKey = self.env["spp.encryption.key"]

        # Check if key already exists
        existing = EncryptionKey.search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        encrypted_b64 = base64.b64encode(encrypted_key).decode()

        if existing:
            # Update the cached encrypted key
            existing.write(
                {
                    "encrypted_key": encrypted_b64,
                }
            )
        else:
            # Create new key record
            max_version = EncryptionKey.search(
                [
                    ("key_id", "=", key_id),
                ],
                order="version desc",
                limit=1,
            )

            new_version = (max_version.version if max_version else 0) + 1

            # Deactivate old versions
            EncryptionKey.search(
                [
                    ("key_id", "=", key_id),
                    ("is_current", "=", True),
                ]
            ).write({"is_current": False})

            EncryptionKey.create(
                {
                    "key_id": key_id,
                    "version": new_version,
                    "is_current": True,
                    "encrypted_key": encrypted_b64,
                }
            )

    def get_index_salt(self, purpose):
        """Get a salt for blind index computation.

        Generates and stores salt in database, encrypted by AWS KMS.

        Args:
            purpose: The purpose identifier for the salt

        Returns:
            bytes: The salt value
        """
        # Use database storage with KMS-encrypted keys
        salt_key_id = f"index-salt-{purpose}"

        EncryptionKey = self.env["spp.encryption.key"]
        existing = EncryptionKey.search(
            [
                ("key_id", "=", salt_key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        if existing:
            # Decrypt the stored salt
            return self._decrypt_data_key(base64.b64decode(existing.encrypted_key))

        # Generate new salt
        import secrets

        new_salt = secrets.token_bytes(32)

        # Encrypt and store
        client = self._get_kms_client()
        kms_key_id = self._get_key_id("index-salt")

        try:
            response = client.encrypt(
                KeyId=kms_key_id,
                Plaintext=new_salt,
            )
            encrypted_salt = response["CiphertextBlob"]
        except ClientError as e:
            raise UserError(f"Failed to encrypt salt with AWS KMS: {e}") from e

        EncryptionKey.create(
            {
                "key_id": salt_key_id,
                "version": 1,
                "is_current": True,
                "encrypted_key": base64.b64encode(encrypted_salt).decode(),
            }
        )

        return new_salt

    def _decrypt_data_key(self, encrypted_key):
        """Decrypt a data key using AWS KMS.

        Args:
            encrypted_key: The encrypted key (bytes)

        Returns:
            bytes: The decrypted key
        """
        client = self._get_kms_client()

        try:
            response = client.decrypt(CiphertextBlob=encrypted_key)
            return response["Plaintext"]
        except ClientError as e:
            raise UserError(f"Failed to decrypt key with AWS KMS: {e}") from e

    def rotate_key(self, key_id):
        """Request key rotation in AWS KMS.

        Note: AWS KMS automatically rotates keys annually when enabled.
        This method triggers immediate rotation for the data key.

        Args:
            key_id: The key to rotate

        Returns:
            int: The new key version
        """
        # Generate a new data key (AWS handles CMK rotation automatically)
        self.get_data_key(key_id)

        # Return the new version from our tracking
        EncryptionKey = self.env["spp.encryption.key"]
        current = EncryptionKey.search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        return current.version if current else 1

    def encrypt_with_kms(self, plaintext, key_id):
        """Encrypt data directly with AWS KMS.

        For small data only (< 4KB). For larger data, use envelope encryption.

        Args:
            plaintext: The data to encrypt (bytes)
            key_id: The key to use

        Returns:
            bytes: The ciphertext
        """
        client = self._get_kms_client()
        kms_key_id = self._get_key_id(key_id)

        try:
            response = client.encrypt(
                KeyId=kms_key_id,
                Plaintext=plaintext,
            )
            return response["CiphertextBlob"]
        except ClientError as e:
            raise UserError(f"AWS KMS encryption failed: {e}") from e

    def decrypt_with_kms(self, ciphertext):
        """Decrypt data directly with AWS KMS.

        Args:
            ciphertext: The ciphertext (bytes)

        Returns:
            bytes: The decrypted data
        """
        client = self._get_kms_client()

        try:
            response = client.decrypt(CiphertextBlob=ciphertext)
            return response["Plaintext"]
        except ClientError as e:
            raise UserError(f"AWS KMS decryption failed: {e}") from e

    # =========================================================================
    # Asymmetric Key Signing Operations (for HSM-backed signing)
    # =========================================================================

    def create_signing_key(self, key_id, key_type="ECC_NIST_P256"):
        """Create an asymmetric signing key in AWS KMS.

        Args:
            key_id: The logical key identifier (used for alias)
            key_type: AWS KMS key spec - 'ECC_NIST_P256', 'ECC_SECG_P256K1',
                      'RSA_2048', 'RSA_3072', 'RSA_4096'

        Returns:
            str: The AWS KMS key ARN
        """
        client = self._get_kms_client()
        alias_name = f"alias/spp-signing-{key_id}"

        # Check if key already exists
        try:
            response = client.describe_key(KeyId=alias_name)
            _logger.debug("AWS KMS signing key already exists: %s", alias_name)
            return response["KeyMetadata"]["Arn"]
        except ClientError as e:
            if e.response["Error"]["Code"] != "NotFoundException":
                raise UserError(f"AWS KMS error: {e}") from e

        # Map key types to AWS KMS key specs
        key_spec_map = {
            "ecdsa-p256": "ECC_NIST_P256",
            "ES256": "ECC_NIST_P256",
            "ECC_NIST_P256": "ECC_NIST_P256",
            "ecdsa-p384": "ECC_NIST_P384",
            "ES384": "ECC_NIST_P384",
            "ECC_NIST_P384": "ECC_NIST_P384",
            "ECC_SECG_P256K1": "ECC_SECG_P256K1",
            "rsa-2048": "RSA_2048",
            "RSA_2048": "RSA_2048",
            "RSA_3072": "RSA_3072",
            "RSA_4096": "RSA_4096",
        }

        # Explicitly reject Ed25519 - AWS KMS doesn't support it
        if key_type in ("ed25519", "EdDSA"):
            raise UserError(
                "AWS KMS does not support Ed25519 keys. "
                "Please use ECDSA (P-256 or P-384) keys with AWS KMS, "
                "or use HashiCorp Vault Transit which supports Ed25519."
            )

        aws_key_spec = key_spec_map.get(key_type)
        if not aws_key_spec:
            raise UserError(f"Unsupported key type for AWS KMS: {key_type}")

        # Determine key usage based on key type
        if aws_key_spec.startswith("RSA"):
            key_usage = "SIGN_VERIFY"
        else:
            key_usage = "SIGN_VERIFY"

        try:
            # Create the key
            response = client.create_key(
                KeySpec=aws_key_spec,
                KeyUsage=key_usage,
                Description=f"OpenSPP signing key: {key_id}",
                Tags=[
                    {"TagKey": "Application", "TagValue": "OpenSPP"},
                    {"TagKey": "Purpose", "TagValue": "Signing"},
                    {"TagKey": "KeyId", "TagValue": key_id},
                ],
            )
            key_arn = response["KeyMetadata"]["Arn"]
            key_id_aws = response["KeyMetadata"]["KeyId"]

            # Create alias for easier access
            client.create_alias(
                AliasName=alias_name,
                TargetKeyId=key_id_aws,
            )

            _logger.info("Created AWS KMS signing key: %s (ARN: %s)", alias_name, key_arn)
            return key_arn

        except ClientError as e:
            raise UserError(f"Failed to create AWS KMS signing key: {e}") from e

    def _get_signing_key_id(self, key_id):
        """Get the AWS KMS key ID or alias for a signing key.

        Args:
            key_id: The logical key identifier

        Returns:
            str: The AWS KMS key ID or alias
        """
        # Check for specific alias configuration
        alias = config.get(f"spp_aws_kms_signing_key_{key_id}")
        if alias:
            return alias

        return f"alias/spp-signing-{key_id}"

    def sign_with_kms(self, key_id, data, algorithm="ECDSA_SHA_256"):
        """Sign data using AWS KMS.

        The private key never leaves AWS KMS - signing happens in the HSM.

        Args:
            key_id: The signing key identifier
            data: The data to sign (bytes)
            algorithm: Signing algorithm - 'ECDSA_SHA_256', 'ECDSA_SHA_384',
                      'RSASSA_PSS_SHA_256', 'RSASSA_PKCS1_V1_5_SHA_256', etc.

        Returns:
            bytes: The signature (in raw format for ECDSA: r || s)
        """
        client = self._get_kms_client()
        kms_key_id = self._get_signing_key_id(key_id)

        # Explicitly reject Ed25519 - AWS KMS doesn't support it
        if algorithm in ("ed25519", "EdDSA"):
            raise UserError(
                "AWS KMS does not support Ed25519 signing. "
                "Please use ECDSA (P-256 or P-384) keys with AWS KMS, "
                "or use HashiCorp Vault Transit which supports Ed25519."
            )

        # Map algorithm names
        algo_map = {
            "ecdsa-p256": "ECDSA_SHA_256",
            "ES256": "ECDSA_SHA_256",
            "ecdsa-p384": "ECDSA_SHA_384",
            "ES384": "ECDSA_SHA_384",
            "ECDSA_SHA_256": "ECDSA_SHA_256",
            "ECDSA_SHA_384": "ECDSA_SHA_384",
            "RSASSA_PSS_SHA_256": "RSASSA_PSS_SHA_256",
            "RSASSA_PKCS1_V1_5_SHA_256": "RSASSA_PKCS1_V1_5_SHA_256",
        }
        aws_algorithm = algo_map.get(algorithm)
        if not aws_algorithm:
            raise UserError(f"Unsupported signing algorithm for AWS KMS: {algorithm}")

        try:
            response = client.sign(
                KeyId=kms_key_id,
                Message=data,
                MessageType="RAW",
                SigningAlgorithm=aws_algorithm,
            )

            signature = response["Signature"]

            # For ECDSA, AWS returns DER-encoded signature
            # Convert to raw format (r || s) for compatibility with claim169
            if aws_algorithm.startswith("ECDSA"):
                signature = der_to_raw_ecdsa(signature, aws_algorithm)

            return signature

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NotFoundException":
                raise UserError(f"AWS KMS signing key not found: {kms_key_id}") from e
            raise UserError(f"AWS KMS signing failed: {e}") from e

    def verify_with_kms(self, key_id, data, signature, algorithm="ECDSA_SHA_256"):
        """Verify a signature using AWS KMS.

        Args:
            key_id: The signing key identifier
            data: The original data (bytes)
            signature: The signature to verify (bytes, raw format for ECDSA)
            algorithm: Signing algorithm

        Returns:
            bool: True if signature is valid
        """
        # Explicitly reject Ed25519 - AWS KMS doesn't support it
        if algorithm in ("ed25519", "EdDSA"):
            raise UserError(
                "AWS KMS does not support Ed25519 verification. Please use ECDSA keys or HashiCorp Vault Transit."
            )

        client = self._get_kms_client()
        kms_key_id = self._get_signing_key_id(key_id)

        algo_map = {
            "ecdsa-p256": "ECDSA_SHA_256",
            "ES256": "ECDSA_SHA_256",
            "ecdsa-p384": "ECDSA_SHA_384",
            "ES384": "ECDSA_SHA_384",
            "ECDSA_SHA_256": "ECDSA_SHA_256",
            "ECDSA_SHA_384": "ECDSA_SHA_384",
        }
        aws_algorithm = algo_map.get(algorithm)
        if not aws_algorithm:
            raise UserError(f"Unsupported verification algorithm for AWS KMS: {algorithm}")

        # Convert raw signature to DER format for AWS KMS
        if aws_algorithm.startswith("ECDSA"):
            signature = raw_to_der_ecdsa(signature, aws_algorithm)

        try:
            response = client.verify(
                KeyId=kms_key_id,
                Message=data,
                MessageType="RAW",
                Signature=signature,
                SigningAlgorithm=aws_algorithm,
            )

            return response["SignatureValid"]

        except ClientError as e:
            _logger.warning("AWS KMS signature verification failed: %s", e)
            return False

    def get_public_key_from_kms(self, key_id):
        """Get the public key from an AWS KMS signing key.

        Args:
            key_id: The signing key identifier

        Returns:
            bytes: The public key in DER format
        """
        client = self._get_kms_client()
        kms_key_id = self._get_signing_key_id(key_id)

        try:
            response = client.get_public_key(KeyId=kms_key_id)
            return response["PublicKey"]
        except ClientError as e:
            raise UserError(f"Failed to get public key from AWS KMS: {e}") from e
