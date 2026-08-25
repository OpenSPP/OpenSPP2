# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Hash existing plaintext API client secrets in place.

Before 19.0.2.0.0 the client secret was stored in plaintext. This migration
computes the scrypt hash for every credential that still carries a plaintext
secret and then blanks the plaintext column. Clients keep authenticating with
their unchanged secrets; only recoverability of the plaintext disappears.

Idempotent: rows that already have a hash and no plaintext are untouched.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Credential = env["spp.attendance.api.client.credential"]

    credentials = Credential.search([("client_secret", "!=", False)])
    hashed = 0
    for credential in credentials:
        vals = {"client_secret": False}
        if not credential.client_secret_hash:
            vals["client_secret_hash"] = Credential._hash_secret(credential.client_secret)
            hashed += 1
        credential.write(vals)

    _logger.info(
        "spp_attendance: hashed %d plaintext client secret(s), scrubbed %d record(s)",
        hashed,
        len(credentials),
    )
