# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Data API endpoints."""

from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestDataAPISchemas(TransactionCase):
    """Test Data API schema validation."""

    def test_data_value_input_schema(self):
        """Test DataValueInput schema validates correctly."""
        from ..schemas.data import DataValueInput

        value_input = DataValueInput(
            variable="school_attendance",
            subject_external_id="EDU-2024-001",
            value=0.95,
            period_key="2024-12",
        )
        assert value_input.variable == "school_attendance"
        assert value_input.subject_external_id == "EDU-2024-001"
        assert value_input.value == 0.95
        assert value_input.period_key == "2024-12"

    def test_data_value_input_with_metadata(self):
        """Test DataValueInput with optional metadata."""
        from ..schemas.data import DataValueInput

        value_input = DataValueInput(
            variable="vaccination_status",
            subject_external_id="urn:gov:health:patient|12345",
            value=True,
            period_key="current",
            as_of=datetime(2024, 12, 1, 12, 0, 0),
            metadata={"source": "clinic_a", "confidence": 0.99},
        )
        assert value_input.metadata["source"] == "clinic_a"
        assert value_input.as_of == datetime(2024, 12, 1, 12, 0, 0)

    def test_data_push_request_schema(self):
        """Test DataPushRequest schema validates correctly."""
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
            ),
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-002",
                value=0.88,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )
        assert request.provider_code == "education_ministry"
        assert len(request.values) == 2

    def test_data_push_response_schema(self):
        """Test DataPushResponse schema validates correctly."""
        from ..schemas.data import DataPushError, DataPushResponse

        errors = [
            DataPushError(
                index=1,
                subject_external_id="EDU-999",
                variable="school_attendance",
                error="Subject not found",
            )
        ]
        response = DataPushResponse(
            success=False,
            processed=2,
            inserted=1,
            updated=0,
            errors=errors,
        )
        assert response.success is False
        assert response.processed == 2
        assert len(response.errors) == 1

    def test_data_pull_response_schema(self):
        """Test DataPullResponse schema validates correctly."""
        from ..schemas.data import DataPullResponse, DataValueOutput

        items = [
            DataValueOutput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
                period_key="current",
                recorded_at=datetime.now(),
                is_stale=False,
                source_type="external",
            )
        ]
        response = DataPullResponse(total=1, items=items)
        assert response.total == 1
        assert len(response.items) == 1

    def test_data_invalidate_request_schema(self):
        """Test DataInvalidateRequest schema validates correctly."""
        from ..schemas.data import DataInvalidateRequest

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="school_attendance",
            subject_external_ids=["EDU-001", "EDU-002"],
            period_key="2024-12",
        )
        assert request.provider_code == "education_ministry"
        assert len(request.subject_external_ids) == 2

    def test_data_invalidate_response_schema(self):
        """Test DataInvalidateResponse schema validates correctly."""
        from ..schemas.data import DataInvalidateResponse

        response = DataInvalidateResponse(success=True, invalidated=5)
        assert response.success is True
        assert response.invalidated == 5

    def test_variable_info_schema(self):
        """Test VariableInfo schema validates correctly."""
        from ..schemas.data import VariableInfo

        var_info = VariableInfo(
            name="School Attendance Rate",
            cel_accessor="school_attendance",
            description="Student attendance rate",
            value_type="number",
            source_type="external",
            cache_strategy="ttl",
            period_granularity="monthly",
            provider_code="education_ministry",
        )
        assert var_info.cel_accessor == "school_attendance"
        assert var_info.value_type == "number"

    def test_variables_list_response_schema(self):
        """Test VariablesListResponse schema validates correctly."""
        from ..schemas.data import VariableInfo, VariablesListResponse

        items = [
            VariableInfo(
                name="Variable 1",
                cel_accessor="var1",
                value_type="number",
                source_type="external",
                cache_strategy="ttl",
            ),
            VariableInfo(
                name="Variable 2",
                cel_accessor="var2",
                value_type="boolean",
                source_type="computed",
                cache_strategy="none",
            ),
        ]
        response = VariablesListResponse(total=2, items=items)
        assert response.total == 2
        assert len(response.items) == 2


class TestDataAPIEndpoints(TransactionCase):
    """Test Data API router endpoints."""

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

        # Lookup ID type vocabulary
        id_type_vocab = cls.env.ref(
            "spp_vocabulary.vocab_id_type",
            raise_if_not_found=False,
        )
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].search(
                [("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1
            )

        # Create a custom ID type for student ID testing (as local code for testing)
        cls.id_type_student = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "student_id",
                "display": "Student ID",
                "definition": "Educational institution student identifier",
                "is_local": True,
            }
        )

        # Create test partners (subjects)
        cls.partner1 = cls.env["res.partner"].create(
            {
                "name": "Test Student 1",
                "ref": "EDU-001",
            }
        )
        cls.partner2 = cls.env["res.partner"].create(
            {
                "name": "Test Student 2",
                "ref": "EDU-002",
            }
        )
        cls.partner3 = cls.env["res.partner"].create(
            {
                "name": "Test Student 3",
                "ref": "HEALTH-001",
            }
        )

        # Create registry IDs for namespace URI testing
        cls.reg_id1 = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner1.id,
                "id_type_id": cls.id_type_student.id,
                "value": "12345",
            }
        )

        # Create data provider
        cls.provider = cls.env["spp.data.provider"].create(
            {
                "name": "Education Ministry",
                "code": "education_ministry",
                "active": True,
                "default_ttl_seconds": 86400,
                "id_mapping_fields": "external_id,ref",
            }
        )

        # Create another provider for access control testing
        cls.other_provider = cls.env["spp.data.provider"].create(
            {
                "name": "Health Ministry",
                "code": "health_ministry",
                "active": True,
                "default_ttl_seconds": 3600,
            }
        )

        # Create variables
        cls.variable1 = cls.env["spp.cel.variable"].create(
            {
                "name": "School Attendance",
                "cel_accessor": "school_attendance",
                "source_type": "external",
                "external_provider_id": cls.provider.id,
                "value_type": "number",
                "cache_strategy": "ttl",
                "period_granularity": "monthly",
            }
        )

        cls.variable2 = cls.env["spp.cel.variable"].create(
            {
                "name": "Vaccination Status",
                "cel_accessor": "vaccination_status",
                "source_type": "external",
                "external_provider_id": cls.other_provider.id,
                "value_type": "boolean",
                "cache_strategy": "manual",
            }
        )

        cls.variable3 = cls.env["spp.cel.variable"].create(
            {
                "name": "Computed Variable",
                "cel_accessor": "computed_var",
                "source_type": "computed",
                "value_type": "number",
                "cache_strategy": "none",
            }
        )

        # Create API client with data scopes
        cls.api_partner = cls.env["res.partner"].create({"name": "API Partner"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.api_partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        # Add data:read scope
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "data",
                "action": "read",
            }
        )
        # Add data:write scope
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "data",
                "action": "all",
            }
        )

        # Create client without scopes
        cls.no_scope_partner = cls.env["res.partner"].create({"name": "No Scope Partner"})
        cls.no_scope_client = cls.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": cls.no_scope_partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )

        # Create client with only read scope
        cls.read_only_partner = cls.env["res.partner"].create({"name": "Read Only Partner"})
        cls.read_only_client = cls.env["spp.api.client"].create(
            {
                "name": "Read Only Client",
                "partner_id": cls.read_only_partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.read_only_client.id,
                "resource": "data",
                "action": "read",
            }
        )

    # ═══════════════════════════════════════════════════════════════════════
    # PUSH ENDPOINT TESTS
    # ═══════════════════════════════════════════════════════════════════════

    async def test_push_values_success(self):
        """Test POST /Data/push with valid data."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
                period_key="2024-12",
            ),
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-002",
                value=0.88,
                period_key="2024-12",
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is True
        assert result.processed == 2
        assert result.inserted >= 0
        assert len(result.errors) == 0

        # Verify values were stored
        DataValue = self.env["spp.data.value"]
        stored = DataValue.search(
            [
                ("variable_name", "=", "school_attendance"),
                ("subject_id", "in", [self.partner1.id, self.partner2.id]),
            ]
        )
        assert len(stored) == 2

    async def test_push_values_with_namespace_uri(self):
        """Test POST /Data/push with namespace URI format external ID."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="urn:openspp:vocab:id-type#student_id|12345",
                value=0.92,
                period_key="2024-12",
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is True
        assert result.processed == 1
        assert len(result.errors) == 0

    async def test_push_values_subject_not_found(self):
        """Test POST /Data/push with non-existent subject."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="NONEXISTENT-999",
                value=0.95,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is False
        assert result.processed == 0
        assert len(result.errors) == 1
        assert "Subject not found" in result.errors[0].error

    async def test_push_values_variable_not_found(self):
        """Test POST /Data/push with non-existent variable."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="nonexistent_variable",
                subject_external_id="EDU-001",
                value=0.95,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is False
        assert result.processed == 0
        assert len(result.errors) == 1
        assert "Variable not found" in result.errors[0].error

    async def test_push_values_wrong_provider(self):
        """Test POST /Data/push with variable from different provider."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        # Try to push vaccination_status through education_ministry
        values = [
            DataValueInput(
                variable="vaccination_status",
                subject_external_id="EDU-001",
                value=True,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is False
        assert len(result.errors) == 1
        assert "not owned by provider" in result.errors[0].error

    async def test_push_values_provider_not_found(self):
        """Test POST /Data/push with non-existent provider."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
            ),
        ]
        request = DataPushRequest(
            provider_code="nonexistent_provider",
            values=values,
        )

        with self.assertRaises(HTTPException) as cm:
            await push_values(
                request=request,
                env=self.env,
                api_client=self.api_client,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND
        assert "Provider not found" in cm.exception.detail

    async def test_push_values_no_write_scope(self):
        """Test POST /Data/push without data:write scope returns 403."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        with self.assertRaises(HTTPException) as cm:
            await push_values(
                request=request,
                env=self.env,
                api_client=self.read_only_client,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
        assert "data:write" in cm.exception.detail

    async def test_push_values_partial_success(self):
        """Test POST /Data/push with mix of valid and invalid values."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
            ),
            DataValueInput(
                variable="school_attendance",
                subject_external_id="NONEXISTENT-999",
                value=0.88,
            ),
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-002",
                value=0.90,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is False
        assert result.processed == 2  # Only valid ones processed
        assert len(result.errors) == 1  # One error
        assert result.errors[0].index == 1  # Second item failed

    async def test_push_values_with_as_of(self):
        """Test POST /Data/push with as_of timestamp."""
        from ..routers.data import push_values
        from ..schemas.data import DataPushRequest, DataValueInput

        as_of_time = datetime(2024, 12, 1, 12, 0, 0)
        values = [
            DataValueInput(
                variable="school_attendance",
                subject_external_id="EDU-001",
                value=0.95,
                as_of=as_of_time,
            ),
        ]
        request = DataPushRequest(
            provider_code="education_ministry",
            values=values,
        )

        result = await push_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is True

        # Verify as_of was stored
        DataValue = self.env["spp.data.value"]
        stored = DataValue.search(
            [
                ("variable_name", "=", "school_attendance"),
                ("subject_id", "=", self.partner1.id),
            ],
            limit=1,
        )
        assert stored.as_of == as_of_time

    # ═══════════════════════════════════════════════════════════════════════
    # PULL ENDPOINT TESTS
    # ═══════════════════════════════════════════════════════════════════════

    async def test_pull_values_success(self):
        """Test GET /Data/pull returns cached values."""
        from ..routers.data import pull_values

        # First push some values
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "current",
                    "value_json": {"value": 0.95},
                    "value_type": "number",
                    "source_type": "external",
                    "provider": "education_ministry",
                    "ttl_seconds": 3600,
                }
            ]
        )

        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="EDU-001",
            period_key="current",
            _count=100,
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].variable == "school_attendance"
        assert result.items[0].value == 0.95
        assert result.items[0].subject_external_id == "EDU-001"

    async def test_pull_values_multiple_subjects(self):
        """Test GET /Data/pull with multiple subjects."""
        from ..routers.data import pull_values

        # Push values for multiple subjects
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "current",
                    "value_json": {"value": 0.95},
                    "source_type": "external",
                },
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner2.id,
                    "period_key": "current",
                    "value_json": {"value": 0.88},
                    "source_type": "external",
                },
            ]
        )

        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="EDU-001,EDU-002",
            period_key="current",
            _count=100,
        )

        assert result.total == 2
        assert len(result.items) == 2

    async def test_pull_values_with_namespace_uri(self):
        """Test GET /Data/pull with namespace URI format."""
        from ..routers.data import pull_values

        # Push value
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "current",
                    "value_json": {"value": 0.95},
                    "source_type": "external",
                }
            ]
        )

        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="urn:openspp:vocab:id-type#student_id|12345",
            period_key="current",
            _count=100,
        )

        assert result.total == 1
        assert len(result.items) == 1

    async def test_pull_values_no_results(self):
        """Test GET /Data/pull with a valid pullable variable but no cached rows."""
        from ..routers.data import pull_values

        # school_attendance is an ordinary external-provider variable (pullable);
        # no values were cached for it in this test, so the result is empty.
        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="EDU-001",
            period_key="current",
            _count=100,
        )

        assert result.total == 0
        assert len(result.items) == 0

    async def test_pull_values_subject_not_found(self):
        """Test GET /Data/pull with non-existent subject returns empty."""
        from ..routers.data import pull_values

        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="NONEXISTENT-999",
            period_key="current",
            _count=100,
        )

        assert result.total == 0
        assert len(result.items) == 0

    async def test_pull_values_no_subject_ids(self):
        """Test GET /Data/pull without subject IDs returns 400."""
        from ..routers.data import pull_values

        with self.assertRaises(HTTPException) as cm:
            await pull_values(
                env=self.env,
                api_client=self.api_client,
                variable="school_attendance",
                subject_external_ids="",
                period_key="current",
                _count=100,
            )

        assert cm.exception.status_code == status.HTTP_400_BAD_REQUEST
        assert "at least one" in cm.exception.detail.lower()

    async def test_pull_values_no_read_scope(self):
        """Test GET /Data/pull without data:read scope returns 403."""
        from ..routers.data import pull_values

        with self.assertRaises(HTTPException) as cm:
            await pull_values(
                env=self.env,
                api_client=self.no_scope_client,
                variable="school_attendance",
                subject_external_ids="EDU-001",
                period_key="current",
                _count=100,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
        assert "data:read" in cm.exception.detail

    async def test_pull_values_with_period_key(self):
        """Test GET /Data/pull with specific period key."""
        from ..routers.data import pull_values

        # Push values for different periods
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "2024-12",
                    "value_json": {"value": 0.95},
                    "source_type": "external",
                },
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "2024-11",
                    "value_json": {"value": 0.88},
                    "source_type": "external",
                },
            ]
        )

        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="EDU-001",
            period_key="2024-12",
            _count=100,
        )

        assert result.total == 1
        assert result.items[0].value == 0.95
        assert result.items[0].period_key == "2024-12"

    async def test_pull_values_stale_flag(self):
        """Test GET /Data/pull includes is_stale flag."""
        from ..routers.data import pull_values

        # Push value that's already expired
        DataValue = self.env["spp.data.value"]
        past_time = datetime.now() - timedelta(hours=1)
        DataValue.create(
            {
                "variable_name": "school_attendance",
                "subject_id": self.partner1.id,
                "period_key": "current",
                "value_json": {"value": 0.95},
                "value_type": "number",
                "source_type": "external",
                "expires_at": past_time,
            }
        )

        # Note: pull_values excludes expired values by default
        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids="EDU-001",
            period_key="current",
            _count=100,
        )

        # Should not return expired values
        assert result.total == 0

    async def test_pull_values_pagination(self):
        """Test GET /Data/pull respects _count parameter."""
        from ..routers.data import pull_values

        # Create many partners and values
        partners = []
        values_to_push = []
        for i in range(20):
            partner = self.env["res.partner"].create(
                {
                    "name": f"Test Student {i}",
                    "ref": f"EDU-{100 + i}",
                }
            )
            partners.append(partner)
            values_to_push.append(
                {
                    "variable_name": "school_attendance",
                    "subject_id": partner.id,
                    "period_key": "current",
                    "value_json": {"value": 0.9 + i * 0.01},
                    "source_type": "external",
                }
            )

        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(values_to_push)

        # Pull with limit
        external_ids = ",".join([f"EDU-{100 + i}" for i in range(20)])
        result = await pull_values(
            env=self.env,
            api_client=self.api_client,
            variable="school_attendance",
            subject_external_ids=external_ids,
            period_key="current",
            _count=10,
        )

        assert result.total <= 10
        assert len(result.items) <= 10

    # ═══════════════════════════════════════════════════════════════════════
    # INVALIDATE ENDPOINT TESTS
    # ═══════════════════════════════════════════════════════════════════════

    async def test_invalidate_values_success(self):
        """Test POST /Data/invalidate marks values as expired."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        # Push some values first
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "current",
                    "value_json": {"value": 0.95},
                    "source_type": "external",
                    "provider": "education_ministry",
                }
            ]
        )

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="school_attendance",
            subject_external_ids=["EDU-001"],
        )

        result = await invalidate_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is True
        assert result.invalidated == 1

        # Verify value is now stale
        stored = DataValue.search(
            [
                ("variable_name", "=", "school_attendance"),
                ("subject_id", "=", self.partner1.id),
            ],
            limit=1,
        )
        assert stored.is_stale is True

    async def test_invalidate_values_all_subjects(self):
        """Test POST /Data/invalidate without subject IDs invalidates all."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        # Push values for multiple subjects
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "current",
                    "value_json": {"value": 0.95},
                    "provider": "education_ministry",
                },
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner2.id,
                    "period_key": "current",
                    "value_json": {"value": 0.88},
                    "provider": "education_ministry",
                },
            ]
        )

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="school_attendance",
            subject_external_ids=None,  # Invalidate all
        )

        result = await invalidate_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is True
        assert result.invalidated >= 2

    async def test_invalidate_values_with_period_key(self):
        """Test POST /Data/invalidate with specific period key."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        # Push values for different periods
        DataValue = self.env["spp.data.value"]
        DataValue.upsert_values(
            [
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "2024-12",
                    "value_json": {"value": 0.95},
                    "provider": "education_ministry",
                },
                {
                    "variable_name": "school_attendance",
                    "subject_id": self.partner1.id,
                    "period_key": "2024-11",
                    "value_json": {"value": 0.88},
                    "provider": "education_ministry",
                },
            ]
        )

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="school_attendance",
            subject_external_ids=["EDU-001"],
            period_key="2024-12",
        )

        result = await invalidate_values(
            request=request,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.success is True
        assert result.invalidated == 1

        # Verify only 2024-12 is stale
        stored_dec = DataValue.search(
            [
                ("variable_name", "=", "school_attendance"),
                ("subject_id", "=", self.partner1.id),
                ("period_key", "=", "2024-12"),
            ],
            limit=1,
        )
        stored_nov = DataValue.search(
            [
                ("variable_name", "=", "school_attendance"),
                ("subject_id", "=", self.partner1.id),
                ("period_key", "=", "2024-11"),
            ],
            limit=1,
        )
        assert stored_dec.is_stale is True
        assert stored_nov.is_stale is False

    async def test_invalidate_values_provider_not_found(self):
        """Test POST /Data/invalidate with non-existent provider."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        request = DataInvalidateRequest(
            provider_code="nonexistent_provider",
            variable="school_attendance",
        )

        with self.assertRaises(HTTPException) as cm:
            await invalidate_values(
                request=request,
                env=self.env,
                api_client=self.api_client,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND
        assert "Provider not found" in cm.exception.detail

    async def test_invalidate_values_variable_not_found(self):
        """Test POST /Data/invalidate with non-existent variable."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="nonexistent_variable",
        )

        with self.assertRaises(HTTPException) as cm:
            await invalidate_values(
                request=request,
                env=self.env,
                api_client=self.api_client,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND
        assert "Variable not found" in cm.exception.detail

    async def test_invalidate_values_wrong_provider(self):
        """Test POST /Data/invalidate with variable from different provider."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="vaccination_status",  # Belongs to health_ministry
        )

        with self.assertRaises(HTTPException) as cm:
            await invalidate_values(
                request=request,
                env=self.env,
                api_client=self.api_client,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
        assert "does not belong to provider" in cm.exception.detail

    async def test_invalidate_values_no_write_scope(self):
        """Test POST /Data/invalidate without data:write scope returns 403."""
        from ..routers.data import invalidate_values
        from ..schemas.data import DataInvalidateRequest

        request = DataInvalidateRequest(
            provider_code="education_ministry",
            variable="school_attendance",
        )

        with self.assertRaises(HTTPException) as cm:
            await invalidate_values(
                request=request,
                env=self.env,
                api_client=self.read_only_client,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
        assert "data:write" in cm.exception.detail

    # ═══════════════════════════════════════════════════════════════════════
    # VARIABLES ENDPOINT TESTS
    # ═══════════════════════════════════════════════════════════════════════

    async def test_list_variables_success(self):
        """Test GET /Data/variables returns variable list."""
        from ..routers.data import list_variables

        result = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code=None,
            source_type=None,
            _count=100,
            _last_id=None,
        )

        # Only ordinary external-provider variables are exchanged via the data
        # API; computed/scoring/aggregate variables are no longer enumerated.
        accessors = [v.cel_accessor for v in result.items]
        assert "school_attendance" in accessors
        assert "vaccination_status" in accessors
        assert "computed_var" not in accessors
        assert all(v.source_type == "external" for v in result.items)

    async def test_list_variables_filter_by_provider(self):
        """Test GET /Data/variables?provider_code filters by provider."""
        from ..routers.data import list_variables

        result = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code="education_ministry",
            source_type=None,
            _count=100,
            _last_id=None,
        )

        # Should only return education_ministry variables
        for var in result.items:
            assert var.provider_code == "education_ministry" or var.provider_code is None

    async def test_list_variables_filter_by_source_type(self):
        """Test GET /Data/variables?source_type filters by source type."""
        from ..routers.data import list_variables

        result = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code=None,
            source_type="external",
            _count=100,
            _last_id=None,
        )

        # Should only return external source variables
        for var in result.items:
            assert var.source_type == "external"

    async def test_list_variables_nonexistent_provider(self):
        """Test GET /Data/variables with non-existent provider returns empty."""
        from ..routers.data import list_variables

        result = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code="nonexistent_provider",
            source_type=None,
            _count=100,
            _last_id=None,
        )

        assert result.total == 0
        assert len(result.items) == 0

    async def test_list_variables_pagination(self):
        """Test GET /Data/variables respects _count and _last_id."""
        from ..routers.data import list_variables

        # Create many variables
        for i in range(10):
            self.env["spp.cel.variable"].create(
                {
                    "name": f"Test Variable {i}",
                    "cel_accessor": f"test_var_{i}",
                    "source_type": "external",
                    "external_provider_id": self.provider.id,
                    "value_type": "number",
                }
            )

        # Get first page
        result1 = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code=None,
            source_type=None,
            _count=5,
            _last_id=None,
        )

        assert len(result1.items) == 5

        # Get second page
        # The endpoint expects the ID, not the accessor
        # Search for the last variable to get its ID
        last_var = self.env["spp.cel.variable"].search([("cel_accessor", "=", result1.items[-1].cel_accessor)], limit=1)

        result2 = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code=None,
            source_type=None,
            _count=5,
            _last_id=last_var.id,
        )

        # Items should be different
        if len(result2.items) > 0:
            assert result2.items[0].cel_accessor != result1.items[0].cel_accessor

    async def test_list_variables_no_read_scope(self):
        """Test GET /Data/variables without data:read scope returns 403."""
        from ..routers.data import list_variables

        with self.assertRaises(HTTPException) as cm:
            await list_variables(
                env=self.env,
                api_client=self.no_scope_client,
                provider_code=None,
                source_type=None,
                _count=100,
                _last_id=None,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
        assert "data:read" in cm.exception.detail

    async def test_list_variables_includes_metadata(self):
        """Test GET /Data/variables includes complete metadata."""
        from ..routers.data import list_variables

        result = await list_variables(
            env=self.env,
            api_client=self.api_client,
            provider_code="education_ministry",
            source_type=None,
            _count=100,
            _last_id=None,
        )

        # Find our test variable
        var = next((v for v in result.items if v.cel_accessor == "school_attendance"), None)
        assert var is not None
        assert var.name == "School Attendance"
        assert var.value_type == "number"
        assert var.source_type == "external"
        assert var.cache_strategy == "ttl"
        assert var.period_granularity == "monthly"
        assert var.provider_code == "education_ministry"

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER FUNCTION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_resolve_subject_id_with_external_id(self):
        """Test _resolve_subject_id with external_id field."""
        from ..routers.data import _resolve_subject_id

        subject_id = _resolve_subject_id(self.env, "EDU-001")
        assert subject_id == self.partner1.id

    def test_resolve_subject_id_with_ref(self):
        """Test _resolve_subject_id with ref field."""
        from ..routers.data import _resolve_subject_id

        subject_id = _resolve_subject_id(self.env, "HEALTH-001")
        assert subject_id == self.partner3.id

    def test_resolve_subject_id_with_namespace_uri(self):
        """Test _resolve_subject_id with namespace URI format."""
        from ..routers.data import _resolve_subject_id

        # Using vocabulary system, namespace is from the ID type vocabulary
        subject_id = _resolve_subject_id(self.env, "urn:openspp:vocab:id-type#student_id|12345")
        assert subject_id == self.partner1.id

    def test_resolve_subject_id_with_provider_mapping(self):
        """Test _resolve_subject_id with provider ID mapping fields."""
        from ..routers.data import _resolve_subject_id

        subject_id = _resolve_subject_id(self.env, "EDU-001", self.provider)
        assert subject_id == self.partner1.id

    def test_resolve_subject_id_not_found(self):
        """Test _resolve_subject_id returns None for non-existent ID."""
        from ..routers.data import _resolve_subject_id

        subject_id = _resolve_subject_id(self.env, "NONEXISTENT-999")
        assert subject_id is None

    def test_get_external_id_with_registry_id(self):
        """Test _get_external_id with registry ID."""
        from ..routers.data import _get_external_id

        external_id = _get_external_id(self.env, self.partner1.id)
        # Using vocabulary system, namespace is from the ID type vocabulary
        assert external_id == "urn:openspp:vocab:id-type#student_id|12345"

    def test_get_external_id_with_external_id_field(self):
        """Test _get_external_id falls back to external_id field."""
        from ..routers.data import _get_external_id

        external_id = _get_external_id(self.env, self.partner2.id)
        # Should fall back to external_id or ref
        assert external_id in ["EDU-002", self.partner2.ref, str(self.partner2.id)]

    def test_get_external_id_not_found(self):
        """Test _get_external_id returns ID string for non-existent partner."""
        from ..routers.data import _get_external_id

        external_id = _get_external_id(self.env, 99999)
        assert external_id is None

    def test_validate_provider_access_success(self):
        """Test _validate_provider_access with valid provider and scope."""
        from ..routers.data import _validate_provider_access

        provider = _validate_provider_access(self.env, self.api_client, "education_ministry", "school_attendance")
        assert provider.id == self.provider.id

    def test_validate_provider_access_no_write_scope(self):
        """Test _validate_provider_access without data:write scope."""
        from ..routers.data import _validate_provider_access

        with self.assertRaises(HTTPException) as cm:
            _validate_provider_access(self.env, self.read_only_client, "education_ministry")

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    def test_validate_provider_access_provider_not_found(self):
        """Test _validate_provider_access with non-existent provider."""
        from ..routers.data import _validate_provider_access

        with self.assertRaises(HTTPException) as cm:
            _validate_provider_access(self.env, self.api_client, "nonexistent_provider")

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    def test_validate_provider_access_wrong_variable(self):
        """Test _validate_provider_access with variable from different provider."""
        from ..routers.data import _validate_provider_access

        with self.assertRaises(HTTPException) as cm:
            _validate_provider_access(self.env, self.api_client, "education_ministry", "vaccination_status")

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN
        assert "does not belong to provider" in cm.exception.detail
