"""OpenG2P FR-as-DR facade for the SPDCI demo.

The OpenG2P playground at https://partner-registry.play.openg2p.org/ exposes
a Farmer/Partner Registry (reg_type ``ns:org:RegistryType:Social``,
reg_record_type ``spdci-extensions-dci:Farmer``), not a Disability Registry.

For the demo we pretend FR is DR: querying OpenG2P for a partner's
existence in its farmer registry yields a synthetic ``has_disability``
value. The semantic is "is registered in OpenG2P" → True. The CEL surface
stays ``has_disability == true``; only this service's interpretation is
the FR-as-DR pretense.

When OpenG2P's real Disability Registry endpoint becomes available, the
migration is purely configuration:

  1. On the OpenG2P data source, set ``vendor = False`` (clear the
     OpenG2P-specific routing) and set ``base_url`` to the new DR URL.
  2. The bridge dispatcher's standard ``_handler_dr`` then uses
     ``spp_dci_client_dr.DRService``, which reads ``has_disability`` from
     the real DR record.

If the real DR endpoint preserves OpenG2P's ``idtype-value`` query quirk
and ``data.reg_records[]`` response wrapper, leave ``vendor='openg2p'``
set and extend this service to query the DR reg_record_type instead of
``Farmer``. Add a v2 selection option to the ``vendor`` field then
(``openg2p_dr``) so the dispatcher routes to a DR-specific facade.
"""

import logging

from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci.schemas import QueryType

from .openg2p_dci_client import OpenG2PDCIClient

_logger = logging.getLogger(__name__)

# OpenG2P playground reg_type / reg_record_type per the OpenAPI schema's
# DciSearchResultData example. Verified live: the server accepts these.
OPENG2P_FR_REG_TYPE = "ns:org:RegistryType:Social"
OPENG2P_FR_REG_RECORD_TYPE = "spdci-extensions-dci:Farmer"

# Identifier priority — same shape as DRService._get_partner_identifier
# so the migration to the real DR service is behaviour-preserving.
IDENTIFIER_PRIORITY = ("UIN", "DRN", "NATIONAL_ID", "NID")


class OpenG2PFRService:
    """DR-shaped facade over OpenG2P's Farmer Registry.

    Mirrors the subset of ``DRService`` that the bridge dispatcher's
    ``_handler_dr`` calls: ``__init__(env, data_source_code)`` and
    ``get_disability_status(partner)``. The dispatcher does not depend on
    any DR-specific helpers, so this class can stand in for DRService
    when the data source's ``vendor`` is set to ``openg2p``.
    """

    def __init__(self, env, data_source_code):
        self.env = env
        self.data_source_code = data_source_code
        self.data_source = env["spp.dci.data.source"].get_by_code(data_source_code)
        # registry_type is still "DR" on the OpenG2P preset's data source
        # (so the bridge dispatcher routes here through _handler_dr). We
        # do NOT validate it here — the dispatcher's vendor check is
        # already authoritative.
        self.client = OpenG2PDCIClient(
            self.data_source,
            env,
            reg_record_type=OPENG2P_FR_REG_RECORD_TYPE,
        )

    # ------------------------------------------------------------------
    # Public API — matches DRService surface used by the bridge dispatcher
    # ------------------------------------------------------------------

    def get_disability_status(self, partner) -> dict | None:
        """Return a DR-shaped dict for ``partner`` based on FR query result.

        Returns:
            dict: ``{"has_disability": True, ...}`` if the partner is found
                in OpenG2P's farmer registry (FR-as-DR pretense).
            None: if the partner has no resolvable identifier OR OpenG2P
                returned no record.

        Raises:
            UserError: If the request fails for non-not-found reasons
                (network error, bad config). Per-subject errors are caught
                by the dispatcher loop and surfaced as audit rows.
        """
        if not partner:
            raise ValidationError("Partner is required")

        identifier = self._get_partner_identifier(partner)
        if not identifier:
            _logger.warning("No suitable identifier found for partner ID=%s", partner.id)
            return None

        identifier_type, identifier_value = identifier
        _logger.info(
            "Querying OpenG2P FR for partner ID=%s using %s:%s",
            partner.id,
            identifier_type,
            identifier_value,
        )

        try:
            response = self.client.search(
                query_type=QueryType.IDTYPE_VALUE,
                query_value=f"{identifier_type}:{identifier_value}",
                registry_type=OPENG2P_FR_REG_TYPE,
                record_type=OPENG2P_FR_REG_RECORD_TYPE,
                page=1,
                page_size=1,
            )
        except Exception as e:
            _logger.error("OpenG2P FR fetch failed: %s", e, exc_info=True)
            raise UserError(f"Failed to query OpenG2P: {e}") from e

        record = self._extract_first_record(response)
        if record is None:
            return None

        # FR-as-DR pretense: presence of a farmer record => has_disability=True
        return {
            "has_disability": True,
            "source_registry": "OpenG2P (FR-as-DR demo)",
            "raw_data": record,
        }

    def is_pwd(self, partner) -> bool:
        """Boolean convenience matching DRService.is_pwd shape."""
        result = self.get_disability_status(partner)
        return bool(result and result.get("has_disability"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_partner_identifier(self, partner):
        """Return (id_type_code, id_value) for the partner. Priority order
        matches DRService so swapping back to the real DRService preserves
        which identifier is tried first.
        """
        reg_ids = self.env["spp.registry.id"].search([("partner_id", "=", partner.id)])
        for id_type in IDENTIFIER_PRIORITY:
            for reg_id in reg_ids:
                if reg_id.id_type_id.code == id_type and reg_id.value:
                    return (reg_id.id_type_id.code, reg_id.value)
        if reg_ids:
            first_id = reg_ids[0]
            if first_id.id_type_id.code and first_id.value:
                return (first_id.id_type_id.code, first_id.value)
        return None

    @staticmethod
    def _extract_first_record(response):
        """Unwrap OpenG2P's response envelope to the first registry record.

        OpenG2P returns:
            response.message.search_response[i].data.reg_records[j]

        The first matching record across the response is returned, or None
        if no records were found (REG-ERR-001 / empty search_response).
        """
        if not isinstance(response, dict):
            return None
        message = response.get("message") or {}
        search_responses = message.get("search_response") or []
        for sr in search_responses:
            data = sr.get("data") or {}
            if not isinstance(data, dict):
                continue
            reg_records = data.get("reg_records") or []
            for record in reg_records:
                if isinstance(record, dict):
                    return record
        return None
