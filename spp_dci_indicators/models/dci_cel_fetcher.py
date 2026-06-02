"""DCI CEL value fetcher.

Implements the outbound fetch for DCI-backed external CEL variables: given a
variable whose data provider is linked to a DCI Data Source, resolve each
subject's identifier, call the appropriate DCI registry service against that
Data Source, and return the computed metric values keyed by subject id.

The result is consumed by the cache manager override (see
data_cache_manager_dci.py), which stores the values in spp.data.value, so all
CEL consumers read them uniformly. The metric a variable represents is keyed
by its cel_accessor, following the <registry>.dci.<metric> convention.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Identifier-type priority when resolving a partner's identifier to send to a
# registry. Mirrors DRService._get_partner_identifier.
_IDENTIFIER_PRIORITY = ["UIN", "DRN", "NATIONAL_ID", "NID", "BRN"]


class DCICelFetcher(models.AbstractModel):
    _name = "spp.dci.cel.fetcher"
    _description = "DCI CEL Value Fetcher"

    def fetch_values(self, variable, subject_ids):
        """Fetch DCI metric values for a variable across subjects.

        Args:
            variable: spp.cel.variable (source_type='external', DCI-backed provider)
            subject_ids: list of res.partner ids

        Returns:
            dict: {subject_id: value} for subjects a value could be fetched for.
        """
        data_source = variable.external_provider_id.dci_data_source_id
        if not data_source:
            return {}

        handler = self._dci_metric_handlers().get(variable.cel_accessor)
        if not handler:
            _logger.warning(
                "No DCI fetch handler registered for accessor '%s' (variable %s)",
                variable.cel_accessor,
                variable.name,
            )
            return {}

        results = {}
        for partner in self.env["res.partner"].browse(subject_ids):
            identifier = self._get_partner_identifier(partner)
            if not identifier:
                _logger.debug("No identifier for partner %s; skipping DCI fetch", partner.id)
                continue
            id_type, id_value = identifier
            try:
                # Handlers are bound methods from _dci_metric_handlers().
                value = handler(data_source, id_type, id_value)
            except Exception as e:
                # A single subject's failure must not abort the batch.
                _logger.error(
                    "DCI fetch failed for accessor '%s' on partner %s: %s",
                    variable.cel_accessor,
                    partner.id,
                    e,
                )
                continue
            if value is not None:
                results[partner.id] = value
        return results

    def _get_partner_identifier(self, partner):
        """Resolve a (identifier_type, identifier_value) for the partner from
        its spp.registry.id records, using the registry priority order."""
        reg_ids = self.env["spp.registry.id"].search([("partner_id", "=", partner.id)])
        for id_type in _IDENTIFIER_PRIORITY:
            for reg_id in reg_ids:
                if reg_id.id_type_id.code == id_type and reg_id.value:
                    return (reg_id.id_type_id.code, reg_id.value)
        if reg_ids:
            first = reg_ids[0]
            if first.value:
                return (first.id_type_id.code, first.value)
        return None

    @api.model
    def _dci_metric_handlers(self):
        """Map a variable's cel_accessor to a handler computing its value.

        Handlers receive (self, data_source, id_type, id_value) and return the
        metric value (or None to skip). Keyed by the <registry>.dci.<metric>
        accessor convention.
        """
        return {
            "crvs.dci.is_alive": self._crvs_is_alive,
            "crvs.dci.birth_verified": self._crvs_birth_verified,
        }

    # ── CRVS handlers ────────────────────────────────────────────────────────

    def _crvs_service(self, data_source):
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        return CRVSService(self.env, data_source.code)

    def _crvs_is_alive(self, data_source, id_type, id_value):
        # Alive == no death record found in CRVS.
        return not self._crvs_service(data_source).check_death(id_type, id_value)

    def _crvs_birth_verified(self, data_source, id_type, id_value):
        return self._crvs_service(data_source).verify_birth(id_type, id_value) is not None
