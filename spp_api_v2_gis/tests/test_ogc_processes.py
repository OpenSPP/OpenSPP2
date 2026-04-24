# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OGC API - Processes endpoints.

Covers process registry, schemas, job model, and HTTP integration.
"""

import json
import logging
import os
import unittest

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase

_logger = logging.getLogger(__name__)

API_BASE = "/api/v2/spp"
OGC_BASE = f"{API_BASE}/gis/ogc"


class TestProcessRegistry(TransactionCase):
    """Unit tests for ProcessRegistry service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test indicator data
        Category = cls.env["spp.metric.category"]
        cls.category = Category.search([("code", "=", "test_proc_category")], limit=1)
        if not cls.category:
            cls.category = Category.create(
                {
                    "name": "Test Process Category",
                    "code": "test_proc_category",
                    "sequence": 50,
                }
            )

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_proc_var",
                "cel_accessor": "test_proc_accessor",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        cls.indicator = cls.env["spp.statistic"].create(
            {
                "name": "proc_test_stat",
                "label": "Process Test Stat",
                "description": "A test statistic for process tests",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "unit": "people",
                "is_published_gis": True,
                "category_id": cls.category.id,
            }
        )

    def test_list_processes_returns_two_processes(self):
        """Registry returns spatial-statistics and proximity-statistics."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        processes = registry.list_processes()

        self.assertEqual(len(processes), 2)
        ids = {p["id"] for p in processes}
        self.assertEqual(ids, {"spatial-statistics", "proximity-statistics"})

    def test_get_process_spatial_statistics(self):
        """spatial-statistics description includes inputs and outputs."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("spatial-statistics")

        self.assertIsNotNone(desc)
        self.assertEqual(desc["id"], "spatial-statistics")
        self.assertIn("geometry", desc["inputs"])
        self.assertIn("variables", desc["inputs"])
        self.assertIn("filters", desc["inputs"])
        self.assertIn("result", desc["outputs"])

    def test_get_process_proximity_statistics(self):
        """proximity-statistics description includes inputs and outputs."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("proximity-statistics")

        self.assertIsNotNone(desc)
        self.assertEqual(desc["id"], "proximity-statistics")
        self.assertIn("reference_points", desc["inputs"])
        self.assertIn("radius_km", desc["inputs"])
        self.assertIn("relation", desc["inputs"])

    def test_get_process_unknown_returns_none(self):
        """Unknown process ID returns None."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        self.assertIsNone(registry.get_process("nonexistent"))

    def test_variables_enum_reflects_indicators(self):
        """Variables input enum includes published spp.statistic names."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("spatial-statistics")

        variables_input = desc["inputs"]["variables"]
        schema = variables_input["schema"]
        items = schema["items"]

        # Should have enum with at least our test indicator
        self.assertIn("enum", items)
        self.assertIn("proc_test_stat", items["enum"])

    def test_x_openspp_statistics_extension(self):
        """Process description includes x-openspp-statistics for UI metadata."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("spatial-statistics")

        variables_input = desc["inputs"]["variables"]
        self.assertIn("x-openspp-statistics", variables_input)

        categories = variables_input["x-openspp-statistics"]["categories"]
        self.assertIsInstance(categories, list)
        self.assertGreater(len(categories), 0)

        # Find our test category
        test_cats = [c for c in categories if c["code"] == "test_proc_category"]
        self.assertEqual(len(test_cats), 1)
        self.assertEqual(test_cats[0]["name"], "Test Process Category")

        # Category should contain our indicator
        stat_names = [s["name"] for s in test_cats[0]["statistics"]]
        self.assertIn("proc_test_stat", stat_names)

    def test_get_statistics_metadata(self):
        """get_statistics_metadata returns variable names and categories."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        variable_names, categories = registry.get_statistics_metadata()

        self.assertIn("proc_test_stat", variable_names)
        self.assertIsInstance(categories, list)
        self.assertGreater(len(categories), 0)


class TestProcessSchemas(TransactionCase):
    """Unit tests for Pydantic process schemas."""

    def test_process_summary_creation(self):
        """ProcessSummary validates correctly."""
        from ..schemas.processes import ProcessSummary

        summary = ProcessSummary(
            id="test",
            title="Test Process",
            description="A test",
            version="1.0.0",
            jobControlOptions=["sync-execute"],
        )
        self.assertEqual(summary.id, "test")
        self.assertEqual(summary.jobControlOptions, ["sync-execute"])

    def test_execute_request_minimal(self):
        """ExecuteRequest works with just inputs."""
        from ..schemas.processes import ExecuteRequest

        req = ExecuteRequest(inputs={"geometry": {"type": "Polygon", "coordinates": []}})
        self.assertIsNotNone(req.inputs)
        self.assertIsNone(req.outputs)
        self.assertIsNone(req.response)

    def test_status_info_serialization(self):
        """StatusInfo serializes with camelCase aliases."""
        from ..schemas.processes import StatusInfo

        info = StatusInfo(
            jobID="abc-123",
            processID="spatial-statistics",
            status="accepted",
        )
        dumped = info.model_dump(by_alias=True)
        self.assertIn("jobID", dumped)
        self.assertIn("processID", dumped)
        self.assertEqual(dumped["jobID"], "abc-123")

    def test_job_list_creation(self):
        """JobList contains StatusInfo objects."""
        from ..schemas.processes import JobList, StatusInfo

        job_list = JobList(
            jobs=[
                StatusInfo(jobID="j1", status="accepted"),
                StatusInfo(jobID="j2", status="running"),
            ]
        )
        self.assertEqual(len(job_list.jobs), 2)


class TestGisProcessJobModel(TransactionCase):
    """Unit tests for spp.gis.process.job Odoo model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test API client
        partner = cls.env["res.partner"].create({"name": "Test Process Client"})
        org_type = cls.env.ref("spp_consent.org_type_government", raise_if_not_found=False)
        if not org_type:
            org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not org_type:
            org_type = cls.env["spp.consent.org.type"].create({"name": "Government", "code": "government"})

        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Process Test Client",
                "partner_id": partner.id,
                "organization_type_id": org_type.id,
            }
        )

    def _create_job(self, **kwargs):
        """Helper to create a job record."""
        import uuid

        vals = {
            "job_id": str(uuid.uuid4()),
            "process_id": "spatial-statistics",
            "client_id": self.api_client.id,
            "inputs": {"geometry": {"type": "Polygon", "coordinates": []}},
        }
        vals.update(kwargs)
        return self.env["spp.gis.process.job"].create(vals)

    def test_create_job_defaults(self):
        """New job has default status=accepted and progress=0."""
        job = self._create_job()
        self.assertEqual(job.status, "accepted")
        self.assertEqual(job.progress, 0)
        self.assertFalse(job.started_at)
        self.assertFalse(job.finished_at)

    def test_dismiss_accepted_job(self):
        """Dismissing an accepted job sets status to dismissed."""
        job = self._create_job()
        job.dismiss()
        self.assertEqual(job.status, "dismissed")
        self.assertTrue(job.finished_at)

    def test_dismiss_running_job_raises(self):
        """Dismissing a running job raises UserError."""
        from odoo.exceptions import UserError

        job = self._create_job()
        job.status = "running"

        with self.assertRaises(UserError):
            job.dismiss()

    def test_dismiss_successful_job_deletes(self):
        """Dismissing a terminal job deletes the record."""
        job = self._create_job()
        job.status = "successful"
        job_id = job.id

        job.dismiss()

        # Record should be deleted
        self.assertFalse(self.env["spp.gis.process.job"].browse(job_id).exists())

    def test_dismiss_failed_job_deletes(self):
        """Dismissing a failed job deletes the record."""
        job = self._create_job()
        job.status = "failed"
        job_id = job.id

        job.dismiss()
        self.assertFalse(self.env["spp.gis.process.job"].browse(job_id).exists())

    def test_cron_cleanup_stale_jobs(self):
        """Cron marks stale accepted/running jobs as failed."""
        from datetime import datetime, timedelta

        job = self._create_job()
        # Backdate the create_date to 2 hours ago
        two_hours_ago = datetime.now() - timedelta(hours=2)
        self.env.cr.execute(
            "UPDATE spp_gis_process_job SET create_date = %s WHERE id = %s",
            (two_hours_ago, job.id),
        )
        job.invalidate_recordset()

        self.env["spp.gis.process.job"].cron_cleanup_jobs()

        job.invalidate_recordset()
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.message, "Job timed out (stale)")

    def test_cron_cleanup_old_jobs(self):
        """Cron deletes jobs older than retention period."""
        from datetime import datetime, timedelta

        job = self._create_job()
        job.status = "successful"
        # Backdate to 10 days ago
        ten_days_ago = datetime.now() - timedelta(days=10)
        self.env.cr.execute(
            "UPDATE spp_gis_process_job SET create_date = %s WHERE id = %s",
            (ten_days_ago, job.id),
        )
        job.invalidate_recordset()
        job_id = job.id

        self.env["spp.gis.process.job"].cron_cleanup_jobs()

        self.assertFalse(self.env["spp.gis.process.job"].browse(job_id).exists())

    def test_execute_process_unknown_process(self):
        """execute_process with unknown process_id sets status to failed."""
        job = self._create_job(process_id="nonexistent-process")
        job.execute_process()

        self.assertEqual(job.status, "failed")
        self.assertIn("Process execution failed", job.message)


class TestOGCConformanceUpdated(TransactionCase):
    """Test that OGC conformance now includes Processes classes."""

    def test_conformance_includes_processes(self):
        """Conformance declaration includes OGC API - Processes classes."""
        from ..services.ogc_service import CONFORMANCE_CLASSES

        processes_classes = [c for c in CONFORMANCE_CLASSES if "processes" in c]
        self.assertGreaterEqual(len(processes_classes), 5)
        self.assertIn("http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core", CONFORMANCE_CLASSES)
        self.assertIn("http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json", CONFORMANCE_CLASSES)
        self.assertIn("http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/job-list", CONFORMANCE_CLASSES)
        self.assertIn("http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/dismiss", CONFORMANCE_CLASSES)
        self.assertIn(
            "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description",
            CONFORMANCE_CLASSES,
        )

    def test_landing_page_includes_processes_link(self):
        """Landing page includes link to /gis/ogc/processes."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, base_url="http://test")
        landing = service.get_landing_page()

        link_rels = [link["rel"] for link in landing["links"]]
        self.assertIn("http://www.opengis.net/def/rel/ogc/1.0/processes", link_rels)


class TestProcessInputValidation(TransactionCase):
    """Unit tests for input validation logic in the processes router."""

    def test_validate_spatial_single_geometry(self):
        """Single GeoJSON geometry is valid."""
        from ..routers.processes import _validate_spatial_statistics_inputs

        # Should not raise
        _validate_spatial_statistics_inputs(
            {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}}
        )

    def test_validate_spatial_batch_with_id_value(self):
        """Batch with {id, value} wrapper is valid."""
        from ..routers.processes import _validate_spatial_statistics_inputs

        _validate_spatial_statistics_inputs(
            {
                "geometry": [
                    {"id": "a1", "value": {"type": "Polygon", "coordinates": []}},
                    {"id": "a2", "value": {"type": "Polygon", "coordinates": []}},
                ]
            }
        )

    def test_validate_spatial_bare_array_rejected(self):
        """Bare geometry arrays (no {id, value} wrapper) are rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_spatial_statistics_inputs

        with self.assertRaises(HTTPException) as ctx:
            _validate_spatial_statistics_inputs(
                {
                    "geometry": [
                        {"type": "Polygon", "coordinates": []},
                    ]
                }
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("id", ctx.exception.detail)

    def test_validate_spatial_empty_array_rejected(self):
        """Empty geometry array is rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_spatial_statistics_inputs

        with self.assertRaises(HTTPException) as ctx:
            _validate_spatial_statistics_inputs({"geometry": []})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_spatial_max_geometries(self):
        """More than 100 geometries is rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_spatial_statistics_inputs

        geometries = [{"id": f"g{i}", "value": {"type": "Polygon"}} for i in range(101)]
        with self.assertRaises(HTTPException) as ctx:
            _validate_spatial_statistics_inputs({"geometry": geometries})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("100", ctx.exception.detail)

    def test_validate_spatial_missing_geometry(self):
        """Missing geometry input is rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_spatial_statistics_inputs

        with self.assertRaises(HTTPException) as ctx:
            _validate_spatial_statistics_inputs({})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_proximity_valid(self):
        """Valid proximity inputs pass validation."""
        from ..routers.processes import _validate_proximity_statistics_inputs

        _validate_proximity_statistics_inputs(
            {
                "reference_points": [{"longitude": 1.0, "latitude": 2.0}],
                "radius_km": 10.0,
            }
        )

    def test_validate_proximity_missing_radius(self):
        """Missing radius_km is rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_proximity_statistics_inputs

        with self.assertRaises(HTTPException) as ctx:
            _validate_proximity_statistics_inputs({"reference_points": [{"longitude": 1.0, "latitude": 2.0}]})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_proximity_invalid_relation(self):
        """Invalid relation value is rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_proximity_statistics_inputs

        with self.assertRaises(HTTPException) as ctx:
            _validate_proximity_statistics_inputs(
                {
                    "reference_points": [{"longitude": 1.0, "latitude": 2.0}],
                    "radius_km": 10.0,
                    "relation": "intersects",
                }
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_proximity_radius_too_large(self):
        """radius_km > 500 is rejected."""
        from fastapi import HTTPException

        from ..routers.processes import _validate_proximity_statistics_inputs

        with self.assertRaises(HTTPException) as ctx:
            _validate_proximity_statistics_inputs(
                {
                    "reference_points": [{"longitude": 1.0, "latitude": 2.0}],
                    "radius_km": 501,
                }
            )
        self.assertEqual(ctx.exception.status_code, 400)


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestOGCProcessesHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for OGC Processes endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="GIS Processes Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Client without gis scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="No GIS Processes Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

        # Create a second client for job scoping tests
        cls.other_client = cls.create_api_client(
            cls,
            name="Other GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.other_token = cls.generate_jwt_token(cls, cls.other_client)

        # Create test indicator for enum tests
        Category = cls.env["spp.metric.category"]
        cls.test_category = Category.search([("code", "=", "http_proc_cat")], limit=1)
        if not cls.test_category:
            cls.test_category = Category.create({"name": "HTTP Proc Category", "code": "http_proc_cat", "sequence": 60})

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "http_proc_var",
                "cel_accessor": "http_proc_accessor",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        cls.test_indicator = cls.env["spp.statistic"].create(
            {
                "name": "http_proc_test_stat",
                "label": "HTTP Process Test Stat",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "is_published_gis": True,
                "category_id": cls.test_category.id,
            }
        )

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def _no_gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    def _other_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.other_token}",
        }

    # === Process list ===

    def test_list_processes_returns_200(self):
        """GET /processes returns 200 with process list."""
        response = self.url_open(f"{OGC_BASE}/processes", headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("processes", data)
        self.assertEqual(len(data["processes"]), 2)

    def test_list_processes_no_scope_returns_403(self):
        """GET /processes without gis scope returns 403."""
        response = self.url_open(f"{OGC_BASE}/processes", headers=self._no_gis_headers())
        self.assertEqual(response.status_code, 403)

    # === Process description ===

    def test_process_description_spatial_returns_200(self):
        """GET /processes/spatial-statistics returns 200."""
        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "spatial-statistics")
        self.assertIn("inputs", data)
        self.assertIn("outputs", data)

    def test_process_description_proximity_returns_200(self):
        """GET /processes/proximity-statistics returns 200."""
        response = self.url_open(
            f"{OGC_BASE}/processes/proximity-statistics",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "proximity-statistics")

    def test_process_description_unknown_returns_404(self):
        """GET /processes/nonexistent returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/processes/nonexistent",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_process_description_includes_indicator_enum(self):
        """Process description includes indicator names in variables enum."""
        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics",
            headers=self._gis_headers(),
        )
        data = response.json()
        variables = data["inputs"]["variables"]
        schema_items = variables["schema"]["items"]
        self.assertIn("enum", schema_items)
        self.assertIn("http_proc_test_stat", schema_items["enum"])

    def test_process_description_includes_x_openspp_statistics(self):
        """Process description includes x-openspp-statistics extension."""
        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics",
            headers=self._gis_headers(),
        )
        data = response.json()
        variables = data["inputs"]["variables"]
        self.assertIn("x-openspp-statistics", variables)

    # === Execution: invalid inputs ===

    def test_execute_unknown_process_returns_404(self):
        """POST /processes/nonexistent/execution returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/processes/nonexistent/execution",
            data=json.dumps({"inputs": {}}),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_execute_missing_geometry_returns_400(self):
        """POST spatial-statistics without geometry returns 400."""
        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps({"inputs": {}}),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_execute_bare_geometry_array_returns_400(self):
        """POST spatial-statistics with bare geometry array returns 400."""
        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {
                    "inputs": {
                        "geometry": [
                            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                        ]
                    }
                }
            ),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_execute_no_scope_returns_403(self):
        """POST execution without gis scope returns 403."""
        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps({"inputs": {"geometry": {"type": "Polygon", "coordinates": []}}}),
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    # === Execution: async flow ===

    def test_async_execution_returns_201(self):
        """POST with Prefer: respond-async returns 201 with Location header."""
        headers = self._gis_headers()
        headers["Prefer"] = "respond-async"

        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {
                    "inputs": {
                        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                    }
                }
            ),
            headers=headers,
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("Location", response.headers)
        data = response.json()
        self.assertIn("jobID", data)
        self.assertEqual(data["status"], "accepted")

    def test_forced_async_for_large_batch(self):
        """Batch with >10 geometries forces async regardless of Prefer header."""
        # Set threshold to 5 for testing
        self.env["ir.config_parameter"].sudo().set_param("spp_gis.forced_async_threshold", "5")

        geometries = [
            {"id": f"g{i}", "value": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}
            for i in range(6)
        ]

        response = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps({"inputs": {"geometry": geometries}}),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("Location", response.headers)

    # === Jobs API ===

    def test_list_jobs_empty(self):
        """GET /jobs returns empty list when no jobs exist for client."""
        response = self.url_open(f"{OGC_BASE}/jobs", headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)

    def test_job_scoping(self):
        """Client A cannot see Client B's jobs."""
        # Create a job via async execution for client A
        headers_a = self._gis_headers()
        headers_a["Prefer"] = "respond-async"
        resp_a = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {"inputs": {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}}
            ),
            headers=headers_a,
        )
        self.assertEqual(resp_a.status_code, 201)
        job_id = resp_a.json()["jobID"]

        # Client A can see the job
        resp_status_a = self.url_open(f"{OGC_BASE}/jobs/{job_id}", headers=self._gis_headers())
        self.assertEqual(resp_status_a.status_code, 200)

        # Client B cannot see it
        resp_status_b = self.url_open(f"{OGC_BASE}/jobs/{job_id}", headers=self._other_headers())
        self.assertEqual(resp_status_b.status_code, 404)

    def test_job_status_not_found(self):
        """GET /jobs/nonexistent returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/jobs/00000000-0000-0000-0000-000000000000",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_job_results_not_ready(self):
        """GET /jobs/{id}/results for non-successful job returns 404."""
        # Create an async job (status=accepted)
        headers = self._gis_headers()
        headers["Prefer"] = "respond-async"
        resp = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {"inputs": {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}}
            ),
            headers=headers,
        )
        job_id = resp.json()["jobID"]

        # Results not available for accepted job
        resp_results = self.url_open(
            f"{OGC_BASE}/jobs/{job_id}/results",
            headers=self._gis_headers(),
        )
        self.assertEqual(resp_results.status_code, 404)

    def test_dismiss_accepted_job(self):
        """DELETE /jobs/{id} for accepted job returns 200 with dismissed status."""
        headers = self._gis_headers()
        headers["Prefer"] = "respond-async"
        resp = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {"inputs": {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}}
            ),
            headers=headers,
        )
        job_id = resp.json()["jobID"]

        # Dismiss the job
        resp_delete = self.url_delete(
            f"{OGC_BASE}/jobs/{job_id}",
            headers=self._gis_headers(),
        )
        self.assertEqual(resp_delete.status_code, 200)
        data = resp_delete.json()
        self.assertEqual(data.get("status"), "dismissed")

    def test_dismiss_running_job_returns_409(self):
        """DELETE /jobs/{id} for running job returns 409."""
        # Create job and manually set to running
        headers = self._gis_headers()
        headers["Prefer"] = "respond-async"
        resp = self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {"inputs": {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}}
            ),
            headers=headers,
        )
        job_id = resp.json()["jobID"]

        # Manually set to running
        job = self.env["spp.gis.process.job"].sudo().search([("job_id", "=", job_id)], limit=1)
        job.status = "running"
        self.env.cr.flush()

        resp_delete = self.url_delete(
            f"{OGC_BASE}/jobs/{job_id}",
            headers=self._gis_headers(),
        )
        self.assertEqual(resp_delete.status_code, 409)

    def test_list_jobs_with_status_filter(self):
        """GET /jobs?status=accepted filters jobs."""
        # Create a job
        headers = self._gis_headers()
        headers["Prefer"] = "respond-async"
        self.url_open(
            f"{OGC_BASE}/processes/spatial-statistics/execution",
            data=json.dumps(
                {"inputs": {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}}
            ),
            headers=headers,
        )

        # Filter by accepted
        resp = self.url_open(f"{OGC_BASE}/jobs?status=accepted", headers=self._gis_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for job in data["jobs"]:
            self.assertEqual(job["status"], "accepted")

    def test_list_jobs_invalid_status_returns_400(self):
        """GET /jobs?status=invalid returns 400."""
        resp = self.url_open(f"{OGC_BASE}/jobs?status=invalid", headers=self._gis_headers())
        self.assertEqual(resp.status_code, 400)

    # === Conformance ===

    def test_conformance_includes_processes(self):
        """GET /conformance includes Processes conformance classes."""
        response = self.url_open(f"{OGC_BASE}/conformance", headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        conforms = data["conformsTo"]
        self.assertIn("http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core", conforms)

    # === Landing page ===

    def test_landing_page_includes_processes_link(self):
        """Landing page includes link to processes."""
        response = self.url_open(OGC_BASE, headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        link_rels = [link["rel"] for link in data["links"]]
        self.assertIn("http://www.opengis.net/def/rel/ogc/1.0/processes", link_rels)

    # === OpenAPI schema ===

    def test_execute_request_inputs_documented_as_oneof(self):
        """ExecuteRequest.inputs should document oneOf of typed inputs in OpenAPI.

        Regression guard for the loss of typed input documentation in commit
        46c2c364 ("revert ExecuteRequest.inputs to dict type").
        """
        response = self.url_open(f"{API_BASE}/openapi.json")
        self.assertEqual(response.status_code, 200, response.text)
        schema = response.json()

        components = schema["components"]["schemas"]
        self.assertIn("ExecuteRequest", components)
        inputs_schema = components["ExecuteRequest"]["properties"]["inputs"]
        self.assertIn("oneOf", inputs_schema, "ExecuteRequest.inputs must declare oneOf")

        refs = [item.get("$ref") for item in inputs_schema["oneOf"]]
        self.assertIn("#/components/schemas/SpatialStatisticsInputs", refs)
        self.assertIn("#/components/schemas/ProximityStatisticsInputs", refs)

        # Both referenced models must actually be present.
        self.assertIn("SpatialStatisticsInputs", components)
        self.assertIn("ProximityStatisticsInputs", components)


class TestProcessGroupByInput(TransactionCase):
    """Unit tests for group_by input and breakdown response in OGC processes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a demographic dimension for testing
        cls.gender_dimension = cls.env["spp.demographic.dimension"].search([("name", "=", "gender")], limit=1)
        if not cls.gender_dimension:
            cls.gender_dimension = cls.env["spp.demographic.dimension"].create(
                {
                    "name": "gender",
                    "label": "Gender",
                    "dimension_type": "field",
                    "field_path": "gender_id.code",
                    "value_labels_json": {"1": "Male", "2": "Female"},
                    "default_value": "unknown",
                }
            )

    def test_spatial_statistics_includes_group_by_input(self):
        """spatial-statistics process description includes group_by input."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("spatial-statistics")

        self.assertIn("group_by", desc["inputs"])
        group_by = desc["inputs"]["group_by"]
        self.assertEqual(group_by["title"], "Disaggregation Dimensions")
        self.assertEqual(group_by["minOccurs"], 0)
        self.assertEqual(group_by["schema"]["type"], "array")
        self.assertEqual(group_by["schema"]["maxItems"], 3)

    def test_proximity_statistics_includes_group_by_input(self):
        """proximity-statistics process description includes group_by input."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("proximity-statistics")

        self.assertIn("group_by", desc["inputs"])

    def test_group_by_enum_reflects_active_dimensions(self):
        """group_by enum includes active dimension names."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("spatial-statistics")

        group_by = desc["inputs"]["group_by"]
        items = group_by["schema"]["items"]

        # Should have enum with at least our test dimension
        self.assertIn("enum", items)
        self.assertIn("gender", items["enum"])

    def test_group_by_x_openspp_dimensions_metadata(self):
        """group_by includes x-openspp-dimensions extension with labels."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        desc = registry.get_process("spatial-statistics")

        group_by = desc["inputs"]["group_by"]
        self.assertIn("x-openspp-dimensions", group_by)

        dim_metadata = group_by["x-openspp-dimensions"]
        gender_dims = [d for d in dim_metadata if d["name"] == "gender"]
        self.assertEqual(len(gender_dims), 1)
        self.assertEqual(gender_dims[0]["label"], "Gender")

    def test_breakdown_schema_field_on_single_result(self):
        """SingleStatisticsResult schema accepts optional breakdown field."""
        from ..schemas.processes import SingleStatisticsResult

        # Without breakdown
        result = SingleStatisticsResult(
            total_count=10,
            query_method="coordinates",
            areas_matched=1,
            statistics={"count": 10},
        )
        self.assertIsNone(result.breakdown)

        # With breakdown
        result_with = SingleStatisticsResult(
            total_count=10,
            query_method="coordinates",
            areas_matched=1,
            statistics={"count": 10},
            breakdown={"1": {"count": 6, "labels": {"gender": {"value": "1", "display": "Male"}}}},
        )
        self.assertIsNotNone(result_with.breakdown)

    def test_breakdown_schema_field_on_batch_result(self):
        """BatchResultItem and BatchSummary schemas accept optional breakdown field."""
        from ..schemas.processes import BatchResultItem, BatchSummary

        item = BatchResultItem(
            id="area_1",
            total_count=10,
            query_method="coordinates",
            areas_matched=1,
            statistics={},
            breakdown={"1": {"count": 6}},
        )
        self.assertIsNotNone(item.breakdown)

        summary = BatchSummary(
            total_count=20,
            geometries_queried=2,
            statistics={},
            breakdown={"1": {"count": 12}},
        )
        self.assertIsNotNone(summary.breakdown)

    def test_breakdown_schema_field_on_proximity_result(self):
        """ProximityResult schema accepts optional breakdown field."""
        from ..schemas.processes import ProximityResult

        result = ProximityResult(
            total_count=10,
            query_method="coordinates",
            areas_matched=1,
            reference_points_count=1,
            radius_km=5.0,
            relation="within",
            statistics={},
            breakdown={"1": {"count": 6}},
        )
        self.assertIsNotNone(result.breakdown)

    def test_run_spatial_statistics_passes_group_by(self):
        """run_spatial_statistics extracts and passes group_by from inputs."""
        from unittest.mock import MagicMock

        from ..services.process_execution import run_spatial_statistics

        mock_service = MagicMock()
        mock_service.query_statistics.return_value = {
            "total_count": 5,
            "query_method": "area_fallback",
            "areas_matched": 1,
            "statistics": {},
            "breakdown": {"1": {"count": 3}},
            "registrant_ids": [1, 2, 3, 4, 5],
        }

        result = run_spatial_statistics(
            mock_service,
            {
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "group_by": ["gender"],
            },
        )

        mock_service.query_statistics.assert_called_once()
        call_kwargs = mock_service.query_statistics.call_args
        self.assertEqual(call_kwargs.kwargs.get("group_by") or call_kwargs[1].get("group_by"), ["gender"])
        self.assertEqual(result.get("breakdown"), {"1": {"count": 3}})

    def test_run_spatial_statistics_no_group_by_backward_compatible(self):
        """run_spatial_statistics without group_by passes None (backward compatible)."""
        from unittest.mock import MagicMock

        from ..services.process_execution import run_spatial_statistics

        mock_service = MagicMock()
        mock_service.query_statistics.return_value = {
            "total_count": 5,
            "query_method": "area_fallback",
            "areas_matched": 1,
            "statistics": {},
            "registrant_ids": [1, 2, 3, 4, 5],
        }

        result = run_spatial_statistics(
            mock_service,
            {
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            },
        )

        call_kwargs = mock_service.query_statistics.call_args
        group_by_value = call_kwargs.kwargs.get("group_by") if call_kwargs.kwargs else call_kwargs[1].get("group_by")
        self.assertIsNone(group_by_value)
        self.assertIsNone(result.get("breakdown"))

    def test_run_proximity_statistics_passes_group_by(self):
        """run_proximity_statistics extracts and passes group_by from inputs."""
        from unittest.mock import MagicMock

        from ..services.process_execution import run_proximity_statistics

        mock_service = MagicMock()
        mock_service.query_proximity.return_value = {
            "total_count": 3,
            "query_method": "area_fallback",
            "areas_matched": 1,
            "statistics": {},
            "breakdown": {"2": {"count": 2}},
            "reference_points_count": 1,
            "radius_km": 10.0,
            "relation": "within",
            "registrant_ids": [1, 2, 3],
        }

        result = run_proximity_statistics(
            mock_service,
            {
                "reference_points": [{"longitude": 1.0, "latitude": 2.0}],
                "radius_km": 10.0,
                "group_by": ["gender"],
            },
        )

        call_kwargs = mock_service.query_proximity.call_args
        self.assertEqual(call_kwargs.kwargs.get("group_by"), ["gender"])
        self.assertEqual(result.get("breakdown"), {"2": {"count": 2}})

    def test_run_spatial_statistics_batch_passes_group_by(self):
        """run_spatial_statistics in batch mode passes group_by to query_statistics_batch."""
        from unittest.mock import MagicMock

        from ..services.process_execution import run_spatial_statistics

        mock_service = MagicMock()
        mock_service.query_statistics_batch.return_value = {
            "results": [
                {
                    "id": "g1",
                    "total_count": 5,
                    "query_method": "area_fallback",
                    "areas_matched": 1,
                    "statistics": {},
                    "breakdown": {"1": {"count": 3}},
                },
            ],
            "summary": {
                "total_count": 5,
                "geometries_queried": 1,
                "statistics": {},
                "breakdown": {"1": {"count": 3}},
            },
        }

        result = run_spatial_statistics(
            mock_service,
            {
                "geometry": [
                    {"id": "g1", "value": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
                ],
                "group_by": ["gender"],
            },
        )

        mock_service.query_statistics_batch.assert_called_once()
        call_kwargs = mock_service.query_statistics_batch.call_args
        self.assertEqual(call_kwargs.kwargs.get("group_by"), ["gender"])
        self.assertIn("breakdown", result["summary"])
        self.assertIn("breakdown", result["results"][0])
