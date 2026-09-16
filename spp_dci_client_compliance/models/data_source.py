# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extension to spp.dci.data.source for compliance testing."""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Well-known bearer token that earlier module versions (19.0.1.0.0) shipped as
# the default for the compliance test data source. It is public, so any data
# source still holding it must never be used to authenticate outbound requests.
DEFAULT_COMPLIANCE_BEARER_TOKEN = "compliance-test-api-key-12345"


class DCIDataSourceCompliance(models.Model):
    """Add compliance testing flag to DCI data sources."""

    _inherit = "spp.dci.data.source"

    is_compliance_test = fields.Boolean(
        string="Compliance Test",
        default=False,
        help="Mark this data source as used for DCI compliance testing. "
        "Only one data source should have this flag enabled.",
    )

    @api.model
    def _purge_default_compliance_bearer_token(self):
        """Delete data sources that still hold the well-known default token.

        Earlier module versions created a compliance data source carrying
        ``DEFAULT_COMPLIANCE_BEARER_TOKEN``. The 19.0.1.0.2 post-migration
        calls this to remove any such retained record so the trigger
        controller falls back to its fail-closed create path (which requires
        an operator-configured token). Records an operator has re-keyed with a
        real token are matched on the token value alone, so they are left
        untouched.

        Returns:
            int: number of data source records removed.
        """
        # sudo(): bearer_token is field-level restricted to base.group_system;
        # this maintenance sweep must see and remove records regardless of the
        # calling user. Scope is limited to the exact known public secret.
        # active_test=False: archived records still hold the token in their
        # bearer_token column and remain usable by non-controller consumers
        # (and readable at rest), so they must be purged too.
        # nosemgrep: odoo-sudo-without-context
        records = self.sudo().with_context(active_test=False)
        stale = records.search([("bearer_token", "=", DEFAULT_COMPLIANCE_BEARER_TOKEN)])
        for record in stale:
            _logger.warning(
                "Removing DCI compliance data source %r that still held the default bearer token.",
                record.code,
            )
        count = len(stale)
        stale.unlink()
        return count
