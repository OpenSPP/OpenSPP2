# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared membership utilities for API V2 services."""

from typing import Any

from odoo.exceptions import ValidationError

from .registrant_resolver import primary_registry_id


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
    group_id = primary_registry_id(group)
    if not group_id:
        raise ValidationError(f"Group {group.name} has no valid external identifiers")

    # id_type_id.uri (full code URI), NOT namespace_uri: the reference must
    # resolve through the identifier lookups, which match on the code URI
    group_ref = {
        "reference": f"Group/{group_id.id_type_id.uri}|{group_id.value}",
        "display": group.name,
    }

    # Build individual reference
    individual = membership.individual
    individual_id = primary_registry_id(individual)
    if not individual_id:
        raise ValidationError(f"Individual {individual.name} has no valid external identifiers")

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
