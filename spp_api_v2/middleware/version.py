# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
API Version Middleware - Adds version headers to all responses.

This middleware adds the X-API-Version header to all API responses,
providing clients with information about which API version they're using.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# API version - should match FastAPI app version
API_VERSION = "2.0.0"


class VersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds X-API-Version header to all responses.

    This helps API clients:
    - Verify they're talking to the expected API version
    - Debug version-related issues
    - Implement version-specific logic if needed
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-API-Version"] = API_VERSION
        return response
