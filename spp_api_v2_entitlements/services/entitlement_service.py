# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Entitlement resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class EntitlementService:
    """Service for Entitlement resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, identifier: str):
        """
        Lookup entitlement by identifier (code).

        Searches both cash and in-kind entitlements.

        Args:
            identifier: Entitlement code

        Returns:
            spp.entitlement or spp.entitlement.inkind record, or empty recordset
        """
        # First try cash entitlement
        entitlement = (
            self.env["spp.entitlement"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
            .search(
                # Read-only entitlement lookup via external code; callers are
                # restricted to API V2 groups.
                [("code", "=", identifier)],
                limit=1,
            )
        )
        if entitlement:
            return entitlement

        # Then try in-kind entitlement
        return (
            self.env["spp.entitlement.inkind"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(  # nosemgrep: odoo-sudo-on-sensitive-models
                # Read-only in-kind entitlement lookup via external code; callers
                # are restricted to API V2 groups.
                [("code", "=", identifier)],
                limit=1,
            )
        )

    def search(self, params: dict) -> tuple[Any, int]:
        """
        Search entitlements with parameters.

        Searches both cash and in-kind entitlements based on type parameter.

        Args:
            params: Search parameters dict

        Returns:
            Tuple of (recordset, total_count)

        Note:
            Authorization is handled at the router level via OAuth scope checks
            (api_client.has_scope("entitlement", "read")).
        """
        entitlement_type = params.get("type", "cash")

        if entitlement_type == "inkind":
            return self._search_inkind(params)
        else:
            return self._search_cash(params)

    def _search_cash(self, params: dict) -> tuple[Any, int]:
        """Search cash entitlements."""
        domain = []

        # Beneficiary filter (by external identifier)
        if params.get("beneficiary"):
            partner = self._find_partner_by_identifier(params["beneficiary"])
            if partner:
                domain.append(("partner_id", "=", partner.id))
            else:
                # No match, return empty
                return self.env["spp.entitlement"], 0

        # Program filter
        if params.get("program"):
            domain.append(("program_id.name", "ilike", params["program"]))

        # Cycle filter
        if params.get("cycle"):
            domain.append(("cycle_id.name", "ilike", params["cycle"]))

        # State filter
        if params.get("state"):
            domain.append(("state", "=", params["state"]))

        # Valid from filter
        if params.get("validFrom"):
            domain.append(("valid_from", ">=", params["validFrom"]))

        # Valid until filter
        if params.get("validUntil"):
            domain.append(("valid_until", "<=", params["validUntil"]))

        # Last updated filter
        if params.get("_lastUpdated"):
            last_updated = params["_lastUpdated"]
            if last_updated.startswith("ge"):
                domain.append(("write_date", ">=", last_updated[2:]))
            elif last_updated.startswith("le"):
                domain.append(("write_date", "<=", last_updated[2:]))
            elif last_updated.startswith("gt"):
                domain.append(("write_date", ">", last_updated[2:]))
            elif last_updated.startswith("lt"):
                domain.append(("write_date", "<", last_updated[2:]))
            else:
                domain.append(("write_date", ">=", last_updated))

        total = (
            self.env["spp.entitlement"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
            .search_count(
                # Read-only entitlement search restricted to
                # spp_api_v2.group_api_v2_viewer.
                domain
            )
        )

        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        records = (
            self.env["spp.entitlement"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
            .search(
                # Read-only entitlement search restricted to
                # spp_api_v2.group_api_v2_viewer.
                domain,
                limit=count,
                offset=offset,
                order="create_date desc",
            )
        )

        return records, total

    def _search_inkind(self, params: dict) -> tuple[Any, int]:
        """Search in-kind entitlements."""
        domain = []

        # Beneficiary filter
        if params.get("beneficiary"):
            partner = self._find_partner_by_identifier(params["beneficiary"])
            if partner:
                domain.append(("partner_id", "=", partner.id))
            else:
                return self.env["spp.entitlement.inkind"], 0

        # Program filter
        if params.get("program"):
            domain.append(("program_id.name", "ilike", params["program"]))

        # Cycle filter
        if params.get("cycle"):
            domain.append(("cycle_id.name", "ilike", params["cycle"]))

        # State filter
        if params.get("state"):
            domain.append(("state", "=", params["state"]))

        # Valid from filter
        if params.get("validFrom"):
            domain.append(("valid_from", ">=", params["validFrom"]))

        # Valid until filter
        if params.get("validUntil"):
            domain.append(("valid_until", "<=", params["validUntil"]))

        # Last updated filter
        if params.get("_lastUpdated"):
            last_updated = params["_lastUpdated"]
            if last_updated.startswith("ge"):
                domain.append(("write_date", ">=", last_updated[2:]))
            elif last_updated.startswith("le"):
                domain.append(("write_date", "<=", last_updated[2:]))
            elif last_updated.startswith("gt"):
                domain.append(("write_date", ">", last_updated[2:]))
            elif last_updated.startswith("lt"):
                domain.append(("write_date", "<", last_updated[2:]))
            else:
                domain.append(("write_date", ">=", last_updated))

        # nosemgrep: odoo-sudo-on-sensitive-models
        # Read-only entitlement search restricted to spp_api_v2.group_api_v2_viewer.
        total = self.env["spp.entitlement.inkind"].sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context

        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        # nosemgrep: odoo-sudo-on-sensitive-models
        # Read-only entitlement search restricted to spp_api_v2.group_api_v2_viewer.
        records = (
            self.env["spp.entitlement.inkind"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                domain,
                limit=count,
                offset=offset,
                order="create_date desc",
            )
        )

        return records, total

    def _find_partner_by_identifier(self, identifier: str):
        """Find partner by external identifier (system|value format)."""
        if "|" not in identifier:
            return None

        system, value = identifier.split("|", 1)

        # Use id_type_id.uri (full code URI) for consistency with spp_api_v2
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system),
                    ("value", "=", value),
                ],
                limit=1,
            )
        )
        return reg_id.partner_id if reg_id else None

    def to_api_schema(self, entitlement) -> dict[str, Any]:
        """
        Convert Odoo entitlement to API schema.

        CRITICAL: NO database IDs exposed

        Args:
            entitlement: spp.entitlement or spp.entitlement.inkind record

        Returns:
            Dictionary matching Entitlement schema
        """
        if not entitlement:
            return {}

        # Determine type
        is_cash = entitlement._name == "spp.entitlement"
        entitlement_type = "cash" if is_cash else "inkind"

        result = {
            "type": "Entitlement",
            "identifier": entitlement.code,
            "entitlementType": entitlement_type,
            "state": entitlement.state,
        }

        # Beneficiary reference
        partner = entitlement.partner_id
        if partner:
            result["beneficiary"] = self._build_partner_reference(partner)

        # Program reference
        if entitlement.program_id:
            result["program"] = {
                "reference": f"Program/{entitlement.program_id.name}",
                "display": entitlement.program_id.name,
            }

        # Cycle reference
        if entitlement.cycle_id:
            result["cycle"] = {
                "reference": f"Cycle/{entitlement.cycle_id.name}",
                "display": entitlement.cycle_id.name,
            }

        # Validity period
        if entitlement.valid_from or entitlement.valid_until:
            result["validPeriod"] = {}
            if entitlement.valid_from:
                result["validPeriod"]["start"] = entitlement.valid_from.isoformat()
            if entitlement.valid_until:
                result["validPeriod"]["end"] = entitlement.valid_until.isoformat()

        # Cash-specific fields
        if is_cash:
            if entitlement.initial_amount:
                currency = entitlement.currency_id.name if entitlement.currency_id else "USD"
                result["initialAmount"] = {
                    "value": entitlement.initial_amount,
                    "currency": currency,
                }
            if entitlement.balance:
                currency = entitlement.currency_id.name if entitlement.currency_id else "USD"
                result["balance"] = {
                    "value": entitlement.balance,
                    "currency": currency,
                }
            if hasattr(entitlement, "ern") and entitlement.ern:
                result["ern"] = entitlement.ern

        # In-kind specific fields
        else:
            if entitlement.product_id:
                product_identifier = entitlement.product_id.default_code or entitlement.product_id.name
                unit_name = entitlement.uom_id.name if entitlement.uom_id else "Unit"

                item = {
                    "product": {
                        "reference": f"Product/{product_identifier}",
                        "display": entitlement.product_id.name,
                    },
                    "quantity": {
                        "value": entitlement.quantity or 1,
                        "unit": unit_name,
                    },
                }

                if entitlement.unit_price:
                    currency = entitlement.currency_id.name if entitlement.currency_id else "USD"
                    item["unitPrice"] = {
                        "value": entitlement.unit_price,
                        "currency": currency,
                    }

                result["items"] = [item]

            # Service point
            if entitlement.service_point_id:
                result["servicePoint"] = {
                    "reference": f"ServicePoint/{entitlement.service_point_id.name}",
                    "display": entitlement.service_point_id.name,
                }

        # Approved date
        if entitlement.date_approved:
            result["approvedDate"] = entitlement.date_approved.isoformat()

        # Metadata
        if entitlement.write_date:
            version_id = str(int(entitlement.write_date.timestamp() * 1000000))
            result["meta"] = {
                "versionId": version_id,
                "lastUpdated": entitlement.write_date.isoformat(),
            }

        return result

    def _build_partner_reference(self, partner) -> dict:
        """Build Reference to a partner (Individual or Group)."""
        resource_type = "Group" if partner.is_group else "Individual"

        # Get primary identifier
        # Use id_type_id.uri (full code URI) for consistency with spp_api_v2
        if partner.reg_ids:
            primary_id = partner.reg_ids[0]
            if primary_id.id_type_id and primary_id.id_type_id.uri:
                ref = f"{resource_type}/{primary_id.id_type_id.uri}|{primary_id.value}"
            else:
                # Fallback to name if no valid URI
                ref = f"{resource_type}/{partner.name}"
        else:
            # Fallback to name
            ref = f"{resource_type}/{partner.name}"

        return {
            "reference": ref,
            "display": partner.name,
        }
