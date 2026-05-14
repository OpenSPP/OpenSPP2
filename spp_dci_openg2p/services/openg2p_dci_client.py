"""OpenG2P-aware DCIClient subclass.

The DCI spec leaves two shapes ambiguous; OpenG2P picked different
interpretations than `spp_dci_client`. This subclass overrides only the
delta:

1. `query` payload for `idtype-value` searches
   ------------------------------------------------------------------
   Upstream emits:    "query": {"type": "<id_type>", "value": "<id_value>"}
   OpenG2P expects:   "query": {"type": "idtype-value",
                                "value": {"id_type":  "<id_type>",
                                          "id_value": "<id_value>"}}
   Verified live: the upstream shape returns
   `rjct.search_criteria.invalid` ("query.value.id_type is required").

2. `reg_record_type` in search_criteria
   ------------------------------------------------------------------
   OpenG2P's DciSearchCriteria schema requires `reg_record_type`
   (e.g., "spdci-extensions-dci:Farmer"). Upstream's `SearchCriteria`
   Pydantic model doesn't carry that field, so it never reaches the wire.
   The subclass injects it into the dumped envelope before signing.

Everything else (envelope, signing, OAuth2, retries, async) reuses
upstream code unchanged.
"""

import logging

from odoo.addons.spp_dci.schemas import QueryType
from odoo.addons.spp_dci_client.services.client import DCIClient

_logger = logging.getLogger(__name__)

DEFAULT_OPENG2P_REG_RECORD_TYPE = "spdci-extensions-dci:Farmer"


class OpenG2PDCIClient(DCIClient):
    """DCIClient that emits OpenG2P-compatible search payloads."""

    def __init__(self, data_source, env, reg_record_type=None):
        super().__init__(data_source, env)
        self._reg_record_type = reg_record_type or DEFAULT_OPENG2P_REG_RECORD_TYPE

    def _parse_query(self, query_type, query_value):
        if query_type == QueryType.IDTYPE_VALUE:
            if ":" not in query_value:
                return super()._parse_query(query_type, query_value)
            id_type, id_value = query_value.split(":", 1)
            return {
                "type": QueryType.IDTYPE_VALUE,
                "value": {
                    "id_type": id_type.strip(),
                    "id_value": id_value.strip(),
                },
            }
        return super()._parse_query(query_type, query_value)

    def _build_search_envelope(
        self,
        query_type,
        query,
        registry_type,
        registry_event_type,
        record_type,
        page,
        page_size,
        callback_url=None,
    ):
        envelope = super()._build_search_envelope(
            query_type=query_type,
            query=query,
            registry_type=registry_type,
            registry_event_type=registry_event_type,
            record_type=record_type,
            page=page,
            page_size=page_size,
            callback_url=callback_url,
        )
        # Upstream's SearchCriteria Pydantic model omits reg_record_type;
        # inject it directly into the dumped message. This must happen
        # BEFORE re-signing because the signature covers header+message.
        message = envelope.get("message") or {}
        for item in message.get("search_request") or []:
            criteria = item.get("search_criteria")
            if isinstance(criteria, dict):
                criteria["reg_record_type"] = self._reg_record_type
        # Re-sign with the modified message so the signature is consistent.
        return self._sign_request(envelope["header"], message)
