# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Product Category resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ProductCategoryService:
    """Service for Product Category resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, identifier: str):
        """
        Lookup category by identifier (name).

        Args:
            identifier: Category name

        Returns:
            product.category record or empty recordset
        """
        return (
            self.env["product.category"]
            .sudo()
            .search(
                [("name", "=", identifier)],
                limit=1,
            )
        )

    def search(self, params: dict) -> tuple[Any, int]:
        """
        Search categories with parameters.

        Args:
            params: Search parameters dict

        Returns:
            Tuple of (recordset, total_count)
        """
        domain = []

        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))

        total = self.env["product.category"].sudo().search_count(domain)

        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        records = (
            self.env["product.category"]
            .sudo()
            .search(
                domain,
                limit=count,
                offset=offset,
                order="name",
            )
        )

        return records, total

    def to_api_schema(self, category) -> dict[str, Any]:
        """
        Convert Odoo category to API schema.

        Args:
            category: product.category record

        Returns:
            Dictionary matching ProductCategory schema
        """
        if not category:
            return {}

        result = {
            "resourceType": "ProductCategory",
            "identifier": category.name,
            "name": category.name,
        }

        # Parent category
        if category.parent_id:
            result["parent"] = {
                "reference": f"ProductCategory/{category.parent_id.name}",
                "display": category.parent_id.name,
            }

        # Metadata
        if category.write_date:
            version_id = str(int(category.write_date.timestamp() * 1000000))
            result["meta"] = {
                "versionId": version_id,
                "lastUpdated": category.write_date.isoformat(),
            }

        return result
