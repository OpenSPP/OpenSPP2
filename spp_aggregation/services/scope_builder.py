# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared scope building utilities for API layers.

This module provides a unified interface for constructing scope dictionaries
that are compatible with the aggregation engine's scope resolver.

The scope dictionaries can be passed directly to spp.aggregation.service.compute_aggregation()
and will be resolved by spp.aggregation.scope.resolver.
"""


def build_area_scope(area_id, include_children=True):
    """Build scope dict for an area query.

    Args:
        area_id: ID of the spp.area record
        include_children: Whether to include child areas in scope (default: True)

    Returns:
        dict: Scope dict compatible with aggregation engine
            {
                "scope_type": "area",
                "area_id": int,
                "include_child_areas": bool,
            }

    Example:
        >>> scope = build_area_scope(area_id=123, include_children=True)
        >>> result = env['spp.aggregation.service'].compute_aggregation(scope=scope)
    """
    return {
        "scope_type": "area",
        "area_id": area_id,
        "include_child_areas": include_children,
    }


def build_cel_scope(cel_expression, profile="registry_individuals"):
    """Build scope dict for a CEL expression query.

    Args:
        cel_expression: CEL expression string to filter partners
        profile: CEL profile name (default: "registry_individuals")

    Returns:
        dict: Scope dict compatible with aggregation engine
            {
                "scope_type": "cel",
                "cel_expression": str,
                "cel_profile": str,
            }

    Example:
        >>> scope = build_cel_scope("partner.age > 18")
        >>> result = env['spp.aggregation.service'].compute_aggregation(scope=scope)
    """
    return {
        "scope_type": "cel",
        "cel_expression": cel_expression,
        "cel_profile": profile,
    }


def build_explicit_scope(partner_ids):
    """Build scope dict for an explicit set of partner IDs.

    Args:
        partner_ids: List or set of partner IDs

    Returns:
        dict: Scope dict compatible with aggregation engine
            {
                "scope_type": "explicit",
                "explicit_partner_ids": list[int],
            }

    Example:
        >>> scope = build_explicit_scope([1, 2, 3])
        >>> result = env['spp.aggregation.service'].compute_aggregation(scope=scope)
    """
    return {
        "scope_type": "explicit",
        "explicit_partner_ids": list(partner_ids),
    }
