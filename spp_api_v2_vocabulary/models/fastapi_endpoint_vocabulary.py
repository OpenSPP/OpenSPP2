# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include Vocabulary router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2VocabularyEndpoint(models.Model):
    """Extend FastAPI endpoint for Vocabulary API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add Vocabulary router to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.vocabulary import vocabulary_router

            routers.append(vocabulary_router)
        return routers
