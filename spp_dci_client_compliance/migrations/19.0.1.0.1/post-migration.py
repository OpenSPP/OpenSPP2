# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Reset the compliance bearer token to force a fresh, non-default value.

Earlier versions of this module shipped a well-known bearer token
('compliance-test-api-key-12345') as the default value for
``dci.client_compliance.bearer_token``. Anyone who installed the module
inherited that shared secret and the trigger controller would happily
use it. Clear the parameter so the operator must set a real token (the
controller raises if it is missing).

Also default ``dci.client_compliance.enabled`` to ``'false'`` so the
endpoints stay closed until explicitly opened - but only when the
parameter is absent, so an operator's explicit choice is preserved.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Go through the ORM so the ir.config_parameter cache stays in sync.
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context

    token_param = ICP.search([("key", "=", "dci.client_compliance.bearer_token")], limit=1)
    if token_param and token_param.value == "compliance-test-api-key-12345":
        _logger.warning(
            "Resetting the default DCI compliance bearer token. "
            "Set 'dci.client_compliance.bearer_token' before re-enabling "
            "the trigger endpoints."
        )
        token_param.unlink()

    # Equivalent of INSERT ... ON CONFLICT DO NOTHING: never overwrite an
    # existing value.
    if ICP.get_param("dci.client_compliance.enabled") is False:
        ICP.set_param("dci.client_compliance.enabled", "false")
