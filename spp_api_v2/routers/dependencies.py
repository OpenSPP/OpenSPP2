# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared router dependencies and utilities for API V2."""

import asyncio
import random
from typing import Any
from urllib.parse import unquote

from fastapi import HTTPException, status

from ..services.consent_service import ConsentService


def parse_resource_reference(
    reference: str | None,
    expected_type: str,
) -> tuple[str, str]:
    """
    Parse a resource reference and return (system, value).

    Args:
        reference: Reference string like "Individual/{system}|{value}"
        expected_type: Expected resource type ("Individual" or "Group")

    Returns:
        Tuple of (system, value)

    Raises:
        HTTPException: If reference format is invalid
    """
    if not reference or not reference.startswith(f"{expected_type}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid reference. Expected: {expected_type}/{{system}}|{{value}}",
        )

    ident_str = reference[len(expected_type) + 1 :]  # Strip "Type/" prefix
    # URL-decode the identifier (handles %23 -> # from JSON bodies that may contain
    # URL-encoded URIs)
    ident_str = unquote(ident_str)
    if "|" not in ident_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format in reference",
        )

    return ident_str.split("|", 1)


def parse_identifier(identifier: str) -> tuple[str, str]:
    """
    Parse an identifier string in format {system}|{value}.

    Args:
        identifier: Identifier string like "{system}|{value}"

    Returns:
        Tuple of (system, value)

    Raises:
        HTTPException: If identifier format is invalid
    """
    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format. Expected: {system}|{value}",
        )

    return identifier.split("|", 1)


async def check_group_access(
    group: Any,
    api_client: Any,
    env: Any,
    operation: str,
) -> None:
    """
    Check if API client has access to a group with proper security measures.

    Handles:
    - Anti-enumeration timing jitter for consent-requiring clients
    - Consent-based access control

    Args:
        group: The group record (or None if not found)
        api_client: The authenticated API client
        env: Odoo environment
        operation: The operation type ("read", "update", "create")

    Raises:
        HTTPException: If group not found or access denied
    """
    # SECURITY: Prevent user enumeration
    # For clients requiring consent, return same error for "not found" and "no consent"
    if not group:
        if api_client.is_require_consent:
            # SECURITY: Add timing jitter to prevent timing-based enumeration
            await asyncio.sleep(0.05 + random.uniform(0, 0.02))  # 50-70ms delay
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    # SECURITY: Check consent before allowing operation (for clients requiring consent)
    if api_client.is_require_consent:
        consent_service = ConsentService(env)
        if not consent_service.check_access(group.id, api_client, "group", operation):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )


async def check_individual_access(
    individual: Any,
    api_client: Any,
    env: Any,
    operation: str,
) -> None:
    """
    Check if API client has access to an individual with proper security measures.

    Handles:
    - Anti-enumeration timing jitter for consent-requiring clients
    - Consent-based access control

    Args:
        individual: The individual record (or None if not found)
        api_client: The authenticated API client
        env: Odoo environment
        operation: The operation type ("read", "update", "create")

    Raises:
        HTTPException: If individual not found or access denied
    """
    # SECURITY: Prevent user enumeration
    if not individual:
        if api_client.is_require_consent:
            # SECURITY: Add timing jitter to prevent timing-based enumeration
            await asyncio.sleep(0.05 + random.uniform(0, 0.02))  # 50-70ms delay
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Individual not found",
        )

    # SECURITY: Check consent before allowing operation (for clients requiring consent)
    if api_client.is_require_consent:
        consent_service = ConsentService(env)
        if not consent_service.check_access(individual.id, api_client, "individual", operation):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
