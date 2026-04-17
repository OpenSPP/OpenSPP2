# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Auto-assign system ID to registrants for API addressability."""

import logging
import uuid

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResPartnerSystemId(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign a system_id registry ID to new registrants.

        Every registrant needs at least one identifier so the API can
        address it. Identity documents (national_id, passport) may be
        added later or not at all. The system_id is a stable UUID that
        fills this gap without exposing internal database IDs.
        """
        partners = super().create(vals_list)
        self._assign_system_ids(partners)
        return partners

    def _assign_system_ids(self, partners):
        """Create system_id registry entries for registrants that lack one."""
        system_id_type = self._get_system_id_type()
        if not system_id_type:
            return

        RegistryId = self.env["spp.registry.id"].sudo()  # nosemgrep: odoo-sudo-without-context

        for partner in partners:
            if not partner.is_registrant:
                continue

            # Check if already has a system_id
            existing = RegistryId.search(
                [
                    ("partner_id", "=", partner.id),
                    ("id_type_id", "=", system_id_type.id),
                ],
                limit=1,
            )
            if existing:
                continue

            RegistryId.create(
                {
                    "partner_id": partner.id,
                    "id_type_id": system_id_type.id,
                    "value": str(uuid.uuid4()),
                }
            )

    def _get_system_id_type(self):
        """Retrieve the system_id vocabulary code, or None if not installed."""
        try:
            return self.env.ref("spp_api_v2.code_id_type_system_id")
        except ValueError:
            _logger.warning("system_id vocabulary code not found — skipping auto-assignment")
            return None
