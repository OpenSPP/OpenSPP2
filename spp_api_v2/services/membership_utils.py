# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared membership utilities for API V2 services."""

import logging
from typing import Any

_logger = logging.getLogger(__name__)


def membership_to_response(membership) -> dict[str, Any] | None:
    """
    Convert spp.group.membership record to MembershipResponse schema.

    This is a shared utility function used by both GroupService and
    IndividualService to avoid code duplication.

    Args:
        membership: spp.group.membership record

    Returns:
        Dictionary matching MembershipResponse schema, or None if
        group or individual lacks valid external identifiers.
    """
    # Build group reference — prefer non-system identifiers over system_id
    group = membership.group
    group_id = next(
        (
            r
            for r in group.reg_ids
            if r.id_type_id and r.id_type_id.uri and r.value and r.id_type_id.code != "system_id"
        ),
        next((r for r in group.reg_ids if r.id_type_id and r.id_type_id.uri and r.value), None),
    )
    if not group_id:
        _logger.warning(
            "Skipping membership (id=%s): group (id=%s) has no valid identifiers.",
            membership.id,
            group.id,
        )
        return None

    group_ref = {
        "reference": f"Group/{group_id.id_type_id.uri}|{group_id.value}",
        "display": group.name,
    }

    # Build individual reference — prefer non-system identifiers over system_id
    individual = membership.individual
    individual_id = next(
        (
            r
            for r in individual.reg_ids
            if r.id_type_id and r.id_type_id.uri and r.value and r.id_type_id.code != "system_id"
        ),
        next((r for r in individual.reg_ids if r.id_type_id and r.id_type_id.uri and r.value), None),
    )
    if not individual_id:
        _logger.warning(
            "Skipping membership (id=%s): individual (id=%s) has no valid identifiers.",
            membership.id,
            individual.id,
        )
        return None

    individual_ref = {
        "reference": f"Individual/{individual_id.id_type_id.uri}|{individual_id.value}",
        "display": individual.name,
    }

    # Build response
    response = {
        "type": "GroupMember",
        "group": group_ref,
        "entity": individual_ref,
        "status": membership.status if membership.status else "active",
    }

    # Add role if available
    if membership.membership_type_ids:
        vocab_code = membership.membership_type_ids[0]
        response["role"] = {
            "coding": [
                {
                    "system": vocab_code.namespace_uri or "urn:openspp:vocab:group-membership-type",
                    "code": vocab_code.code,
                    "display": vocab_code.display,
                }
            ]
        }

    # Add dates (convert datetime to date for API response)
    if membership.start_date:
        response["startDate"] = membership.start_date.date().isoformat()

    if membership.ended_date:
        response["endedDate"] = membership.ended_date.date().isoformat()

    return response
