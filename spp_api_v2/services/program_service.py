# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Program resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ProgramService:
    """Service for Program resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, system_uri: str, value: str):
        """
        Lookup program by external identifier.

        CRITICAL: Uses full code URI for identifier type.

        Args:
            system_uri: Full URI of identifier type (e.g., urn:openspp:vocab:program-id#program_code)
            value: Identifier value

        Returns:
            spp.program record or empty recordset
        """
        # Programs may have identifiers in spp.registry.id if they're linked to a partner
        # or they may have their own identifier system. Let's check both approaches.

        # First, try to find via program's own identifier if it has one
        # For now, we'll search by a field on spp.program if it exists
        # Check if program has external identifiers stored

        # Since spp.program doesn't inherit from res.partner and may not have
        # spp.registry.id records, we'll need to look at how programs store their IDs.
        # Based on the model, programs don't have a standard external ID field.
        # We'll need to check if there's a program_id module or use name matching.

        # Try searching in spp.program.id model if it exists (from spp_program_id module)
        # NOTE: If spp.program.id uses vocabulary codes, update to use id_type_id.uri
        if "spp.program.id" in self.env:
            prog_id = (
                self.env["spp.program.id"]
                .sudo()
                .search(
                    [
                        ("namespace_uri", "=", system_uri),
                        ("value", "=", value),
                    ],
                    limit=1,
                )
            )
            if prog_id and prog_id.program_id:
                return prog_id.program_id

        # Fallback: try to find by name-derived slug when spp.program.id is not available
        if system_uri == "urn:openspp:program":
            # Convert slug back to name for search (e.g., "test-program" -> "test program")
            name_guess = value.replace("-", " ")
            program = (
                self.env["spp.program"]
                .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
                .search(
                    [("name", "=ilike", name_guess)],
                    limit=1,
                )
            )
            if program:
                return program

        return self.env["spp.program"]

    def to_api_schema(self, program, extensions=None) -> dict[str, Any]:
        """
        Convert Odoo program to Program API schema.

        CRITICAL REQUIREMENTS:
        - NO database IDs exposed
        - Use namespace_uri for identifiers
        - Include source tracking in meta

        Args:
            program: spp.program record
            extensions: List of extension names to include (or None for none)

        Returns:
            Dictionary matching Program schema
        """
        if not program:
            return {}

        # Build identifier list (REQUIRED, at least one)
        identifiers = []

        # Check if program has external identifiers
        if "spp.program.id" in self.env and hasattr(program, "program_id_ids"):
            for prog_id in program.program_id_ids:
                if prog_id.namespace_uri and prog_id.value:
                    identifiers.append(
                        {
                            "system": prog_id.namespace_uri,
                            "value": prog_id.value,
                        }
                    )

        # If no identifiers found, create a default one using program name
        if not identifiers:
            # Use program name as fallback identifier
            identifiers.append(
                {
                    "system": "urn:openspp:program",
                    "value": program.name.lower().replace(" ", "-"),
                }
            )

        # Build program type CodeableConcept
        # Programs don't have a standard type field in base module
        # Default to a generic program type
        program_type = {
            "coding": [
                {
                    "system": "urn:openspp:vocab:program-type",
                    "code": "social-protection",
                    "display": "Social Protection Program",
                }
            ],
            "text": "Social Protection Program",
        }

        # Build Program resource
        program_data = {
            "type": "Program",
            "identifier": identifiers,
            "active": program.state == "active",
            "name": program.name,
            "description": program.description or None,
            "programType": program_type,
            "targetType": program.target_type,
        }

        # Eligibility criteria (human-readable text)
        # Programs may have eligibility managers, but we'll provide a simple text description
        if program.eligibility_manager_ids:
            program_data["eligibilityCriteria"] = (
                f"Program uses {len(program.eligibility_manager_ids)} eligibility manager(s)"
            )

        # Period - use date_ended if program is ended
        if program.state == "ended" and program.date_ended:
            program_data["period"] = {
                "start": None,
                "end": program.date_ended.isoformat() if program.date_ended else None,
            }

        # Metadata
        # Use integer microseconds for versionId to avoid float precision issues
        version_id = str(int(program.write_date.timestamp() * 1000000)) if program.write_date else "1"
        program_data["meta"] = {
            "versionId": version_id,
            "lastUpdated": program.write_date.isoformat() if program.write_date else None,
            "source": None,  # Programs don't have source tracking in base module
        }

        return program_data
