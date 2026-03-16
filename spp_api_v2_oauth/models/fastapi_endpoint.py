# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2OAuthEndpoint(models.Model):
    """Extends FastAPI endpoint to add RS256 auth and token generation for API V2."""

    _inherit = "fastapi.endpoint"

    def _get_app_dependencies_overrides(self):
        overrides = super()._get_app_dependencies_overrides()
        if self.app == "api_v2":
            from odoo.addons.spp_api_v2.middleware.auth import (
                get_authenticated_client,
            )

            from ..middleware.auth_rs256 import get_authenticated_client_rs256

            overrides[get_authenticated_client] = get_authenticated_client_rs256
        return overrides

    def _get_fastapi_routers(self) -> list[APIRouter]:
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.oauth_rs256 import oauth_rs256_router

            routers.append(oauth_rs256_router)
        return routers
