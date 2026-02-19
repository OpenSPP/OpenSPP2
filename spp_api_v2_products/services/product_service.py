# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Product resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ProductService:
    """Service for Product resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, identifier: str):
        """
        Lookup product by identifier (default_code or name).

        Args:
            identifier: Product default_code or name

        Returns:
            product.template record or empty recordset
        """
        # First try by default_code (SKU)
        product = (
            self.env["product.template"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [("default_code", "=", identifier)],
                limit=1,
            )
        )
        if product:
            return product

        # Then try by name
        return (
            self.env["product.template"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [("name", "=", identifier)],
                limit=1,
            )
        )

    def search(self, params: dict) -> tuple[Any, int]:
        """
        Search products with parameters.

        Args:
            params: Search parameters dict

        Returns:
            Tuple of (recordset, total_count)
        """
        domain = []

        # Name filter (contains)
        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))

        # Code filter
        if params.get("code"):
            domain.append(("default_code", "ilike", params["code"]))

        # Category filter
        if params.get("category"):
            domain.append(("categ_id.name", "ilike", params["category"]))

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
        total = self.env["product.template"].sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context

        # Get paginated records
        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        records = (
            self.env["product.template"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                domain,
                limit=count,
                offset=offset,
                order="name",
            )
        )

        return records, total

    def to_api_schema(self, product) -> dict[str, Any]:
        """
        Convert Odoo product to API schema.

        CRITICAL: NO database IDs exposed

        Args:
            product: product.template record

        Returns:
            Dictionary matching Product schema
        """
        if not product:
            return {}

        # Use default_code if available, otherwise name
        identifier = product.default_code or product.name

        result = {
            "resourceType": "Product",
            "identifier": identifier,
            "name": product.name,
            "active": product.active,
        }

        # Code (SKU)
        if product.default_code:
            result["defaultCode"] = product.default_code

        # Category
        if product.categ_id:
            result["category"] = {
                "reference": f"ProductCategory/{product.categ_id.name}",
                "display": product.categ_id.name,
            }

        # Unit of measure
        if product.uom_id:
            result["unitOfMeasure"] = {
                "reference": f"UnitOfMeasure/{product.uom_id.name}",
                "display": product.uom_id.name,
            }

        # Price
        if product.list_price:
            result["listPrice"] = product.list_price
            if product.currency_id:
                result["currency"] = product.currency_id.name

        # Image available flag (don't expose database ID in URL)
        # Use /api/v2/spp/Product/{identifier}/image endpoint instead
        if product.image_1920:
            result["hasImage"] = True

        # Metadata
        if product.write_date:
            version_id = str(int(product.write_date.timestamp() * 1000000))
            result["meta"] = {
                "versionId": version_id,
                "lastUpdated": product.write_date.isoformat(),
            }

        return result
