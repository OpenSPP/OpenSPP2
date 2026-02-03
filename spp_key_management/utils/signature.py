# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Signature format conversion utilities.

This module provides utilities for converting between different ECDSA
signature formats used by various KMS providers.

Uses the cryptography library's decode_dss_signature and encode_dss_signature
for correct and maintainable DER parsing/encoding.
"""

import logging

from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

_logger = logging.getLogger(__name__)


def der_to_raw_ecdsa(der_signature, algorithm):
    """Convert DER-encoded ECDSA signature to raw format (r || s).

    ECDSA signatures can be encoded in two formats:
    - DER: ASN.1 structure (SEQUENCE { INTEGER r, INTEGER s })
    - Raw: Fixed-size concatenation (r || s)

    Most KMS providers (AWS, GCP) return DER format, but claim169 and
    many crypto libraries expect raw format.

    Args:
        der_signature: DER-encoded signature bytes
        algorithm: Algorithm string to determine component size.
                   Use '384' in the string for P-384 (48 bytes each),
                   otherwise P-256 (32 bytes each).

    Returns:
        bytes: Raw signature (r || s) with fixed-size components

    Example:
        >>> raw = der_to_raw_ecdsa(der_sig, "ECDSA_SHA_256")
        >>> len(raw)  # P-256: 32 + 32
        64
    """
    # Determine the size of r and s based on curve
    if "384" in str(algorithm):
        component_size = 48  # P-384
    else:
        component_size = 32  # P-256

    try:
        # Check for DER SEQUENCE tag
        if not der_signature or der_signature[0] != 0x30:
            # Not DER format, assume already raw
            return der_signature

        # Use cryptography library to decode DER signature
        r, s = decode_dss_signature(der_signature)
        return r.to_bytes(component_size, "big") + s.to_bytes(component_size, "big")

    except ValueError as e:
        _logger.warning("Failed to parse DER signature, returning as-is: %s", e)
        return der_signature


def raw_to_der_ecdsa(raw_signature, algorithm):
    """Convert raw ECDSA signature (r || s) to DER format.

    Args:
        raw_signature: Raw signature bytes (r || s concatenated)
        algorithm: Algorithm string to determine component size.
                   Use '384' in the string for P-384 (48 bytes each),
                   otherwise P-256 (32 bytes each).

    Returns:
        bytes: DER-encoded signature (ASN.1 SEQUENCE of INTEGERs)

    Example:
        >>> der = raw_to_der_ecdsa(raw_sig, "ES256")
        >>> der[0]  # SEQUENCE tag
        0x30
    """
    if "384" in str(algorithm):
        component_size = 48  # P-384
    else:
        component_size = 32  # P-256

    # Check if already in some other format
    if len(raw_signature) != component_size * 2:
        # Not raw format, assume already DER
        return raw_signature

    r = int.from_bytes(raw_signature[:component_size], "big")
    s = int.from_bytes(raw_signature[component_size:], "big")

    # Use cryptography library to encode DER signature
    return encode_dss_signature(r, s)
