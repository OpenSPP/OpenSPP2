import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApprovalReview(models.Model):
    """Tracks individual approval review steps.

    Each review represents one approval action on a record.
    """

    _name = "spp.approval.review"
    _description = "Approval Review Record"
    _order = "create_date desc"

    # Polymorphic reference to the approved record
    model = fields.Char(required=True, index=True)
    res_id = fields.Many2oneReference(
        string="Record ID",
        model_field="model",
        index=True,
    )

    definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        ondelete="restrict",
    )

    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        required=True,
        index=True,
    )

    # Request info
    requested_by_id = fields.Many2one(
        "res.users",
        string="Requested By",
        default=lambda self: self.env.user,
        readonly=True,
    )
    requested_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
    )

    # Review info
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewed By",
        readonly=True,
    )
    review_date = fields.Datetime(readonly=True)
    comment = fields.Text(string="Comment")

    # SLA tracking
    sla_deadline = fields.Datetime(
        string="SLA Deadline",
        compute="_compute_sla_deadline",
        store=True,
    )
    is_sla_exceeded = fields.Boolean(
        compute="_compute_sla_exceeded",
        store=True,
    )

    def init(self):
        """Create optimized indexes and constraints for common queries."""
        # Unique constraint for pending reviews (only one pending per definition per record)
        # Using EXCLUDE constraint for conditional uniqueness
        # Note: Requires btree_gist extension
        try:
            self.env.cr.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'spp_approval_review_unique_pending'
                    ) THEN
                        ALTER TABLE spp_approval_review
                        ADD CONSTRAINT spp_approval_review_unique_pending
                        EXCLUDE (model WITH =, res_id WITH =, definition_id WITH =)
                        WHERE (status = 'pending');
                    END IF;
                END $$;
            """
            )
        except Exception as e:
            # Log the error - constraint may already exist or btree_gist not available
            _logger.warning(
                "Could not create spp_approval_review_unique_pending constraint: %s. "
                "This may happen if btree_gist extension is not available.",
                str(e),
            )

        # Partial index for pending reviews (most queried)
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS approval_review_pending_idx
            ON spp_approval_review (model, res_id)
            WHERE status = 'pending'
        """
        )

        # Index for reviewer dashboard (reviewer_id for approvers checking their queue)
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS approval_review_reviewer_status_idx
            ON spp_approval_review (reviewer_id, status)
            WHERE status = 'pending'
        """
        )

        # Index for audit queries
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS approval_review_date_idx
            ON spp_approval_review (review_date DESC)
            WHERE status IN ('approved', 'rejected')
        """
        )

    @api.depends("requested_date", "definition_id.sla_days")
    def _compute_sla_deadline(self):
        for record in self:
            if record.definition_id and record.definition_id.sla_days:
                record.sla_deadline = fields.Datetime.add(record.requested_date, days=record.definition_id.sla_days)
            else:
                record.sla_deadline = False

    @api.depends("sla_deadline", "status", "review_date")
    def _compute_sla_exceeded(self):
        now = fields.Datetime.now()
        for record in self:
            if not record.sla_deadline:
                record.is_sla_exceeded = False
            elif record.status == "pending":
                record.is_sla_exceeded = now > record.sla_deadline
            elif record.review_date:
                record.is_sla_exceeded = record.review_date > record.sla_deadline
            else:
                record.is_sla_exceeded = False

    def action_approve(self, comment=None):
        """Mark the review as approved."""
        self.write(
            {
                "status": "approved",
                "reviewer_id": self.env.user.id,
                "review_date": fields.Datetime.now(),
                "comment": comment,
            }
        )

    def action_reject(self, comment=None):
        """Mark the review as rejected."""
        self.write(
            {
                "status": "rejected",
                "reviewer_id": self.env.user.id,
                "review_date": fields.Datetime.now(),
                "comment": comment,
            }
        )

    def get_record(self):
        """Get the actual record being reviewed."""
        self.ensure_one()
        if self.model and self.res_id:
            return self.env[self.model].browse(self.res_id)
        return None

    @api.model
    def get_pending_for_user(self, user_id=None, limit=None):
        """Get pending reviews for a user.

        Args:
            user_id: User ID (defaults to current user)
            limit: Max number of reviews to return

        Returns:
            spp.approval.review recordset

        Note:
            Manager-type approvals require checking if the user is the manager
            of the requester, which is done via Python filtering after the search.
        """
        user_id = user_id or self.env.user.id
        user = self.env["res.users"].browse(user_id)
        domain = [("status", "=", "pending")]

        # Get definitions where this user is an approver (group or user type)
        # Use sudo() to check group membership without requiring read access to res.groups
        definitions = (
            self.env["spp.approval.definition"]
            .sudo()
            .search(
                [
                    "|",
                    ("approval_user_ids", "in", [user_id]),
                    ("approval_group_id.user_ids", "in", [user_id]),
                ]
            )
        )

        # Also check for manager-type definitions
        manager_definitions = self.env["spp.approval.definition"].sudo().search([("approval_type", "=", "manager")])

        all_definition_ids = definitions.ids

        # For manager-type definitions, we need to find reviews where this user
        # is the manager of the requester
        if manager_definitions:
            # Check if user has an employee record to be a manager
            if hasattr(user, "employee_id") and user.employee_id:
                # Find employees that report to this user
                subordinates = self.env["hr.employee"].search([("parent_id", "=", user.employee_id.id)])
                subordinate_user_ids = subordinates.mapped("user_id").ids
                if subordinate_user_ids:
                    manager_reviews = self.search(
                        [
                            ("status", "=", "pending"),
                            ("definition_id", "in", manager_definitions.ids),
                            ("requested_by_id", "in", subordinate_user_ids),
                        ]
                    )
                    # Combine results
                    if all_definition_ids:
                        base_reviews = self.search(
                            domain + [("definition_id", "in", all_definition_ids)],
                            limit=limit,
                            order="requested_date asc",
                        )
                        return base_reviews | manager_reviews
                    else:
                        return manager_reviews

        if all_definition_ids:
            domain.append(("definition_id", "in", all_definition_ids))
            return self.search(domain, limit=limit, order="requested_date asc")

        return self.browse()  # Empty recordset

    @api.model
    def get_pending_summary(self, user_id=None):
        """Get summary of pending approvals grouped by model.

        Args:
            user_id: User ID (defaults to current user)

        Returns:
            List of dicts with model, pending_count, oldest_request

        Note:
            Manager-type approvals are handled separately to ensure users only
            see reviews where they are actually the manager of the requester.
        """
        user_id = user_id or self.env.user.id
        user = self.env["res.users"].browse(user_id)

        # Get definitions where this user is an approver (via user list or group)
        definitions = self.env["spp.approval.definition"].search(
            [
                "|",
                ("approval_user_ids", "in", [user_id]),
                ("approval_group_id.user_ids", "in", [user_id]),
            ]
        )

        # Get pending reviews for these definitions
        reviews = self.search(
            [
                ("status", "=", "pending"),
                ("definition_id", "in", definitions.ids),
            ]
        )

        # Group by model
        results = {}
        for review in reviews:
            model = review.model
            if model not in results:
                results[model] = {
                    "model": model,
                    "pending_count": 0,
                    "oldest_request": review.requested_date,
                }
            results[model]["pending_count"] += 1
            if review.requested_date < results[model]["oldest_request"]:
                results[model]["oldest_request"] = review.requested_date

        # Handle manager-type approvals separately
        # Only include reviews where the user is actually the manager
        if hasattr(user, "employee_id") and user.employee_id:
            subordinates = self.env["hr.employee"].search([("parent_id", "=", user.employee_id.id)])
            subordinate_user_ids = subordinates.mapped("user_id").ids
            if subordinate_user_ids:
                manager_definitions = self.env["spp.approval.definition"].search([("approval_type", "=", "manager")])
                if manager_definitions:
                    manager_reviews = self.search(
                        [
                            ("status", "=", "pending"),
                            ("definition_id", "in", manager_definitions.ids),
                            ("requested_by_id", "in", subordinate_user_ids),
                        ]
                    )
                    for review in manager_reviews:
                        model = review.model
                        if model not in results:
                            results[model] = {
                                "model": model,
                                "pending_count": 0,
                                "oldest_request": review.requested_date,
                            }
                        results[model]["pending_count"] += 1
                        if review.requested_date < results[model]["oldest_request"]:
                            results[model]["oldest_request"] = review.requested_date

        # Sort by pending_count descending
        return sorted(results.values(), key=lambda x: x["pending_count"], reverse=True)
