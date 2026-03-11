"""
CEL Vocabulary Functions - Odoo Model Integration.

Registers vocabulary-aware CEL functions with the function registry and
provides environment-aware wrappers for pure Python functions.

ADR-016 Phase 3: CEL Integration for vocabulary-aware expressions.
"""

import logging

from odoo import api, models

from ..services import cel_vocabulary_functions as vocab_funcs

_logger = logging.getLogger(__name__)


class CelVocabularyFunctions(models.AbstractModel):
    """Model that manages vocabulary-aware CEL function registration.

    This model:
    1. Wraps pure Python functions with Odoo environment
    2. Registers functions with the CEL function registry
    3. Provides lifecycle management (install/uninstall)
    """

    _name = "spp.cel.vocabulary.functions"
    _description = "CEL Vocabulary Functions"

    def _register_hook(self):
        """Ensure vocabulary functions are registered on every server start."""
        super()._register_hook()
        # Note: We can't call register_vocabulary_functions here because
        # _register_hook runs before database context is available.
        # Functions are registered via post_init_hook on module install,
        # but the registry is cleared on server restart.
        # To handle this, we mark that registration is needed and do it
        # lazily on first access.
        self.__class__._needs_registration = True
        _logger.debug("[CEL Vocabulary] Marked for lazy registration on first access")

    @api.model
    def _ensure_registered(self):
        """Ensure vocabulary functions are registered (lazy initialization)."""
        if getattr(self.__class__, "_needs_registration", True):
            self.register_vocabulary_functions()
            self.__class__._needs_registration = False

    @api.model
    def _create_env_marker(self, func):
        """Create a marker wrapper indicating this function needs env injection.

        The actual environment injection happens at evaluation time in the
        CEL service, which wraps the function with its current environment.

        This approach avoids capturing a stale environment/cursor in the closure
        at registration time.

        Args:
            func: Pure Python function that expects env as first parameter

        Returns:
            The function marked as needing environment injection
        """
        # Mark the function as needing environment injection
        func._cel_needs_env = True

        return func

    @api.model
    def register_vocabulary_functions(self):
        """Register all vocabulary functions with the CEL function registry.

        This method is called during module installation and whenever
        function registration needs to be refreshed.

        Returns:
            int: Number of functions registered
        """
        registry = self.env["spp.cel.function.registry"]
        count = 0

        for name, func in vocab_funcs.VOCABULARY_FUNCTIONS.items():
            # Mark the function as needing environment injection
            # (actual injection happens at evaluation time in CEL service)
            marked = self._create_env_marker(func)

            # Register with CEL function registry
            if registry.register(name, marked):
                count += 1
                _logger.debug("[CEL Vocabulary] Registered function '%s'", name)

        _logger.info("[CEL Vocabulary] Registered %d vocabulary function(s)", count)

        return count

    @api.model
    def unregister_vocabulary_functions(self):
        """Unregister vocabulary functions from the CEL function registry.

        This method is called during module uninstallation.

        Returns:
            int: Number of functions unregistered
        """
        registry = self.env["spp.cel.function.registry"]
        count = 0

        for name in vocab_funcs.VOCABULARY_FUNCTIONS.keys():
            if registry.unregister(name):
                count += 1
                _logger.debug("[CEL Vocabulary] Unregistered function '%s'", name)

        _logger.info("[CEL Vocabulary] Unregistered %d vocabulary function(s)", count)

        return count

    @api.model
    def get_function_list(self):
        """Get list of all registered vocabulary functions.

        Returns:
            list: List of function names
        """
        return list(vocab_funcs.VOCABULARY_FUNCTIONS.keys())

    @api.model
    def get_function_help(self, function_name):
        """Get help documentation for a vocabulary function.

        Args:
            function_name (str): Name of the function

        Returns:
            str: Function docstring or empty string
        """
        func = vocab_funcs.VOCABULARY_FUNCTIONS.get(function_name)
        return func.__doc__ if func else ""
