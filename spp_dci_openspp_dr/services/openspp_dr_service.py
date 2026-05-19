"""OpenSPP-DR Disability Registry client service.

Talks to the sibling OpenSPP-DR over DCI. Two paths today:

* ``get_partner_record`` — read-side, used by the bridge dispatcher to
  resolve CEL variables like ``has_disability``. Calls the DR's
  ``/sync/search`` endpoint and returns the first
  ``data.reg_records[0]`` dict.
* ``register_individuals`` — write-side, used by the SR-import wizard
  to mirror SP-side registrants into the DR. Calls the DR's
  ``/sync/register`` endpoint with a list of UIN-keyed individuals and
  returns per-item status (created/updated/skipped/rjct).

Why this exists rather than reusing upstream ``DRService``:

  The upstream ``spp_dci_client_dr.DRService`` reads disability fields
  from the search response's ``data`` object directly, but the SPDCI
  spec (and our OpenSPP-DR server) put records at
  ``data.reg_records[0]``. Until DRService is fixed upstream, this
  adapter takes ownership of the response unwrap so the bridge sees
  the correct wire-format keys.
"""

import logging
import uuid

from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci_client.services import DCIClient

_logger = logging.getLogger(__name__)

# Identifier priority for resolving which reg_id value to send. Matches
# upstream DRService's priority so swapping between SR and DR sources
# doesn't change which identifier gets sent first.
IDENTIFIER_PRIORITY = ("UIN", "DRN", "NATIONAL_ID", "NID")

# DR-side register endpoint. Companion to /sync/search; defined in
# spp_dci_server_disability/routers/disability_router.py.
REGISTER_ENDPOINT = "/dci_api/v1/disability/registry/sync/register"


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

    # ------------------------------------------------------------------
    # Register (write-side)
    # ------------------------------------------------------------------

    def register_individuals(self, items: list[dict], refresh_existing: bool = False) -> dict:
        """Send a register-individual envelope to the DR.

        ``items`` is a list of dicts with keys ``uin`` and any of
        ``name``, ``given_name``, ``family_name``, ``sex``, ``birth_date``.
        Returns the raw response envelope dict — caller inspects
        ``message.register_response`` for per-item status (succ / rjct)
        and operation (created / updated / skipped).

        Raises UserError on transport-level failures (HTTP error, malformed
        envelope from DR). Per-item failures DO NOT raise — they surface
        as ``status='rjct'`` rows in the response list, mirroring the
        contract of the search side.
        """
        if not items:
            raise ValidationError(self.env._("No items to register on the DR"))

        register_items = []
        for it in items:
            # Pydantic's `str | None` and `date | None` schema fields accept
            # None or the typed value — NOT Odoo's `False`-for-empty-Char
            # convention. Coerce empty/falsy values to None before they
            # leave the SP so the DR's envelope validation accepts them.
            bd = it.get("birth_date")
            if bd and hasattr(bd, "isoformat"):
                bd_wire = bd.isoformat()
            elif bd:
                bd_wire = str(bd)
            else:
                bd_wire = None
            register_items.append(
                {
                    "reference_id": str(uuid.uuid4()),
                    "uin": it["uin"],
                    "name": it.get("name") or None,
                    "given_name": it.get("given_name") or None,
                    "family_name": it.get("family_name") or None,
                    "sex": it.get("sex") or None,
                    "birth_date": bd_wire,
                    "is_disabled": bool(it.get("is_disabled")),
                }
            )

        message = {
            "transaction_id": str(uuid.uuid4()),
            "register_request": register_items,
            "refresh_existing": bool(refresh_existing),
        }
        envelope = self.client._build_envelope(action="register-individual", message=message)
        _logger.info(
            "DR register: sending %d item(s), refresh=%s",
            len(register_items),
            refresh_existing,
        )
        try:
            return self.client._make_request(REGISTER_ENDPOINT, envelope)
        except Exception as e:
            _logger.error("DR register call failed: %s", e, exc_info=True)
            raise UserError(self.env._("Failed to register on DR: %s", e)) from e

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
