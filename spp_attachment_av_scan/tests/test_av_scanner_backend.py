import logging
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestAVScannerBackend(TransactionCase):
    """Test cases for AV Scanner Backend model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scanner_backend = cls.env["spp.av.scanner.backend"]

    def test_create_scanner_backend(self):
        """Test creating a scanner backend."""
        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
            }
        )
        self.assertEqual(backend.name, "Test Scanner")
        self.assertEqual(backend.backend_type, "clamd_socket")
        self.assertTrue(backend.is_active)

    def test_max_file_size_constraint(self):
        """Test that max file size must be positive."""
        with self.assertRaises(ValidationError):
            self.scanner_backend.create(
                {
                    "name": "Test Scanner",
                    "backend_type": "clamd_socket",
                    "max_file_size_mb": 0,
                }
            )

    def test_scan_timeout_constraint(self):
        """Test that scan timeout must be positive."""
        with self.assertRaises(ValidationError):
            self.scanner_backend.create(
                {
                    "name": "Test Scanner",
                    "backend_type": "clamd_socket",
                    "scan_timeout_seconds": -1,
                }
            )

    def test_clamd_port_constraint(self):
        """Test that ClamAV port must be in valid range."""
        with self.assertRaises(ValidationError):
            self.scanner_backend.create(
                {
                    "name": "Test Scanner",
                    "backend_type": "clamd_network",
                    "clamd_port": 70000,  # Invalid port
                }
            )

    def test_get_active_scanner(self):
        """Test getting active scanner backend."""
        # Create inactive backend (intentionally unused - verifies active scanner returns correct one)
        self.scanner_backend.create(
            {
                "name": "Inactive Scanner",
                "backend_type": "clamd_socket",
                "is_active": False,
            }
        )

        # Create active backend
        active = self.scanner_backend.create(
            {
                "name": "Active Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
                "sequence": 5,
            }
        )

        # Should return the active scanner
        result = self.scanner_backend.get_active_scanner()
        self.assertEqual(result, active)

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_binary_clean_file(self, mock_pyclamd):
        """Test scanning a clean file."""
        # Mock ClamAV scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = None  # Clean file
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
            }
        )

        result = backend.scan_binary(b"test data", filename="test.txt")

        self.assertEqual(result["status"], "clean")
        self.assertIsNone(result["threat_name"])
        mock_scanner.scan_stream.assert_called_once()

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_binary_infected_file(self, mock_pyclamd):
        """Test scanning an infected file."""
        # Mock ClamAV scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
            }
        )

        result = backend.scan_binary(b"test virus data", filename="virus.exe")

        self.assertEqual(result["status"], "infected")
        self.assertEqual(result["threat_name"], "Eicar-Test-Signature")

    def test_scan_binary_file_too_large(self):
        """Test skipping scan for files that are too large."""
        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
                "max_file_size_mb": 1,  # 1 MB limit
            }
        )

        # Create 2 MB of data
        large_data = b"x" * (2 * 1024 * 1024)

        result = backend.scan_binary(large_data)

        self.assertEqual(result["status"], "skipped")
        self.assertIn("exceeds maximum", result["details"])

    def test_scan_binary_inactive_backend(self):
        """Test that inactive backends skip scanning."""
        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": False,
            }
        )

        result = backend.scan_binary(b"test data")

        self.assertEqual(result["status"], "skipped")
        self.assertIn("not active", result["details"])

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_test_connection_success(self, mock_pyclamd):
        """Test successful connection test."""
        # Mock ClamAV scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.version.return_value = "ClamAV 0.103.0"
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
            }
        )

        result = backend.test_connection()

        self.assertTrue(backend.last_connection_test_result)
        self.assertFalse(backend.last_connection_error)  # Odoo Char fields are False when empty
        self.assertEqual(result["type"], "ir.actions.client")

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_test_connection_failure(self, mock_pyclamd):
        """Test failed connection test."""
        # Mock ClamAV scanner to raise exception
        mock_pyclamd.ClamdUnixSocket.side_effect = Exception("Connection refused")

        backend = self.scanner_backend.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
            }
        )

        result = backend.test_connection()

        self.assertFalse(backend.last_connection_test_result)
        self.assertIsNotNone(backend.last_connection_error)
        self.assertEqual(result["params"]["type"], "danger")

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_binary_network_socket(self, mock_pyclamd):
        """Test scanning using network socket backend type."""
        # Mock ClamAV network scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = None  # Clean file
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_scanner

        backend = self.scanner_backend.create(
            {
                "name": "Network Scanner",
                "backend_type": "clamd_network",
                "clamd_host": "192.168.1.100",
                "clamd_port": 3310,
                "is_active": True,
            }
        )

        result = backend.scan_binary(b"test data", filename="test.txt")

        self.assertEqual(result["status"], "clean")
        # Verify ClamdNetworkSocket was called with correct params
        mock_pyclamd.ClamdNetworkSocket.assert_called_once_with(
            host="192.168.1.100",
            port=3310,
            timeout=backend.scan_timeout_seconds,
        )

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_network_connection_test_success(self, mock_pyclamd):
        """Test successful connection test with network socket."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.version.return_value = "ClamAV 0.105.0"
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_scanner

        backend = self.scanner_backend.create(
            {
                "name": "Network Scanner",
                "backend_type": "clamd_network",
                "clamd_host": "clamav-server",
                "clamd_port": 3310,
            }
        )

        result = backend.test_connection()

        self.assertTrue(backend.last_connection_test_result)
        self.assertEqual(result["type"], "ir.actions.client")
        mock_pyclamd.ClamdNetworkSocket.assert_called_once()

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_binary_infected_network(self, mock_pyclamd):
        """Test detecting infected file via network socket."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Win.Trojan.Generic")}
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_scanner

        backend = self.scanner_backend.create(
            {
                "name": "Network Scanner",
                "backend_type": "clamd_network",
                "is_active": True,
            }
        )

        result = backend.scan_binary(b"malicious content")

        self.assertEqual(result["status"], "infected")
        self.assertEqual(result["threat_name"], "Win.Trojan.Generic")
