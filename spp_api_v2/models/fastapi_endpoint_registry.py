# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models

from fastapi import APIRouter, FastAPI

_logger = logging.getLogger(__name__)


class SppApiV2Endpoint(models.Model):
    """FastAPI endpoint for OpenSPP API V2"""

    _inherit = "fastapi.endpoint"

    app: str = fields.Selection(
        selection_add=[("api_v2", "OpenSPP API V2")],
        ondelete={"api_v2": "cascade"},
    )

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Return the API routers for API V2"""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            # Import routers (cannot import at top due to dependency graph)
            from ..routers.batch import batch_router
            from ..routers.bulk import bulk_router
            from ..routers.consent import router as consent_router
            from ..routers.filter import (
                group_filter_router,
                individual_filter_router,
            )
            from ..routers.group import group_router
            from ..routers.individual import individual_router
            from ..routers.metadata import metadata_router
            from ..routers.oauth import oauth_router

            routers.extend(
                [
                    oauth_router,
                    metadata_router,
                    individual_router,
                    individual_filter_router,
                    group_router,
                    group_filter_router,
                    batch_router,
                    bulk_router,
                    consent_router,
                ]
            )
        return routers

    def _get_app(self) -> FastAPI:
        """Configure FastAPI app for V2 API"""
        if self.app == "api_v2":
            # Create FastAPI app with OpenSPP API V2 metadata
            app = FastAPI(
                title="OpenSPP API V2",
                version="2.0.0",
                description="Standards-aligned, consent-respecting API for social protection data exchange",
                contact={
                    "name": "OpenSPP",
                    "url": "https://openspp.org",
                },
                license_info={
                    "name": "LGPL-3.0",
                    "identifier": "LGPL-3.0-or-later",
                },
                docs_url="/docs",
                redoc_url="/redoc",
                openapi_url="/openapi.json",
            )
            # Include all routers
            for router in self._get_fastapi_routers():
                app.include_router(router=router)
            # Add dependency overrides
            app.dependency_overrides.update(self._get_app_dependencies_overrides())
            # Add version middleware to include X-API-Version header in all responses
            from ..middleware.version import VersionMiddleware

            app.add_middleware(VersionMiddleware)
            # V2 API uses public endpoint with JWT authentication in middleware
            # No default authentication required at app level
            return app
        return super()._get_app()

    @api.model
    def sync_endpoint_id_with_registry(self, endpoint_id):
        """Sync endpoint registry (called by endpoint sync mechanism)"""
        return self.browse(endpoint_id).action_sync_registry()
