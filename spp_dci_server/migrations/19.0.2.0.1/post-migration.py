# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Warn operators about the bearer-token fail-closed change.

Previous versions accepted any non-empty bearer token when
``dci.api_tokens`` was unset. From 19.0.2.0.1 the middleware rejects
that case unless ``dci.api_tokens_required`` is explicitly set to
``'false'``. Existing deployments relying on the old behaviour will
start failing 401 with ``err.auth.no_tokens_configured`` until they
either configure ``dci.api_tokens`` or opt out.

We do not auto-set the opt-out for the operator on upgrade - silently
preserving the insecure default would defeat the point of the change.
We log a CRITICAL warning instead so the upgrade noise is hard to miss.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT value FROM ir_config_parameter
        WHERE key = 'dci.api_tokens'
        """
    )
    row = cr.fetchone()
    tokens = (row[0] or "").strip() if row else ""

    if tokens:
        return

    cr.execute(
        """
        SELECT value FROM ir_config_parameter
        WHERE key = 'dci.api_tokens_required'
        """
    )
    row = cr.fetchone()
    required = (row[0] or "").strip().lower() if row else ""

    if required == "false":
        return

    _logger.critical(
        "DCI bearer-token middleware is now fail-closed when "
        "'dci.api_tokens' is empty. This deployment has no tokens "
        "configured, so every bearer-authenticated DCI route will "
        "respond 401 until you either set 'dci.api_tokens' to a "
        "comma-separated list or set 'dci.api_tokens_required' to "
        "'false' (development only)."
    )
