# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""HTTP answer for an identifier that matches more than one registrant.

The API refuses to guess (409). But saying "this identifier is ambiguous"
also says "it exists", so a client that needs consent only learns it when
it has consent for every matching registrant; otherwise it gets the same
403 as a registrant that does not exist (api-error-responses.md,
anti-enumeration).
"""

import asyncio
import random

from fastapi import HTTPException, status

from ..services.consent_service import ConsentService
from ..services.registrant_resolver import AmbiguousIdentifierError

AMBIGUOUS_DETAIL = "Identifier matches more than one registrant"


def ambiguous_identifier_status(env, api_client, error: AmbiguousIdentifierError, resource_type=None) -> int:
    """
    409 if the client may know the identifier is ambiguous, else 403.

    Args:
        resource_type: consent resource to check; by default each match's own
            kind ("group" or "individual")
    """
    if api_client.is_require_consent:
        consent_service = ConsentService(env)
        for partner in error.partners:
            kind = resource_type or ("group" if partner.is_group else "individual")
            if not consent_service.check_access(partner.id, api_client, kind, "read"):
                return status.HTTP_403_FORBIDDEN
    return status.HTTP_409_CONFLICT


def ambiguous_identifier_exception(env, api_client, error, resource_type=None) -> HTTPException:
    """HTTPException for an ambiguous identifier, without timing jitter (sync callers)."""
    if ambiguous_identifier_status(env, api_client, error, resource_type) == status.HTTP_403_FORBIDDEN:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=AMBIGUOUS_DETAIL)


async def raise_ambiguous_identifier(env, api_client, error, resource_type=None):
    """Raise the 409/403 for an ambiguous identifier; a 403 gets the "not found" timing jitter."""
    exc = ambiguous_identifier_exception(env, api_client, error, resource_type)
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        # SECURITY: same 50-70ms delay as the "not found" path, so timing
        # does not tell "ambiguous" from "missing"
        await asyncio.sleep(0.05 + random.uniform(0, 0.02))
    raise exc


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
