# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Filter discovery + advanced search endpoints for Program and ProgramMembership.

Registers the Program / ProgramMembership resources into the shared
``RESOURCE_SERVICES`` registry defined in ``spp_api_v2`` and exposes their
``/_filters`` and ``/_search`` endpoints. The endpoint factories are reused
from the base filter module so behaviour is identical to the pre-split
implementation (OP#1081).
"""

from odoo.addons.spp_api_v2.routers.filter import (
    RESOURCE_SERVICES,
    _create_filter_metadata_endpoint,
    _create_search_endpoint,
)
from odoo.addons.spp_api_v2.schemas.bundle import Bundle
from odoo.addons.spp_api_v2.schemas.filter import FilterMetadataResponse

from fastapi import APIRouter

from ..services.program_membership_service import ProgramMembershipService
from ..services.program_service import ProgramService

# Register program resources into the shared filter registry so the generic
# search / filter factories resolve them at request time.
RESOURCE_SERVICES["Program"] = {
    "service_class": ProgramService,
    "model": "spp.program",
    "base_domain": [],
    "consent_type": None,
}
RESOURCE_SERVICES["ProgramMembership"] = {
    "service_class": ProgramMembershipService,
    "model": "spp.program.membership",
    "base_domain": [],
    "consent_type": "program_membership",
}

program_filter_router = APIRouter(tags=["Program"], prefix="/Program")
program_membership_filter_router = APIRouter(tags=["ProgramMembership"], prefix="/ProgramMembership")

# Register endpoints for Program
program_filter_router.add_api_route(
    "/_filters",
    _create_filter_metadata_endpoint("Program"),
    methods=["GET"],
    response_model=FilterMetadataResponse,
    response_model_exclude_none=True,
    summary="Get Program Filters",
    description="Get available filters and presets for Program resource",
)
program_filter_router.add_api_route(
    "/_search",
    _create_search_endpoint("Program"),
    methods=["POST"],
    response_model=Bundle,
    response_model_exclude_none=True,
    summary="Advanced Program Search",
    description="Search programs with complex filter conditions",
)

# Register endpoints for ProgramMembership
program_membership_filter_router.add_api_route(
    "/_filters",
    _create_filter_metadata_endpoint("ProgramMembership"),
    methods=["GET"],
    response_model=FilterMetadataResponse,
    response_model_exclude_none=True,
    summary="Get ProgramMembership Filters",
    description="Get available filters and presets for ProgramMembership resource",
)
program_membership_filter_router.add_api_route(
    "/_search",
    _create_search_endpoint("ProgramMembership"),
    methods=["POST"],
    response_model=Bundle,
    response_model_exclude_none=True,
    summary="Advanced ProgramMembership Search",
    description="Search program memberships with complex filter conditions",
)
