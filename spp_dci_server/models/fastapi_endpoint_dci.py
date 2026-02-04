# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint for DCI API."""

import json
import logging
import uuid
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from odoo import fields, models

from fastapi import APIRouter, FastAPI, Request

_logger = logging.getLogger(__name__)


def _format_dci_error_response(status_code: int, detail: str) -> dict:
    """Format an error response according to DCI specification.

    Args:
        status_code: HTTP status code
        detail: Error detail message

    Returns:
        DCI-compliant error response dict
    """
    return {
        "message": {
            "ack_status": "ERR",
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": str(uuid.uuid4()),
            "error": {
                "code": f"err.{status_code}",
                "message": detail,
            },
        }
    }


class DCIErrorResponseMiddleware(BaseHTTPMiddleware):
    """Middleware to convert error responses to DCI-compliant format.

    This middleware intercepts responses with error status codes (4xx, 5xx)
    and reformats them according to the DCI specification, which requires
    ack_status, timestamp, correlation_id, and error fields.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only transform error responses (4xx and 5xx)
        if response.status_code >= 400:
            # Read the response body
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk

            # Try to parse as JSON
            try:
                body = json.loads(body_bytes.decode("utf-8"))

                # Only transform if it's a simple error response (not already DCI formatted)
                if "detail" in body and "message" not in body:
                    detail = body.get("detail", "Unknown error")
                    if isinstance(detail, dict) or isinstance(detail, list):
                        detail = json.dumps(detail)

                    dci_body = _format_dci_error_response(response.status_code, str(detail))
                    new_body = json.dumps(dci_body)

                    # Create new response with DCI format
                    return Response(
                        content=new_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json",
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Not JSON, return as-is
                pass

            # Return original body if no transformation needed
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response


class SppDciServerEndpoint(models.Model):
    """DCI API FastAPI endpoint extension."""

    _inherit = "fastapi.endpoint"

    app: str = fields.Selection(
        selection_add=[("dci_api", "OpenSPP DCI API")],
        ondelete={"dci_api": "cascade"},
    )

    def _get_app(self) -> FastAPI:
        """Override to add DCI-specific middleware."""
        app = super()._get_app()
        if self.app == "dci_api":
            # Add DCI error response middleware
            app.add_middleware(DCIErrorResponseMiddleware)
        return app

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add DCI routers when app is dci_api."""
        routers = super()._get_fastapi_routers()
        if self.app == "dci_api":
            from ..routers.async_router import dci_async_router
            from ..routers.bulk_upload import dci_bulk_upload_router
            from ..routers.callbacks import dci_callback_router
            from ..routers.jwks import jwks_router
            from ..routers.receipt import dci_receipt_router
            from ..routers.registry_aliases import (
                crvs_router,
                disability_router,
                farmer_router,
            )
            from ..routers.search import dci_search_router

            # JWKS at root level (/.well-known/jwks.json)
            routers.append(jwks_router)

            # Registry operations under /social/registry prefix (SPDCI-compliant)
            social_router = APIRouter(prefix="/social/registry", tags=["Social Registry"])
            social_router.include_router(dci_search_router)
            social_router.include_router(dci_async_router)
            social_router.include_router(dci_callback_router)
            social_router.include_router(dci_bulk_upload_router)
            social_router.include_router(dci_receipt_router)
            routers.append(social_router)

            # Add SPDCI-compliant registry type endpoints (stub implementations)
            routers.append(disability_router)
            routers.append(crvs_router)
            routers.append(farmer_router)
        return routers
