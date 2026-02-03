# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Cycle API endpoints."""

from datetime import date, timedelta
from urllib.parse import quote

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestCycleAPI(TransactionCase):
    """Test Cycle API functionality."""

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

        # Create test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program",
                "journal_id": cls.env["account.journal"].search([("type", "=", "bank")], limit=1).id,
            }
        )

        # Create test cycles with dynamic dates (must be today or in the future)
        today = date.today()
        cls.cycle1 = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle Q1",
                "program_id": cls.program.id,
                "sequence": 1,
                "start_date": today,
                "end_date": today + timedelta(days=90),
                "state": "draft",
            }
        )

        cls.cycle2 = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle Q2",
                "program_id": cls.program.id,
                "sequence": 2,
                "start_date": today + timedelta(days=91),
                "end_date": today + timedelta(days=180),
                "state": "approved",
            }
        )

        cls.cycle3 = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle Q3",
                "program_id": cls.program.id,
                "sequence": 3,
                "start_date": today + timedelta(days=181),
                "end_date": today + timedelta(days=270),
                "state": "distributed",
            }
        )

        # Create another program with cycle
        cls.program2 = cls.env["spp.program"].create(
            {
                "name": "Other Program",
                "journal_id": cls.env["account.journal"].search([("type", "=", "bank")], limit=1).id,
            }
        )

        cls.cycle4 = cls.env["spp.cycle"].create(
            {
                "name": "Other Cycle 2024",
                "program_id": cls.program2.id,
                "sequence": 1,
                "start_date": today + timedelta(days=180),
                "end_date": today + timedelta(days=270),
                "state": "draft",
            }
        )

        # Set up cycle navigation
        cls.cycle1.next_cycle_id = cls.cycle2.id
        cls.cycle2.previous_cycle_id = cls.cycle1.id
        cls.cycle2.next_cycle_id = cls.cycle3.id
        cls.cycle3.previous_cycle_id = cls.cycle2.id

        # Create test partner and API client
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
        # Add cycle scope
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "cycle",
                "action": "read",
            }
        )

    def test_cycle_statistics_schema(self):
        """Test CycleStatistics schema validates correctly."""
        from ..schemas.cycle import CycleStatistics

        stats = CycleStatistics(
            members_count=100,
            entitlements_count=100,
            payments_count=50,
            total_amount=50000.00,
            currency="USD",
        )
        assert stats.members_count == 100
        assert stats.entitlements_count == 100
        assert stats.payments_count == 50
        assert stats.total_amount == 50000.00
        assert stats.currency == "USD"

    def test_cycle_schema(self):
        """Test Cycle schema validates correctly."""
        from ..schemas.cycle import Cycle

        cycle = Cycle(
            identifier="Test-2024-Q1",
            name="Test 2024 Q1",
            sequence=1,
            program={
                "reference": "Program/Test",
                "display": "Test Program",
            },
            period={
                "start": "2024-01-01",
                "end": "2024-03-31",
            },
            state="draft",
        )
        assert cycle.identifier == "Test-2024-Q1"
        assert cycle.name == "Test 2024 Q1"
        assert cycle.sequence == 1
        assert cycle.state == "draft"
        assert cycle.program.reference == "Program/Test"

    def test_client_has_cycle_scope(self):
        """Test API client has cycle read scope."""
        assert self.api_client.has_scope("cycle", "read")

    def test_client_without_cycle_scope(self):
        """Test API client without cycle scope."""
        # Create client without scope
        client = self.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": self.partner.id,
                "organization_type_id": self.org_type_private.id,
            }
        )
        assert not client.has_scope("cycle", "read")

    def test_cycle_model_exists(self):
        """Test cycle record was created correctly."""
        assert self.cycle1.name == "Test Cycle Q1"
        assert self.cycle1.program_id == self.program
        assert self.cycle1.sequence == 1
        assert self.cycle1.state == "draft"

    def test_cycle_navigation(self):
        """Test cycle navigation relationships."""
        assert self.cycle1.next_cycle_id == self.cycle2
        assert self.cycle2.previous_cycle_id == self.cycle1
        assert self.cycle2.next_cycle_id == self.cycle3
        assert self.cycle3.previous_cycle_id == self.cycle2

    def test_service_find_by_identifier(self):
        """Test CycleService.find_by_identifier finds cycle by name."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        cycle = service.find_by_identifier("Test Cycle Q1")

        assert cycle
        assert cycle.name == "Test Cycle Q1"
        assert cycle.id == self.cycle1.id

    def test_service_find_by_identifier_not_found(self):
        """Test CycleService.find_by_identifier returns empty for non-existent cycle."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        cycle = service.find_by_identifier("Nonexistent Cycle")

        assert not cycle

    def test_service_to_api_schema(self):
        """Test CycleService.to_api_schema converts cycle correctly."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        data = service.to_api_schema(self.cycle1)

        assert data["type"] == "Cycle"
        assert data["identifier"] == "Test Cycle Q1"
        assert data["name"] == "Test Cycle Q1"
        assert data["sequence"] == 1
        assert data["state"] == "draft"
        assert data["program"]["reference"] == f"Program/{self.program.name}"
        assert data["program"]["display"] == self.program.name
        today = date.today()
        assert data["period"]["start"] == today.isoformat()
        assert data["period"]["end"] == (today + timedelta(days=90)).isoformat()

    def test_service_to_api_schema_with_navigation(self):
        """Test CycleService.to_api_schema includes navigation links."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        data = service.to_api_schema(self.cycle2)

        assert "previousCycle" in data
        assert data["previousCycle"]["reference"] == f"Cycle/{self.cycle1.name}"
        assert data["previousCycle"]["display"] == self.cycle1.name

        assert "nextCycle" in data
        assert data["nextCycle"]["reference"] == f"Cycle/{self.cycle3.name}"
        assert data["nextCycle"]["display"] == self.cycle3.name

    def test_service_to_api_schema_no_database_ids(self):
        """Test CycleService.to_api_schema does not expose database IDs."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        data = service.to_api_schema(self.cycle1)

        # Ensure no database IDs are present
        assert "id" not in data
        assert "program_id" not in data
        assert "previous_cycle_id" not in data
        assert "next_cycle_id" not in data

        # References should use names, not IDs
        assert "Program/" in data["program"]["reference"]
        assert str(self.program.id) not in data["program"]["reference"]

    def test_service_search_basic(self):
        """Test CycleService.search finds cycles."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        records, total = service.search({})

        assert total >= 4
        assert len(records) >= 4

    def test_service_search_by_program(self):
        """Test CycleService.search filters by program name."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        records, total = service.search({"program": "Test Program"})

        assert total == 3
        assert len(records) == 3
        assert all(c.program_id == self.program for c in records)

    def test_service_search_by_state(self):
        """Test CycleService.search filters by state."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)
        records, total = service.search({"state": "draft"})

        assert total >= 2
        assert all(c.state == "draft" for c in records)

    def test_service_search_by_start_date(self):
        """Test CycleService.search filters by start date."""
        from ..services.cycle_service import CycleService

        today = date.today()
        filter_date = today + timedelta(days=91)
        filter_str = filter_date.isoformat()

        service = CycleService(self.env)

        # Greater than or equal
        records, total = service.search({"startDate": f"ge{filter_str}"})
        assert all(c.start_date >= filter_date for c in records)

        # Less than or equal
        records, total = service.search({"startDate": f"le{filter_str}"})
        assert all(c.start_date <= filter_date for c in records)

        # Exact match (treats as >=)
        today_str = today.isoformat()
        records, total = service.search({"startDate": today_str})
        assert all(c.start_date >= today for c in records)

    def test_service_search_by_end_date(self):
        """Test CycleService.search filters by end date."""
        from ..services.cycle_service import CycleService

        today = date.today()
        filter_date = today + timedelta(days=180)
        filter_str = filter_date.isoformat()

        service = CycleService(self.env)

        # Greater than or equal
        records, total = service.search({"endDate": f"ge{filter_str}"})
        assert all(c.end_date >= filter_date for c in records)

        # Less than or equal
        records, total = service.search({"endDate": f"le{filter_str}"})
        assert all(c.end_date <= filter_date for c in records)

    def test_service_search_pagination(self):
        """Test CycleService.search respects pagination parameters."""
        from ..services.cycle_service import CycleService

        service = CycleService(self.env)

        # First page
        records, total = service.search({"_count": 2, "_offset": 0})
        assert len(records) == 2
        assert total >= 4

        # Second page
        records2, total2 = service.search({"_count": 2, "_offset": 2})
        assert len(records2) <= 2
        assert total2 == total

        # Records should be different
        if len(records2) > 0:
            assert records[0].id != records2[0].id


class TestCycleAPIEndpoints(TransactionCase):
    """Test Cycle API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "4Ps",
                "journal_id": cls.env["account.journal"].search([("type", "=", "bank")], limit=1).id,
            }
        )

        # Create test cycles with dynamic dates (must be today or in the future)
        today = date.today()
        cls.cycle1 = cls.env["spp.cycle"].create(
            {
                "name": "4Ps-Q1",
                "program_id": cls.program.id,
                "sequence": 1,
                "start_date": today,
                "end_date": today + timedelta(days=90),
                "state": "approved",
                "approved_date": today,
                "approved_by": cls.env.ref("base.user_admin").id,
            }
        )

        cls.cycle2 = cls.env["spp.cycle"].create(
            {
                "name": "4Ps-Q2",
                "program_id": cls.program.id,
                "sequence": 2,
                "start_date": today + timedelta(days=91),
                "end_date": today + timedelta(days=180),
                "state": "draft",
            }
        )

        # Create another program
        cls.program2 = cls.env["spp.program"].create(
            {
                "name": "Cash Transfer",
                "journal_id": cls.env["account.journal"].search([("type", "=", "bank")], limit=1).id,
            }
        )

        cls.cycle3 = cls.env["spp.cycle"].create(
            {
                "name": "CT-01",
                "program_id": cls.program2.id,
                "sequence": 1,
                "start_date": today + timedelta(days=181),
                "end_date": today + timedelta(days=210),
                "state": "ended",
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
                "resource": "cycle",
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

    async def test_read_cycle_success(self):
        """Test GET /Cycle/{identifier} returns cycle details."""
        from unittest.mock import MagicMock

        from ..routers.cycle import read_cycle

        response = MagicMock()
        result = await read_cycle(
            identifier="4Ps-2024-Q1",
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["identifier"] == "4Ps-2024-Q1"
        assert result["name"] == "4Ps-2024-Q1"
        assert result["state"] == "approved"
        assert result["sequence"] == 1
        assert result["program"]["reference"] == "Program/4Ps"
        assert result["period"]["start"] == "2024-01-01"
        assert result["period"]["end"] == "2024-03-31"
        assert "approvedDate" in result
        assert "approvedBy" in result

        # Check ETag header was set
        assert "ETag" in response.headers

    async def test_read_cycle_url_encoded(self):
        """Test GET /Cycle/{identifier} handles URL encoding."""
        from unittest.mock import MagicMock

        from ..routers.cycle import read_cycle

        # Test with URL-encoded identifier
        encoded_identifier = quote("4Ps-2024-Q1", safe="")

        response = MagicMock()
        result = await read_cycle(
            identifier=encoded_identifier,
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        assert result["identifier"] == "4Ps-2024-Q1"

    async def test_read_cycle_not_found(self):
        """Test GET /Cycle/{identifier} returns 404 for non-existent cycle."""
        from unittest.mock import MagicMock

        from ..routers.cycle import read_cycle

        response = MagicMock()
        with self.assertRaises(HTTPException) as cm:
            await read_cycle(
                identifier="Nonexistent-Cycle",
                env=self.env,
                api_client=self.api_client,
                response=response,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_cycle_no_scope(self):
        """Test GET /Cycle/{identifier} without scope returns 403."""
        from unittest.mock import MagicMock

        from ..routers.cycle import read_cycle

        response = MagicMock()
        with self.assertRaises(HTTPException) as cm:
            await read_cycle(
                identifier="4Ps-2024-Q1",
                env=self.env,
                api_client=self.no_scope_client,
                response=response,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_cycles_success(self):
        """Test GET /Cycle returns cycle list."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
        )

        assert result.meta.total >= 3
        assert len(result.data) >= 3
        assert all(e["type"] == "Cycle" for e in result.data)

    async def test_search_cycles_with_program_filter(self):
        """Test GET /Cycle?program=4Ps filters by program."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            program="4Ps",
        )

        assert result.meta.total == 2
        assert len(result.data) == 2
        assert all(e["program"]["reference"] == "Program/4Ps" for e in result.data)

    async def test_search_cycles_with_state_filter(self):
        """Test GET /Cycle?state=approved filters by state."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            state="approved",
        )

        assert result.meta.total >= 1
        assert all(e["state"] == "approved" for e in result.data)

    async def test_search_cycles_with_start_date_filter(self):
        """Test GET /Cycle?startDate=ge2024-02-01 filters by start date."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            start_date="ge2024-02-01",
        )

        assert result.meta.total >= 2
        # All cycles should have start_date >= 2024-02-01
        for data in result.data:
            period = data.get("period", {})
            if period.get("start"):
                assert period["start"] >= "2024-02-01"

    async def test_search_cycles_with_end_date_filter(self):
        """Test GET /Cycle?endDate=le2024-06-30 filters by end date."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            end_date="le2024-06-30",
        )

        assert result.meta.total >= 2
        # All cycles should have end_date <= 2024-06-30
        for data in result.data:
            period = data.get("period", {})
            if period.get("end"):
                assert period["end"] <= "2024-06-30"

    async def test_search_cycles_with_last_updated_filter(self):
        """Test GET /Cycle?_lastUpdated=ge2024-01-01 filters by last updated."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            last_updated="ge2024-01-01",
        )

        # Should return cycles
        assert result.meta.total >= 1

    async def test_search_cycles_pagination(self):
        """Test GET /Cycle respects pagination parameters."""
        from ..routers.cycle import search_cycles

        # First page
        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            count=2,
            offset=0,
        )

        assert len(result.data) == 2
        assert result.meta.total >= 3
        assert result.meta.count == 2
        assert result.meta.offset == 0

        # Check for next link
        assert result.links.next is not None
        assert "_offset=2" in result.links.next

        # Second page
        result2 = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            count=2,
            offset=2,
        )

        assert len(result2.data) <= 2

        # Check for previous link
        assert result2.links.prev is not None
        assert "_offset=0" in result2.links.prev

        # Records should be different
        if len(result2.data) > 0:
            assert result.data[0]["identifier"] != result2.data[0]["identifier"]

    async def test_search_cycles_no_scope(self):
        """Test GET /Cycle without scope returns 403."""
        from ..routers.cycle import search_cycles

        with self.assertRaises(HTTPException) as cm:
            await search_cycles(
                env=self.env,
                api_client=self.no_scope_client,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_search_cycles_empty_result(self):
        """Test GET /Cycle with filters that match nothing."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            program="Nonexistent Program",
        )

        assert result.meta.total == 0
        assert len(result.data) == 0

    async def test_search_cycles_combined_filters(self):
        """Test GET /Cycle with multiple filters."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            program="4Ps",
            state="approved",
        )

        assert result.meta.total == 1
        assert len(result.data) == 1
        assert result.data[0]["identifier"] == "4Ps-2024-Q1"

    async def test_search_cycles_search_result_structure(self):
        """Test GET /Cycle returns proper SearchResult structure."""
        from ..routers.cycle import search_cycles

        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            count=10,
        )

        # Verify SearchResult structure
        assert isinstance(result.data, list)
        assert isinstance(result.meta.total, int)
        assert isinstance(result.meta.count, int)
        assert isinstance(result.meta.offset, int)
        assert isinstance(result.links.self, str)

        # Verify self link
        assert "/Cycle" in result.links.self

        # Verify data structure
        for cycle_data in result.data:
            assert cycle_data["type"] == "Cycle"
            assert "identifier" in cycle_data

    async def test_read_cycle_no_database_ids_exposed(self):
        """Test GET /Cycle/{identifier} does not expose database IDs."""
        from unittest.mock import MagicMock

        from ..routers.cycle import read_cycle

        response = MagicMock()
        result = await read_cycle(
            identifier="4Ps-2024-Q1",
            env=self.env,
            api_client=self.api_client,
            response=response,
        )

        # Ensure no database IDs are present
        assert "id" not in result
        assert "program_id" not in result
        assert "approved_by" not in result  # Should be approvedBy with user name

        # Check that references use names, not IDs
        assert "Program/" in result["program"]["reference"]
        assert str(self.program.id) not in result["program"]["reference"]

    async def test_search_cycles_max_count_limit(self):
        """Test GET /Cycle respects max count limit of 100."""
        from ..routers.cycle import search_cycles

        # Request with count > 100 should be capped
        result = await search_cycles(
            env=self.env,
            api_client=self.api_client,
            count=100,  # At the limit
        )

        # Should succeed
        assert result.meta.total >= 0
        assert len(result.data) <= 100
