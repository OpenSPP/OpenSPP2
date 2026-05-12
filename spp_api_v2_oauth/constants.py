# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared constants for the OAuth RS256 bridge module.

These must match the values used by spp_api_v2 in auth.py and oauth.py.
"""

JWT_AUDIENCE = "openspp"
JWT_ISSUER = "openspp-api-v2"

# Allowed clock skew (seconds) for RS256 verification. Absorbs normal NTP drift
# between OpenSPP and external IdPs. Applied to internal RS256 verification too
# for symmetry; harmless there since the issuer and verifier share a clock.
JWT_CLOCK_SKEW_LEEWAY_SECONDS = 30
