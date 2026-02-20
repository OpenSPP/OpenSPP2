# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Extend spp.change.request with computed DCI verification fields.

These fields pull DCI birth verification data from the detail record
and make it visible on the main CR form, so reviewers can see
verification status without navigating into the detail sub-form.
"""

import logging

from markupsafe import Markup, escape

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SPPChangeRequestDCI(models.Model):
    """Extend CR with computed DCI verification fields for reviewer UX."""

    _inherit = "spp.change.request"

    dci_verification_status = fields.Selection(
        [
            ("unverified", "Unverified"),
            ("verified", "Verified"),
            ("not_found", "Not Found"),
            ("error", "Error"),
        ],
        compute="_compute_dci_verification",
        string="DCI Verification Status",
    )

    dci_verification_html = fields.Html(
        compute="_compute_dci_verification",
        string="DCI Verification Summary",
        sanitize=False,
    )

    dci_data_match = fields.Boolean(
        compute="_compute_dci_verification",
        string="DCI Data Matches",
    )

    @api.depends("detail_res_model", "detail_res_id", "approval_state")
    def _compute_dci_verification(self):
        for rec in self:
            rec.dci_verification_status = False
            rec.dci_verification_html = ""
            rec.dci_data_match = False

            # Only applicable for add_member detail type
            if rec.detail_res_model != "spp.cr.detail.add_member":
                continue

            detail = rec.get_detail()
            if not detail:
                continue

            # Check if the detail has DCI fields (from spp_dci_demo)
            if not hasattr(detail, "birth_verification_status"):
                continue

            status = detail.birth_verification_status
            if not status or status == "unverified":
                rec.dci_verification_status = status or "unverified"
                continue

            rec.dci_verification_status = status
            rec.dci_data_match = detail.dci_data_match

            # Build HTML summary
            badge_class = {
                "verified": "bg-success",
                "not_found": "bg-warning",
                "error": "bg-danger",
            }.get(status, "bg-secondary")

            status_label = {
                "verified": "Verified",
                "not_found": "Not Found",
                "error": "Error",
            }.get(status, status)

            parts = []

            # Status badge
            parts.append(
                Markup(
                    '<div class="d-flex align-items-center mb-2">'
                    '<strong class="me-2">Birth Verification:</strong>'
                    '<span class="badge {}">{}</span>'
                    "</div>"
                ).format(badge_class, escape(status_label))
            )

            # BRN
            if detail.birth_registration_number:
                parts.append(
                    Markup('<div class="mb-1"><span class="text-muted">BRN:</span> <strong>{}</strong></div>').format(
                        escape(detail.birth_registration_number)
                    )
                )

            # Data match indicator
            if status == "verified":
                if detail.dci_data_match:
                    parts.append(
                        Markup(
                            '<div class="mb-1">'
                            '<span class="text-muted">Data Match:</span> '
                            '<span class="text-success">'
                            '<i class="fa fa-check-circle me-1"></i>All fields match'
                            "</span></div>"
                        )
                    )
                else:
                    parts.append(
                        Markup(
                            '<div class="mb-1">'
                            '<span class="text-muted">Data Match:</span> '
                            '<span class="text-danger">'
                            '<i class="fa fa-exclamation-circle me-1"></i>'
                            "Mismatch detected"
                            "</span></div>"
                        )
                    )

            # Verification date
            if detail.birth_verification_date:
                parts.append(
                    Markup('<div class="text-muted small">Verified: {}</div>').format(
                        escape(str(detail.birth_verification_date))
                    )
                )

            rec.dci_verification_html = Markup("").join(parts)
