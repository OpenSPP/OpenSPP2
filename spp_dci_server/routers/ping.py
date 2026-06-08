# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI authenticated ping endpoint.

A lightweight endpoint clients can call to verify both reachability *and*
their bearer-token configuration in one request. Unlike the search routes it
requires only a valid bearer token (no signed DCI envelope), so a plain GET is
enough — which is exactly what the client's "Test Connection" needs.
"""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends

from ..middleware.signature import verify_bearer_token

_logger = logging.getLogger(__name__)

dci_ping_router = APIRouter(tags=["DCI Ping"])


@dci_ping_router.get("/ping")
async def ping(
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """Authenticated liveness/auth check.

    Returns 200 with the server's sender id when the bearer token is accepted.
    The ``verify_bearer_token`` dependency raises 401 when the token is missing
    or not in the configured ``dci.api_tokens`` allow-list, so a client can
    distinguish a reachable-but-misconfigured server from a working one.

    **Authentication**: Bearer token only (no DCI signature required).
    """
    # nosemgrep: odoo-sudo-without-context
    sender_id = env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")
    return {"status": "ok", "sender_id": sender_id}
