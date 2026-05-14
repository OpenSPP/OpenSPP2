"""DCI Disability Registry search service.

Looks up local res.partner records by the incoming ``search_text`` and
returns disability data (``has_disability``, ``disability_certified``,
``disability_percentage``) in a DCI SearchResponse envelope.

The service is intentionally narrow — it owns:

  - Query parsing: extracts ``search_text`` from the supported query
    types (``idtype-value``, ``expression``).
  - Partner lookup: searches ``spp.registry.id.value`` against the
    extracted search_text. The first matching partner wins.
  - Disability extraction: reads ``is_person_with_disability``,
    ``disability_certified``, and ``disability_percentage`` from the
    partner and returns them under the wire-format key
    ``has_disability`` (plus the others verbatim).
  - Response construction: builds ``SearchResponseItem`` records with
    ``status='succ'`` for matches and ``status='rjct'`` /
    ``status_reason_code='REG-ERR-001'`` for unknown identifiers.

Authentication, signing, and rate limiting live in the router and its
middleware — this service does no I/O beyond Odoo ORM reads.
"""

import logging
import uuid
from datetime import UTC, datetime

from odoo.addons.spp_dci.schemas.constants import (
    QueryType,
    SearchStatusReasonCode,
)
from odoo.addons.spp_dci.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResponseData,
    SearchResponseItem,
)

_logger = logging.getLogger(__name__)

# Wire-format reg_type / reg_record_type for the DR response envelope.
# DR is the canonical SPDCI registry-type code; PWD_PERSON is the
# SPDCI-defined record type for person-with-disability records. The
# spp_cel_dci_bridge dispatcher accepts both literal "DR" and the
# namespaced URI form, so we use the short form.
DR_REG_TYPE = "DR"
DR_REG_RECORD_TYPE = "PWD_PERSON"

# SPDCI's SearchStatusReasonCode enum doesn't include a "not found"
# code. OpenG2P uses ``REG-ERR-001`` with reason ``REGISTER_NOT_FOUND``
# at the envelope-header level for the same case; we adopt that
# convention at the per-item level so SP-side audit rows surface a
# stable, recognisable code.
REGISTER_NOT_FOUND_CODE = "REG-ERR-001"
REGISTER_NOT_FOUND_MESSAGE = "REGISTER_NOT_FOUND"


class DisabilitySearchService:
    """Look up partners by identifier and return disability data."""

    def __init__(self, env):
        self.env = env

    def execute_search(self, search_request: SearchRequest) -> SearchResponse:
        """Process a SearchRequest and produce a SearchResponse.

        One SearchResponseItem is produced per SearchRequestItem. Items
        are independent: one item's failure does not affect siblings.
        """
        response_items = []
        for req_item in search_request.search_request:
            response_items.append(self._handle_search_item(req_item))
        return SearchResponse(
            transaction_id=search_request.transaction_id,
            correlation_id=str(uuid.uuid4()),
            search_response=response_items,
        )

    # ------------------------------------------------------------------
    # Per-item processing
    # ------------------------------------------------------------------

    def _handle_search_item(self, req_item) -> SearchResponseItem:
        """Process one search request item — extract search_text, look up
        the partner, build the response item."""
        timestamp = datetime.now(UTC)
        try:
            search_text = self._extract_search_text(req_item.search_criteria)
        except ValueError as e:
            return SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=timestamp,
                status="rjct",
                status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                status_reason_message=str(e),
                locale=req_item.locale,
            )

        if not search_text:
            return SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=timestamp,
                status="rjct",
                status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                status_reason_message="search_text is empty",
                locale=req_item.locale,
            )

        partner = self._find_partner_by_identifier(search_text)
        if not partner:
            return SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=timestamp,
                status="rjct",
                status_reason_code=REGISTER_NOT_FOUND_CODE,
                status_reason_message=(
                    f"{REGISTER_NOT_FOUND_MESSAGE}: "
                    f"No registrant found for identifier '{search_text}'"
                ),
                locale=req_item.locale,
            )

        reg_record = self._build_reg_record(partner)
        data = SearchResponseData(
            reg_type=DR_REG_TYPE,
            reg_record_type=DR_REG_RECORD_TYPE,
            reg_records=[reg_record],
        )
        return SearchResponseItem(
            reference_id=req_item.reference_id,
            timestamp=timestamp,
            status="succ",
            data=data,
            locale=req_item.locale,
        )

    # ------------------------------------------------------------------
    # Query parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_search_text(criteria) -> str | None:
        """Pull the ``search_text`` value out of the criteria's query.

        Supports two shapes the SP-side may emit:

          1. ``idtype-value`` query — the value is the identifier directly,
             or ``{id_type, id_value}`` per upstream's flat shape.

          2. ``expression`` query — the value is OpenG2P's nested shape
             ``{expression: {query: {search_text: {$eq: <value>}}}}``.

        Returns None for query types we cannot interpret. Raises
        ValueError for malformed payloads where the shape is recognised
        but the expected field is absent.
        """
        query_type = criteria.query_type
        query = criteria.query
        # Compare against the enum string value; QueryType is StrEnum so
        # equality with bare strings works.
        if query_type == QueryType.IDTYPE_VALUE.value:
            if isinstance(query, dict):
                value = query.get("value")
                if isinstance(value, dict):
                    id_value = value.get("id_value")
                    if id_value:
                        return str(id_value)
                    raise ValueError("idtype-value query missing 'id_value'")
                if isinstance(value, str):
                    return value
            return None

        if query_type == QueryType.EXPRESSION.value:
            if not isinstance(query, dict):
                return None
            value = query.get("value")
            if not isinstance(value, dict):
                return None
            # OpenG2P nested shape: value.expression.query.search_text.$eq
            expression = value.get("expression") if isinstance(value, dict) else None
            if isinstance(expression, dict):
                inner_query = expression.get("query")
                if isinstance(inner_query, dict):
                    search_text = inner_query.get("search_text")
                    if isinstance(search_text, dict):
                        eq = search_text.get("$eq")
                        if eq:
                            return str(eq)
                        raise ValueError(
                            "expression query missing 'search_text.$eq'"
                        )
                    if isinstance(search_text, str):
                        return search_text
            return None

        # Unsupported query type — caller decides whether to surface as
        # rjct or just skip. Return None to signal "no search_text found".
        return None

    # ------------------------------------------------------------------
    # Partner lookup
    # ------------------------------------------------------------------

    def _find_partner_by_identifier(self, identifier_value: str):
        """Return the first res.partner whose registry_id has the given value.

        Multiple partners may share an identifier in pathological data;
        we deterministically pick the lowest partner.id so repeat queries
        are stable. The disability data we return is a function of the
        single matched partner.
        """
        reg_id = self.env["spp.registry.id"].search(
            [("value", "=", identifier_value)],
            order="partner_id asc",
            limit=1,
        )
        return reg_id.partner_id if reg_id else self.env["res.partner"].browse()

    # ------------------------------------------------------------------
    # Reg-record construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_reg_record(partner) -> dict:
        """Produce the wire-format reg_record dict from a res.partner.

        The CEL-bridge SP side reads ``has_disability`` (not the local
        field name ``is_person_with_disability``). Mapping happens here.

        Disability-related fields are read defensively — modules that
        define them are not strict dependencies of this server module,
        so the fields may be missing on the partner record. Missing
        fields are reported as ``False`` / ``None`` rather than raising.
        """
        return {
            "has_disability": bool(
                getattr(partner, "is_person_with_disability", False)
            ),
            "disability_certified": bool(
                getattr(partner, "disability_certified", False)
            ),
            "disability_percentage": getattr(
                partner, "disability_percentage", None
            ),
            "partner_name": partner.name,
            "partner_uid": partner.id,
        }
