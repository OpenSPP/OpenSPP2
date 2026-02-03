# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Vocabulary API endpoints."""

import logging
from typing import Annotated
from urllib.parse import unquote

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..schemas.vocabulary import (
    VocabularyCodeResponse,
    VocabularyCodesResponse,
    VocabularyListResponse,
    VocabularyResponse,
)

_logger = logging.getLogger(__name__)

vocabulary_router = APIRouter(tags=["Vocabulary"], prefix="/Vocabulary")


def _validate_namespace_uri(decoded_uri: str) -> None:
    """
    Validate namespace URI for security issues.

    Args:
        decoded_uri: URL-decoded namespace URI

    Raises:
        HTTPException: If validation fails
    """
    # Check for path traversal and other malicious patterns
    if ".." in decoded_uri or "\x00" in decoded_uri or any(ord(c) < 32 for c in decoded_uri) or len(decoded_uri) > 255:
        _logger.warning("Suspicious namespace_uri: %s", decoded_uri[:50])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid namespace URI format",
        )


@vocabulary_router.get(
    "",
    response_model=VocabularyListResponse,
    summary="List vocabularies",
    description="Get all available vocabularies.",
)
async def list_vocabularies(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    domain: Annotated[
        str | None,
        Query(description="Filter by domain (core, social_assistance, health, etc.)"),
    ] = None,
    _count: Annotated[int, Query(ge=1, le=100, alias="_count")] = 50,
    _offset: Annotated[int, Query(ge=0, alias="_offset")] = 0,
):
    """
    List all available vocabularies.

    Vocabularies are standardized code lists used across OpenSPP.
    They can be based on international standards (ISO, WHO) or
    OpenSPP-specific definitions.
    """
    # Check permission - vocabulary scope with read action
    if not api_client.has_scope("vocabulary", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read vocabularies",
        )

    # Input validation
    if domain:
        if len(domain) > 50 or not domain.replace("_", "").isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain parameter",
            )

    # Build domain
    search_domain = [("active", "=", True)]
    if domain:
        search_domain.append(("domain", "=", domain))

    Vocabulary = env["spp.vocabulary"].sudo()

    # Get total count
    total = Vocabulary.search_count(search_domain)

    # Get records with pagination
    vocabularies = Vocabulary.search(
        search_domain,
        limit=_count,
        offset=_offset,
        order="name",
    )

    items = [
        VocabularyResponse(
            namespace_uri=v.namespace_uri,
            name=v.name,
            version=v.version or None,
            description=v.description or None,
            reference_url=v.reference_url or None,
            domain=v.domain,
            is_hierarchical=v.is_hierarchical,
            code_count=v.code_count,
        )
        for v in vocabularies
    ]

    return VocabularyListResponse(total=total, items=items)


@vocabulary_router.get(
    "/{namespace_uri:path}/codes",
    response_model=VocabularyCodesResponse,
    summary="Get vocabulary codes",
    description="Get all codes within a vocabulary.",
)
async def get_vocabulary_codes(
    namespace_uri: Annotated[
        str,
        Path(
            description="Namespace URI of the vocabulary (URL-encoded)",
            examples=["urn:iso:std:iso:5218", "urn:openspp:vocab:relationship"],
        ),
    ],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    include_deprecated: Annotated[
        bool,
        Query(description="Include deprecated codes"),
    ] = False,
    parent_code: Annotated[
        str | None,
        Query(description="Filter by parent code (for hierarchical vocabularies)"),
    ] = None,
    _count: Annotated[int, Query(ge=1, le=500, alias="_count")] = 100,
    _offset: Annotated[int, Query(ge=0, alias="_offset")] = 0,
):
    """
    Get codes within a vocabulary.

    Returns all active codes for the specified vocabulary.
    For hierarchical vocabularies, use parent_code to get children.
    """
    # Check permission
    if not api_client.has_scope("vocabulary", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read vocabulary codes",
        )

    # URL-decode the namespace_uri
    decoded_uri = unquote(namespace_uri)

    # Security validation
    _validate_namespace_uri(decoded_uri)

    # Input validation for parent_code
    if parent_code:
        if len(parent_code) > 64 or "\x00" in parent_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent_code parameter",
            )

    # Find vocabulary
    Vocabulary = env["spp.vocabulary"].sudo()
    vocabulary = Vocabulary.search(
        [("namespace_uri", "=", decoded_uri), ("active", "=", True)],
        limit=1,
    )

    if not vocabulary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vocabulary not found: {decoded_uri}",
        )

    # Build domain for codes
    VocabularyCode = env["spp.vocabulary.code"].sudo()
    code_domain = [
        ("vocabulary_id", "=", vocabulary.id),
        ("active", "=", True),
    ]

    if not include_deprecated:
        code_domain.append(("deprecated", "=", False))

    if parent_code:
        # Find parent code record
        parent = VocabularyCode.search(
            [
                ("vocabulary_id", "=", vocabulary.id),
                ("code", "=", parent_code),
            ],
            limit=1,
        )
        if parent:
            code_domain.append(("parent_id", "=", parent.id))
        else:
            # Parent not found - return empty
            return VocabularyCodesResponse(
                namespace_uri=decoded_uri,
                vocabulary_name=vocabulary.name,
                total=0,
                items=[],
            )

    # Get total
    total = VocabularyCode.search_count(code_domain)

    # Get codes
    codes = VocabularyCode.search(
        code_domain,
        limit=_count,
        offset=_offset,
        order="sequence, code",
    )

    items = [
        VocabularyCodeResponse(
            code=c.code,
            display=c.display,
            definition=c.definition or None,
            deprecated=c.deprecated,
            parent_code=c.parent_id.code if c.parent_id else None,
            level=c.level,
        )
        for c in codes
    ]

    return VocabularyCodesResponse(
        namespace_uri=decoded_uri,
        vocabulary_name=vocabulary.name,
        total=total,
        items=items,
    )


@vocabulary_router.get(
    "/{namespace_uri:path}",
    response_model=VocabularyResponse,
    summary="Get vocabulary details",
    description="Get details of a specific vocabulary.",
)
async def get_vocabulary(
    namespace_uri: Annotated[
        str,
        Path(
            description="Namespace URI of the vocabulary (URL-encoded)",
            examples=["urn:iso:std:iso:5218"],
        ),
    ],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Get details of a specific vocabulary.

    Returns metadata about the vocabulary including name, version,
    description, and code count.
    """
    # Check permission
    if not api_client.has_scope("vocabulary", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read vocabularies",
        )

    # URL-decode the namespace_uri
    decoded_uri = unquote(namespace_uri)

    # Security validation
    _validate_namespace_uri(decoded_uri)

    # Find vocabulary
    Vocabulary = env["spp.vocabulary"].sudo()
    vocabulary = Vocabulary.search(
        [("namespace_uri", "=", decoded_uri), ("active", "=", True)],
        limit=1,
    )

    if not vocabulary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vocabulary not found: {decoded_uri}",
        )

    return VocabularyResponse(
        namespace_uri=vocabulary.namespace_uri,
        name=vocabulary.name,
        version=vocabulary.version or None,
        description=vocabulary.description or None,
        reference_url=vocabulary.reference_url or None,
        domain=vocabulary.domain,
        is_hierarchical=vocabulary.is_hierarchical,
        code_count=vocabulary.code_count,
    )
