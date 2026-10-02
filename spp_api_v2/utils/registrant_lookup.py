# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""HTTP answer for an identifier that matches more than one registrant.

The API refuses to guess (409). But saying "this identifier is ambiguous"
also says "it exists", so a client only learns it when it may read every
matching registrant; otherwise it gets exactly what it would get for a
registrant that does not exist (api-error-responses.md, anti-enumeration):
the 403 of a read, or the empty page of a search.
"""

import asyncio
import random

from fastapi import HTTPException, status

from ..services.consent_service import ConsentService
from ..services.registrant_resolver import AmbiguousIdentifierError

AMBIGUOUS_DETAIL = "Identifier matches more than one registrant"


def consent_denied(env, api_client, partner, resource_type) -> bool:
    """Whether the client may not read ``partner``'s ``resource_type`` data.

    The same rule as a successful read (legal basis, consent, consent scope),
    evaluated without logging an access.
    """
    filtered = ConsentService(env).filter_response(partner.id, api_client, resource_type, {}, log_access=False)
    return filtered.get("_consent", {}).get("status") in ("no_consent", "scope_mismatch")


async def deny_access():
    """Raise the anti-enumeration 403, with the 50-70ms delay of the "not found" path."""
    # SECURITY: the same delay whether the record is missing, ambiguous or
    # not consented, so timing does not tell them apart
    await asyncio.sleep(0.05 + random.uniform(0, 0.02))
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def ambiguous_identifier_status(env, api_client, error: AmbiguousIdentifierError, resource_type=None) -> int:
    """
    409 if the client may read every match, else 403.

    Args:
        resource_type: consent resource to check; by default each match's own
            kind ("group" or "individual")
    """
    for partner in error.partners:
        kind = resource_type or ("group" if partner.is_group else "individual")
        if consent_denied(env, api_client, partner, kind):
            return status.HTTP_403_FORBIDDEN
    return status.HTTP_409_CONFLICT


async def raise_ambiguous_identifier(env, api_client, error, resource_type=None):
    """Raise the 409, or the jittered "not found" 403, for an ambiguous identifier."""
    if ambiguous_identifier_status(env, api_client, error, resource_type) == status.HTTP_403_FORBIDDEN:
        await deny_access()
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=AMBIGUOUS_DETAIL)


def ambiguous_filter_result(env, api_client, error, empty_records, resource_type=None):
    """
    Search-filter form: an empty page (what "not found" looks like in a search)
    for a client that may not know, else 409.

    Returns:
        (empty_records, 0), the (records, total) shape of a search function
    """
    if ambiguous_identifier_status(env, api_client, error, resource_type) == status.HTTP_403_FORBIDDEN:
        return empty_records, 0
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=AMBIGUOUS_DETAIL)


async def lookup_registrant(env, api_client, lookup, system, value, resource_type=None):
    """
    Call ``lookup(system, value)``, answering an ambiguous identifier with 409/403.

    Returns:
        whatever ``lookup`` returns (a registrant or an empty recordset)
    """
    try:
        return lookup(system, value)
    except AmbiguousIdentifierError as e:
        await raise_ambiguous_identifier(env, api_client, e, resource_type)
