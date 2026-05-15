"""OpenSPP-DR Disability Registry client service.

Queries the sibling OpenSPP-DR instance over DCI (``spp_dci_server_disability``
endpoint at ``/dci_api/v1/disability/registry/sync/search``) and returns the raw
``data.reg_records[0]`` dict. The bridge dispatcher applies the variable's
``dci_attribute_path`` to that dict — so the CEL variable
``has_disability`` extracts the wire-format ``has_disability`` field
without this service needing to know which.

Why this exists rather than reusing upstream ``DRService``:

  The upstream ``spp_dci_client_dr.DRService`` reads disability fields
  from the search response's ``data`` object directly, but the SPDCI
  spec (and our OpenSPP-DR server) put records at
  ``data.reg_records[0]``. Until DRService is fixed upstream, this
  adapter takes ownership of the response unwrap so the bridge sees
  the correct wire-format keys.
"""

import logging

from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci_client.services import DCIClient

_logger = logging.getLogger(__name__)

# Identifier priority for resolving which reg_id value to send. Matches
# upstream DRService's priority so swapping between SR and DR sources
# doesn't change which identifier gets sent first.
IDENTIFIER_PRIORITY = ("UIN", "DRN", "NATIONAL_ID", "NID")


class OpenSPPDRService:
    """Service for querying an OpenSPP-DR instance over DCI."""

    def __init__(self, env, data_source_code):
        self.env = env
        self.data_source_code = data_source_code
        self.data_source = env["spp.dci.data.source"].get_by_code(data_source_code)
        # Upstream DCIClient is sufficient — OpenSPP-DR speaks vanilla
        # SPDCI; no query/envelope quirks to absorb (unlike the
        # OpenG2P-vendor adapter).
        self.client = DCIClient(self.data_source, env)

    # ------------------------------------------------------------------
    # Public API — surface called by the bridge dispatcher
    # ------------------------------------------------------------------

    def get_partner_record(self, partner) -> dict | None:
        """Look up ``partner`` in the OpenSPP-DR and return the first matching record.

        Returns:
            dict: The raw OpenSPP-DR record from ``data.reg_records[0]``
                if a match was found.
            None: if the partner has no resolvable identifier OR the
                OpenSPP-DR returned no record (status='rjct' with
                REG-ERR-001 / empty ``search_response``).

        Raises:
            UserError: If the request fails for non-not-found reasons
                (network error, server 5xx, malformed envelope). The
                dispatcher loop catches these per-subject and records
                them as audit ``result=error`` rows.
        """
        if not partner:
            raise ValidationError(self.env._("Partner is required"))

        identifier = self._get_partner_identifier(partner)
        if not identifier:
            _logger.warning(
                "No suitable identifier found for partner ID=%s — skipping OpenSPP-DR query",
                partner.id,
            )
            return None

        id_type, id_value = identifier
        _logger.info(
            "Querying OpenSPP-DR for partner ID=%s using %s:%s",
            partner.id,
            id_type,
            id_value,
        )

        try:
            response = self.client.search_by_id(
                identifier_type=id_type,
                identifier_value=id_value,
                record_type="PERSON",
                page=1,
                page_size=1,
            )
        except Exception as e:
            _logger.error("OpenSPP-DR fetch failed: %s", e, exc_info=True)
            raise UserError(self.env._("Failed to query OpenSPP-DR: %s", e)) from e

        return self._extract_first_record(response)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_partner_identifier(self, partner):
        """Return ``(id_type_code, id_value)`` for the partner's highest-
        priority matching reg_id, or None if no usable id was found."""
        reg_ids = self.env["spp.registry.id"].search([("partner_id", "=", partner.id)])
        for id_type in IDENTIFIER_PRIORITY:
            for reg_id in reg_ids:
                if reg_id.id_type_id.code == id_type and reg_id.value:
                    return (id_type, reg_id.value)
        if reg_ids:
            first_id = reg_ids[0]
            if first_id.value and first_id.id_type_id:
                return (first_id.id_type_id.code, first_id.value)
        return None

    @staticmethod
    def _extract_first_record(response):
        """Unwrap the OpenSPP-DR response envelope to the first registry record.

        SPDCI shape:

            response.message.search_response[i].data.reg_records[j]

        Returns the first matching record across the response, or None
        if no records were found (status='rjct' / empty search_response).
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
