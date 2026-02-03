# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for signature format conversion utilities."""

import unittest


class TestSignatureUtils(unittest.TestCase):
    """Test signature DER/raw ECDSA conversion utilities."""

    def test_der_to_raw_p256(self):
        """Test DER to raw conversion for P-256 signatures."""
        from ..utils.signature import der_to_raw_ecdsa

        # Example P-256 DER signature (r and s are 32 bytes each)
        # This is a valid DER-encoded ECDSA signature structure
        r_int = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0
        s_int = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A1

        # Build DER manually
        r_bytes = r_int.to_bytes(32, "big")
        s_bytes = s_int.to_bytes(32, "big")

        # DER encode: SEQUENCE { INTEGER r, INTEGER s }
        def encode_int(val_bytes):
            # Add leading zero if high bit set
            if val_bytes[0] & 0x80:
                val_bytes = b"\x00" + val_bytes
            return b"\x02" + bytes([len(val_bytes)]) + val_bytes

        r_der = encode_int(r_bytes)
        s_der = encode_int(s_bytes)
        der_sig = b"\x30" + bytes([len(r_der) + len(s_der)]) + r_der + s_der

        # Convert to raw
        raw_sig = der_to_raw_ecdsa(der_sig, "ES256")

        # Should be 64 bytes (32 + 32)
        self.assertEqual(len(raw_sig), 64)
        self.assertEqual(raw_sig[:32], r_bytes)
        self.assertEqual(raw_sig[32:], s_bytes)

    def test_raw_to_der_p256(self):
        """Test raw to DER conversion for P-256 signatures."""
        from ..utils.signature import raw_to_der_ecdsa

        # Create raw signature (r || s, each 32 bytes)
        r_bytes = bytes([0x01] * 32)
        s_bytes = bytes([0x02] * 32)
        raw_sig = r_bytes + s_bytes

        # Convert to DER
        der_sig = raw_to_der_ecdsa(raw_sig, "ES256")

        # Should start with SEQUENCE tag
        self.assertEqual(der_sig[0], 0x30)

        # Should contain two INTEGERs
        self.assertIn(b"\x02", der_sig)

    def test_roundtrip_p256(self):
        """Test DER -> raw -> DER roundtrip for P-256."""
        from ..utils.signature import der_to_raw_ecdsa, raw_to_der_ecdsa

        # Create raw signature
        r_bytes = bytes([0x7F] + [0xAB] * 31)  # High bit not set
        s_bytes = bytes([0x7F] + [0xCD] * 31)
        original_raw = r_bytes + s_bytes

        # Convert to DER then back to raw
        der_sig = raw_to_der_ecdsa(original_raw, "ES256")
        recovered_raw = der_to_raw_ecdsa(der_sig, "ES256")

        self.assertEqual(recovered_raw, original_raw)

    def test_der_to_raw_p384(self):
        """Test DER to raw conversion for P-384 signatures."""
        from ..utils.signature import der_to_raw_ecdsa

        # Create P-384 size components (48 bytes each)
        r_bytes = bytes([0x01] * 48)
        s_bytes = bytes([0x02] * 48)

        # Build DER manually
        def encode_int(val_bytes):
            if val_bytes[0] & 0x80:
                val_bytes = b"\x00" + val_bytes
            return b"\x02" + bytes([len(val_bytes)]) + val_bytes

        r_der = encode_int(r_bytes)
        s_der = encode_int(s_bytes)
        der_sig = b"\x30" + bytes([len(r_der) + len(s_der)]) + r_der + s_der

        # Convert to raw (algorithm contains "384")
        raw_sig = der_to_raw_ecdsa(der_sig, "ES384")

        # Should be 96 bytes (48 + 48)
        self.assertEqual(len(raw_sig), 96)

    def test_already_raw_passthrough(self):
        """Test that already-raw signatures pass through unchanged."""
        from ..utils.signature import der_to_raw_ecdsa

        # Raw signature (doesn't start with 0x30)
        raw_sig = bytes([0x01] * 64)

        result = der_to_raw_ecdsa(raw_sig, "ES256")
        self.assertEqual(result, raw_sig)

    def test_already_der_passthrough(self):
        """Test that already-DER signatures pass through unchanged."""
        from ..utils.signature import raw_to_der_ecdsa

        # DER signature (starts with 0x30, wrong length for raw)
        der_sig = b"\x30\x45\x02\x21" + bytes([0x00] * 33) + b"\x02\x20" + bytes([0x01] * 32)

        result = raw_to_der_ecdsa(der_sig, "ES256")
        # Wrong length for raw (64), so should pass through unchanged
        self.assertEqual(result, der_sig)

    def test_leading_zero_handling(self):
        """Test that high-bit integers get proper leading zeros in DER."""
        from ..utils.signature import raw_to_der_ecdsa

        # r has high bit set (0x80), needs leading zero in DER
        r_bytes = bytes([0x80] + [0x00] * 31)
        s_bytes = bytes([0x01] * 32)
        raw_sig = r_bytes + s_bytes

        der_sig = raw_to_der_ecdsa(raw_sig, "ES256")

        # The first INTEGER should have a leading zero
        # Structure: 0x30 len 0x02 len r_data 0x02 len s_data
        # Find first INTEGER
        self.assertEqual(der_sig[2], 0x02)  # INTEGER tag
        r_len = der_sig[3]
        self.assertEqual(r_len, 33)  # 32 bytes + 1 leading zero
        self.assertEqual(der_sig[4], 0x00)  # Leading zero
        self.assertEqual(der_sig[5], 0x80)  # Original first byte


if __name__ == "__main__":
    unittest.main()
