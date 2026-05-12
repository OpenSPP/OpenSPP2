# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Trusted external RS256 token issuer.

A record represents one external Identity Provider whose RS256-signed tokens
the bridge will accept. The bridge looks the record up by the JWT `iss` claim
and uses either its configured JWKS endpoint or its static public key to
verify the signature.

The internal `openspp-api-v2` issuer is NOT represented here — it remains
hard-wired to the spp_oauth key store.
"""

import logging
from urllib.parse import urlparse

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Whitelist of JWT signing algorithms allowed for external issuers.
# Symmetric algorithms (HS*) are excluded — they would let the bridge accept
# tokens signed with a shared secret, which is incompatible with the trust
# model here. `none` is excluded for obvious reasons.
ALLOWED_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"})

# Localhost hostnames where http:// (no TLS) is acceptable for dev IdPs.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class SppOAuthIssuer(models.Model):
    _name = "spp.oauth.issuer"
    _description = "Trusted External OAuth Issuer"
    _order = "name"

    name = fields.Char(required=True, help="Display name, e.g. 'Org Keycloak'.")
    issuer = fields.Char(
        required=True,
        help="Exact value expected in the JWT `iss` claim. Tokens are routed to "
        "this verifier when their `iss` matches.",
    )
    audience = fields.Char(
        required=True,
        help="Expected JWT `aud` claim. Tokens whose audience does not match are rejected.",
    )
    key_source = fields.Selection(
        selection=[
            ("jwks_uri", "JWKS URI"),
            ("public_key", "Static Public Key (PEM)"),
        ],
        required=True,
        default="jwks_uri",
    )
    jwks_uri = fields.Char(help="URL of the IdP's JWKS endpoint. Required when key source is JWKS.")
    public_key = fields.Text(help="PEM-encoded RSA or EC public key. Required when key source is Static Public Key.")
    algorithms = fields.Char(
        required=True,
        default="RS256",
        help="Comma-separated list of JWT algorithms accepted from this issuer. Allowed values: {}".format(
            ", ".join(sorted(ALLOWED_ALGORITHMS))
        ),
    )
    client_claim = fields.Char(
        required=True,
        default="client_id",
        help="Name of the JWT claim whose value is looked up against "
        "spp.api.client.client_id to resolve the calling client.",
    )
    jwks_cache_ttl_seconds = fields.Integer(
        default=3600,
        help="How long the JWKS response is cached in process memory (seconds).",
    )
    http_timeout_seconds = fields.Integer(
        default=5,
        help="HTTP timeout when fetching the JWKS document (seconds).",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "issuer_unique",
            "UNIQUE(issuer)",
            "Each `iss` claim value can only map to one issuer record.",
        ),
    ]

    # ----------------------------------------------------------------- constraints
    @api.constrains("issuer")
    def _check_issuer_unique(self):
        for rec in self:
            if not rec.issuer:
                continue
            # sudo() is required so the uniqueness constraint sees all records
            # regardless of the writing user's record rules — uniqueness is a
            # global invariant, not a per-user view.
            count = self.sudo().search_count([("issuer", "=", rec.issuer)])  # nosemgrep: odoo-sudo-without-context
            if count > 1:
                raise ValidationError(_("Issuer '%s' is already registered on another record.") % rec.issuer)

    @api.constrains("key_source", "jwks_uri", "public_key")
    def _check_key_source_consistency(self):
        for rec in self:
            if rec.key_source == "jwks_uri":
                if not rec.jwks_uri:
                    raise ValidationError(_("JWKS URI is required when key source is 'JWKS URI'."))
                _validate_jwks_uri(rec.jwks_uri)
            elif rec.key_source == "public_key":
                if not rec.public_key:
                    raise ValidationError(_("Public Key (PEM) is required when key source is 'Static Public Key'."))
                _validate_public_key_pem(rec.public_key)

    @api.constrains("algorithms")
    def _check_algorithms_whitelist(self):
        for rec in self:
            if not rec.algorithms or not rec.algorithms.strip():
                raise ValidationError(_("Algorithms must not be empty."))
            algs = [a.strip() for a in rec.algorithms.split(",") if a.strip()]
            if not algs:
                raise ValidationError(_("Algorithms must not be empty."))
            bad = [a for a in algs if a not in ALLOWED_ALGORITHMS]
            if bad:
                raise ValidationError(
                    _(
                        "Algorithms %(bad)s are not allowed. Permitted: %(ok)s.",
                        bad=", ".join(bad),
                        ok=", ".join(sorted(ALLOWED_ALGORITHMS)),
                    )
                )

    @api.constrains("client_claim")
    def _check_client_claim(self):
        for rec in self:
            if not rec.client_claim or not rec.client_claim.strip():
                raise ValidationError(_("Client claim must not be empty."))

    # ----------------------------------------------------------------- write/unlink hooks
    def write(self, vals):
        # Invalidate cached PyJWKClients when issuer config changes.
        keys_that_affect_client = {
            "jwks_uri",
            "jwks_cache_ttl_seconds",
            "http_timeout_seconds",
            "active",
            "key_source",
        }
        if keys_that_affect_client & vals.keys():
            from ..tools.jwks_cache import invalidate

            invalidate(self.ids)
        return super().write(vals)

    def unlink(self):
        from ..tools.jwks_cache import invalidate

        invalidate(self.ids)
        return super().unlink()

    # ----------------------------------------------------------------- helpers
    def get_allowed_algorithms(self):
        """Return the configured algorithms list as a Python list of strings."""
        self.ensure_one()
        return [a.strip() for a in (self.algorithms or "").split(",") if a.strip()]


# ----------------------------------------------------------------- module-level validators


def _validate_jwks_uri(uri):
    """Validate JWKS URI scheme. Plain http:// only accepted for loopback hosts."""
    try:
        parsed = urlparse(uri)
    except (ValueError, AttributeError) as exc:
        raise ValidationError(_("JWKS URI is not a valid URL: %s") % uri) from exc

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError(_("JWKS URI must be an http(s) URL: %s") % uri)

    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower()
        if host not in _LOCAL_HOSTS:
            raise ValidationError(
                _("JWKS URI must use https://. Plain http:// is only allowed for loopback hosts (got %s).") % uri
            )


def _validate_public_key_pem(pem_str):
    """Validate that `pem_str` parses as a public RSA/EC key in PEM form."""
    try:
        key = load_pem_public_key(pem_str.encode("utf-8"))
    except (ValueError, UnsupportedAlgorithm, TypeError) as exc:
        raise ValidationError(_("Public Key is not a valid PEM-encoded public key: %s") % exc) from exc
    if not isinstance(key, (RSAPublicKey, EllipticCurvePublicKey)):
        raise ValidationError(_("Public Key must be an RSA or EC public key."))
