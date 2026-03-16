# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Process execution logic shared between sync (router) and async (model) paths."""

import logging

_logger = logging.getLogger(__name__)


def run_spatial_statistics(service, inputs, on_progress=None):
    """Run spatial-statistics process and return results.

    Args:
        service: SpatialQueryService instance
        inputs: Validated process inputs dict
        on_progress: Optional callback(completed_count) for batch progress tracking

    Returns:
        dict: Statistics results (registrant_ids stripped)
    """
    geometry = inputs.get("geometry")
    filters = inputs.get("filters")
    variables = inputs.get("variables")
    group_by = inputs.get("group_by")

    _logger.info(
        "run_spatial_statistics: variables=%r, filters=%r, geometry_type=%s",
        variables,
        filters,
        type(geometry).__name__,
    )

    if isinstance(geometry, list):
        # Batch mode: geometry is a list of {id, value} dicts
        geometries = [{"id": g["id"], "geometry": g["value"]} for g in geometry]
        result = service.query_statistics_batch(
            geometries=geometries,
            filters=filters,
            variables=variables,
            group_by=group_by,
            on_progress=on_progress,
        )
        for item in result.get("results", []):
            item.pop("registrant_ids", None)
        return result

    # Single geometry mode
    result = service.query_statistics(
        geometry=geometry,
        filters=filters,
        variables=variables,
        group_by=group_by,
    )
    result.pop("registrant_ids", None)
    return result


def run_proximity_statistics(service, inputs):
    """Run proximity-statistics process and return results.

    Args:
        service: SpatialQueryService instance
        inputs: Validated process inputs dict

    Returns:
        dict: Proximity statistics results (registrant_ids stripped)
    """
    result = service.query_proximity(
        reference_points=inputs["reference_points"],
        radius_km=inputs["radius_km"],
        relation=inputs.get("relation", "within"),
        filters=inputs.get("filters"),
        variables=inputs.get("variables"),
        group_by=inputs.get("group_by"),
    )
    result.pop("registrant_ids", None)
    return result
