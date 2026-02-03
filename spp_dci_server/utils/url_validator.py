# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""URL validation utilities for DCI callback URLs.

Prevents SSRF (Server-Side Request Forgery) attacks by validating
callback URLs before making requests.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Private/internal IP ranges that should never be used as callback targets
BLOCKED_IP_RANGES = [
    # Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    # Private networks (RFC 1918)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Link-local
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    # Cloud metadata endpoints
    ipaddress.ip_network("169.254.169.254/32"),  # AWS/GCP/Azure metadata
    # Documentation ranges (should never be routable)
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
]

# Blocked hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
}

# Blocked ports (common internal services)
BLOCKED_PORTS = {
    22,  # SSH
    23,  # Telnet
    25,  # SMTP
    53,  # DNS
    110,  # POP3
    143,  # IMAP
    389,  # LDAP
    445,  # SMB
    3306,  # MySQL
    5432,  # PostgreSQL
    6379,  # Redis
    8069,  # Odoo (internal)
    27017,  # MongoDB
}


def is_ip_blocked(ip_str: str) -> bool:
    """Check if an IP address is in a blocked range.

    Args:
        ip_str: IP address string

    Returns:
        True if IP is blocked, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in BLOCKED_IP_RANGES:
            if ip in network:
                return True
        return False
    except ValueError:
        # Invalid IP address format
        return False


def validate_callback_url(url: str, require_https: bool = True, skip_ip_check: bool = False) -> str:
    """Validate a callback URL for SSRF protection.

    Args:
        url: The URL to validate
        require_https: If True, only HTTPS URLs are allowed (recommended for production)
        skip_ip_check: If True, skip IP address blocking (DANGEROUS - only for testing)

    Returns:
        The validated URL (normalized)

    Raises:
        ValidationError: If the URL is invalid or blocked
    """
    if not url:
        raise ValidationError("Callback URL is required")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}") from e

    # Check scheme
    if require_https:
        if parsed.scheme != "https":
            raise ValidationError("Callback URL must use HTTPS protocol for security. " f"Got: {parsed.scheme}://")
    else:
        if parsed.scheme not in ("http", "https"):
            raise ValidationError(f"Callback URL must use HTTP or HTTPS protocol. Got: {parsed.scheme}://")

    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("Callback URL must include a hostname")

    # Normalize hostname
    hostname = hostname.lower()

    # Check blocked hostnames
    if hostname in BLOCKED_HOSTNAMES:
        raise ValidationError(f"Callback URL hostname '{hostname}' is blocked for security reasons")

    # Check port
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port in BLOCKED_PORTS:
        raise ValidationError(f"Callback URL port {port} is blocked for security reasons")

    # Resolve hostname and check IP
    if skip_ip_check:
        _logger.warning(
            "SECURITY WARNING: IP address check SKIPPED for callback URL %s. "
            "This should only be used in testing environments!",
            url,
        )
    else:
        try:
            # Get all IP addresses for the hostname
            addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                if is_ip_blocked(ip_str):
                    _logger.warning(
                        "Callback URL %s resolves to blocked IP %s",
                        url,
                        ip_str,
                    )
                    raise ValidationError(
                        "Callback URL resolves to a blocked IP address range. "
                        "Internal/private IPs are not allowed for security reasons."
                    )
        except socket.gaierror as e:
            # DNS resolution failed - this could be legitimate (DNS not available)
            # or could be an attack. Log and allow with warning.
            _logger.warning(
                "Could not resolve callback URL hostname %s: %s. " "Proceeding with caution.",
                hostname,
                str(e),
            )

    _logger.debug("Callback URL validated: %s", url)
    return url


def validate_callback_url_permissive(url: str) -> str:
    """Validate callback URL with permissive settings (allow HTTP).

    Use this only in development/testing environments.

    Args:
        url: The URL to validate

    Returns:
        The validated URL

    Raises:
        ValidationError: If the URL is invalid or blocked
    """
    return validate_callback_url(url, require_https=False)
