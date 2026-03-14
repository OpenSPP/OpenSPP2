# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GisProcessJob(models.Model):
    _name = "spp.gis.process.job"
    _description = "OGC Process Job"
    _order = "create_date desc"

    job_id = fields.Char(
        required=True,
        index=True,
        help="UUID external identifier for the job (OGC jobID)",
    )
    process_id = fields.Char(
        required=True,
        index=True,
        help="Process identifier (e.g., 'spatial-statistics')",
    )
    status = fields.Selection(
        selection=[
            ("accepted", "Accepted"),
            ("running", "Running"),
            ("successful", "Successful"),
            ("failed", "Failed"),
            ("dismissed", "Dismissed"),
        ],
        default="accepted",
        required=True,
        index=True,
    )
    client_id = fields.Many2one(
        comodel_name="spp.api.client",
        index=True,
        help="API client that submitted the job",
    )
    message = fields.Text(help="Human-readable status message")
    progress = fields.Integer(default=0, help="Job progress percentage (0-100)")
    inputs = fields.Json(help="Serialized execute request inputs")
    results = fields.Json(help="Serialized process output")
    started_at = fields.Datetime(help="Timestamp when job execution started")
    finished_at = fields.Datetime(help="Timestamp when job execution finished")
    job_uuid = fields.Char(
        index=True,
        help="Job worker UUID for tracking the background job",
    )

    _sql_constraints = [
        ("job_id_unique", "UNIQUE(job_id)", "Job ID must be unique"),
    ]

    def dismiss(self):
        """Dismiss a job.

        For accepted jobs: sets status to dismissed and records finished_at.
        For running jobs: raises a UserError (cannot dismiss running jobs).
        For terminal jobs (successful/failed/dismissed): deletes the record.
        """
        self.ensure_one()
        if self.status == "accepted":
            self.write(
                {
                    "status": "dismissed",
                    "finished_at": fields.Datetime.now(),
                }
            )
        elif self.status == "running":
            raise UserError(_("Cannot dismiss a running job. Wait for it to finish or check back later."))
        else:
            # Terminal statuses: successful, failed, dismissed
            self.unlink()

    def execute_process(self):
        """Execute the process for this job.

        This method is called by the job worker. It runs the appropriate
        SpatialQueryService method based on process_id, stores the results,
        and updates the job status accordingly.

        For batch spatial-statistics requests, progress is updated per geometry.
        """
        self.ensure_one()

        self.write(
            {
                "status": "running",
                "started_at": fields.Datetime.now(),
            }
        )

        try:
            # Lazy imports to avoid circular imports
            from ..services.process_execution import run_proximity_statistics, run_spatial_statistics
            from ..services.spatial_query_service import SpatialQueryService

            service = SpatialQueryService(self.env)
            inputs = self.inputs or {}

            if self.process_id == "spatial-statistics":
                geometry = inputs.get("geometry")
                if isinstance(geometry, list) and len(geometry) > 1:
                    results = self._execute_batch_with_progress(service, inputs)
                else:
                    results = run_spatial_statistics(service, inputs)
            elif self.process_id == "proximity-statistics":
                results = run_proximity_statistics(service, inputs)
            else:
                raise ValueError(f"Unknown process_id: {self.process_id!r}")

            self.write(
                {
                    "status": "successful",
                    "finished_at": fields.Datetime.now(),
                    "progress": 100,
                    "results": results,
                }
            )

        except Exception:
            _logger.exception("GIS process job %s failed", self.job_id)
            self.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "message": "Process execution failed. Check server logs for details.",
                }
            )

    def _execute_batch_with_progress(self, service, inputs):
        """Execute batch spatial-statistics with per-geometry progress updates.

        Calls the service's batch method with a progress callback so that
        the job record is updated after each geometry is processed.
        """
        geometry = inputs["geometry"]
        geometries = [{"id": g["id"], "geometry": g["value"]} for g in geometry]
        total = len(geometries)

        def on_progress(completed):
            self.write({"progress": int(completed / total * 100)})

        result = service.query_statistics_batch(
            geometries=geometries,
            filters=inputs.get("filters"),
            variables=inputs.get("variables"),
            on_progress=on_progress,
        )
        for item in result.get("results", []):
            item.pop("registrant_ids", None)
        return result

    @api.model
    def cron_cleanup_jobs(self):
        """Clean up old and stale jobs.

        Called by ir.cron on a daily schedule.

        - Deletes jobs older than the configured retention period.
        - Marks stale accepted/running jobs (older than 1 hour) as failed.
        """
        IrConfig = self.env["ir.config_parameter"].sudo()
        try:
            retention_days = int(IrConfig.get_param("spp_gis.job_retention_days", default=7))
        except (ValueError, TypeError):
            retention_days = 7

        cutoff_date = fields.Datetime.subtract(fields.Datetime.now(), days=retention_days)
        stale_cutoff = fields.Datetime.subtract(fields.Datetime.now(), hours=1)

        # Mark stale in-progress jobs as failed first (before deletion cutoff)
        stale_jobs = self.search(
            [
                ("status", "in", ["accepted", "running"]),
                ("create_date", "<", stale_cutoff),
            ]
        )
        if stale_jobs:
            _logger.info("Marking %d stale GIS process jobs as failed", len(stale_jobs))
            stale_jobs.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "message": "Job timed out (stale)",
                }
            )

        # Delete jobs older than retention period
        old_jobs = self.search([("create_date", "<", cutoff_date)])
        if old_jobs:
            _logger.info(
                "Deleting %d GIS process jobs older than %d days",
                len(old_jobs),
                retention_days,
            )
            old_jobs.unlink()
