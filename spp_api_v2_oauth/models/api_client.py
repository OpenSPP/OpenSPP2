# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extends `spp.api.client` with a Trusted-Issuer link.

When set, the client can ONLY be reached by RS256 tokens issued by the linked
`spp.oauth.issuer` record. When unset, the client is "internal" and can be
reached by HS256 tokens (`spp_api_v2` /oauth/token) or by internal RS256 tokens
(/oauth/token/rs256 with `iss == openspp-api-v2`). The bridge middleware
(`auth_rs256.get_authenticated_client_rs256`) enforces this routing.

SECURITY: Without this field, an external IdP that happened to emit a claim
value matching an internal client's `client_id` would silently authenticate
as that internal client.
"""

from odoo import fields, models


class SppApiClient(models.Model):
    _inherit = "spp.api.client"

    oauth_issuer_id = fields.Many2one(
        "spp.oauth.issuer",
        string="Trusted OAuth Issuer",
        ondelete="restrict",
        help=(
            "External Identity Provider whose RS256 tokens may authenticate as this "
            "client. When set, ONLY tokens from the linked issuer can resolve to this "
            "client; the client is not reachable via internal HS256 or internal RS256 "
            "auth. Leave empty for clients used with the built-in /oauth/token and "
            "/oauth/token/rs256 endpoints."
        ),
    )
