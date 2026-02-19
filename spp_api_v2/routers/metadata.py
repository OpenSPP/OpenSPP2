# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Metadata endpoint for API capability discovery"""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends

from ..schemas.api_metadata import (
    ApiMetadata,
    AuthenticationMetadata,
    ExtensionMetadata,
    ResourceMetadata,
)

_logger = logging.getLogger(__name__)

metadata_router = APIRouter(tags=["Metadata"])


@metadata_router.get("/metadata", response_model=ApiMetadata)
async def get_metadata(
    env: Annotated[Environment, Depends(odoo_env)],
):
    """
    Get API capability information.

    Returns information about:
    - API name and version
    - Supported resources (Individual, Group, Program, ProgramMembership)
    - Supported operations per resource (read, search, create, update)
    - Available search parameters per resource
    - Available extensions from optional modules
    - Authentication configuration
    - Documentation URL

    This endpoint is public (no authentication required).
    """
    # Build resources dict with metadata for each resource type
    resources = {
        "Individual": ResourceMetadata(
            operations=["read", "search", "create", "update", "patch"],
            search_params=[
                "identifier",
                "name",
                "birthdate",
                "gender",
                "address",
                "group",
            ],
        ),
        "Group": ResourceMetadata(
            operations=["read", "search", "create", "update", "patch"],
            search_params=["identifier", "name", "type", "member"],
        ),
        "Program": ResourceMetadata(
            operations=["read", "search"],
            search_params=["identifier", "name", "status", "type", "targetType"],
        ),
        "ProgramMembership": ResourceMetadata(
            operations=["read", "search", "create", "update"],
            search_params=["beneficiary", "program", "status"],
        ),
    }

    # Build extensions from registered API extensions
    extensions = _get_extensions(env)

    # Get OpenSPP version
    modules = env["ir.module.module"].sudo()  # nosemgrep: odoo-sudo-without-context
    spp_base = modules.search([("name", "=", "spp_base")], limit=1)
    version = spp_base.latest_version if spp_base else "2.0.0"

    return ApiMetadata(
        name="OpenSPP API",
        version=version,
        resources=resources,
        extensions=extensions,
        authentication=AuthenticationMetadata(
            type="oauth2",
            token_endpoint="/api/v2/spp/oauth/token",
            grant_types=["client_credentials"],
        ),
        docs="/api/v2/spp/docs",
    )


def _get_extensions(env: Environment) -> list[ExtensionMetadata]:
    """
    Get list of available extensions.

    Extensions are registered by modules via spp.api.extension model.
    Each extension provides additional fields for specific resource types.
    """
    extensions = []

    # Query active extensions (public endpoint, use sudo for access)
    ext_model = env["spp.api.extension"].sudo()  # nosemgrep: odoo-sudo-without-context
    active_extensions = ext_model.search([("active", "=", True), ("module_id.state", "=", "installed")])

    for ext in active_extensions:
        # Determine which resources this extension applies to
        applies_to_list = []
        if ext.applies_to == "individual":
            applies_to_list = ["Individual"]
        elif ext.applies_to == "group":
            applies_to_list = ["Group"]
        elif ext.applies_to == "both":
            applies_to_list = ["Individual", "Group"]

        # Get field names
        field_names = ext.get_field_names()

        extensions.append(
            ExtensionMetadata(
                url=ext.url,
                module=ext.module_id.name,
                applies_to=applies_to_list,
                fields=field_names,
            )
        )

    return extensions
