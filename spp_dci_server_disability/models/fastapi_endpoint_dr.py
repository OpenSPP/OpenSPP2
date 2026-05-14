"""Replace spp_dci_server's 501 disability stub with the real router.

The base ``spp_dci_server.models.fastapi_endpoint_dci.SppDciServerEndpoint``
appends a ``disability_router`` to the FastAPI app that returns 501 for
every search request. Installing this module is what lights up the real
endpoint: the override below filters the stub out of the parent's
returned router list and substitutes our concrete
``disability_search_router``.

Why filtering instead of "just add our router on top":

  - FastAPI matches routes by registration order. The stub and the real
    router share the path ``/disability/registry/sync/search``, so the
    first-registered one wins. The parent's super() call adds the stub
    BEFORE we get a chance to add ours, so without filtering the stub
    keeps shadowing the real handler.
"""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppDciServerEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        routers = super()._get_fastapi_routers()
        if self.app != "dci_api":
            return routers

        try:
            from odoo.addons.spp_dci_server.routers.registry_aliases import (
                disability_router as stub_router,
            )
        except ImportError:
            stub_router = None

        from ..routers.disability_router import disability_search_router

        if stub_router is not None:
            # Remove the parent's stub if it's still in the list — keep any
            # other routers (CRVS, Farmer, Social, etc.) untouched.
            routers = [r for r in routers if r is not stub_router]

        routers.append(disability_search_router)
        return routers
