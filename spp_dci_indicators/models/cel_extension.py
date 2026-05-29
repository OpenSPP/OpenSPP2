"""CEL Extension for DCI Indicators.

This module extends the CEL executor to inject DCI symbols (dr, crvs, ibr)
into the evaluation context when compiling CEL expressions.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class CELExecutorDCIExtension(models.AbstractModel):
    """Extend CEL Executor to support DCI symbols."""

    _inherit = "spp.cel.executor"

    @api.model
    def _build_symbol_context(self, root_record, cfg):
        """Override to inject DCI symbols into the context.

        Args:
            root_record: The root record being evaluated
            cfg: CEL profile configuration

        Returns:
            dict: Symbol context with DCI symbols added
        """
        # Get base context from parent
        context = super()._build_symbol_context(root_record, cfg)

        # Only add DCI symbols for partner-based evaluations
        if not root_record or root_record._name != "res.partner":
            return context

        try:
            # Get DCI symbol providers
            dci_service = self.env["spp.dci.cel.integration"]
            dci_symbols = dci_service.get_dci_symbols(root_record)

            # Add DCI symbols to context
            context.update(dci_symbols)

            _logger.debug(
                "[DCI CEL Extension] Added DCI symbols for partner %s",
                root_record.id,
            )

        except Exception as e:
            _logger.warning(
                "[DCI CEL Extension] Failed to add DCI symbols: %s",
                str(e),
            )

        return context


class CELRegistryDCIExtension(models.AbstractModel):
    """Extend CEL Registry to document DCI symbols."""

    _inherit = "spp.cel.registry"

    @api.model
    def load_profile(self, profile, force_reload=False):
        """Override to add DCI symbols to profile configurations.

        Args:
            profile: Profile name
            force_reload: Force reload from source

        Returns:
            dict: Profile configuration with DCI symbols
        """
        # Get base profile
        cfg = super().load_profile(profile, force_reload=force_reload)

        # Add DCI symbols documentation to relevant profiles
        if profile in ["registry_individuals", "registry_groups"]:
            if "symbols" not in cfg:
                cfg["symbols"] = {}

            # Add DCI symbol definitions
            cfg["symbols"].update(
                {
                    "dr": {
                        "type": "provider",
                        "description": "Disability Registry data access",
                    },
                    "crvs": {
                        "type": "provider",
                        "description": "Civil Registration and Vital Statistics data",
                    },
                    "ibr": {
                        "type": "provider",
                        "description": "Integrated Beneficiary Registry duplication checks",
                    },
                }
            )

            _logger.debug(
                "[DCI CEL Extension] Added DCI symbols to profile '%s'",
                profile,
            )

        return cfg


# NOTE: IndicatorDefinitionDCIExtension was removed as spp.indicator.definition
# has been deprecated in favor of the unified spp.cel.variable system.
# DCI examples can be found in data/indicator_data.xml which creates
# spp.cel.variable records for DCI-related data points.
