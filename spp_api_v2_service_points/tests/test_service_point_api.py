# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ServicePoint API endpoints."""

from urllib.parse import quote

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestServicePointAPI(TransactionCase):
    """Test ServicePoint API functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test country
        cls.country_ph = cls.env.ref("base.ph")
        cls.country_us = cls.env.ref("base.us")

        # Get organization types
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

        # Create test areas
        cls.area_manila = cls.env["spp.area"].create(
            {
                "name": "Manila",
                "draft_name": "Manila",
            }
        )
        cls.area_cebu = cls.env["spp.area"].create(
            {
                "name": "Cebu",
                "draft_name": "Cebu",
            }
        )

        # Create or find service type vocabulary (avoid duplicate namespace_uri)
        cls.service_vocab = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:service-types")], limit=1
        )
        if not cls.service_vocab:
            cls.service_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Service Types",
                    "namespace_uri": "urn:openspp:vocab:service-types",
                    "domain": "core",
                }
            )
        cls.service_type_cash = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.service_vocab.id), ("code", "=", "CASH")],
            limit=1,
        )
        if not cls.service_type_cash:
            cls.service_type_cash = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.service_vocab.id,
                    "code": "CASH",
                    "display": "Cash Distribution",
                }
            )
        cls.service_type_voucher = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.service_vocab.id), ("code", "=", "VOUCHER")],
            limit=1,
        )
        if not cls.service_type_voucher:
            cls.service_type_voucher = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.service_vocab.id,
                    "code": "VOUCHER",
                    "display": "Voucher Distribution",
                }
            )

        # Create test companies
        cls.company1 = cls.env["res.partner"].create(
            {
                "name": "Distribution Company A",
                "is_company": True,
            }
        )
        cls.company2 = cls.env["res.partner"].create(
            {
                "name": "Distribution Company B",
                "is_company": True,
            }
        )

        # Create test service points
        cls.sp1 = cls.env["spp.service.point"].create(
            {
                "name": "SP-MANILA-001",
                "area_id": cls.area_manila.id,
                "country_id": cls.country_ph.id,
                "phone_no": "+639171234567",
                "shop_address": "123 Main St, Manila",
                "is_contract_active": True,
                "is_disabled": False,
                "res_partner_company_id": cls.company1.id,
                "service_type_ids": [(6, 0, [cls.service_type_cash.id])],
            }
        )
        cls.sp2 = cls.env["spp.service.point"].create(
            {
                "name": "SP-CEBU-002",
                "area_id": cls.area_cebu.id,
                "country_id": cls.country_ph.id,
                "phone_no": "+639177654321",
                "shop_address": "456 Market St, Cebu",
                "is_contract_active": False,
                "is_disabled": False,
                "res_partner_company_id": cls.company2.id,
                "service_type_ids": [(6, 0, [cls.service_type_voucher.id])],
            }
        )
        cls.sp3 = cls.env["spp.service.point"].create(
            {
                "name": "SP-US-003",
                "country_id": cls.country_us.id,
                "is_contract_active": True,
                "is_disabled": True,
            }
        )
        cls.sp4 = cls.env["spp.service.point"].create(
            {
                "name": "SP With Spaces",
                "country_id": cls.country_ph.id,
                "is_contract_active": True,
                "is_disabled": False,
            }
        )

        # Create test partner and API client with scope
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test API Partner",
            }
        )
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        # Add service_point scope
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "service_point",
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

    def test_service_point_schema(self):
        """Test ServicePoint schema validates correctly."""
        from ..schemas.service_point import ServicePoint

        sp = ServicePoint(
            identifier="SP-TEST-001",
            name="Test Service Point",
            contractActive=True,
            disabled=False,
            country="PH",
        )
        assert sp.identifier == "SP-TEST-001"
        assert sp.name == "Test Service Point"
        assert sp.active is True
        assert sp.disabled is False

    def test_client_has_service_point_scope(self):
        """Test API client has service_point read scope."""
        assert self.api_client.has_scope("service_point", "read")

    def test_client_without_service_point_scope(self):
        """Test API client without service_point scope."""
        assert not self.no_scope_client.has_scope("service_point", "read")

    def test_service_point_model_exists(self):
        """Test service point records were created correctly."""
        assert self.sp1.name == "SP-MANILA-001"
        assert self.sp1.area_id == self.area_manila
        assert self.sp1.country_id == self.country_ph
        assert self.sp1.is_contract_active is True
        assert self.sp1.is_disabled is False

    def test_service_point_to_api_schema_no_db_ids(self):
        """Test that to_api_schema does not expose database IDs."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)
        data = service.to_api_schema(self.sp1)

        # Check basic fields
        assert data["identifier"] == "SP-MANILA-001"
        assert data["name"] == "SP-MANILA-001"
        assert data["contractActive"] is True
        assert data["disabled"] is False
        assert data["country"] == "PH"

        # Check area reference does not contain DB ID
        assert "area" in data
        assert data["area"]["reference"] == f"Area/{self.area_manila.name}"
        assert data["area"]["display"] == self.area_manila.name
        assert str(self.area_manila.id) not in str(data["area"])

        # Check company reference does not contain DB ID
        assert "company" in data
        assert data["company"]["reference"] == f"Organization/{self.company1.name}"
        assert data["company"]["display"] == self.company1.name
        assert str(self.company1.id) not in str(data["company"])

        # Ensure no field directly exposes database ID as a value
        assert "id" not in data
        for key in ("area", "company"):
            if key in data and isinstance(data[key], dict):
                assert "id" not in data[key]

    def test_service_point_metadata(self):
        """Test service point includes metadata."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)
        data = service.to_api_schema(self.sp1)

        assert "meta" in data
        assert "versionId" in data["meta"]
        assert "lastUpdated" in data["meta"]
        # versionId should be timestamp in microseconds
        assert len(data["meta"]["versionId"]) > 10
        # lastUpdated should be ISO format
        assert "T" in data["meta"]["lastUpdated"]

    def test_service_point_with_phone(self):
        """Test service point with phone number."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)
        data = service.to_api_schema(self.sp1)

        assert "telecom" in data
        assert len(data["telecom"]) == 1
        assert data["telecom"][0]["system"] == "phone"
        assert data["telecom"][0]["use"] == "work"
        # Should use sanitized phone if available
        if self.sp1.phone_sanitized:
            assert data["telecom"][0]["value"] == self.sp1.phone_sanitized
        else:
            assert data["telecom"][0]["value"] == self.sp1.phone_no

    def test_service_point_with_service_types(self):
        """Test service point with service types."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)
        data = service.to_api_schema(self.sp1)

        assert "serviceType" in data
        assert "Cash Distribution" in data["serviceType"]

    def test_service_point_router_included(self):
        """Test that service_point router is included in API V2."""
        endpoint = self.env["fastapi.endpoint"].search(
            [("app", "=", "api_v2")],
            limit=1,
        )
        if not endpoint:
            self.skipTest("No API V2 endpoint found")

        routers = endpoint._get_fastapi_routers()
        router_prefixes = [r.prefix for r in routers]
        self.assertIn("/ServicePoint", router_prefixes)


class TestServicePointAPIEndpoints(TransactionCase):
    """Test ServicePoint API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test data
        cls.country_ph = cls.env.ref("base.ph")
        cls.country_us = cls.env.ref("base.us")

        # Get organization types
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        cls.area_manila = cls.env["spp.area"].create(
            {
                "name": "Manila",
                "draft_name": "Manila",
            }
        )
        cls.area_cebu = cls.env["spp.area"].create(
            {
                "name": "Cebu",
                "draft_name": "Cebu",
            }
        )

        cls.service_vocab = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:service-types")], limit=1
        )
        if not cls.service_vocab:
            cls.service_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Service Types",
                    "namespace_uri": "urn:openspp:vocab:service-types",
                    "domain": "core",
                }
            )
        cls.service_type_cash = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.service_vocab.id), ("code", "=", "CASH")],
            limit=1,
        )
        if not cls.service_type_cash:
            cls.service_type_cash = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.service_vocab.id,
                    "code": "CASH",
                    "display": "Cash Distribution",
                }
            )

        cls.company1 = cls.env["res.partner"].create(
            {
                "name": "Company A",
                "is_company": True,
            }
        )

        # Create service points
        cls.sp1 = cls.env["spp.service.point"].create(
            {
                "name": "SP-MANILA-001",
                "area_id": cls.area_manila.id,
                "country_id": cls.country_ph.id,
                "phone_no": "+639171234567",
                "shop_address": "123 Main St, Manila",
                "is_contract_active": True,
                "is_disabled": False,
                "res_partner_company_id": cls.company1.id,
                "service_type_ids": [(6, 0, [cls.service_type_cash.id])],
            }
        )
        cls.sp2 = cls.env["spp.service.point"].create(
            {
                "name": "SP-CEBU-002",
                "area_id": cls.area_cebu.id,
                "country_id": cls.country_ph.id,
                "is_contract_active": False,
                "is_disabled": False,
            }
        )
        cls.sp3 = cls.env["spp.service.point"].create(
            {
                "name": "SP-US-003",
                "country_id": cls.country_us.id,
                "is_contract_active": True,
                "is_disabled": False,
            }
        )
        cls.sp_with_spaces = cls.env["spp.service.point"].create(
            {
                "name": "SP With Spaces",
                "country_id": cls.country_ph.id,
                "is_contract_active": True,
                "is_disabled": False,
            }
        )

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
                "resource": "service_point",
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

    async def test_read_service_point_success(self):
        """Test GET /ServicePoint/{identifier} returns service point."""
        from unittest.mock import MagicMock

        from ..routers.service_point import read_service_point

        # Mock Response object
        mock_response = MagicMock()
        mock_response.headers = {}

        result = await read_service_point(
            identifier="SP-MANILA-001",
            env=self.env,
            api_client=self.api_client,
            response=mock_response,
        )

        assert result["identifier"] == "SP-MANILA-001"
        assert result["name"] == "SP-MANILA-001"
        assert result["contractActive"] is True
        assert result["disabled"] is False
        assert result["country"] == "PH"
        assert "area" in result
        assert result["area"]["display"] == "Manila"
        # Check ETag header was set
        assert "ETag" in mock_response.headers

    async def test_read_service_point_url_encoded(self):
        """Test GET /ServicePoint/{identifier} handles URL encoding."""
        from unittest.mock import MagicMock

        from ..routers.service_point import read_service_point

        mock_response = MagicMock()
        mock_response.headers = {}

        # Test with URL-encoded identifier
        encoded_identifier = quote("SP With Spaces", safe="")

        result = await read_service_point(
            identifier=encoded_identifier,
            env=self.env,
            api_client=self.api_client,
            response=mock_response,
        )

        assert result["identifier"] == "SP With Spaces"
        assert result["name"] == "SP With Spaces"

    async def test_read_service_point_not_found(self):
        """Test GET /ServicePoint/{identifier} returns 404 for non-existent service point."""
        from unittest.mock import MagicMock

        from ..routers.service_point import read_service_point

        mock_response = MagicMock()
        mock_response.headers = {}

        with self.assertRaises(HTTPException) as cm:
            await read_service_point(
                identifier="NONEXISTENT-SP",
                env=self.env,
                api_client=self.api_client,
                response=mock_response,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_service_point_no_scope(self):
        """Test GET /ServicePoint/{identifier} without scope returns 403."""
        from unittest.mock import MagicMock

        from ..routers.service_point import read_service_point

        mock_response = MagicMock()
        mock_response.headers = {}

        with self.assertRaises(HTTPException) as cm:
            await read_service_point(
                identifier="SP-MANILA-001",
                env=self.env,
                api_client=self.no_scope_client,
                response=mock_response,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_service_points_success(self):
        """Test GET /ServicePoint returns service point list."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.resourceType == "Bundle"
        assert result.type == "searchset"
        assert result.total >= 4
        assert len(result.entry) >= 4
        # Check bundle entries have resources
        for entry in result.entry:
            assert entry.resource is not None
            assert entry.resource["resourceType"] == "ServicePoint"
            assert "identifier" in entry.resource

    async def test_search_service_points_by_name(self):
        """Test GET /ServicePoint?name=MANILA filters by name."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name="MANILA",
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.total >= 1
        assert any(entry.resource["identifier"] == "SP-MANILA-001" for entry in result.entry)

    async def test_search_service_points_by_area(self):
        """Test GET /ServicePoint?area=Cebu filters by area."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area="Cebu",
            country=None,
            active=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.total >= 1
        assert any(entry.resource["identifier"] == "SP-CEBU-002" for entry in result.entry)

    async def test_search_service_points_by_country(self):
        """Test GET /ServicePoint?country=PH filters by country."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country="PH",
            active=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        # Should return PH service points
        assert result.total >= 3
        assert all(entry.resource.get("country") == "PH" for entry in result.entry if "country" in entry.resource)

    async def test_search_service_points_by_country_lowercase(self):
        """Test GET /ServicePoint?country=ph converts to uppercase."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country="ph",  # lowercase
            active=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        # Should return PH service points (case insensitive)
        assert result.total >= 3

    async def test_search_service_points_by_active(self):
        """Test GET /ServicePoint?contractActive=true filters by contract status."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=True,
            last_updated=None,
            count=20,
            offset=0,
        )

        # Should return only active contracts
        assert result.total >= 2
        assert all(entry.resource["contractActive"] is True for entry in result.entry)

    async def test_search_service_points_by_inactive(self):
        """Test GET /ServicePoint?contractActive=false filters inactive contracts."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=False,
            last_updated=None,
            count=20,
            offset=0,
        )

        # Should return only inactive contracts
        assert result.total >= 1
        assert all(entry.resource["contractActive"] is False for entry in result.entry)

    async def test_search_service_points_by_last_updated_ge(self):
        """Test GET /ServicePoint?_lastUpdated=ge2020-01-01 filters by date."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated="ge2020-01-01",
            count=20,
            offset=0,
        )

        # Should return records updated after 2020
        assert result.total >= 4

    async def test_search_service_points_by_last_updated_le(self):
        """Test GET /ServicePoint?_lastUpdated=le2099-12-31 filters by date."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated="le2099-12-31",
            count=20,
            offset=0,
        )

        # Should return all records
        assert result.total >= 4

    async def test_search_service_points_combined_filters(self):
        """Test GET /ServicePoint with multiple filters."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name="SP",
            area=None,
            country="PH",
            active=True,
            last_updated=None,
            count=20,
            offset=0,
        )

        # Should return only active PH service points with SP in name
        assert result.total >= 2
        for entry in result.entry:
            assert "SP" in entry.resource["identifier"]
            if "country" in entry.resource:
                assert entry.resource["country"] == "PH"
            assert entry.resource["contractActive"] is True

    async def test_search_service_points_pagination(self):
        """Test GET /ServicePoint respects pagination parameters."""
        from ..routers.service_point import search_service_points

        # Create more service points for pagination
        for i in range(10):
            self.env["spp.service.point"].create(
                {
                    "name": f"SP-TEST-{i:03d}",
                    "country_id": self.country_ph.id,
                    "is_contract_active": True,
                }
            )

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=5,
            offset=0,
        )

        assert len(result.entry) == 5
        assert result.total >= 14

        # Test offset
        result2 = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=5,
            offset=5,
        )

        assert len(result2.entry) == 5
        # Items should be different
        assert result2.entry[0].resource["identifier"] != result.entry[0].resource["identifier"]

    async def test_search_service_points_pagination_links(self):
        """Test GET /ServicePoint includes correct pagination links."""
        from ..routers.service_point import search_service_points

        # Create more service points
        for i in range(10):
            self.env["spp.service.point"].create(
                {
                    "name": f"SP-LINK-{i:03d}",
                    "country_id": self.country_ph.id,
                }
            )

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=5,
            offset=0,
        )

        # Should have self and next links
        link_relations = [link.relation for link in result.link]
        assert "self" in link_relations
        assert "next" in link_relations
        assert "previous" not in link_relations  # No previous on first page

        # Check next page
        result2 = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=5,
            offset=5,
        )

        link_relations2 = [link.relation for link in result2.link]
        assert "self" in link_relations2
        assert "previous" in link_relations2

    async def test_search_service_points_no_scope(self):
        """Test GET /ServicePoint without scope returns 403."""
        from ..routers.service_point import search_service_points

        with self.assertRaises(HTTPException) as cm:
            await search_service_points(
                env=self.env,
                api_client=self.no_scope_client,
                name=None,
                area=None,
                country=None,
                active=None,
                last_updated=None,
                count=20,
                offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_service_points_empty_result(self):
        """Test GET /ServicePoint handles empty results."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name="NONEXISTENT-SERVICE-POINT",
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=20,
            offset=0,
        )

        assert result.total == 0
        assert len(result.entry) == 0
        # Should still have self link
        link_relations = [link.relation for link in result.link]
        assert "self" in link_relations

    async def test_search_service_points_max_count(self):
        """Test GET /ServicePoint respects max count of 100."""
        from ..routers.service_point import search_service_points

        result = await search_service_points(
            env=self.env,
            api_client=self.api_client,
            name=None,
            area=None,
            country=None,
            active=None,
            last_updated=None,
            count=100,  # max allowed
            offset=0,
        )

        # Should succeed
        assert len(result.entry) <= 100

    def test_service_point_find_by_identifier(self):
        """Test ServicePointService.find_by_identifier."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)

        # Find existing
        sp = service.find_by_identifier("SP-MANILA-001")
        assert sp.id == self.sp1.id

        # Find non-existing
        sp = service.find_by_identifier("NONEXISTENT")
        assert not sp

    def test_service_point_search_service(self):
        """Test ServicePointService.search."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)

        # Search all
        records, total = service.search({"_count": 10, "_offset": 0})
        assert total >= 4
        assert len(records) >= 4

        # Search by name
        records, total = service.search({"name": "MANILA", "_count": 10, "_offset": 0})
        assert total >= 1
        assert any(r.name == "SP-MANILA-001" for r in records)

        # Search by area
        records, total = service.search({"area": "Cebu", "_count": 10, "_offset": 0})
        assert total >= 1
        assert any(r.name == "SP-CEBU-002" for r in records)

        # Search by country
        records, total = service.search({"country": "US", "_count": 10, "_offset": 0})
        assert total >= 1
        assert any(r.name == "SP-US-003" for r in records)

        # Search by contractActive
        records, total = service.search({"contractActive": True, "_count": 10, "_offset": 0})
        assert total >= 2
        assert all(r.is_contract_active for r in records)

    def test_no_db_ids_in_bundle(self):
        """Test that search results contain no database IDs as values."""
        from ..services.service_point_service import ServicePointService

        service = ServicePointService(self.env)
        records, total = service.search({"_count": 10, "_offset": 0})

        for sp in records:
            data = service.to_api_schema(sp)
            # Check that no top-level or nested dict value is a raw DB integer ID
            # (simple string matching is too aggressive for small IDs like 1, 2, 3)
            self._assert_no_id_value(data, "id", sp.id)
            if sp.area_id:
                self._assert_no_id_value(data, "area_id", sp.area_id.id)
            if sp.country_id:
                self._assert_no_id_value(data, "country_id", sp.country_id.id)
            if sp.res_partner_company_id:
                self._assert_no_id_value(data, "company_id", sp.res_partner_company_id.id)

    def _assert_no_id_value(self, data, label, db_id):
        """Check that a DB ID doesn't appear as a direct value in the response dict."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "meta":
                    continue  # Skip metadata (timestamps contain numbers)
                if isinstance(value, int) and value == db_id:
                    raise AssertionError(f"Database ID {db_id} ({label}) found as value for key '{key}'")
                if isinstance(value, dict | list):
                    self._assert_no_id_value(value, label, db_id)
        elif isinstance(data, list):
            for item in data:
                self._assert_no_id_value(item, label, db_id)

    async def test_read_service_point_etag_header(self):
        """Test GET /ServicePoint/{identifier} sets ETag header."""
        from unittest.mock import MagicMock

        from ..routers.service_point import read_service_point

        mock_response = MagicMock()
        mock_response.headers = {}

        result = await read_service_point(
            identifier="SP-MANILA-001",
            env=self.env,
            api_client=self.api_client,
            response=mock_response,
        )

        # Check ETag header was set
        assert "ETag" in mock_response.headers
        etag = mock_response.headers["ETag"]
        # ETag should be quoted
        assert etag.startswith('"')
        assert etag.endswith('"')
        # Should match versionId
        assert etag.strip('"') == result["meta"]["versionId"]
