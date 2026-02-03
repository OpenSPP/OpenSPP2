# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DrimsReport4WWizard(models.TransientModel):
    _name = "spp.drims.report.4w.wizard"
    _description = "DRIMS 4W Report Wizard"

    # Who filters
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        help="Filter data by specific incident",
    )

    # When filters
    date_from = fields.Date(
        string="Date From",
        help="Start date for filtering requests",
    )
    date_to = fields.Date(
        string="Date To",
        help="End date for filtering requests",
    )

    # What filters (clusters/sectors)
    cluster_ids = fields.Many2many(
        "spp.vocabulary.code",
        string="Clusters/Sectors",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:item-categories')]",
        help="Filter by humanitarian clusters/sectors (item categories)",
    )

    # Where filters
    area_id = fields.Many2one(
        "spp.area",
        string="Area",
        help="Filter by geographic area",
    )

    # Status filters
    include_planned = fields.Boolean(
        string="Include Planned/Pending",
        default=True,
        help="Include requests in draft, submitted, or approved states",
    )
    include_completed = fields.Boolean(
        string="Include Completed",
        default=True,
        help="Include requests that have been dispatched or delivered",
    )

    cluster_ids_domain = fields.Char(
        compute="_compute_cluster_ids_domain",
        readonly=True,
        store=False,
    )

    @api.depends("incident_id")
    def _compute_cluster_ids_domain(self):
        for rec in self:
            domain = [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:item-categories")]
            rec.cluster_ids_domain = json.dumps(domain)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        """Ensure date_to is not before date_from."""
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise UserError(_("End date cannot be before start date."))

    def generate_report(self):
        """Generate 4W report and return pivot view action.

        The 4W report aggregates:
        - Who: Organizations providing assistance (requester/donor)
        - What: Type of assistance (clusters/sectors from item categories)
        - Where: Geographic location (destination area)
        - When: Time period (date requested/needed)
        """
        self.ensure_one()

        # Build domain for requests
        domain = [("incident_id", "=", self.incident_id.id)]

        # Date filters
        if self.date_from:
            domain.append(("date_requested", ">=", self.date_from))
        if self.date_to:
            domain.append(("date_requested", "<=", self.date_to))

        # Area filter
        if self.area_id:
            domain.append(("destination_area_id", "child_of", self.area_id.id))

        # Status filters
        if not self.include_planned and not self.include_completed:
            raise UserError(_("Please select at least one status filter."))

        state_codes = []
        if self.include_planned:
            state_codes.extend(["draft", "submitted", "approved", "allocated"])
        if self.include_completed:
            state_codes.extend(["dispatched", "delivered", "fulfilled"])

        if state_codes:
            domain.append(("state", "in", state_codes))

        # Cluster/sector filter - need to filter by product categories
        # This will be handled in the view grouping

        context = {
            "create": False,
            "edit": False,
            "delete": False,
            "search_default_group_area": 1,
            "search_default_group_requester": 1,
        }

        # Get view references
        pivot_view_id = self.env.ref("spp_drims.view_drims_request_4w_pivot", raise_if_not_found=False)
        graph_view_id = self.env.ref("spp_drims.view_drims_request_4w_graph", raise_if_not_found=False)
        search_view_id = self.env.ref("spp_drims.view_drims_request_4w_search", raise_if_not_found=False)

        views = []
        if pivot_view_id:
            views.append((pivot_view_id.id, "pivot"))
        if graph_view_id:
            views.append((graph_view_id.id, "graph"))

        return {
            "name": _("4W Report - %s") % self.incident_id.name,
            "view_mode": "pivot,graph",
            "res_model": "spp.drims.request",
            "views": views if views else False,
            "search_view_id": search_view_id.id if search_view_id else False,
            "domain": domain,
            "context": context,
            "type": "ir.actions.act_window",
            "target": "current",
        }
