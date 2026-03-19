# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import base64
import logging
import os
from datetime import UTC
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StorageBackend(models.Model):
    """Storage Backend Configuration for pluggable file storage systems."""

    _name = "spp.storage.backend"
    _description = "Storage Backend Configuration"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        help="Name of the storage backend configuration",
    )
    sequence = fields.Integer(
        default=10,
        help="Display order",
    )
    backend_type = fields.Selection(
        [
            ("odoo", "Odoo Default (Filestore/Database)"),
            ("s3", "Amazon S3 / S3-Compatible"),
            ("azure", "Azure Blob Storage"),
            ("filesystem", "External Filesystem"),
        ],
        required=True,
        default="odoo",
        help="Type of storage backend to use",
    )
    is_default = fields.Boolean(
        default=False,
        help="Use this backend as the default for new files",
    )
    is_active = fields.Boolean(
        default=True,
        help="Whether this backend is currently active",
    )

    # S3 Configuration
    s3_endpoint_url = fields.Char(
        string="S3 Endpoint URL",
        help="S3 endpoint URL (leave empty for AWS S3, set for S3-compatible services like MinIO)",
    )
    s3_bucket = fields.Char(
        string="Bucket Name",
        help="Name of the S3 bucket",
    )
    s3_access_key = fields.Char(
        string="Access Key",
        help="AWS Access Key ID or S3-compatible access key",
    )
    s3_secret_key = fields.Char(
        string="Secret Key",
        help="AWS Secret Access Key or S3-compatible secret key",
    )
    s3_region = fields.Char(
        string="Region",
        default="us-east-1",
        help="AWS region or S3-compatible region",
    )
    s3_use_ssl = fields.Boolean(
        string="Use SSL",
        default=True,
        help="Use SSL/TLS for S3 connections",
    )

    # Azure Configuration
    azure_connection_string = fields.Char(
        string="Connection String",
        help="Azure Storage connection string",
    )
    azure_container = fields.Char(
        string="Container Name",
        help="Name of the Azure Blob container",
    )

    # Filesystem Configuration
    filesystem_path = fields.Char(
        string="Base Path",
        help="Base directory path for file storage (must be absolute)",
    )

    _unique_default_backend = models.Constraint(
        "EXCLUDE (is_default WITH =) WHERE (is_default = true)",
        "Only one backend can be set as default",
    )

    @api.constrains("backend_type", "s3_bucket", "s3_access_key", "s3_secret_key")
    def _check_s3_configuration(self):
        """Validate S3 backend configuration."""
        for record in self:
            if record.backend_type == "s3":
                if not record.s3_bucket:
                    raise ValidationError(_("S3 Bucket Name is required for S3 backends."))
                if not record.s3_access_key:
                    raise ValidationError(_("S3 Access Key is required for S3 backends."))
                if not record.s3_secret_key:
                    raise ValidationError(_("S3 Secret Key is required for S3 backends."))

    @api.constrains("backend_type", "azure_connection_string", "azure_container")
    def _check_azure_configuration(self):
        """Validate Azure backend configuration."""
        for record in self:
            if record.backend_type == "azure":
                if not record.azure_connection_string:
                    raise ValidationError(_("Azure Connection String is required for Azure backends."))
                if not record.azure_container:
                    raise ValidationError(_("Azure Container Name is required for Azure backends."))

    @api.constrains("backend_type", "filesystem_path")
    def _check_filesystem_configuration(self):
        """Validate filesystem backend configuration."""
        for record in self:
            if record.backend_type == "filesystem":
                if not record.filesystem_path:
                    raise ValidationError(_("Base Path is required for filesystem backends."))
                if not os.path.isabs(record.filesystem_path):
                    raise ValidationError(_("Base Path must be an absolute path."))

    @api.model
    def get_default_backend(self):
        """
        Get the default storage backend.

        Returns:
            recordset: The default backend, or the first Odoo backend if none is set as default
        """
        default = self.search([("is_default", "=", True), ("is_active", "=", True)], limit=1)
        if not default:
            # Fallback to first active Odoo backend
            default = self.search([("backend_type", "=", "odoo"), ("is_active", "=", True)], limit=1)
        if not default:
            # Fallback to any active backend
            default = self.search([("is_active", "=", True)], limit=1)
        return default

    def store(self, binary_data, path):
        """
        Store binary data using this backend.

        Args:
            binary_data: Binary data to store (bytes)
            path: Relative path/key for the file

        Returns:
            str: Storage reference (backend-specific identifier)

        Raises:
            UserError: If storage operation fails
        """
        self.ensure_one()

        if not self.is_active:
            raise UserError(_("Cannot use inactive storage backend: %(name)s") % {"name": self.name})

        try:
            if self.backend_type == "odoo":
                return self._store_odoo(binary_data, path)
            elif self.backend_type == "s3":
                return self._store_s3(binary_data, path)
            elif self.backend_type == "azure":
                return self._store_azure(binary_data, path)
            elif self.backend_type == "filesystem":
                return self._store_filesystem(binary_data, path)
            else:
                raise UserError(_("Unsupported backend type: %(backend_type)s") % {"backend_type": self.backend_type})
        except Exception as e:
            _logger.error(
                "Storage operation failed for backend_id=%s, path=%s: %s",
                self.id,
                path,
                str(e),
            )
            raise UserError(_("Failed to store file: %(error)s") % {"error": str(e)}) from e

    def retrieve(self, reference):
        """
        Retrieve binary data from this backend.

        Args:
            reference: Storage reference returned by store()

        Returns:
            bytes: Binary data

        Raises:
            UserError: If retrieval fails
        """
        self.ensure_one()

        try:
            if self.backend_type == "odoo":
                return self._retrieve_odoo(reference)
            elif self.backend_type == "s3":
                return self._retrieve_s3(reference)
            elif self.backend_type == "azure":
                return self._retrieve_azure(reference)
            elif self.backend_type == "filesystem":
                return self._retrieve_filesystem(reference)
            else:
                raise UserError(_("Unsupported backend type: %(backend_type)s") % {"backend_type": self.backend_type})
        except Exception as e:
            _logger.error(
                "Retrieval failed for backend_id=%s, reference=%s: %s",
                self.id,
                reference,
                str(e),
            )
            raise UserError(_("Failed to retrieve file: %(error)s") % {"error": str(e)}) from e

    def delete(self, reference):
        """
        Delete file from this backend.

        Args:
            reference: Storage reference returned by store()

        Returns:
            bool: True if successful

        Raises:
            UserError: If deletion fails
        """
        self.ensure_one()

        try:
            if self.backend_type == "odoo":
                return self._delete_odoo(reference)
            elif self.backend_type == "s3":
                return self._delete_s3(reference)
            elif self.backend_type == "azure":
                return self._delete_azure(reference)
            elif self.backend_type == "filesystem":
                return self._delete_filesystem(reference)
            else:
                raise UserError(_("Unsupported backend type: %(backend_type)s") % {"backend_type": self.backend_type})
        except Exception as e:
            _logger.error(
                "Deletion failed for backend_id=%s, reference=%s: %s",
                self.id,
                reference,
                str(e),
            )
            raise UserError(_("Failed to delete file: %(error)s") % {"error": str(e)}) from e

    def get_public_url(self, reference, expires_in=3600):
        """
        Generate a public URL for accessing the file.

        Args:
            reference: Storage reference returned by store()
            expires_in: Expiration time in seconds (for signed URLs)

        Returns:
            str or None: Public URL if supported by backend, None otherwise
        """
        self.ensure_one()

        try:
            if self.backend_type == "s3":
                return self._get_s3_public_url(reference, expires_in)
            elif self.backend_type == "azure":
                return self._get_azure_public_url(reference, expires_in)
            else:
                # Odoo and filesystem backends don't support public URLs by default
                return None
        except Exception as e:
            _logger.warning(
                "Failed to generate public URL for backend_id=%s, reference=%s: %s",
                self.id,
                reference,
                str(e),
            )
            return None

    def test_connection(self):
        """
        Test the connection to the storage backend.

        Returns:
            bool: True if connection successful

        Raises:
            UserError: If connection test fails
        """
        self.ensure_one()

        try:
            if self.backend_type == "odoo":
                return self._test_odoo_connection()
            elif self.backend_type == "s3":
                return self._test_s3_connection()
            elif self.backend_type == "azure":
                return self._test_azure_connection()
            elif self.backend_type == "filesystem":
                return self._test_filesystem_connection()
            else:
                raise UserError(_("Unsupported backend type: %(backend_type)s") % {"backend_type": self.backend_type})
        except Exception as e:
            _logger.error(
                "Connection test failed for backend_id=%s: %s",
                self.id,
                str(e),
            )
            raise UserError(_("Connection test failed: %(error)s") % {"error": str(e)}) from e

    def action_test_connection(self):
        """UI action to test backend connection."""
        self.ensure_one()
        if self.test_connection():
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Connection to storage backend '%(name)s' was successful.") % {"name": self.name},
                    "type": "success",
                    "sticky": False,
                },
            }

    # ========================================================================
    # ODOO BACKEND IMPLEMENTATION
    # ========================================================================

    def _store_odoo(self, binary_data, path):
        """Store using Odoo's default filestore/database."""
        # For Odoo backend, we just return the base64-encoded data
        # The actual storage is handled by the attachment model
        return base64.b64encode(binary_data).decode("ascii")

    def _retrieve_odoo(self, reference):
        """Retrieve from Odoo's default filestore/database."""
        return base64.b64decode(reference)

    def _delete_odoo(self, reference):
        """Delete from Odoo's default storage (no-op, handled by attachment model)."""
        return True

    def _test_odoo_connection(self):
        """Test Odoo backend (always succeeds)."""
        return True

    # ========================================================================
    # S3 BACKEND IMPLEMENTATION
    # ========================================================================

    def _get_s3_client(self):
        """Get configured S3 client."""
        try:
            import boto3
        except ImportError as e:
            raise UserError(_("boto3 library is not installed. Please install it to use S3 storage.")) from e

        config = {
            "aws_access_key_id": self.s3_access_key,
            "aws_secret_access_key": self.s3_secret_key,
            "region_name": self.s3_region,
        }

        if self.s3_endpoint_url:
            config["endpoint_url"] = self.s3_endpoint_url

        if not self.s3_use_ssl:
            config["use_ssl"] = False

        return boto3.client("s3", **config)

    def _store_s3(self, binary_data, path):
        """Store file in S3."""
        client = self._get_s3_client()

        # Upload to S3
        client.put_object(
            Bucket=self.s3_bucket,
            Key=path,
            Body=binary_data,
        )

        _logger.info("File stored in S3: bucket=%s, key=%s", self.s3_bucket, path)
        return path

    def _retrieve_s3(self, reference):
        """Retrieve file from S3."""
        client = self._get_s3_client()

        response = client.get_object(
            Bucket=self.s3_bucket,
            Key=reference,
        )

        return response["Body"].read()

    def _delete_s3(self, reference):
        """Delete file from S3."""
        client = self._get_s3_client()

        client.delete_object(
            Bucket=self.s3_bucket,
            Key=reference,
        )

        _logger.info("File deleted from S3: bucket=%s, key=%s", self.s3_bucket, reference)
        return True

    def _get_s3_public_url(self, reference, expires_in):
        """Generate presigned URL for S3 object."""
        client = self._get_s3_client()

        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.s3_bucket,
                "Key": reference,
            },
            ExpiresIn=expires_in,
        )

        return url

    def _test_s3_connection(self):
        """Test S3 connection by listing buckets."""
        client = self._get_s3_client()

        # Try to head the bucket to verify access
        client.head_bucket(Bucket=self.s3_bucket)

        _logger.info("S3 connection test successful for bucket: %s", self.s3_bucket)
        return True

    # ========================================================================
    # AZURE BACKEND IMPLEMENTATION
    # ========================================================================

    def _get_azure_client(self):
        """Get configured Azure Blob client."""
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as e:
            raise UserError(
                _("azure-storage-blob library is not installed. Please install it to use Azure storage.")
            ) from e

        service_client = BlobServiceClient.from_connection_string(self.azure_connection_string)
        return service_client.get_container_client(self.azure_container)

    def _store_azure(self, binary_data, path):
        """Store file in Azure Blob Storage."""
        container_client = self._get_azure_client()
        blob_client = container_client.get_blob_client(path)

        blob_client.upload_blob(binary_data, overwrite=True)

        _logger.info("File stored in Azure: container=%s, blob=%s", self.azure_container, path)
        return path

    def _retrieve_azure(self, reference):
        """Retrieve file from Azure Blob Storage."""
        container_client = self._get_azure_client()
        blob_client = container_client.get_blob_client(reference)

        stream = BytesIO()
        blob_client.download_blob().readinto(stream)

        return stream.getvalue()

    def _delete_azure(self, reference):
        """Delete file from Azure Blob Storage."""
        container_client = self._get_azure_client()
        blob_client = container_client.get_blob_client(reference)

        blob_client.delete_blob()

        _logger.info("File deleted from Azure: container=%s, blob=%s", self.azure_container, reference)
        return True

    def _get_azure_public_url(self, reference, expires_in):
        """Generate SAS URL for Azure blob."""
        try:
            from datetime import datetime, timedelta

            from azure.storage.blob import BlobSasPermissions, generate_blob_sas
        except ImportError as e:
            raise UserError(_("azure-storage-blob library is not installed.")) from e

        container_client = self._get_azure_client()
        blob_client = container_client.get_blob_client(reference)

        # Extract account name and key from connection string
        conn_parts = dict(item.split("=", 1) for item in self.azure_connection_string.split(";") if "=" in item)
        account_name = conn_parts.get("AccountName")
        account_key = conn_parts.get("AccountKey")

        if not account_name or not account_key:
            raise UserError(_("Could not extract account credentials from connection string."))

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.azure_container,
            blob_name=reference,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in),
        )

        return f"{blob_client.url}?{sas_token}"

    def _test_azure_connection(self):
        """Test Azure connection by getting container properties."""
        container_client = self._get_azure_client()
        container_client.get_container_properties()

        _logger.info("Azure connection test successful for container: %s", self.azure_container)
        return True

    # ========================================================================
    # FILESYSTEM BACKEND IMPLEMENTATION
    # ========================================================================

    def _validate_path_within_base(self, path):
        """Ensure resolved path stays within base directory (prevent path traversal).

        Args:
            path: Relative path to validate

        Returns:
            str: Full validated path

        Raises:
            UserError: If path attempts to escape base directory
        """
        base = os.path.realpath(self.filesystem_path)
        # Join and resolve to get the real path
        full = os.path.realpath(os.path.join(base, path))
        # Ensure the resolved path starts with the base directory
        if not (full.startswith(base + os.sep) or full == base):
            _logger.warning(
                "Path traversal attempt detected: base=%s, requested=%s, resolved=%s",
                base,
                path,
                full,
            )
            raise UserError(_("Invalid path: access denied."))
        return full

    def _store_filesystem(self, binary_data, path):
        """Store file in external filesystem."""
        full_path = self._validate_path_within_base(path)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write file
        with open(full_path, "wb") as f:
            f.write(binary_data)

        _logger.info("File stored in filesystem: %s", full_path)
        return path

    def _retrieve_filesystem(self, reference):
        """Retrieve file from external filesystem."""
        full_path = self._validate_path_within_base(reference)

        if not os.path.exists(full_path):
            raise UserError(_("File not found: %(path)s") % {"path": reference})

        with open(full_path, "rb") as f:
            return f.read()

    def _delete_filesystem(self, reference):
        """Delete file from external filesystem."""
        full_path = self._validate_path_within_base(reference)

        if os.path.exists(full_path):
            os.remove(full_path)
            _logger.info("File deleted from filesystem: %s", full_path)

        return True

    def _test_filesystem_connection(self):
        """Test filesystem backend by checking path exists and is writable."""
        if not os.path.exists(self.filesystem_path):
            raise UserError(_("Path does not exist: %(path)s") % {"path": self.filesystem_path})

        if not os.path.isdir(self.filesystem_path):
            raise UserError(_("Path is not a directory: %(path)s") % {"path": self.filesystem_path})

        if not os.access(self.filesystem_path, os.W_OK):
            raise UserError(_("Path is not writable: %(path)s") % {"path": self.filesystem_path})

        _logger.info("Filesystem connection test successful: %s", self.filesystem_path)
        return True
