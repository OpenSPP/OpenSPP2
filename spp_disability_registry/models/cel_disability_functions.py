"""
CEL Disability Functions - Odoo Model Integration.

Registers disability-related CEL functions with the function registry.
"""

import logging

from odoo import api, models

from ..services import cel_functions as disability_funcs

_logger = logging.getLogger(__name__)


class CelDisabilityFunctions(models.AbstractModel):
    """Model that manages disability CEL function registration.

    This model:
    1. Wraps pure Python functions with Odoo environment marker
    2. Registers functions with the CEL function registry
    3. Provides lifecycle management (install/uninstall)
    """

    _name = "spp.cel.disability.functions"
    _description = "CEL Disability Functions"

    def _register_hook(self):
        """Mark for lazy registration on server start."""
        super()._register_hook()
        self.__class__._needs_registration = True
        _logger.debug("[CEL Disability] Marked for lazy registration")

    @api.model
    def _ensure_registered(self):
        """Ensure disability functions are registered (lazy initialization)."""
        if getattr(self.__class__, "_needs_registration", True):
            self.register_disability_functions()
            self.__class__._needs_registration = False

    @api.model
    def _create_env_marker(self, func):
        """Mark function as needing env injection.

        The actual environment injection happens at evaluation time.
        """
        func._cel_needs_env = True
        return func

    @api.model
    def register_disability_functions(self):
        """Register all disability functions with CEL function registry.

        Returns:
            int: Number of functions registered
        """
        registry = self.env["spp.cel.function.registry"]
        count = 0

        for name, func in disability_funcs.DISABILITY_FUNCTIONS.items():
            marked = self._create_env_marker(func)

            if registry.register(name, marked):
                count += 1
                _logger.debug(f"[CEL Disability] Registered function '{name}'")

        _logger.info(f"[CEL Disability] Registered {count} disability function(s)")
        return count

    @api.model
    def unregister_disability_functions(self):
        """Unregister disability functions from CEL registry.

        Returns:
            int: Number of functions unregistered
        """
        registry = self.env["spp.cel.function.registry"]
        count = 0

        for name in disability_funcs.DISABILITY_FUNCTIONS.keys():
            if registry.unregister(name):
                count += 1
                _logger.debug(f"[CEL Disability] Unregistered function '{name}'")

        _logger.info(f"[CEL Disability] Unregistered {count} disability function(s)")
        return count

    @api.model
    def get_function_list(self):
        """Get list of registered disability functions.

        Returns:
            list: List of function names
        """
        return list(disability_funcs.DISABILITY_FUNCTIONS.keys())

    @api.model
    def get_function_help(self, function_name):
        """Get help documentation for a disability function.

        Args:
            function_name (str): Name of the function

        Returns:
            str: Function docstring or empty string
        """
        func = disability_funcs.DISABILITY_FUNCTIONS.get(function_name)
        return func.__doc__ if func else ""
