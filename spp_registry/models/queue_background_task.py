from odoo import fields, models


class SPPQueueBackgroundTask(models.Model):
    _name = "spp.queue.background.task"
    _description = "SPP Queue Background Task"

    worker_type = fields.Char(default="example_worker")  # Default worker type
    worker_payload = fields.Json(required=True)
    task_status = fields.Selection(
        selection=[
            ("PENDING", "PENDING"),
            ("COMPLETED", "COMPLETED"),
            ("FAILED", "FAILED"),
        ],
        required=True,
        default="PENDING",
    )
    queued_datetime = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
    )
    number_of_attempts = fields.Integer(
        required=True,
        default=0,
    )
    last_attempt_datetime = fields.Datetime()
    last_attempt_error_code = fields.Char()
