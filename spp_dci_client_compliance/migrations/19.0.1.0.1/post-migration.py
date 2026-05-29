# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Reset the compliance bearer token to force a fresh, non-default value.

Earlier versions of this module shipped a well-known bearer token
('compliance-test-api-key-12345') as the default value for
``dci.client_compliance.bearer_token``. Anyone who installed the module
inherited that shared secret and the trigger controller would happily
use it. Clear the parameter so the operator must set a real token (the
controller raises if it is missing).

Also default ``dci.client_compliance.enabled`` to ``'false'`` so the
endpoints stay closed until explicitly opened.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT value FROM ir_config_parameter
        WHERE key = 'dci.client_compliance.bearer_token'
        """
    )
    row = cr.fetchone()
    if row and row[0] == "compliance-test-api-key-12345":
        _logger.warning(
            "Resetting the default DCI compliance bearer token. "
            "Set 'dci.client_compliance.bearer_token' before re-enabling "
            "the trigger endpoints."
        )
        cr.execute(
            """
            DELETE FROM ir_config_parameter
            WHERE key = 'dci.client_compliance.bearer_token'
            """
        )

    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES ('dci.client_compliance.enabled', 'false', 1, 1, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )
