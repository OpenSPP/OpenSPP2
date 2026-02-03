# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Unit of Measure resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class UomService:
    """Service for Unit of Measure resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, identifier: str):
        """
        Lookup UoM by identifier (name).

        Args:
            identifier: UoM name

        Returns:
            uom.uom record or empty recordset
        """
        return (
            self.env["uom.uom"]
            .sudo()
            .search(
                [("name", "=", identifier)],
                limit=1,
            )
        )

    def search(self, params: dict) -> tuple[Any, int]:
        """
        Search UoMs with parameters.

        Args:
            params: Search parameters dict

        Returns:
            Tuple of (recordset, total_count)
        """
        domain = []

        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))

        # Category filter: In Odoo 19 UoM uses relative_uom_id (reference unit)
        if params.get("category"):
            domain.append(("relative_uom_id.name", "ilike", params["category"]))

        total = self.env["uom.uom"].sudo().search_count(domain)

        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        records = (
            self.env["uom.uom"]
            .sudo()
            .search(
                domain,
                limit=count,
                offset=offset,
                order="name",
            )
        )

        return records, total

    def to_api_schema(self, uom) -> dict[str, Any]:
        """
        Convert Odoo UoM to API schema.

        Args:
            uom: uom.uom record

        Returns:
            Dictionary matching UnitOfMeasure schema
        """
        if not uom:
            return {}

        result = {
            "resourceType": "UnitOfMeasure",
            "identifier": uom.name,
            "name": uom.name,
        }

        # Symbol (if available - may not be in all versions)
        if hasattr(uom, "symbol") and uom.symbol:
            result["symbol"] = uom.symbol

        # Category: In Odoo 19 UoM uses relative_uom_id as reference unit
        if uom.relative_uom_id:
            result["category"] = {
                "reference": f"UnitOfMeasure/{uom.relative_uom_id.name}",
                "display": uom.relative_uom_id.name,
            }

        # Conversion factor
        if uom.factor:
            result["factor"] = uom.factor

        if uom.rounding:
            result["rounding"] = uom.rounding

        # Metadata
        if uom.write_date:
            version_id = str(int(uom.write_date.timestamp() * 1000000))
            result["meta"] = {
                "versionId": version_id,
                "lastUpdated": uom.write_date.isoformat(),
            }

        return result
