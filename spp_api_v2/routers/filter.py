# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Filter discovery and advanced search endpoints."""

import logging
from typing import Annotated

from odoo.api import Environment
from odoo.osv import expression

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..middleware.auth import get_authenticated_client
from ..schemas.bundle import Bundle, BundleEntry, BundleLink, BundleSearch
from ..schemas.filter import FilterMetadataResponse, SearchRequest
from ..services.consent_service import ConsentService
from ..services.filter_service import FilterService
from ..services.group_service import GroupService
from ..services.individual_service import IndividualService

_logger = logging.getLogger(__name__)


# Router for filter metadata - mounted per resource
individual_filter_router = APIRouter(tags=["Individual"], prefix="/Individual")
group_filter_router = APIRouter(tags=["Group"], prefix="/Group")


# Service mapping for resource types. Companion modules (e.g. spp_api_v2_programs)
# register their own resources into this dict at import time.
RESOURCE_SERVICES = {
    "Individual": {
        "service_class": IndividualService,
        "model": "res.partner",
        "base_domain": [("is_registrant", "=", True), ("is_group", "=", False)],
        "consent_type": "individual",
    },
    "Group": {
        "service_class": GroupService,
        "model": "res.partner",
        "base_domain": [("is_registrant", "=", True), ("is_group", "=", True)],
        "consent_type": "group",
    },
}


def _create_filter_metadata_endpoint(resource_name: str):
    """Factory to create filter metadata endpoint for a resource."""

    async def get_filters(
        env: Annotated[Environment, Depends(odoo_env)],
        api_client: Annotated[object, Depends(get_authenticated_client)],
    ) -> FilterMetadataResponse:
        """
        Get available filters for this resource.

        Returns metadata about all filterable fields and saved presets.
        """
        filter_service = FilterService(env)
        metadata = filter_service.get_filter_metadata(resource_name, api_client)

        return FilterMetadataResponse(**metadata)

    return get_filters


def _create_search_endpoint(resource_name: str):
    """Factory to create advanced search endpoint for a resource."""

    async def search(
        search_request: SearchRequest,
        env: Annotated[Environment, Depends(odoo_env)],
        api_client: Annotated[object, Depends(get_authenticated_client)],
        extensions: Annotated[str | None, Query(alias="_extensions")] = None,
    ) -> Bundle:
        """
        Advanced search with complex filter conditions.

        Supports:
        - Simple filters with various operators
        - Compound AND/OR logic
        - Saved presets
        - Pagination and sorting
        """
        resource_config = RESOURCE_SERVICES.get(resource_name)
        if not resource_config:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unknown resource type: {resource_name}",
            )

        filter_service = FilterService(env)

        # Build domain from filters
        domain = list(resource_config["base_domain"])

        # Validate complexity
        all_filters = []
        if search_request.filters:
            all_filters.extend(search_request.filters)
        if search_request.additional_filters:
            all_filters.extend(search_request.additional_filters)

        if all_filters:
            is_valid, error = filter_service.validate_filter_complexity(
                [f.model_dump() for f in all_filters],
                resource_name,
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error,
                )

        # Apply preset if specified
        if search_request.preset:
            preset_domain = filter_service.apply_preset(
                search_request.preset,
                resource_name,
                [f.model_dump() for f in search_request.additional_filters]
                if search_request.additional_filters
                else None,
                api_client,
            )
            domain.extend(preset_domain)
        elif search_request.filters:
            # Apply filters
            filter_domain = filter_service.parse_json_filters(
                [f.model_dump() for f in search_request.filters],
                resource_name,
                api_client,
                search_request.filter_logic,
            )
            domain.extend(filter_domain)

        # Build pagination
        pagination = search_request.pagination
        count = pagination.count if pagination else 20
        last_id = pagination.last_id if pagination and hasattr(pagination, "last_id") else None

        # Build sort order
        order = "id"  # Use id for cursor-based pagination
        if search_request.sort:
            sort_parts = []
            for sort_field in search_request.sort:
                direction = "DESC" if sort_field.direction.lower() == "desc" else "ASC"
                sort_parts.append(f"{sort_field.field} {direction}")
            if sort_parts:
                # Append id to maintain cursor pagination
                sort_parts.append("id ASC")
                order = ", ".join(sort_parts)

        # Apply cursor-based pagination
        if last_id is not None:
            domain = expression.AND([domain, [("id", ">", last_id)]])

        # Execute search with consent-aware over-fetching for cursor-based pagination
        Model = env[resource_config["model"]]
        service = resource_config["service_class"](env)
        consent_service = ConsentService(env)
        extension_list = extensions.split(",") if extensions else None

        consent_type = resource_config["consent_type"]
        total = Model.search_count(domain)

        # Over-fetch to fill page when consent filtering removes records
        entries = []
        consent_was_applied = False
        cursor_domain = list(domain)
        max_overfetch = count * 3
        fetched_so_far = 0
        last_record_id = None

        while len(entries) < count and fetched_so_far < max_overfetch:
            batch_size = min(count * 2, max_overfetch - fetched_so_far)
            records = Model.search(cursor_domain, limit=batch_size, order=order)
            if not records:
                break
            for record in records:
                last_record_id = record.id
                data = service.to_api_schema(record, extensions=extension_list)

                if consent_type:
                    partner_id = record.id if resource_config["model"] == "res.partner" else None
                    if partner_id:
                        data = consent_service.filter_response(partner_id, api_client, consent_type, data)
                        consent_info = data.pop("_consent", None)
                        if consent_info and consent_info.get("status") in (
                            "no_consent",
                            "scope_mismatch",
                        ):
                            consent_was_applied = True
                            continue

                entries.append(
                    BundleEntry(
                        resource=data,
                        search=BundleSearch(mode="match", score=1.0),
                    )
                )
                if len(entries) >= count:
                    break

            fetched_so_far += len(records)
            # Advance cursor past fetched records
            if records:
                cursor_domain = expression.AND([domain, [("id", ">", records[-1].id)]])
            if len(records) < batch_size:
                break

        entries = entries[:count]

        # Suppress total when consent filtering is active
        if consent_was_applied:
            total = len(entries)

        # Build pagination links using cursor-based pagination (last_id)
        base_url = f"/api/v2/spp/{resource_name}/_search"
        last_id_param = f"&_lastId={last_id}" if last_id is not None else ""
        links = [
            BundleLink(
                relation="self",
                url=f"{base_url}?_count={count}{last_id_param}",
            )
        ]

        if len(entries) >= count and last_record_id is not None:
            links.append(
                BundleLink(
                    relation="next",
                    url=f"{base_url}?_count={count}&_lastId={last_record_id}",
                )
            )

        return Bundle(
            resourceType="Bundle",
            type="searchset",
            total=total,
            link=links,
            entry=entries,
        )

    return search


# Register endpoints for Individual
individual_filter_router.add_api_route(
    "/_filters",
    _create_filter_metadata_endpoint("Individual"),
    methods=["GET"],
    response_model=FilterMetadataResponse,
    response_model_exclude_none=True,
    summary="Get Individual Filters",
    description="Get available filters and presets for Individual resource",
)

individual_filter_router.add_api_route(
    "/_search",
    _create_search_endpoint("Individual"),
    methods=["POST"],
    response_model=Bundle,
    response_model_exclude_none=True,
    summary="Advanced Individual Search",
    description="Search individuals with complex filter conditions",
)

# Register endpoints for Group
group_filter_router.add_api_route(
    "/_filters",
    _create_filter_metadata_endpoint("Group"),
    methods=["GET"],
    response_model=FilterMetadataResponse,
    response_model_exclude_none=True,
    summary="Get Group Filters",
    description="Get available filters and presets for Group resource",
)

group_filter_router.add_api_route(
    "/_search",
    _create_search_endpoint("Group"),
    methods=["POST"],
    response_model=Bundle,
    response_model_exclude_none=True,
    summary="Advanced Group Search",
    description="Search groups with complex filter conditions",
)
