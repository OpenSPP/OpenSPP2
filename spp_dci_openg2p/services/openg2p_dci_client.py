"""OpenG2P-aware DCIClient subclass.

OpenG2P's canonical request envelope (per the sample payload provided
by the OpenG2P team on 2026-05-14) differs from upstream's defaults in
five places. This subclass absorbs all five so callers can issue
``client.search(query_type=QueryType.EXPRESSION, query_value=<id>, ...)``
and produce an OpenG2P-acceptable request without further adapter work.

The five deltas:

1. ``query_type`` is ``"expression"`` (not ``"idtype-value"``).
   Upstream supports both; we make this subclass's preferred path
   expression.

2. ``query.type`` is the namespaced URI ``"ns:org:QueryType:expression"``
   (not the short form ``"expression"``).

3. ``query.value`` is the nested expression shape::

       {"expression": {"query": {"search_text": {"$eq": "<id_value>"}}}}

   The partner identifier we want to look up is the ``$eq`` value.

4. ``reg_type`` and ``reg_record_type`` are both the literal string
   ``"Individual"`` (not the namespaced URIs we'd previously guessed,
   like ``ns:org:RegistryType:Social`` or
   ``spdci-extensions-dci:Farmer``). Upstream's ``SearchCriteria``
   Pydantic model also doesn't carry ``reg_record_type``, so we inject
   it post-build.

5. ``consent`` and ``authorize`` blocks are required on every
   ``search_criteria``. We hard-code sensible defaults (purpose code
   ``ELIGIBILITY_CHECK``) — production deployments can override via
   a future ``spp.dci.data.source.consent_purpose_code`` field
   (planned, see ADR-024 §6.2).

Everything else (header, signing, OAuth2, retries, async, transport)
reuses upstream ``DCIClient`` unchanged.
"""

import logging
from datetime import UTC, datetime

from odoo.addons.spp_dci.schemas import QueryType
from odoo.addons.spp_dci_client.services.client import DCIClient

_logger = logging.getLogger(__name__)

# OpenG2P's record-type discriminator. Both reg_type and reg_record_type
# are literally "Individual" — verified against the OpenG2P-provided sample.
DEFAULT_OPENG2P_REG_TYPE = "Individual"
DEFAULT_OPENG2P_REG_RECORD_TYPE = "Individual"

# Namespaced URI form of the query type used inside the query payload.
# search_criteria.query_type stays as the short form per the DCI envelope.
OPENG2P_QUERY_TYPE_URI = "ns:org:QueryType:expression"

# Consent + authorize defaults. Production deployments override per source.
DEFAULT_CONSENT_PURPOSE = {
    "text": "Eligibility verification for social-protection program",
    "code": "ELIGIBILITY_CHECK",
    "ref_uri": "https://docs.openspp.org/consent/eligibility-check",
}
DEFAULT_CONSENT_CONTEXT = "https://schema.spdci.org/common/v1/api-schemas/Consent.jsonld"
DEFAULT_AUTHORIZE_CONTEXT = "https://schema.spdci.org/common/v1/api-schemas/Authorize.jsonld"


class OpenG2PDCIClient(DCIClient):
    """DCIClient that emits OpenG2P-compatible search payloads."""

    def __init__(self, data_source, env, reg_type=None, reg_record_type=None):
        super().__init__(data_source, env)
        self._reg_type = reg_type or DEFAULT_OPENG2P_REG_TYPE
        self._reg_record_type = reg_record_type or DEFAULT_OPENG2P_REG_RECORD_TYPE

    # ------------------------------------------------------------------
    # Query shape: expression with nested search_text
    # ------------------------------------------------------------------

    def _parse_query(self, query_type, query_value):
        """Build OpenG2P's canonical query.value for expression queries.

        For QueryType.EXPRESSION, ``query_value`` is the search_text to
        match (typically a partner identifier like ``IND-NSR-0001``).
        Returns the full DciQuery object — ``search_criteria.query`` gets
        this dict directly with no further wrapping.

        Other query types fall through to upstream behaviour. Idtype-value
        is no longer overridden here; if a caller really wants it, they
        get upstream's flat-shape format (which OpenG2P rejects).
        """
        if query_type == QueryType.EXPRESSION:
            return {
                "type": OPENG2P_QUERY_TYPE_URI,
                "value": {
                    "expression": {
                        "query": {
                            "search_text": {"$eq": query_value},
                        },
                    },
                },
            }
        return super()._parse_query(query_type, query_value)

    # ------------------------------------------------------------------
    # Envelope shaping: force reg_type, inject reg_record_type,
    # attach consent + authorize blocks, re-sign.
    # ------------------------------------------------------------------

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
            # Always force OpenG2P's reg_type (literal "Individual") even
            # if the caller passed something else. The data source's
            # configured registry_type is a routing concept; OpenG2P's
            # reg_type is a wire-format concept.
            registry_type=self._reg_type,
            registry_event_type=registry_event_type,
            record_type=record_type,
            page=page,
            page_size=page_size,
            callback_url=callback_url,
        )
        message = envelope.get("message") or {}
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        consent_block = self._build_consent_block(now_iso)
        authorize_block = self._build_authorize_block(now_iso)
        for item in message.get("search_request") or []:
            criteria = item.get("search_criteria")
            if isinstance(criteria, dict):
                # reg_record_type is required by OpenG2P but absent from
                # upstream's SearchCriteria Pydantic model — inject.
                criteria["reg_record_type"] = self._reg_record_type
                # consent + authorize are required on every criteria.
                # Insert only if upstream didn't already populate them
                # (so a future feature can pass them through unchanged).
                criteria.setdefault("consent", consent_block)
                criteria.setdefault("authorize", authorize_block)
        # Re-sign with the modified message so the signature is consistent
        # with what we actually send over the wire.
        return self._sign_request(envelope["header"], message)

    # ------------------------------------------------------------------
    # Consent + authorize block construction
    # ------------------------------------------------------------------

    def _build_consent_block(self, timestamp_iso):
        """Return a JSON-LD consent block matching OpenG2P's expected shape.

        Hard-coded defaults for v1. Future enhancement: read consent
        purpose from a configurable field on ``spp.dci.data.source``
        (planned, ADR-024 §6.2).
        """
        return {
            "@context": DEFAULT_CONSENT_CONTEXT,
            "@type": "Consent",
            "ts": timestamp_iso,
            "purpose": dict(DEFAULT_CONSENT_PURPOSE),
        }

    def _build_authorize_block(self, timestamp_iso):
        """Return a JSON-LD authorize block matching OpenG2P's expected shape."""
        return {
            "@context": DEFAULT_AUTHORIZE_CONTEXT,
            "@type": "Authorize",
            "ts": timestamp_iso,
            "purpose": dict(DEFAULT_CONSENT_PURPOSE),
        }
