# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Remove compliance data sources that still hold the old shared bearer token.

The 19.0.1.0.1 migration cleared only the ``ir.config_parameter`` copy of the
well-known token ``compliance-test-api-key-12345``. Earlier versions also
created an ``spp.dci.data.source`` record carrying that token in its own
``bearer_token`` column, which the trigger controller would keep using once the
compliance gate was re-enabled - re-exposing the shared secret over the
``auth='none'`` routes on upgraded databases.

Delete any such retained record so the controller falls back to its fail-closed
create path (which requires an operator-configured token). Records an operator
has re-keyed with a real token are left untouched.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    removed = env["spp.dci.data.source"]._purge_default_compliance_bearer_token()
    if removed:
        _logger.warning(
            "Removed %d DCI compliance data source(s) that still held the default bearer token. "
            "Set 'dci.client_compliance.bearer_token' before re-enabling the trigger endpoints.",
            removed,
        )
