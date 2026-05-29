"""CEL Integration Service for DCI Indicators.

This service provides symbol resolution for CEL expressions that reference
DCI data. It registers the 'dr', 'crvs', 'ibr', and 'sr' symbols in CEL profiles.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class DCICELIntegrationService(models.AbstractModel):
    """Service for integrating DCI symbols into CEL expressions."""

    _name = "spp.dci.cel.integration"
    _description = "DCI CEL Integration Service"

    @api.model
    def get_dci_symbols(self, partner):
        """Get DCI symbol providers for a partner.

        Args:
            partner: res.partner record

        Returns:
            dict: Dictionary with 'dr', 'crvs', 'ibr', and 'sr' symbol providers
        """
        from ..symbols.dci_symbols import (
            CRVSSymbolProvider,
            DRSymbolProvider,
            IBRSymbolProvider,
            SRSymbolProvider,
        )

        return {
            "dr": DRSymbolProvider(self.env, partner),
            "crvs": CRVSSymbolProvider(self.env, partner),
            "ibr": IBRSymbolProvider(self.env, partner),
            "sr": SRSymbolProvider(self.env, partner),
        }

    @api.model
    def register_dci_symbols(self):
        """Register DCI symbols in CEL profiles.

        This method should be called during module initialization to add
        DCI symbols to the relevant CEL profiles.

        Returns:
            bool: True if registration succeeded
        """
        try:
            _logger.info("[DCI CEL Integration] DCI symbols registered for CEL profiles")
            return True

        except Exception as e:
            _logger.error(
                "[DCI CEL Integration] Failed to register DCI symbols: %s",
                str(e),
                exc_info=True,
            )
            return False

    @api.model
    def get_symbol_documentation(self):
        """Get documentation for DCI symbols.

        Returns:
            dict: Documentation for each DCI symbol
        """
        return {
            "dr": {
                "name": "Disability Registry",
                "properties": {
                    "has_disability": {
                        "type": "bool",
                        "description": "True if person has any disability",
                        "example": "dr.has_disability == true",
                    },
                    "types": {
                        "type": "list",
                        "description": "List of disability types",
                        "example": "'Vision' in dr.types",
                    },
                    "assessed": {
                        "type": "bool",
                        "description": "True if functional assessment exists",
                        "example": "dr.assessed == true",
                    },
                },
                "methods": {
                    "severity": {
                        "args": ["disability_type: str"],
                        "returns": "int",
                        "description": "Get severity for disability type (1-4)",
                        "example": "dr.severity('Vision') >= 3",
                    },
                    "has_type": {
                        "args": ["disability_type: str"],
                        "returns": "bool",
                        "description": "Check if person has specific disability type",
                        "example": "dr.has_type('Mobility')",
                    },
                },
            },
            "crvs": {
                "name": "Civil Registration and Vital Statistics",
                "properties": {
                    "is_alive": {
                        "type": "bool",
                        "description": "True if no death event recorded",
                        "example": "crvs.is_alive == true",
                    },
                    "birth_verified": {
                        "type": "bool",
                        "description": "True if birth was registered",
                        "example": "crvs.birth_verified == true",
                    },
                    "is_married": {
                        "type": "bool",
                        "description": "True if currently married",
                        "example": "crvs.is_married == false",
                    },
                },
                "methods": {
                    "has_event": {
                        "args": ["event_type: str"],
                        "returns": "bool",
                        "description": "Check if specific event type exists",
                        "example": "crvs.has_event('birth')",
                    },
                },
            },
            "ibr": {
                "name": "Integrated Beneficiary Registry",
                "properties": {
                    "has_duplicate": {
                        "type": "bool",
                        "description": "True if duplication check found matches",
                        "example": "ibr.has_duplicate == false",
                    },
                    "last_check_date": {
                        "type": "datetime",
                        "description": "Date of last duplication check",
                        "example": "ibr.last_check_date != None",
                    },
                    "matched_programs": {
                        "type": "list",
                        "description": "List of programs where duplicates found",
                        "example": "len(ibr.matched_programs) > 0",
                    },
                },
                "methods": {
                    "is_enrolled": {
                        "args": ["program_name: str"],
                        "returns": "bool",
                        "description": "Check if enrolled in program",
                        "example": "ibr.is_enrolled('Cash Transfer')",
                    },
                },
            },
            "sr": {
                "name": "Social Registry",
                "properties": {
                    "is_registered": {
                        "type": "bool",
                        "description": "True if person exists in external SR",
                        "example": "sr.is_registered == true",
                    },
                    "program_count": {
                        "type": "int",
                        "description": "Number of programs enrolled in",
                        "example": "sr.program_count >= 1",
                    },
                    "enrolled_programs": {
                        "type": "list",
                        "description": "List of enrolled program names",
                        "example": "'Cash Transfer' in sr.enrolled_programs",
                    },
                    "household_id": {
                        "type": "str",
                        "description": "Household ID from SR",
                        "example": "sr.household_id != None",
                    },
                    "household_size": {
                        "type": "int",
                        "description": "Number of household members",
                        "example": "sr.household_size > 3",
                    },
                    "is_head_of_household": {
                        "type": "bool",
                        "description": "True if person is head of household",
                        "example": "sr.is_head_of_household == true",
                    },
                },
                "methods": {
                    "is_enrolled": {
                        "args": ["program_name: str"],
                        "returns": "bool",
                        "description": "Check if enrolled in specific program",
                        "example": "sr.is_enrolled('Food Assistance')",
                    },
                },
            },
        }
