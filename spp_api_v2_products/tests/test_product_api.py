# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Product API endpoints."""

from urllib.parse import quote

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestProductSchemas(TransactionCase):
    """Test Product API schema validation."""

    def test_product_response_schema(self):
        """Test Product schema validates correctly."""
        from ..schemas.product import Product

        product = Product(
            identifier="RICE-25KG",
            name="Rice 25kg Bag",
            code="RICE-25KG",
            active=True,
        )
        assert product.identifier == "RICE-25KG"
        assert product.name == "Rice 25kg Bag"
        assert product.resource_type == "Product"

    def test_product_category_response_schema(self):
        """Test ProductCategory schema validates correctly."""
        from ..schemas.product_category import ProductCategory

        category = ProductCategory(
            identifier="Food",
            name="Food",
        )
        assert category.identifier == "Food"
        assert category.name == "Food"
        assert category.resource_type == "ProductCategory"

    def test_unit_of_measure_response_schema(self):
        """Test UnitOfMeasure schema validates correctly."""
        from ..schemas.uom import UnitOfMeasure

        uom = UnitOfMeasure(
            identifier="kg",
            name="Kilogram",
            symbol="kg",
        )
        assert uom.identifier == "kg"
        assert uom.name == "Kilogram"
        assert uom.symbol == "kg"
        assert uom.resource_type == "UnitOfMeasure"


class TestProductService(TransactionCase):
    """Test Product service functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use standard UoM reference
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not cls.uom_kg:
            cls.uom_kg = cls.env["uom.uom"].search([], limit=1)

        # Create product category
        cls.food_category = cls.env["product.category"].create(
            {
                "name": "Food",
            }
        )

        # Use existing currency (search including inactive)
        cls.currency = cls.env["res.currency"].with_context(active_test=False).search([("name", "=", "PHP")], limit=1)
        if cls.currency and not cls.currency.active:
            cls.currency.active = True
        if not cls.currency:
            cls.currency = cls.env["res.currency"].search([], limit=1)

        # Create test products
        cls.product1 = cls.env["product.template"].create(
            {
                "name": "Rice 25kg Bag",
                "default_code": "RICE-25KG",
                "categ_id": cls.food_category.id,
                "uom_id": cls.uom_kg.id,
                "list_price": 1250.00,
                "currency_id": cls.currency.id,
            }
        )

        cls.product2 = cls.env["product.template"].create(
            {
                "name": "Sugar 1kg",
                "default_code": "SUGAR-1KG",
                "categ_id": cls.food_category.id,
                "uom_id": cls.uom_kg.id,
                "list_price": 50.00,
                "currency_id": cls.currency.id,
            }
        )

        cls.product_no_code = cls.env["product.template"].create(
            {
                "name": "Generic Product",
                "categ_id": cls.food_category.id,
                "uom_id": cls.uom_kg.id,
            }
        )

    def test_find_by_default_code(self):
        """Test finding product by default_code."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        product = service.find_by_identifier("RICE-25KG")

        assert product
        assert product.id == self.product1.id
        assert product.name == "Rice 25kg Bag"

    def test_find_by_name(self):
        """Test finding product by name."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        product = service.find_by_identifier("Generic Product")

        assert product
        assert product.id == self.product_no_code.id

    def test_find_nonexistent_product(self):
        """Test finding non-existent product returns empty."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        product = service.find_by_identifier("NONEXISTENT")

        assert not product

    def test_search_all_products(self):
        """Test searching all products."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        records, total = service.search({"_count": 100, "_offset": 0})

        assert total >= 3
        assert len(records) >= 3

    def test_search_by_name(self):
        """Test searching products by name."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        records, total = service.search({"name": "Rice", "_count": 100})

        assert total >= 1
        assert any(r.name == "Rice 25kg Bag" for r in records)

    def test_search_by_code(self):
        """Test searching products by code."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        records, total = service.search({"code": "SUGAR", "_count": 100})

        assert total >= 1
        assert any(r.default_code == "SUGAR-1KG" for r in records)

    def test_search_by_category(self):
        """Test searching products by category."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        records, total = service.search({"category": "Food", "_count": 100})

        assert total >= 3
        assert all(r.categ_id.name == "Food" for r in records)

    def test_search_pagination(self):
        """Test search pagination."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        records1, total = service.search({"_count": 1, "_offset": 0})

        assert len(records1) == 1
        assert total >= 3

        records2, _ = service.search({"_count": 1, "_offset": 1})
        assert len(records2) == 1
        assert records2[0].id != records1[0].id

    def test_to_api_schema_complete(self):
        """Test converting product to API schema with all fields."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        data = service.to_api_schema(self.product1)

        assert data["resourceType"] == "Product"
        assert data["identifier"] == "RICE-25KG"
        assert data["name"] == "Rice 25kg Bag"
        assert data["defaultCode"] == "RICE-25KG"
        assert data["active"] is True
        assert data["listPrice"] == 1250.00
        # Currency comes from product.currency_id (may be company currency)
        if "currency" in data:
            assert isinstance(data["currency"], str)

        # Check category reference
        assert "category" in data
        assert data["category"]["reference"] == "ProductCategory/Food"
        assert data["category"]["display"] == "Food"

        # Check UoM reference
        assert "unitOfMeasure" in data
        assert data["unitOfMeasure"]["reference"] == f"UnitOfMeasure/{self.uom_kg.name}"
        assert data["unitOfMeasure"]["display"] == self.uom_kg.name

        # Check metadata
        assert "meta" in data
        assert "versionId" in data["meta"]
        assert "lastUpdated" in data["meta"]

    def test_to_api_schema_no_code(self):
        """Test converting product without default_code."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        data = service.to_api_schema(self.product_no_code)

        assert data["identifier"] == "Generic Product"
        assert "defaultCode" not in data

    def test_to_api_schema_no_database_id(self):
        """Test that API schema does not expose database IDs."""
        from ..services.product_service import ProductService

        service = ProductService(self.env)
        data = service.to_api_schema(self.product1)

        # Verify no database IDs in main object
        assert "id" not in data

        # Verify no database IDs in references
        if "category" in data:
            assert "id" not in data["category"]
            # Reference should use name, not ID
            assert "Food" in data["category"]["reference"]
            assert str(self.food_category.id) not in data["category"]["reference"]

        if "unitOfMeasure" in data:
            assert "id" not in data["unitOfMeasure"]
            assert self.uom_kg.name in data["unitOfMeasure"]["reference"]
            assert str(self.uom_kg.id) not in data["unitOfMeasure"]["reference"]


class TestProductCategoryService(TransactionCase):
    """Test ProductCategory service functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create category hierarchy
        cls.all_category = cls.env["product.category"].create(
            {
                "name": "All",
            }
        )

        cls.food_category = cls.env["product.category"].create(
            {
                "name": "Food",
                "parent_id": cls.all_category.id,
            }
        )

    def test_find_by_name(self):
        """Test finding category by name."""
        from ..services.product_category_service import ProductCategoryService

        service = ProductCategoryService(self.env)
        category = service.find_by_identifier("Food")

        assert category
        assert category.id == self.food_category.id

    def test_find_nonexistent_category(self):
        """Test finding non-existent category returns empty."""
        from ..services.product_category_service import ProductCategoryService

        service = ProductCategoryService(self.env)
        category = service.find_by_identifier("NONEXISTENT")

        assert not category

    def test_search_categories(self):
        """Test searching categories."""
        from ..services.product_category_service import ProductCategoryService

        service = ProductCategoryService(self.env)
        records, total = service.search({"_count": 100, "_offset": 0})

        assert total >= 2
        assert len(records) >= 2

    def test_to_api_schema_with_parent(self):
        """Test converting category with parent to API schema."""
        from ..services.product_category_service import ProductCategoryService

        service = ProductCategoryService(self.env)
        data = service.to_api_schema(self.food_category)

        assert data["resourceType"] == "ProductCategory"
        assert data["identifier"] == "Food"
        assert data["name"] == "Food"

        # Check parent reference
        assert "parent" in data
        assert data["parent"]["reference"] == "ProductCategory/All"
        assert data["parent"]["display"] == "All"

    def test_to_api_schema_no_parent(self):
        """Test converting category without parent."""
        from ..services.product_category_service import ProductCategoryService

        service = ProductCategoryService(self.env)
        data = service.to_api_schema(self.all_category)

        assert data["identifier"] == "All"
        assert "parent" not in data

    def test_to_api_schema_no_database_id(self):
        """Test that category schema does not expose database IDs."""
        from ..services.product_category_service import ProductCategoryService

        service = ProductCategoryService(self.env)
        data = service.to_api_schema(self.food_category)

        assert "id" not in data
        if "parent" in data:
            assert "id" not in data["parent"]
            assert str(self.all_category.id) not in data["parent"]["reference"]


class TestUomService(TransactionCase):
    """Test UoM service functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use standard UoM references
        cls.kg = cls.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not cls.kg:
            cls.kg = cls.env["uom.uom"].search([], limit=1)

        cls.gram = cls.env.ref("uom.product_uom_gram", raise_if_not_found=False)
        if not cls.gram:
            cls.gram = cls.env["uom.uom"].search([("id", "!=", cls.kg.id)], limit=1)

    def test_find_by_name(self):
        """Test finding UoM by name."""
        from ..services.uom_service import UomService

        service = UomService(self.env)
        uom = service.find_by_identifier(self.kg.name)

        assert uom
        assert uom.id == self.kg.id

    def test_find_nonexistent_uom(self):
        """Test finding non-existent UoM returns empty."""
        from ..services.uom_service import UomService

        service = UomService(self.env)
        uom = service.find_by_identifier("NONEXISTENT")

        assert not uom

    def test_search_uoms(self):
        """Test searching UoMs."""
        from ..services.uom_service import UomService

        service = UomService(self.env)
        records, total = service.search({"_count": 100, "_offset": 0})

        assert total >= 2
        assert len(records) >= 2

    def test_search_by_category(self):
        """Test searching UoMs by category (relative_uom_id name)."""
        from ..services.uom_service import UomService

        service = UomService(self.env)
        records, total = service.search({"category": self.kg.name, "_count": 100})

        # At least gram should match (its relative_uom_id points to kg)
        assert total >= 1
        assert all(r.relative_uom_id.name == self.kg.name for r in records)

    def test_to_api_schema(self):
        """Test converting UoM to API schema."""
        from ..services.uom_service import UomService

        service = UomService(self.env)
        data = service.to_api_schema(self.kg)

        assert data["resourceType"] == "UnitOfMeasure"
        assert data["identifier"] == self.kg.name
        assert data["name"] == self.kg.name

        # Check category reference if relative_uom_id is set
        if self.kg.relative_uom_id:
            assert "category" in data
            assert data["category"]["reference"] == f"UnitOfMeasure/{self.kg.relative_uom_id.name}"
            assert data["category"]["display"] == self.kg.relative_uom_id.name

    def test_to_api_schema_no_database_id(self):
        """Test that UoM schema does not expose database IDs."""
        from ..services.uom_service import UomService

        service = UomService(self.env)
        data = service.to_api_schema(self.kg)

        assert "id" not in data
        if "category" in data:
            assert "id" not in data["category"]
            assert str(self.kg.relative_uom_id.id) not in data["category"]["reference"]


class TestProductAPIEndpoints(TransactionCase):
    """Test Product API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use standard UoM reference
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not cls.uom_kg:
            cls.uom_kg = cls.env["uom.uom"].search([], limit=1)

        # Create product category
        cls.food_category = cls.env["product.category"].create({"name": "Food"})

        # Use existing currency (search including inactive)
        cls.currency = cls.env["res.currency"].with_context(active_test=False).search([("name", "=", "PHP")], limit=1)
        if cls.currency and not cls.currency.active:
            cls.currency.active = True
        if not cls.currency:
            cls.currency = cls.env["res.currency"].search([], limit=1)

        # Create test products
        cls.rice = cls.env["product.template"].create(
            {
                "name": "Rice 25kg Bag",
                "default_code": "RICE-25KG",
                "categ_id": cls.food_category.id,
                "uom_id": cls.uom_kg.id,
                "list_price": 1250.00,
                "currency_id": cls.currency.id,
            }
        )

        cls.sugar = cls.env["product.template"].create(
            {
                "name": "Sugar 1kg",
                "default_code": "SUGAR-1KG",
                "categ_id": cls.food_category.id,
                "uom_id": cls.uom_kg.id,
                "list_price": 50.00,
                "currency_id": cls.currency.id,
            }
        )

        # Lookup organization type
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        # Create API client with scope
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "product",
                "action": "read",
            }
        )

        # Create client without scope
        cls.no_scope_partner = cls.env["res.partner"].create({"name": "No Scope"})
        cls.no_scope_client = cls.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": cls.no_scope_partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )

    def test_client_has_product_scope(self):
        """Test API client has product read scope."""
        assert self.api_client.has_scope("product", "read")

    def test_client_without_product_scope(self):
        """Test API client without product scope."""
        assert not self.no_scope_client.has_scope("product", "read")

    async def test_read_product_by_code_success(self):
        """Test GET /Product/{identifier} returns product by code."""
        from unittest.mock import MagicMock

        from ..routers.product import read_product

        response = MagicMock()
        result = await read_product(
            identifier="RICE-25KG",
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["identifier"] == "RICE-25KG"
        assert result["name"] == "Rice 25kg Bag"
        assert result["defaultCode"] == "RICE-25KG"
        assert result["resourceType"] == "Product"

        # Check ETag header was set
        assert response.headers.__setitem__.called

    async def test_read_product_by_name_success(self):
        """Test GET /Product/{identifier} returns product by name."""
        from unittest.mock import MagicMock

        from ..routers.product import read_product

        response = MagicMock()
        result = await read_product(
            identifier="Sugar 1kg",
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["name"] == "Sugar 1kg"
        assert result["defaultCode"] == "SUGAR-1KG"

    async def test_read_product_url_encoded(self):
        """Test GET /Product/{identifier} handles URL encoding."""
        from unittest.mock import MagicMock

        from ..routers.product import read_product

        encoded_identifier = quote("Rice 25kg Bag", safe="")
        response = MagicMock()

        result = await read_product(
            identifier=encoded_identifier,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["name"] == "Rice 25kg Bag"

    async def test_read_product_not_found(self):
        """Test GET /Product/{identifier} returns 404 for non-existent product."""
        from unittest.mock import MagicMock

        from ..routers.product import read_product

        with self.assertRaises(HTTPException) as cm:
            await read_product(
                identifier="NONEXISTENT",
                env=self.env,
                api_client=self.api_client,
                response=MagicMock(),
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_product_no_scope(self):
        """Test GET /Product/{identifier} without scope returns 403."""
        from unittest.mock import MagicMock

        from ..routers.product import read_product

        with self.assertRaises(HTTPException) as cm:
            await read_product(
                identifier="RICE-25KG",
                env=self.env,
                api_client=self.no_scope_client,
                response=MagicMock(),
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_products_success(self):
        """Test GET /Product returns product list."""
        from ..routers.product import search_products

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name=None,
            code=None,
            category=None,
            last_updated=None,
            count=50,
            offset=0,
        )

        assert result.resourceType == "Bundle"
        assert result.type == "searchset"
        assert result.total >= 2
        assert len(result.entry) >= 2
        assert any(e.resource["name"] == "Rice 25kg Bag" for e in result.entry)

    async def test_search_products_by_name(self):
        """Test GET /Product?name=Rice filters by name."""
        from ..routers.product import search_products

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name="Rice",
            code=None,
            category=None,
            last_updated=None,
            count=50,
            offset=0,
        )

        assert all("rice" in e.resource["name"].lower() for e in result.entry)

    async def test_search_products_by_code(self):
        """Test GET /Product?code=SUGAR filters by code."""
        from ..routers.product import search_products

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name=None,
            code="SUGAR",
            category=None,
            last_updated=None,
            count=50,
            offset=0,
        )

        assert result.total >= 1
        assert any("SUGAR" in e.resource.get("defaultCode", "") for e in result.entry)

    async def test_search_products_by_category(self):
        """Test GET /Product?category=Food filters by category."""
        from ..routers.product import search_products

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name=None,
            code=None,
            category="Food",
            last_updated=None,
            count=50,
            offset=0,
        )

        assert result.total >= 2
        assert all(
            e.resource.get("category", {}).get("display") == "Food" for e in result.entry if "category" in e.resource
        )

    async def test_search_products_pagination(self):
        """Test GET /Product respects pagination parameters."""
        from ..routers.product import search_products

        # Create more products
        for i in range(5):
            self.env["product.template"].create(
                {
                    "name": f"Test Product {i}",
                    "default_code": f"TEST-{i}",
                    "categ_id": self.food_category.id,
                    "uom_id": self.uom_kg.id,
                }
            )

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name=None,
            code=None,
            category=None,
            last_updated=None,
            count=2,
            offset=0,
        )

        assert len(result.entry) == 2
        assert result.total >= 5

        # Test offset
        result2 = await search_products(
            env=self.env,
            api_client=self.api_client,
            name=None,
            code=None,
            category=None,
            last_updated=None,
            count=2,
            offset=2,
        )

        assert len(result2.entry) <= 2
        # Items should be different
        if len(result2.entry) > 0 and len(result.entry) > 0:
            assert result2.entry[0].resource["identifier"] != result.entry[0].resource["identifier"]

    async def test_search_products_bundle_links(self):
        """Test GET /Product includes pagination links."""
        from ..routers.product import search_products

        # Create more products to ensure pagination
        for i in range(10):
            self.env["product.template"].create(
                {
                    "name": f"Link Test {i}",
                    "default_code": f"LINK-{i}",
                    "categ_id": self.food_category.id,
                    "uom_id": self.uom_kg.id,
                }
            )

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name=None,
            code=None,
            category=None,
            last_updated=None,
            count=5,
            offset=0,
        )

        # Should have self and next links
        assert any(link.relation == "self" for link in result.link)
        if result.total > 5:
            assert any(link.relation == "next" for link in result.link)

    async def test_search_products_no_scope(self):
        """Test GET /Product without scope returns 403."""
        from ..routers.product import search_products

        with self.assertRaises(HTTPException) as cm:
            await search_products(
                env=self.env,
                api_client=self.no_scope_client,
                name=None,
                code=None,
                category=None,
                last_updated=None,
                count=50,
                offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_products_empty_result(self):
        """Test GET /Product handles empty search results."""
        from ..routers.product import search_products

        result = await search_products(
            env=self.env,
            api_client=self.api_client,
            name="NONEXISTENT_PRODUCT_NAME_THAT_WONT_MATCH",
            code=None,
            category=None,
            last_updated=None,
            count=50,
            offset=0,
        )

        assert result.total == 0
        assert len(result.entry) == 0


class TestProductCategoryAPIEndpoints(TransactionCase):
    """Test ProductCategory API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create category hierarchy
        cls.all_category = cls.env["product.category"].create({"name": "All Products"})
        cls.food_category = cls.env["product.category"].create(
            {
                "name": "Food Items",
                "parent_id": cls.all_category.id,
            }
        )

        # Lookup organization type
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        # Create API client with scope
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "product",
                "action": "read",
            }
        )

        # Create client without scope
        cls.no_scope_client = cls.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )

    async def test_read_category_success(self):
        """Test GET /ProductCategory/{identifier} returns category."""
        from unittest.mock import MagicMock

        from ..routers.product_category import read_product_category

        response = MagicMock()
        result = await read_product_category(
            identifier="Food Items",
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["identifier"] == "Food Items"
        assert result["name"] == "Food Items"
        assert result["resourceType"] == "ProductCategory"
        assert "parent" in result
        assert result["parent"]["display"] == "All Products"

    async def test_read_category_url_encoded(self):
        """Test GET /ProductCategory/{identifier} handles URL encoding."""
        from unittest.mock import MagicMock

        from ..routers.product_category import read_product_category

        encoded_identifier = quote("Food Items", safe="")
        response = MagicMock()

        result = await read_product_category(
            identifier=encoded_identifier,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["name"] == "Food Items"

    async def test_read_category_not_found(self):
        """Test GET /ProductCategory/{identifier} returns 404."""
        from unittest.mock import MagicMock

        from ..routers.product_category import read_product_category

        with self.assertRaises(HTTPException) as cm:
            await read_product_category(
                identifier="NONEXISTENT",
                env=self.env,
                api_client=self.api_client,
                response=MagicMock(),
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_category_no_scope(self):
        """Test GET /ProductCategory/{identifier} without scope returns 403."""
        from unittest.mock import MagicMock

        from ..routers.product_category import read_product_category

        with self.assertRaises(HTTPException) as cm:
            await read_product_category(
                identifier="Food Items",
                env=self.env,
                api_client=self.no_scope_client,
                response=MagicMock(),
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_categories_success(self):
        """Test GET /ProductCategory returns category list."""
        from ..routers.product_category import search_product_categories

        result = await search_product_categories(
            env=self.env,
            api_client=self.api_client,
            name=None,
            count=50,
            offset=0,
        )

        assert result.resourceType == "Bundle"
        assert result.type == "searchset"
        assert result.total >= 2
        assert len(result.entry) >= 2

    async def test_search_categories_by_name(self):
        """Test GET /ProductCategory?name=Food filters by name."""
        from ..routers.product_category import search_product_categories

        result = await search_product_categories(
            env=self.env,
            api_client=self.api_client,
            name="Food",
            count=50,
            offset=0,
        )

        assert all("food" in e.resource["name"].lower() for e in result.entry)

    async def test_search_categories_pagination(self):
        """Test GET /ProductCategory respects pagination."""
        from ..routers.product_category import search_product_categories

        # Create more categories
        for i in range(5):
            self.env["product.category"].create({"name": f"Test Category {i}"})

        result = await search_product_categories(
            env=self.env,
            api_client=self.api_client,
            name=None,
            count=2,
            offset=0,
        )

        assert len(result.entry) == 2
        assert result.total >= 5

    async def test_search_categories_no_scope(self):
        """Test GET /ProductCategory without scope returns 403."""
        from ..routers.product_category import search_product_categories

        with self.assertRaises(HTTPException) as cm:
            await search_product_categories(
                env=self.env,
                api_client=self.no_scope_client,
                name=None,
                count=50,
                offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN


class TestUnitOfMeasureAPIEndpoints(TransactionCase):
    """Test UnitOfMeasure API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use standard UoM references
        cls.kg = cls.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if not cls.kg:
            cls.kg = cls.env["uom.uom"].search([], limit=1)

        cls.gram = cls.env.ref("uom.product_uom_gram", raise_if_not_found=False)
        if not cls.gram:
            cls.gram = cls.env["uom.uom"].search([("id", "!=", cls.kg.id)], limit=1)

        # Lookup organization type
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        # Create API client with scope
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "product",
                "action": "read",
            }
        )

        # Create client without scope
        cls.no_scope_client = cls.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )

    async def test_read_uom_success(self):
        """Test GET /UnitOfMeasure/{identifier} returns UoM."""
        from unittest.mock import MagicMock

        from ..routers.uom import read_uom

        response = MagicMock()
        result = await read_uom(
            identifier=self.kg.name,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["identifier"] == self.kg.name
        assert result["name"] == self.kg.name
        assert result["resourceType"] == "UnitOfMeasure"
        assert "factor" in result

    async def test_read_uom_url_encoded(self):
        """Test GET /UnitOfMeasure/{identifier} handles URL encoding."""
        from unittest.mock import MagicMock

        from ..routers.uom import read_uom

        encoded_identifier = quote(self.kg.name, safe="")
        response = MagicMock()

        result = await read_uom(
            identifier=encoded_identifier,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["name"] == self.kg.name

    async def test_read_uom_not_found(self):
        """Test GET /UnitOfMeasure/{identifier} returns 404."""
        from unittest.mock import MagicMock

        from ..routers.uom import read_uom

        with self.assertRaises(HTTPException) as cm:
            await read_uom(
                identifier="NONEXISTENT",
                env=self.env,
                api_client=self.api_client,
                response=MagicMock(),
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_uom_no_scope(self):
        """Test GET /UnitOfMeasure/{identifier} without scope returns 403."""
        from unittest.mock import MagicMock

        from ..routers.uom import read_uom

        with self.assertRaises(HTTPException) as cm:
            await read_uom(
                identifier=self.kg.name,
                env=self.env,
                api_client=self.no_scope_client,
                response=MagicMock(),
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_uoms_success(self):
        """Test GET /UnitOfMeasure returns UoM list."""
        from ..routers.uom import search_uoms

        result = await search_uoms(
            env=self.env,
            api_client=self.api_client,
            name=None,
            category=None,
            count=50,
            offset=0,
        )

        assert result.resourceType == "Bundle"
        assert result.type == "searchset"
        assert result.total >= 2
        assert len(result.entry) >= 2

    async def test_search_uoms_by_name(self):
        """Test GET /UnitOfMeasure?name=Gram filters by name."""
        from ..routers.uom import search_uoms

        result = await search_uoms(
            env=self.env,
            api_client=self.api_client,
            name=self.gram.name,
            category=None,
            count=50,
            offset=0,
        )

        assert all(self.gram.name.lower() in e.resource["name"].lower() for e in result.entry)

    async def test_search_uoms_by_category(self):
        """Test GET /UnitOfMeasure?category filters by reference UoM name."""
        from ..routers.uom import search_uoms

        result = await search_uoms(
            env=self.env,
            api_client=self.api_client,
            name=None,
            category=self.kg.name,
            count=50,
            offset=0,
        )

        # At least gram should match (its relative_uom_id points to kg)
        assert result.total >= 1
        assert all(
            e.resource.get("category", {}).get("display") == self.kg.name
            for e in result.entry
            if "category" in e.resource
        )

    async def test_search_uoms_pagination(self):
        """Test GET /UnitOfMeasure respects pagination."""
        from ..routers.uom import search_uoms

        # Create more UoMs (search first to avoid duplicates)
        for i in range(5):
            uom_name = f"Test UoM {i}"
            existing = self.env["uom.uom"].search([("name", "=", uom_name)], limit=1)
            if not existing:
                self.env["uom.uom"].create(
                    {
                        "name": uom_name,
                        "relative_uom_id": self.kg.id,
                        "relative_factor": float(i + 1),
                    }
                )

        result = await search_uoms(
            env=self.env,
            api_client=self.api_client,
            name=None,
            category=None,
            count=2,
            offset=0,
        )

        assert len(result.entry) == 2
        assert result.total >= 5

    async def test_search_uoms_no_scope(self):
        """Test GET /UnitOfMeasure without scope returns 403."""
        from ..routers.uom import search_uoms

        with self.assertRaises(HTTPException) as cm:
            await search_uoms(
                env=self.env,
                api_client=self.no_scope_client,
                name=None,
                category=None,
                count=50,
                offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
