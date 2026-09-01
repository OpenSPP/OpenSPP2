# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Read-only benefit monitoring portal for family heads.

Security model: no record rules open spp models to the portal group. Every
read below runs as sudo but is hard-scoped to the families in which the
logged-in partner holds the head or mother role; any child outside that set
is a 404. The pages render a strict allowlist of fields — never the computed
birth order or other registry data (only authorized back-office roles may see
those).
"""

from werkzeug.exceptions import NotFound

from odoo import fields, http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

GROUP_TYPE_NS = "urn:openspp:vocab:group-type"
MEMBERSHIP_TYPE_NS = "urn:openspp:vocab:group-membership-type"


class ChildBenefitPortal(CustomerPortal):
    def _live_membership_domain(self):
        """A membership is live when it has not ended yet. `is_ended` is a
        stored compute that only refreshes when `ended_date` is written, so an
        authorization gate must test `ended_date` against the clock directly."""
        now = fields.Datetime.now()
        return ["|", ("ended_date", "=", False), ("ended_date", ">", now)]

    def _payee_role_ids(self):
        """Resolved payee role code ids (namespace-qualified, not bare strings).

        The 'head' code lives in the system vocabulary; 'mother' is shipped by
        this module. Resolving both to ids means a same-named code in another
        vocabulary (e.g. a 'head' relationship code) can never grant access."""
        head = request.env["spp.vocabulary.code"].sudo().get_code(MEMBERSHIP_TYPE_NS, "head")
        mother = request.env.ref("spp_child_benefit.code_membership_type_mother")
        return {head.id, mother.id}

    def _get_benefit_children(self):
        """Children of the family groups where the logged-in partner holds a
        payee role (head or mother). Matching is by resolved vocabulary code
        id and namespace, never by bare code string."""
        partner = request.env.user.partner_id
        Membership = request.env["spp.group.membership"].sudo()
        child_role = request.env.ref("spp_child_benefit.code_membership_type_child")
        payee_role_ids = self._payee_role_ids()

        my_memberships = Membership.search([("individual", "=", partner.id)] + self._live_membership_domain())
        families = my_memberships.filtered(
            lambda m: m.group.group_type_id.namespace_uri == GROUP_TYPE_NS
            and m.group.group_type_id.code == "family"
            and payee_role_ids & set(m.membership_type_ids.ids)
        ).mapped("group")
        if not families:
            return request.env["res.partner"].sudo().browse()
        child_memberships = Membership.search([("group", "in", families.ids)] + self._live_membership_domain())
        return child_memberships.filtered(lambda m: child_role.id in m.membership_type_ids.ids).mapped("individual")

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
