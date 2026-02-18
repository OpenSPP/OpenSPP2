# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Service Point resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ServicePointService:
    """Service for Service Point resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, identifier: str):
        """
        Lookup service point by identifier (name).

        Args:
            identifier: Service point name

        Returns:
            spp.service.point record or empty recordset
        """
        return (
            self.env["spp.service.point"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [("name", "=", identifier)],
                limit=1,
            )
        )

    def search(self, params: dict) -> tuple[Any, int]:
        """
        Search service points with parameters.

        Args:
            params: Search parameters dict

        Returns:
            Tuple of (recordset, total_count)
        """
        domain = []

        # Name filter (contains)
        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))

        # Area filter
        if params.get("area"):
            domain.append(("area_id.name", "ilike", params["area"]))

        # Country filter
        if params.get("country"):
            domain.append(("country_id.code", "=", params["country"].upper()))

        # Contract active filter
        if "contractActive" in params:
            domain.append(("is_contract_active", "=", params["contractActive"]))

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

        # Get total count
        total = self.env["spp.service.point"].sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context

        # Get paginated records
        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        records = (
            self.env["spp.service.point"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                domain,
                limit=count,
                offset=offset,
                order="name",
            )
        )

        return records, total

    def to_api_schema(self, sp) -> dict[str, Any]:
        """
        Convert Odoo service point to API schema.

        CRITICAL REQUIREMENTS:
        - NO database IDs exposed
        - Use service point name as identifier

        Args:
            sp: spp.service.point record

        Returns:
            Dictionary matching ServicePoint schema
        """
        if not sp:
            return {}

        service_point = {
            "resourceType": "ServicePoint",
            "identifier": sp.name,
            "name": sp.name,
            "contractActive": sp.is_contract_active,
            "disabled": sp.is_disabled,
        }

        # Country
        if sp.country_id:
            service_point["country"] = sp.country_id.code

        # Area reference
        if sp.area_id:
            service_point["area"] = {
                "reference": f"Area/{sp.area_id.name}",
                "display": sp.area_id.name,
            }

        # Address
        if sp.shop_address:
            service_point["address"] = {
                "text": sp.shop_address,
                "type": "physical",
            }

        # Telecom
        if sp.phone_no:
            service_point["telecom"] = [
                {
                    "system": "phone",
                    "value": sp.phone_sanitized or sp.phone_no,
                    "use": "work",
                }
            ]

        # Company reference
        if sp.res_partner_company_id:
            service_point["company"] = {
                "reference": f"Organization/{sp.res_partner_company_id.name}",
                "display": sp.res_partner_company_id.name,
            }

        # Service types
        if sp.service_type_ids:
            service_point["serviceType"] = [st.display for st in sp.service_type_ids]

        # Metadata
        if sp.write_date:
            version_id = str(int(sp.write_date.timestamp() * 1000000))
            service_point["meta"] = {
                "versionId": version_id,
                "lastUpdated": sp.write_date.isoformat(),
            }

        return service_point
