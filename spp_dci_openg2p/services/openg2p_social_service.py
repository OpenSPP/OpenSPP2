"""OpenG2P Social Registry service.

Queries OpenG2P's DCI Social Registry endpoint by `search_text` (typically
the partner's reg_id value, e.g., ``IND-NSR-0001``) and returns the raw
record dict from ``data.reg_records[0]``. The bridge dispatcher applies
the variable's ``dci_attribute_path`` to that dict — so each variable
extracts whatever field it needs (``is_poor``, ``has_dependent_under_school_age``,
etc.) without this service needing to know which.

This service replaces the earlier ``OpenG2PFRService`` (the FR-as-DR
pretense). The pretense was retired by ADR-024 once a separate
OpenSPP-DR instance became available — OpenG2P returns to its proper
role as the Social Registry.

Request shape (per the OpenG2P-provided sample, see ADR-024 §"Findings
from the OpenG2P-provided payload"):

  - query_type:    "expression"
  - query.type:    "ns:org:QueryType:expression"  (set by OpenG2PDCIClient)
  - query.value:   {"expression": {"query": {"search_text": {"$eq": <id>}}}}
  - reg_type:      "Individual"
  - reg_record_type: "Individual"
  - consent + authorize blocks attached by OpenG2PDCIClient

Response unwrap:

  response.message.search_response[0].data.reg_records[0]
"""

import logging

from odoo.addons.spp_dci.schemas import QueryType
from odoo.exceptions import UserError, ValidationError

from .openg2p_dci_client import OpenG2PDCIClient

_logger = logging.getLogger(__name__)

# Identifier priority for resolving the partner's search_text. The first
# matching reg_id type with a non-empty value wins. Priority is preserved
# from the previous FR service so existing test partners with UIN reg_ids
# continue to work; OpenG2P's typical id_type for SR records is plain
# "UIN" or a national-registry-prefixed value (e.g., IND-NSR-XXXX).
IDENTIFIER_PRIORITY = ("UIN", "DRN", "NATIONAL_ID", "NID")


class OpenG2PSocialService:
    """Service for querying OpenG2P as a Social Registry.

    Mirrors the surface the bridge dispatcher needs: ``__init__(env,
    data_source_code)`` and ``get_partner_record(partner)``. The
    dispatcher applies ``variable.dci_attribute_path`` to the returned
    record, so this service stays generic — no variable-specific
    extraction logic.
    """

    def __init__(self, env, data_source_code):
        self.env = env
        self.data_source_code = data_source_code
        self.data_source = env["spp.dci.data.source"].get_by_code(data_source_code)
        # OpenG2PDCIClient defaults: reg_type="Individual", reg_record_type="Individual".
        self.client = OpenG2PDCIClient(self.data_source, env)

    # ------------------------------------------------------------------
    # Public API — surface called by the bridge dispatcher
    # ------------------------------------------------------------------

    def get_partner_record(self, partner) -> dict | None:
        """Look up ``partner`` in OpenG2P and return the first matching record.

        Returns:
            dict: The raw OpenG2P record from ``data.reg_records[0]`` if
                a match was found.
            None: if the partner has no resolvable identifier OR OpenG2P
                returned no record (REG-ERR-001 / empty ``search_response``).

        Raises:
            UserError: If the request fails for non-not-found reasons
                (network error, server 5xx, malformed envelope). The
                dispatcher loop catches these per-subject and records
                them as audit ``result=error`` rows.
        """
        if not partner:
            raise ValidationError("Partner is required")

        search_text = self._get_partner_search_text(partner)
        if not search_text:
            _logger.warning(
                "No suitable identifier found for partner ID=%s — skipping OpenG2P query",
                partner.id,
            )
            return None

        _logger.info(
            "Querying OpenG2P SR for partner ID=%s using search_text=%s",
            partner.id,
            search_text,
        )

        try:
            response = self.client.search(
                query_type=QueryType.EXPRESSION,
                query_value=search_text,
                # registry_type / record_type are ignored by OpenG2PDCIClient
                # (which always forces "Individual") but we pass something
                # plausible for upstream's logging.
                registry_type="Individual",
                record_type="Individual",
                page=1,
                page_size=1,
            )
        except Exception as e:
            _logger.error("OpenG2P SR fetch failed: %s", e, exc_info=True)
            raise UserError(f"Failed to query OpenG2P: {e}") from e

        return self._extract_first_record(response)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_partner_search_text(self, partner):
        """Return the search_text value for ``partner`` — the value of
        the partner's highest-priority matching reg_id.

        The priority list matches DRService's so swapping between SR and
        DR sources doesn't change which identifier is sent first.
        """
        reg_ids = self.env["spp.registry.id"].search([("partner_id", "=", partner.id)])
        for id_type in IDENTIFIER_PRIORITY:
            for reg_id in reg_ids:
                if reg_id.id_type_id.code == id_type and reg_id.value:
                    return reg_id.value
        if reg_ids:
            first_id = reg_ids[0]
            if first_id.value:
                return first_id.value
        return None

    @staticmethod
    def _extract_first_record(response):
        """Unwrap OpenG2P's response envelope to the first registry record.

        OpenG2P returns:

            response.message.search_response[i].data.reg_records[j]

        Returns the first matching record across the response, or None
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
