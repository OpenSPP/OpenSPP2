# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared membership utilities for API V2 services."""

from typing import Any

from odoo.exceptions import ValidationError


def membership_to_response(membership) -> dict[str, Any]:
    """
    Convert spp.group.membership record to MembershipResponse schema.

    This is a shared utility function used by both GroupService and
    IndividualService to avoid code duplication.

    Args:
        membership: spp.group.membership record

    Returns:
        Dictionary matching MembershipResponse schema

    Raises:
        ValidationError: If group or individual lacks external identifiers
    """
    # Build group reference
    group = membership.group
    group_id = group.reg_ids[0] if group.reg_ids else None
    if not group_id:
        raise ValidationError(f"Group {group.name} has no valid external identifiers")

    group_ref = {
        "reference": f"Group/{group_id.namespace_uri}|{group_id.value}",
        "display": group.name,
    }

    # Build individual reference
    individual = membership.individual
    individual_id = individual.reg_ids[0] if individual.reg_ids else None
    if not individual_id:
        raise ValidationError(f"Individual {individual.name} has no valid external identifiers")

    individual_ref = {
        "reference": f"Individual/{individual_id.namespace_uri}|{individual_id.value}",
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
