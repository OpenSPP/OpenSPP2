# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SPDCI-compliant short-form Social Registry endpoint aliases (/sr/*).

This module provides thin redirects from SPDCI short-form paths to our
main implementation paths. No business logic duplication.

Endpoint redirects:
- /sr/sync/search     -> uses social_search.sync_search
- /sr/search          -> uses async_router.async_search
- /sr/subscribe       -> uses async_router.subscribe
- /sr/unsubscribe     -> uses async_router.unsubscribe
- /sr/txn/status      -> uses async_router.txn_status
- /sr/sync/txn/status -> uses async_router.txn_status (sync mode)
"""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import (
    SearchRequest,
    SearchResponse,
)

from fastapi import APIRouter, Depends

_logger = logging.getLogger(__name__)

# Social Registry short-form router with /sr prefix (SPDCI compliance)
sr_alias_router = APIRouter(tags=["SPDCI Social Registry Aliases"], prefix="/sr")


@sr_alias_router.post(
    "/sync/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
)
async def sr_sync_search(
    request: SearchRequest,
    env: Annotated[Environment, Depends(odoo_env)],
):
    """Alias for /registry/social/sync/search."""
    from .social_search import sync_search

    return await sync_search(request, env)


# Note: For async endpoints (/sr/search, /sr/subscribe, etc.), these are
# handled by the base spp_dci_server async_router which already provides
# the correct paths. If you need /sr/* aliases for those, add them here
# by importing and calling the corresponding functions from async_router.
