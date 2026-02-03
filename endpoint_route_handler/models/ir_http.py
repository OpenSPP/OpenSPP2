# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
import threading
from itertools import chain

import werkzeug

from odoo import SUPERUSER_ID, api, http, models
from odoo.modules.registry import Registry

from ..registry import EndpointRegistry

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _endpoint_route_registry(cls, env):
        return EndpointRegistry.registry_for(env.cr)

    @classmethod
    def _get_env_for_routing(cls):
        """Get an environment suitable for routing map generation.

        Returns http.request.env if available (during HTTP request),
        otherwise creates a new environment from the registry.
        """
        try:
            # Try to use http.request.env if available
            return http.request.env
        except RuntimeError:
            # No active HTTP request - create environment from registry
            dbname = threading.current_thread().dbname
            if dbname:
                registry = Registry(dbname)
                with registry.cursor() as cr:
                    return api.Environment(cr, SUPERUSER_ID, {})
        return None

    def _generate_routing_rules(self, modules, converters):
        # Override to inject custom endpoint rules.
        return chain(
            super()._generate_routing_rules(modules, converters),
            self._endpoint_routing_rules(),
        )

    def _endpoint_routing_rules(self):
        """Yield custom endpoint rules."""
        # Create registry directly from the cursor to avoid context issues
        try:
            dbname = threading.current_thread().dbname
            if dbname:
                registry = Registry(dbname)
                with registry.cursor() as cr:
                    e_registry = EndpointRegistry.registry_for(cr)
                    for endpoint_rule in e_registry.get_rules():
                        _logger.debug("LOADING %s", endpoint_rule)
                        endpoint = endpoint_rule.endpoint
                        for url in endpoint_rule.routing["routes"]:
                            yield (url, endpoint)
        except Exception as e:
            _logger.warning("Error loading endpoint routing rules: %s", e)

    def _endpoint_route_last_version(self):
        """Get the last version of endpoint routes for cache invalidation."""
        try:
            dbname = threading.current_thread().dbname
            if dbname:
                registry = Registry(dbname)
                with registry.cursor() as cr:
                    e_registry = EndpointRegistry.registry_for(cr)
                    return e_registry.last_version()
        except Exception as e:
            _logger.debug("Error getting endpoint route version: %s", e)
        return 0

    @classmethod
    def _get_routing_map_last_version(cls, env):
        return cls._endpoint_route_registry(env).last_version()

    @classmethod
    def _auth_method_user_endpoint(cls):
        """Special method for user auth which raises Unauthorized when needed.

        If you get an HTTP request (instead of a JSON one),
        the standard `user` method raises `SessionExpiredException`
        when there's no user session.
        This leads to a redirect to `/web/login`
        which is not desiderable for technical endpoints.

        This method makes sure that no matter the type of request we get,
        a proper exception is raised.
        """
        try:
            cls._auth_method_user()
        except http.SessionExpiredException as err:
            raise werkzeug.exceptions.Unauthorized() from err
