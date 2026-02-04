# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Entitlement API endpoints."""

from datetime import date, timedelta
from urllib.parse import quote

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestEntitlementAPI(TransactionCase):
    """Test Entitlement API functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Lookup organization types
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        cls.org_type_private = cls.env.ref(
            "spp_consent.org_type_private",
            raise_if_not_found=False,
        )
        if not cls.org_type_private:
            cls.org_type_private = cls.env["spp.consent.org.type"].search([("code", "=", "private")], limit=1)

        # Lookup or create ID type vocabulary code for registry IDs
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )
        cls.id_type_national = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "NATIONAL_ID")],
            limit=1,
        )
        if not cls.id_type_national:
            cls.id_type_national = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "NATIONAL_ID",
                    "display": "National ID",
                    "is_local": True,
                    "target_type": "individual",
                }
            )

        # Get or create currency (include inactive to avoid unique constraint)
        cls.currency = cls.env["res.currency"].with_context(active_test=False).search([("name", "=", "USD")], limit=1)
        if not cls.currency:
            cls.currency = cls.env["res.currency"].create(
                {
                    "name": "USD",
                    "symbol": "$",
                    "rounding": 0.01,
                }
            )
        elif not cls.currency.active:
            cls.currency.active = True

        # Get or create journal for entitlements (search first to avoid unique code)
        cls.journal = cls.env["account.journal"].search([("code", "=", "TENT")], limit=1)
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {
                    "name": "Test Entitlement Journal",
                    "type": "bank",
                    "code": "TENT",
                    "currency_id": cls.currency.id,
                }
            )

        # Create program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Cash Transfer Program",
                "journal_id": cls.journal.id,
            }
        )

        # Create cycle
        today = date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle 2024-Q1",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": today + timedelta(days=90),
            }
        )

        # Create registrants (beneficiaries)
        cls.registrant1 = cls.env["res.partner"].create(
            {
                "name": "John Doe",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Add external ID for registrant1
        cls.reg_id1 = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.registrant1.id,
                "id_type_id": cls.id_type_national.id,
                "value": "PH-123456",
            }
        )

        cls.registrant2 = cls.env["res.partner"].create(
            {
                "name": "Jane Smith",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Add external ID for registrant2
        cls.reg_id2 = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.registrant2.id,
                "id_type_id": cls.id_type_national.id,
                "value": "PH-789012",
            }
        )

        # Create group registrant
        cls.group_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Family Group",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create cash entitlements
        cls.cash_ent1 = cls.env["spp.entitlement"].create(
            {
                "partner_id": cls.registrant1.id,
                "cycle_id": cls.cycle.id,
                "initial_amount": 1000.0,
                "currency_id": cls.currency.id,
                "state": "approved",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
                "date_approved": today,
            }
        )

        cls.cash_ent2 = cls.env["spp.entitlement"].create(
            {
                "partner_id": cls.registrant2.id,
                "cycle_id": cls.cycle.id,
                "initial_amount": 1500.0,
                "currency_id": cls.currency.id,
                "state": "draft",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
            }
        )

        cls.cash_ent3 = cls.env["spp.entitlement"].create(
            {
                "partner_id": cls.group_registrant.id,
                "cycle_id": cls.cycle.id,
                "initial_amount": 2000.0,
                "currency_id": cls.currency.id,
                "state": "approved",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
                "date_approved": today,
            }
        )

        # Create product for in-kind entitlements
        # In Odoo 19, 'product' type was replaced with 'consu' (consumable)
        cls.product = cls.env["product.product"].create(
            {
                "name": "Rice 25kg",
                "type": "consu",
                "default_code": "RICE-25KG",
            }
        )

        # Get UOM from demo data (Odoo 19 removed uom.category)
        cls.uom = cls.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        if not cls.uom:
            cls.uom = cls.env["uom.uom"].search([("name", "ilike", "unit")], limit=1)
        if not cls.uom:
            # Create a reference UoM - in Odoo 19, it points to itself
            cls.uom = cls.env["uom.uom"].create(
                {
                    "name": "Units",
                    "relative_factor": 1.0,
                }
            )
            cls.uom.relative_uom_id = cls.uom.id

        # Create service point
        cls.service_point = cls.env["spp.service.point"].create(
            {
                "name": "Main Distribution Center",
            }
        )

        # Create in-kind entitlements
        cls.inkind_ent1 = cls.env["spp.entitlement.inkind"].create(
            {
                "partner_id": cls.registrant1.id,
                "cycle_id": cls.cycle.id,
                "product_id": cls.product.id,
                "quantity": 2,
                "unit_price": 500.0,
                "uom_id": cls.uom.id,
                "service_point_id": cls.service_point.id,
                "state": "approved",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
                "date_approved": today,
            }
        )

        cls.inkind_ent2 = cls.env["spp.entitlement.inkind"].create(
            {
                "partner_id": cls.registrant2.id,
                "cycle_id": cls.cycle.id,
                "product_id": cls.product.id,
                "quantity": 3,
                "unit_price": 500.0,
                "uom_id": cls.uom.id,
                "state": "draft",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
            }
        )

        # Create API client with entitlement scope
        cls.partner = cls.env["res.partner"].create({"name": "Test API Partner"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Entitlement Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "entitlement",
                "action": "read",
            }
        )

        # Create client without scope
        cls.no_scope_partner = cls.env["res.partner"].create({"name": "No Scope Partner"})
        cls.no_scope_client = cls.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": cls.no_scope_partner.id,
                "organization_type_id": cls.org_type_private.id,
            }
        )

    def test_money_value_schema(self):
        """Test MoneyValue schema validates correctly."""
        from ..schemas.entitlement import MoneyValue

        money = MoneyValue(value=1000.50, currency="USD")
        assert money.value == 1000.50
        assert money.currency == "USD"

    def test_quantity_schema(self):
        """Test Quantity schema validates correctly."""
        from ..schemas.entitlement import Quantity

        qty = Quantity(value=5.0, unit="kg")
        assert qty.value == 5.0
        assert qty.unit == "kg"

    def test_product_quantity_schema(self):
        """Test ProductQuantity schema validates correctly."""
        from odoo.addons.spp_api_v2.schemas.base import Reference

        from ..schemas.entitlement import ProductQuantity, Quantity

        product_qty = ProductQuantity(
            product=Reference(reference="Product/RICE-25KG", display="Rice 25kg"),
            quantity=Quantity(value=2.0, unit="Units"),
            unitPrice={"value": 500.0, "currency": "USD"},
        )
        assert product_qty.product.reference == "Product/RICE-25KG"
        assert product_qty.quantity.value == 2.0
        assert product_qty.unit_price.value == 500.0

    def test_entitlement_schema_cash(self):
        """Test Entitlement schema validates correctly for cash type."""
        from ..schemas.entitlement import Entitlement

        ent = Entitlement(
            identifier="abc123",
            entitlementType="cash",
            state="approved",
            initialAmount={"value": 1000.0, "currency": "USD"},
            balance={"value": 1000.0, "currency": "USD"},
        )
        assert ent.identifier == "abc123"
        assert ent.entitlement_type == "cash"
        assert ent.state == "approved"
        assert ent.initial_amount.value == 1000.0

    def test_entitlement_schema_inkind(self):
        """Test Entitlement schema validates correctly for in-kind type."""

        from ..schemas.entitlement import Entitlement

        ent = Entitlement(
            identifier="xyz789",
            entitlementType="inkind",
            state="approved",
            items=[
                {
                    "product": {"reference": "Product/RICE", "display": "Rice"},
                    "quantity": {"value": 2.0, "unit": "bags"},
                }
            ],
        )
        assert ent.identifier == "xyz789"
        assert ent.entitlement_type == "inkind"
        assert len(ent.items) == 1
        assert ent.items[0].product.reference == "Product/RICE"

    def test_client_has_entitlement_scope(self):
        """Test API client has entitlement read scope."""
        assert self.api_client.has_scope("entitlement", "read")

    def test_client_without_entitlement_scope(self):
        """Test API client without entitlement scope."""
        assert not self.no_scope_client.has_scope("entitlement", "read")

    def test_cash_entitlement_created(self):
        """Test cash entitlement was created correctly."""
        assert self.cash_ent1.code
        assert self.cash_ent1.partner_id == self.registrant1
        assert self.cash_ent1.initial_amount == 1000.0
        assert self.cash_ent1.state == "approved"

    def test_inkind_entitlement_created(self):
        """Test in-kind entitlement was created correctly."""
        assert self.inkind_ent1.code
        assert self.inkind_ent1.partner_id == self.registrant1
        assert self.inkind_ent1.product_id == self.product
        assert self.inkind_ent1.quantity == 2
        assert self.inkind_ent1.state == "approved"

    def test_service_find_by_identifier_cash(self):
        """Test finding cash entitlement by code."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)
        found = service.find_by_identifier(self.cash_ent1.code)
        assert found == self.cash_ent1

    def test_service_find_by_identifier_inkind(self):
        """Test finding in-kind entitlement by code."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)
        found = service.find_by_identifier(self.inkind_ent1.code)
        assert found == self.inkind_ent1

    def test_service_find_by_identifier_not_found(self):
        """Test finding non-existent entitlement returns empty."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)
        found = service.find_by_identifier("NONEXISTENT-CODE")
        assert not found

    def test_service_to_api_schema_cash(self):
        """Test converting cash entitlement to API schema."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)
        data = service.to_api_schema(self.cash_ent1)

        assert data["type"] == "Entitlement"
        assert data["identifier"] == self.cash_ent1.code
        assert data["entitlementType"] == "cash"
        assert data["state"] == "approved"
        assert data["initialAmount"]["value"] == 1000.0
        assert data["initialAmount"]["currency"] == "USD"
        assert "beneficiary" in data
        assert "program" in data
        assert "cycle" in data
        assert "meta" in data
        assert "versionId" in data["meta"]

        # Verify no database IDs exposed as dictionary keys
        assert "id" not in data
        assert "partner_id" not in data
        assert "program_id" not in data
        assert "cycle_id" not in data

    def test_service_to_api_schema_inkind(self):
        """Test converting in-kind entitlement to API schema."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)
        data = service.to_api_schema(self.inkind_ent1)

        assert data["type"] == "Entitlement"
        assert data["identifier"] == self.inkind_ent1.code
        assert data["entitlementType"] == "inkind"
        assert data["state"] == "approved"
        assert len(data["items"]) == 1
        assert data["items"][0]["product"]["reference"] == "Product/RICE-25KG"
        assert data["items"][0]["quantity"]["value"] == 2
        assert data["items"][0]["unitPrice"]["value"] == 500.0
        assert data["servicePoint"]["reference"] == f"ServicePoint/{self.service_point.name}"

        # Verify no database IDs exposed as dictionary keys
        assert "id" not in data
        assert "partner_id" not in data
        assert "product_id" not in data

    def test_service_search_cash_entitlements(self):
        """Test searching cash entitlements."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)
        # Add user to api_v2 viewer group
        self.env.user.write(
            {
                "group_ids": [(4, self.env.ref("spp_api_v2.group_api_v2_viewer").id)],
            }
        )

        params = {"type": "cash", "_count": 10, "_offset": 0}
        records, total = service.search(params)

        assert total >= 3
        assert self.cash_ent1 in records or self.cash_ent2 in records or self.cash_ent3 in records

    def test_service_search_inkind_entitlements(self):
        """Test searching in-kind entitlements."""
        from ..services.entitlement_service import EntitlementService

        # Add user to api_v2 viewer group
        self.env.user.write(
            {
                "group_ids": [(4, self.env.ref("spp_api_v2.group_api_v2_viewer").id)],
            }
        )

        service = EntitlementService(self.env)
        params = {"type": "inkind", "_count": 10, "_offset": 0}
        records, total = service.search(params)

        assert total >= 2
        assert self.inkind_ent1 in records or self.inkind_ent2 in records

    def test_service_search_by_state(self):
        """Test searching entitlements by state."""
        from ..services.entitlement_service import EntitlementService

        # Add user to api_v2 viewer group
        self.env.user.write(
            {
                "group_ids": [(4, self.env.ref("spp_api_v2.group_api_v2_viewer").id)],
            }
        )

        service = EntitlementService(self.env)
        params = {"type": "cash", "state": "approved", "_count": 10, "_offset": 0}
        records, total = service.search(params)

        assert total >= 2
        assert all(rec.state == "approved" for rec in records)

    def test_service_search_by_beneficiary(self):
        """Test searching entitlements by beneficiary identifier."""
        from ..services.entitlement_service import EntitlementService

        # Add user to api_v2 viewer group
        self.env.user.write(
            {
                "group_ids": [(4, self.env.ref("spp_api_v2.group_api_v2_viewer").id)],
            }
        )

        service = EntitlementService(self.env)
        beneficiary_id = f"{self.reg_id1.id_type_id.uri}|{self.reg_id1.value}"
        params = {
            "type": "cash",
            "beneficiary": beneficiary_id,
            "_count": 10,
            "_offset": 0,
        }
        records, total = service.search(params)

        assert total >= 1
        assert all(rec.partner_id == self.registrant1 for rec in records)

    def test_service_search_pagination(self):
        """Test search respects pagination parameters."""
        from ..services.entitlement_service import EntitlementService

        # Add user to api_v2 viewer group
        self.env.user.write(
            {
                "group_ids": [(4, self.env.ref("spp_api_v2.group_api_v2_viewer").id)],
            }
        )

        service = EntitlementService(self.env)
        params = {"type": "cash", "_count": 1, "_offset": 0}
        records, total = service.search(params)

        assert len(records) <= 1
        assert total >= 3


class TestEntitlementAPIEndpoints(TransactionCase):
    """Test Entitlement API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Lookup or create ID type vocabulary code for registry IDs
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )
        cls.id_type_national = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "NATIONAL_ID")],
            limit=1,
        )
        if not cls.id_type_national:
            cls.id_type_national = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "NATIONAL_ID",
                    "display": "National ID",
                    "is_local": True,
                    "target_type": "individual",
                }
            )

        # Get or create currency (include inactive in search to avoid unique constraint)
        cls.currency = cls.env["res.currency"].with_context(active_test=False).search([("name", "=", "PHP")], limit=1)
        if not cls.currency:
            cls.currency = cls.env["res.currency"].create(
                {
                    "name": "PHP",
                    "symbol": "₱",
                    "rounding": 0.01,
                }
            )
        elif not cls.currency.active:
            cls.currency.active = True

        # Get or create journal (search first to avoid unique code constraint)
        cls.journal = cls.env["account.journal"].search([("code", "=", "4PSE")], limit=1)
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {
                    "name": "4Ps Entitlement Journal Endpoints",
                    "type": "bank",
                    "code": "4PSE",
                    "currency_id": cls.currency.id,
                }
            )

        # Create program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Pantawid Pamilyang Pilipino Program",
                "journal_id": cls.journal.id,
            }
        )

        # Create cycle
        today = date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "4Ps-2024-Q1",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": today + timedelta(days=90),
            }
        )

        # Create registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Maria Santos",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Add external ID
        cls.reg_id = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.registrant.id,
                "id_type_id": cls.id_type_national.id,
                "value": "PH-123",
            }
        )

        # Create cash entitlement
        cls.cash_ent = cls.env["spp.entitlement"].create(
            {
                "partner_id": cls.registrant.id,
                "cycle_id": cls.cycle.id,
                "initial_amount": 3000.0,
                "currency_id": cls.currency.id,
                "state": "approved",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
                "date_approved": today,
            }
        )

        # Create product
        # In Odoo 19, 'product' type was replaced with 'consu' (consumable)
        cls.product = cls.env["product.product"].create(
            {
                "name": "Food Pack",
                "type": "consu",
                "default_code": "FOOD-PACK",
            }
        )

        # Get UOM from demo data (Odoo 19 removed uom.category)
        cls.uom = cls.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        if not cls.uom:
            cls.uom = cls.env["uom.uom"].search([("name", "ilike", "unit")], limit=1)
        if not cls.uom:
            # Create a reference UoM - in Odoo 19, it points to itself
            cls.uom = cls.env["uom.uom"].create(
                {
                    "name": "Units",
                    "relative_factor": 1.0,
                }
            )
            cls.uom.relative_uom_id = cls.uom.id

        # Create in-kind entitlement
        cls.inkind_ent = cls.env["spp.entitlement.inkind"].create(
            {
                "partner_id": cls.registrant.id,
                "cycle_id": cls.cycle.id,
                "product_id": cls.product.id,
                "quantity": 1,
                "unit_price": 500.0,
                "uom_id": cls.uom.id,
                "state": "approved",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
                "date_approved": today,
            }
        )

        # Lookup organization type (required for spp.api.client)
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        # Create API client with scope
        cls.partner = cls.env["res.partner"].create({"name": "Test API Partner"})
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
                "resource": "entitlement",
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

    async def test_read_cash_entitlement_success(self):
        """Test GET /Entitlement/{identifier} returns cash entitlement."""
        from unittest.mock import MagicMock

        from ..routers.entitlement import read_entitlement

        response = MagicMock()
        result = await read_entitlement(
            identifier=self.cash_ent.code,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["type"] == "Entitlement"
        assert result["identifier"] == self.cash_ent.code
        assert result["entitlementType"] == "cash"
        assert result["state"] == "approved"
        assert result["initialAmount"]["value"] == 3000.0
        assert result["initialAmount"]["currency"] == "PHP"
        assert result["beneficiary"]["display"] == "Maria Santos"
        assert result["program"]["display"] == "Pantawid Pamilyang Pilipino Program"
        assert result["cycle"]["display"] == "4Ps-2024-Q1"

        # Verify ETag header was set
        assert response.headers.__setitem__.called
        etag_set = False
        for call in response.headers.__setitem__.call_args_list:
            if call[0][0] == "ETag":
                etag_set = True
                break
        assert etag_set

        # Verify no database IDs exposed
        assert self.cash_ent.id not in str(result)

    async def test_read_inkind_entitlement_success(self):
        """Test GET /Entitlement/{identifier} returns in-kind entitlement."""
        from unittest.mock import MagicMock

        from ..routers.entitlement import read_entitlement

        response = MagicMock()
        result = await read_entitlement(
            identifier=self.inkind_ent.code,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["type"] == "Entitlement"
        assert result["identifier"] == self.inkind_ent.code
        assert result["entitlementType"] == "inkind"
        assert result["state"] == "approved"
        assert len(result["items"]) == 1
        assert result["items"][0]["product"]["reference"] == "Product/FOOD-PACK"
        assert result["items"][0]["quantity"]["value"] == 1

    async def test_read_entitlement_url_encoded(self):
        """Test GET /Entitlement/{identifier} handles URL encoding."""
        from unittest.mock import MagicMock

        from ..routers.entitlement import read_entitlement

        encoded_code = quote(self.cash_ent.code, safe="")
        response = MagicMock()
        result = await read_entitlement(
            identifier=encoded_code,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["identifier"] == self.cash_ent.code

    async def test_read_entitlement_not_found(self):
        """Test GET /Entitlement/{identifier} returns 404 for non-existent."""
        from unittest.mock import MagicMock

        from ..routers.entitlement import read_entitlement

        with self.assertRaises(HTTPException) as cm:
            response = MagicMock()
            await read_entitlement(
                identifier="NONEXISTENT-CODE",
                env=self.env,
                api_client=self.api_client,
                response=response,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_entitlement_no_scope(self):
        """Test GET /Entitlement/{identifier} without scope returns 403."""
        from unittest.mock import MagicMock

        from ..routers.entitlement import read_entitlement

        with self.assertRaises(HTTPException) as cm:
            response = MagicMock()
            await read_entitlement(
                identifier=self.cash_ent.code,
                env=self.env,
                api_client=self.no_scope_client,
                response=response,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_entitlements_success(self):
        """Test GET /Entitlement returns entitlement search result."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.meta.total >= 1
        assert result.meta.count >= 1
        assert result.meta.offset == 0
        assert len(result.data) >= 1
        assert result.links.self

        # Check first entry
        entry = result.data[0]
        assert entry["type"] == "Entitlement"

    async def test_search_entitlements_by_type_cash(self):
        """Test GET /Entitlement?entitlementType=cash filters cash entitlements."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert all(e["entitlementType"] == "cash" for e in result.data)

    async def test_search_entitlements_by_type_inkind(self):
        """Test GET /Entitlement?entitlementType=inkind filters in-kind entitlements."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="inkind",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert all(e["entitlementType"] == "inkind" for e in result.data)

    async def test_search_entitlements_by_state(self):
        """Test GET /Entitlement?state=approved filters by state."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state="approved",
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert all(e["state"] == "approved" for e in result.data)

    async def test_search_entitlements_by_beneficiary(self):
        """Test GET /Entitlement?beneficiary=system|value filters by beneficiary."""
        from ..routers.entitlement import search_entitlements

        beneficiary_id = f"{self.reg_id.id_type_id.uri}|{self.reg_id.value}"
        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=beneficiary_id,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.meta.total >= 1
        assert all("Maria Santos" in e.get("beneficiary", {}).get("display", "") for e in result.data)

    async def test_search_entitlements_by_program(self):
        """Test GET /Entitlement?program=name filters by program."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program="Pantawid",
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.meta.total >= 1
        assert all("Pantawid" in e.get("program", {}).get("display", "") for e in result.data if "program" in e)

    async def test_search_entitlements_by_cycle(self):
        """Test GET /Entitlement?cycle=name filters by cycle."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle="2024-Q1",
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.meta.total >= 1
        assert all("2024-Q1" in e.get("cycle", {}).get("display", "") for e in result.data if "cycle" in e)

    async def test_search_entitlements_pagination(self):
        """Test GET /Entitlement respects pagination."""
        # Create more entitlements
        for i in range(5):
            self.env["spp.entitlement"].create(
                {
                    "partner_id": self.registrant.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 1000.0 + (i * 100),
                    "currency_id": self.currency.id,
                    "state": "approved",
                }
            )

        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=2,
            offset=0,
        )

        assert len(result.data) == 2
        assert result.meta.total >= 5

        # Check for next link
        assert result.links.next is not None
        assert "_offset=2" in result.links.next

    async def test_search_entitlements_pagination_offset(self):
        """Test GET /Entitlement with offset returns different results."""
        from ..routers.entitlement import search_entitlements

        result1 = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=1,
            offset=0,
        )

        result2 = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=1,
            offset=1,
        )

        if len(result1.data) > 0 and len(result2.data) > 0:
            assert result1.data[0]["identifier"] != result2.data[0]["identifier"]

    async def test_search_entitlements_pagination_previous_link(self):
        """Test GET /Entitlement with offset includes previous link."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=2,
            offset=2,
        )

        if result.meta.total > 2:
            assert result.links.prev is not None
            assert "_offset=0" in result.links.prev

    async def test_search_entitlements_no_scope(self):
        """Test GET /Entitlement without scope returns 403."""
        from ..routers.entitlement import search_entitlements

        with self.assertRaises(HTTPException) as cm:
            await search_entitlements(
                env=self.env,
                api_client=self.no_scope_client,
                beneficiary=None,
                program=None,
                cycle=None,
                state=None,
                entitlement_type="cash",
                valid_from=None,
                valid_until=None,
                last_updated=None,
                count=20,
                offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_entitlements_no_results(self):
        """Test GET /Entitlement with no matches returns empty result."""
        from ..routers.entitlement import search_entitlements

        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary="urn:nonexistent|NONE",
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.meta.total == 0
        assert len(result.data) == 0

    async def test_search_entitlements_last_updated_filter(self):
        """Test GET /Entitlement?_lastUpdated=ge2024-01-01 filters by update date."""
        from ..routers.entitlement import search_entitlements

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        result = await search_entitlements(
            env=self.env,
            api_client=self.api_client,
            beneficiary=None,
            program=None,
            cycle=None,
            state=None,
            entitlement_type="cash",
            valid_from=None,
            valid_until=None,
            last_updated=f"ge{yesterday}",
            count=20,
            offset=0,
        )

        # Should return entitlements created today
        assert result.meta.total >= 1

    def test_entitlement_router_included(self):
        """Test that entitlement router is included in API V2."""
        endpoint = self.env["fastapi.endpoint"].search(
            [("app", "=", "api_v2")],
            limit=1,
        )
        if not endpoint:
            self.skipTest("No API V2 endpoint found")

        routers = endpoint._get_fastapi_routers()
        router_prefixes = [r.prefix for r in routers]
        self.assertIn("/Entitlement", router_prefixes)

    def test_no_database_ids_in_response(self):
        """Test that database IDs are never exposed in API responses."""
        from ..services.entitlement_service import EntitlementService

        service = EntitlementService(self.env)

        # Test cash entitlement
        cash_data = service.to_api_schema(self.cash_ent)

        # Check that database ID field names are not in the response
        assert "id" not in cash_data
        assert "partner_id" not in cash_data
        assert "cycle_id" not in cash_data
        assert "program_id" not in cash_data

        # Test in-kind entitlement
        inkind_data = service.to_api_schema(self.inkind_ent)

        assert "id" not in inkind_data
        assert "product_id" not in inkind_data

    def test_entitlement_code_uniqueness(self):
        """Test that entitlement codes are unique."""
        codes = set()
        for _ in range(10):
            ent = self.env["spp.entitlement"].create(
                {
                    "partner_id": self.registrant.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 1000.0,
                    "currency_id": self.currency.id,
                }
            )
            codes.add(ent.code)

        # All codes should be unique
        assert len(codes) == 10
