# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for URL validation and SSRF protection."""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from ..utils.url_validator import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IP_RANGES,
    BLOCKED_PORTS,
    is_ip_blocked,
    validate_callback_url,
)


class TestIsIpBlocked(TransactionCase):
    """Tests for is_ip_blocked function."""

    def test_loopback_ipv4_blocked(self):
        """Test that loopback IPv4 addresses are blocked."""
        self.assertTrue(is_ip_blocked("127.0.0.1"))
        self.assertTrue(is_ip_blocked("127.0.0.2"))
        self.assertTrue(is_ip_blocked("127.255.255.255"))

    def test_loopback_ipv6_blocked(self):
        """Test that loopback IPv6 addresses are blocked."""
        self.assertTrue(is_ip_blocked("::1"))

    def test_private_10_network_blocked(self):
        """Test that 10.0.0.0/8 private network is blocked."""
        self.assertTrue(is_ip_blocked("10.0.0.1"))
        self.assertTrue(is_ip_blocked("10.255.255.255"))

    def test_private_172_network_blocked(self):
        """Test that 172.16.0.0/12 private network is blocked."""
        self.assertTrue(is_ip_blocked("172.16.0.1"))
        self.assertTrue(is_ip_blocked("172.31.255.255"))
        # 172.32.x.x should NOT be blocked
        self.assertFalse(is_ip_blocked("172.32.0.1"))

    def test_private_192_network_blocked(self):
        """Test that 192.168.0.0/16 private network is blocked."""
        self.assertTrue(is_ip_blocked("192.168.0.1"))
        self.assertTrue(is_ip_blocked("192.168.255.255"))

    def test_aws_metadata_blocked(self):
        """Test that AWS/GCP/Azure metadata endpoint is blocked."""
        self.assertTrue(is_ip_blocked("169.254.169.254"))

    def test_link_local_blocked(self):
        """Test that link-local addresses are blocked."""
        self.assertTrue(is_ip_blocked("169.254.0.1"))
        self.assertTrue(is_ip_blocked("169.254.255.255"))

    def test_public_ip_allowed(self):
        """Test that public IPs are allowed."""
        self.assertFalse(is_ip_blocked("8.8.8.8"))
        self.assertFalse(is_ip_blocked("1.1.1.1"))
        self.assertFalse(is_ip_blocked("93.184.216.34"))

    def test_invalid_ip_returns_false(self):
        """Test that invalid IP addresses return False (not blocked)."""
        self.assertFalse(is_ip_blocked("not-an-ip"))
        self.assertFalse(is_ip_blocked(""))
        self.assertFalse(is_ip_blocked("256.256.256.256"))


class TestValidateCallbackUrl(TransactionCase):
    """Tests for validate_callback_url function."""

    def test_valid_https_url_allowed(self):
        """Test that valid HTTPS URLs are allowed."""
        url = "https://example.com/callback"
        result = validate_callback_url(url)
        self.assertEqual(result, url)

    def test_http_blocked_by_default(self):
        """Test that HTTP URLs are blocked by default (require_https=True)."""
        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("http://example.com/callback")
        self.assertIn("HTTPS", str(ctx.exception))

    def test_http_allowed_when_permissive(self):
        """Test that HTTP URLs are allowed when require_https=False."""
        url = "http://example.com/callback"
        result = validate_callback_url(url, require_https=False)
        self.assertEqual(result, url)

    def test_empty_url_rejected(self):
        """Test that empty URLs are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("")
        self.assertIn("required", str(ctx.exception))

    def test_none_url_rejected(self):
        """Test that None URLs are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url(None)
        self.assertIn("required", str(ctx.exception))

    def test_invalid_scheme_rejected(self):
        """Test that non-HTTP(S) schemes are rejected."""
        with self.assertRaises(ValidationError):
            validate_callback_url("ftp://example.com/callback", require_https=False)

        with self.assertRaises(ValidationError):
            validate_callback_url("file:///etc/passwd", require_https=False)

    def test_localhost_blocked(self):
        """Test that localhost hostnames are blocked."""
        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("https://localhost/callback")
        self.assertIn("blocked", str(ctx.exception).lower())

    def test_localhost_localdomain_blocked(self):
        """Test that localhost.localdomain is blocked."""
        with self.assertRaises(ValidationError):
            validate_callback_url("https://localhost.localdomain/callback")

    def test_metadata_google_internal_blocked(self):
        """Test that GCP metadata endpoint is blocked."""
        with self.assertRaises(ValidationError):
            validate_callback_url("https://metadata.google.internal/callback")

    def test_blocked_ports(self):
        """Test that blocked ports are rejected."""
        blocked_test_ports = [22, 3306, 5432, 6379, 8069]
        for port in blocked_test_ports:
            with self.assertRaises(ValidationError) as ctx:
                validate_callback_url(f"https://example.com:{port}/callback")
            self.assertIn("port", str(ctx.exception).lower())

    def test_allowed_ports(self):
        """Test that standard HTTP(S) ports are allowed."""
        # Port 443 (default HTTPS)
        validate_callback_url("https://example.com/callback")
        # Port 80 (default HTTP, when allowed)
        validate_callback_url("http://example.com/callback", require_https=False)
        # Non-blocked custom ports
        validate_callback_url("https://example.com:8443/callback")

    def test_missing_hostname_rejected(self):
        """Test that URLs without hostname are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("https:///callback")
        self.assertIn("hostname", str(ctx.exception).lower())

    @patch("socket.getaddrinfo")
    def test_private_ip_resolution_blocked(self, mock_getaddrinfo):
        """Test that URLs resolving to private IPs are blocked."""
        # Mock DNS resolution to return a private IP
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("10.0.0.1", 443)),
        ]

        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("https://evil-redirect.com/callback")
        self.assertIn("blocked", str(ctx.exception).lower())

    @patch("socket.getaddrinfo")
    def test_loopback_resolution_blocked(self, mock_getaddrinfo):
        """Test that URLs resolving to loopback IPs are blocked."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ]

        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("https://evil-redirect.com/callback")
        self.assertIn("blocked", str(ctx.exception).lower())

    @patch("socket.getaddrinfo")
    def test_metadata_ip_resolution_blocked(self, mock_getaddrinfo):
        """Test that URLs resolving to cloud metadata IP are blocked."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("169.254.169.254", 443)),
        ]

        with self.assertRaises(ValidationError) as ctx:
            validate_callback_url("https://evil-redirect.com/callback")
        self.assertIn("blocked", str(ctx.exception).lower())

    @patch("socket.getaddrinfo")
    def test_public_ip_resolution_allowed(self, mock_getaddrinfo):
        """Test that URLs resolving to public IPs are allowed."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ]

        url = "https://example.com/callback"
        result = validate_callback_url(url)
        self.assertEqual(result, url)

    @patch("socket.getaddrinfo")
    def test_dns_failure_logs_warning_but_allows(self, mock_getaddrinfo):
        """Test that DNS failures log warning but don't block."""
        import socket

        mock_getaddrinfo.side_effect = socket.gaierror("DNS resolution failed")

        # Should not raise - logs warning but proceeds
        url = "https://unknown-host.example.com/callback"
        result = validate_callback_url(url)
        self.assertEqual(result, url)


class TestBlockedLists(TransactionCase):
    """Tests to verify blocked lists are comprehensive."""

    def test_blocked_ip_ranges_includes_rfc1918(self):
        """Verify all RFC 1918 private ranges are blocked."""
        import ipaddress

        rfc1918_ranges = [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
        ]
        [str(net) for net in BLOCKED_IP_RANGES]
        for rfc_range in rfc1918_ranges:
            self.assertIn(
                ipaddress.ip_network(rfc_range),
                BLOCKED_IP_RANGES,
                f"RFC 1918 range {rfc_range} should be in BLOCKED_IP_RANGES",
            )

    def test_blocked_hostnames_includes_localhost(self):
        """Verify localhost variants are blocked."""
        self.assertIn("localhost", BLOCKED_HOSTNAMES)
        self.assertIn("localhost.localdomain", BLOCKED_HOSTNAMES)

    def test_blocked_hostnames_includes_cloud_metadata(self):
        """Verify cloud metadata endpoints are blocked."""
        self.assertIn("metadata.google.internal", BLOCKED_HOSTNAMES)

    def test_blocked_ports_includes_databases(self):
        """Verify common database ports are blocked."""
        db_ports = {3306, 5432, 6379, 27017}
        for port in db_ports:
            self.assertIn(
                port,
                BLOCKED_PORTS,
                f"Database port {port} should be in BLOCKED_PORTS",
            )

    def test_blocked_ports_includes_odoo(self):
        """Verify Odoo internal port is blocked."""
        self.assertIn(8069, BLOCKED_PORTS)
