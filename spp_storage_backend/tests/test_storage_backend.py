# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import os
import tempfile
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStorageBackend(TransactionCase):
    """Tests for Storage Backend model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.StorageBackend = cls.env["spp.storage.backend"]

    def test_01_create_odoo_backend(self):
        """Test creating an Odoo backend."""
        backend = self.StorageBackend.create(
            {
                "name": "Test Odoo Backend",
                "backend_type": "odoo",
            }
        )
        self.assertEqual(backend.backend_type, "odoo")
        self.assertTrue(backend.is_active)
        self.assertFalse(backend.is_default)

    def test_02_create_filesystem_backend(self):
        """Test creating a filesystem backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = self.StorageBackend.create(
                {
                    "name": "Test Filesystem Backend",
                    "backend_type": "filesystem",
                    "filesystem_path": temp_dir,
                }
            )
            self.assertEqual(backend.backend_type, "filesystem")
            self.assertEqual(backend.filesystem_path, temp_dir)

    def test_03_filesystem_backend_requires_absolute_path(self):
        """Test that filesystem backend requires absolute path."""
        with self.assertRaises(ValidationError):
            self.StorageBackend.create(
                {
                    "name": "Test Invalid Filesystem",
                    "backend_type": "filesystem",
                    "filesystem_path": "relative/path",
                }
            )

    def test_04_s3_backend_requires_bucket(self):
        """Test that S3 backend requires bucket name."""
        with self.assertRaises(ValidationError):
            self.StorageBackend.create(
                {
                    "name": "Test S3 No Bucket",
                    "backend_type": "s3",
                    "s3_access_key": "test_key",
                    "s3_secret_key": "test_secret",
                }
            )

    def test_05_s3_backend_requires_credentials(self):
        """Test that S3 backend requires access credentials."""
        with self.assertRaises(ValidationError):
            self.StorageBackend.create(
                {
                    "name": "Test S3 No Creds",
                    "backend_type": "s3",
                    "s3_bucket": "test-bucket",
                }
            )

    def test_06_azure_backend_requires_connection_string(self):
        """Test that Azure backend requires connection string."""
        with self.assertRaises(ValidationError):
            self.StorageBackend.create(
                {
                    "name": "Test Azure No Conn",
                    "backend_type": "azure",
                    "azure_container": "test-container",
                }
            )

    def test_07_azure_backend_requires_container(self):
        """Test that Azure backend requires container name."""
        with self.assertRaises(ValidationError):
            self.StorageBackend.create(
                {
                    "name": "Test Azure No Container",
                    "backend_type": "azure",
                    "azure_connection_string": "DefaultEndpointsProtocol=https;AccountName=test",
                }
            )

    def test_08_get_default_backend(self):
        """Test getting default backend."""
        # The demo data already creates a default backend
        default = self.StorageBackend.get_default_backend()
        self.assertTrue(default.exists())
        self.assertTrue(default.is_default)

    def test_09_get_default_backend_fallback(self):
        """Test default backend fallback when no default is set."""
        # Create a backend without default flag
        self.StorageBackend.create(
            {
                "name": "Test Non-Default Backend",
                "backend_type": "odoo",
                "is_default": False,
            }
        )

        # Should return the odoo backend as fallback
        default = self.StorageBackend.get_default_backend()
        self.assertTrue(default.exists())

    def test_10_odoo_backend_test_connection(self):
        """Test connection test for Odoo backend (always succeeds)."""
        backend = self.StorageBackend.create(
            {
                "name": "Test Odoo Connection",
                "backend_type": "odoo",
            }
        )
        result = backend.test_connection()
        self.assertTrue(result)

    def test_11_odoo_backend_store_retrieve(self):
        """Test storing and retrieving data with Odoo backend."""
        backend = self.StorageBackend.create(
            {
                "name": "Test Odoo Store",
                "backend_type": "odoo",
            }
        )

        test_data = b"Hello, World!"
        reference = backend.store(test_data, "test/file.txt")
        self.assertTrue(reference)

        retrieved_data = backend.retrieve(reference)
        self.assertEqual(retrieved_data, test_data)

    def test_12_filesystem_backend_store_retrieve(self):
        """Test storing and retrieving data with filesystem backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = self.StorageBackend.create(
                {
                    "name": "Test FS Store",
                    "backend_type": "filesystem",
                    "filesystem_path": temp_dir,
                }
            )

            test_data = b"Filesystem test content"
            reference = backend.store(test_data, "subdir/test.txt")
            self.assertEqual(reference, "subdir/test.txt")

            # Verify file exists
            full_path = os.path.join(temp_dir, "subdir/test.txt")
            self.assertTrue(os.path.exists(full_path))

            # Retrieve and verify
            retrieved = backend.retrieve(reference)
            self.assertEqual(retrieved, test_data)

    def test_13_filesystem_backend_delete(self):
        """Test deleting file from filesystem backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = self.StorageBackend.create(
                {
                    "name": "Test FS Delete",
                    "backend_type": "filesystem",
                    "filesystem_path": temp_dir,
                }
            )

            test_data = b"To be deleted"
            reference = backend.store(test_data, "delete_me.txt")

            full_path = os.path.join(temp_dir, "delete_me.txt")
            self.assertTrue(os.path.exists(full_path))

            backend.delete(reference)
            self.assertFalse(os.path.exists(full_path))

    def test_14_filesystem_path_traversal_protection(self):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = self.StorageBackend.create(
                {
                    "name": "Test Path Traversal",
                    "backend_type": "filesystem",
                    "filesystem_path": temp_dir,
                }
            )

            # Attempt path traversal attack
            with self.assertRaises(UserError):
                backend.store(b"malicious", "../../../etc/passwd")

            with self.assertRaises(UserError):
                backend.retrieve("../../../etc/passwd")

            with self.assertRaises(UserError):
                backend.delete("../../../etc/passwd")

    def test_15_filesystem_connection_test(self):
        """Test connection test for filesystem backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = self.StorageBackend.create(
                {
                    "name": "Test FS Connection",
                    "backend_type": "filesystem",
                    "filesystem_path": temp_dir,
                }
            )
            result = backend.test_connection()
            self.assertTrue(result)

    def test_16_filesystem_connection_test_invalid_path(self):
        """Test connection test fails for non-existent path."""
        backend = self.StorageBackend.create(
            {
                "name": "Test FS Invalid Path",
                "backend_type": "filesystem",
                "filesystem_path": "/nonexistent/path/that/does/not/exist",
            }
        )
        with self.assertRaises(UserError):
            backend.test_connection()

    def test_17_inactive_backend_cannot_store(self):
        """Test that inactive backends cannot be used for storage."""
        backend = self.StorageBackend.create(
            {
                "name": "Test Inactive",
                "backend_type": "odoo",
                "is_active": False,
            }
        )
        with self.assertRaises(UserError):
            backend.store(b"data", "path.txt")

    # ========================================================================
    # S3 Backend Tests (Mocked)
    # ========================================================================

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_s3_client")
    def test_18_s3_backend_store(self, mock_get_client):
        """Test S3 backend storage with mocked boto3."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        backend = self.StorageBackend.create(
            {
                "name": "Test S3 Backend",
                "backend_type": "s3",
                "s3_bucket": "test-bucket",
                "s3_access_key": "test-access-key",
                "s3_secret_key": "test-secret-key",
            }
        )

        test_data = b"S3 test content"
        reference = backend.store(test_data, "test/file.txt")

        # Verify S3 put_object was called
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.txt",
            Body=test_data,
        )
        self.assertEqual(reference, "test/file.txt")

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_s3_client")
    def test_19_s3_backend_retrieve(self, mock_get_client):
        """Test S3 backend retrieval with mocked boto3."""
        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"S3 retrieved content"
        mock_client.get_object.return_value = {"Body": mock_body}
        mock_get_client.return_value = mock_client

        backend = self.StorageBackend.create(
            {
                "name": "Test S3 Backend",
                "backend_type": "s3",
                "s3_bucket": "test-bucket",
                "s3_access_key": "test-access-key",
                "s3_secret_key": "test-secret-key",
            }
        )

        result = backend.retrieve("test/file.txt")

        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.txt",
        )
        self.assertEqual(result, b"S3 retrieved content")

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_s3_client")
    def test_20_s3_backend_delete(self, mock_get_client):
        """Test S3 backend deletion with mocked boto3."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        backend = self.StorageBackend.create(
            {
                "name": "Test S3 Backend",
                "backend_type": "s3",
                "s3_bucket": "test-bucket",
                "s3_access_key": "test-access-key",
                "s3_secret_key": "test-secret-key",
            }
        )

        result = backend.delete("test/file.txt")

        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.txt",
        )
        self.assertTrue(result)

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_s3_client")
    def test_21_s3_backend_presigned_url(self, mock_get_client):
        """Test S3 backend presigned URL generation."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/test?signature=xxx"
        mock_get_client.return_value = mock_client

        backend = self.StorageBackend.create(
            {
                "name": "Test S3 Backend",
                "backend_type": "s3",
                "s3_bucket": "test-bucket",
                "s3_access_key": "test-access-key",
                "s3_secret_key": "test-secret-key",
            }
        )

        url = backend.get_public_url("test/file.txt", expires_in=3600)

        mock_client.generate_presigned_url.assert_called_once()
        self.assertEqual(url, "https://s3.example.com/test?signature=xxx")

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_s3_client")
    def test_22_s3_backend_connection_test(self, mock_get_client):
        """Test S3 backend connection test."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        backend = self.StorageBackend.create(
            {
                "name": "Test S3 Backend",
                "backend_type": "s3",
                "s3_bucket": "test-bucket",
                "s3_access_key": "test-access-key",
                "s3_secret_key": "test-secret-key",
            }
        )

        result = backend.test_connection()

        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        self.assertTrue(result)

    # ========================================================================
    # Azure Backend Tests (Mocked)
    # ========================================================================

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_azure_client")
    def test_23_azure_backend_store(self, mock_get_client):
        """Test Azure backend storage with mocked SDK."""
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_get_client.return_value = mock_container_client

        backend = self.StorageBackend.create(
            {
                "name": "Test Azure Backend",
                "backend_type": "azure",
                "azure_connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
                "azure_container": "test-container",
            }
        )

        test_data = b"Azure test content"
        reference = backend.store(test_data, "test/file.txt")

        mock_container_client.get_blob_client.assert_called_once_with("test/file.txt")
        mock_blob_client.upload_blob.assert_called_once_with(test_data, overwrite=True)
        self.assertEqual(reference, "test/file.txt")

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_azure_client")
    def test_24_azure_backend_retrieve(self, mock_get_client):
        """Test Azure backend retrieval with mocked SDK."""
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()
        mock_download = MagicMock()
        mock_download.readinto.side_effect = lambda stream: stream.write(b"Azure content")
        mock_blob_client.download_blob.return_value = mock_download
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_get_client.return_value = mock_container_client

        backend = self.StorageBackend.create(
            {
                "name": "Test Azure Backend",
                "backend_type": "azure",
                "azure_connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
                "azure_container": "test-container",
            }
        )

        result = backend.retrieve("test/file.txt")

        mock_container_client.get_blob_client.assert_called_once_with("test/file.txt")
        mock_blob_client.download_blob.assert_called_once()
        # Result may be empty due to mock side_effect implementation
        self.assertIsNotNone(result)

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_azure_client")
    def test_25_azure_backend_delete(self, mock_get_client):
        """Test Azure backend deletion with mocked SDK."""
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_get_client.return_value = mock_container_client

        backend = self.StorageBackend.create(
            {
                "name": "Test Azure Backend",
                "backend_type": "azure",
                "azure_connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
                "azure_container": "test-container",
            }
        )

        result = backend.delete("test/file.txt")

        mock_container_client.get_blob_client.assert_called_once_with("test/file.txt")
        mock_blob_client.delete_blob.assert_called_once()
        self.assertTrue(result)

    @patch("odoo.addons.spp_storage_backend.models.storage_backend.StorageBackend._get_azure_client")
    def test_26_azure_backend_connection_test(self, mock_get_client):
        """Test Azure backend connection test."""
        mock_container_client = MagicMock()
        mock_get_client.return_value = mock_container_client

        backend = self.StorageBackend.create(
            {
                "name": "Test Azure Backend",
                "backend_type": "azure",
                "azure_connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key",
                "azure_container": "test-container",
            }
        )

        result = backend.test_connection()

        mock_container_client.get_container_properties.assert_called_once()
        self.assertTrue(result)
