# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Read-only benefit monitoring portal for family heads.

Security model: no record rules open spp models to the portal group. Every
read below runs as sudo but is hard-scoped to the families in which the
logged-in partner holds the head or mother role; any child outside that set
is a 404. The pages render a strict allowlist of fields — never the computed
birth order or other registry data (only authorized back-office roles may see
those).
"""

import logging

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

PAYEE_ROLES = {"head", "mother"}


class ChildBenefitPortal(CustomerPortal):
    def _get_benefit_children(self):
        """Children of the families the logged-in partner heads."""
        partner = request.env.user.partner_id
        Membership = request.env["spp.group.membership"].sudo()
        my_memberships = Membership.search([("individual", "=", partner.id), ("is_ended", "=", False)])
        families = my_memberships.filtered(
            lambda m: m.group.group_type_id.code == "family" and PAYEE_ROLES & set(m.membership_type_ids.mapped("code"))
        ).mapped("group")
        if not families:
            return request.env["res.partner"].sudo().browse()
        child_memberships = Membership.search([("group", "in", families.ids), ("is_ended", "=", False)])
        return child_memberships.filtered(lambda m: "child" in m.membership_type_ids.mapped("code")).mapped(
            "individual"
        )

    def _get_active_schedules(self, children):
        return (
            request.env["spp.entitlement.schedule"]
            .sudo()
            .search([("partner_id", "in", children.ids), ("state", "=", "active")])
        )

    @http.route(["/my/benefits"], type="http", auth="user", website=True)
    def portal_my_benefits(self, **kw):
        children = self._get_benefit_children()
        schedules = self._get_active_schedules(children)
        schedules_by_child = {}
        for schedule in schedules:
            schedules_by_child.setdefault(schedule.partner_id.id, schedule)
        values = {
            "children": children,
            "schedules_by_child": schedules_by_child,
            "page_name": "benefits",
        }
        return request.render("spp_child_benefit.portal_my_benefits", values)

    @http.route(["/my/benefits/child/<int:child_id>"], type="http", auth="user", website=True)
    def portal_benefit_child(self, child_id, **kw):
        children = self._get_benefit_children()
        child = children.filtered(lambda c: c.id == child_id)
        if not child:
            raise NotFound()
        schedule = self._get_active_schedules(child)
        values = {
            "child": child,
            "schedule": schedule[:1],
            "page_name": "benefits",
        }
        return request.render("spp_child_benefit.portal_benefit_child", values)
