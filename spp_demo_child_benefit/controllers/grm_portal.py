# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Portal grievance form: choose which family member the request concerns.

The submitter stays the ticket contact (``partner_id``), so the own-tickets
record rule and the confirmation e-mail are unchanged. The chosen individual
becomes ``registrant_id`` and their family ``household_id`` — the same fields
the back office fills — so the ticket shows on the registrant's and the
family's records. The posted id is validated against the family recomputed
server-side; anything else is a 400.
"""

from werkzeug.exceptions import BadRequest

from odoo import fields, http
from odoo.http import request

from odoo.addons.spp_grm.controllers.grm_portal import SPPGrmPortal

GROUP_TYPE_NS = "urn:openspp:vocab:group-type"


class GrmPortalFamily(SPPGrmPortal):
    def _live_membership_domain(self):
        """`is_ended` is a stored compute refreshed only on write, so test
        `ended_date` against the clock directly."""
        now = fields.Datetime.now()
        return ["|", ("ended_date", "=", False), ("ended_date", ">", now)]

    def _portal_family_members(self):
        """Live members of the family groups the logged-in partner belongs to,
        as {individual: family}, submitter first. The submitter is always
        offered, even without a family."""
        partner = request.env.user.partner_id
        Membership = request.env["spp.group.membership"].sudo()
        live = self._live_membership_domain()
        mine = Membership.search([("individual", "=", partner.id)] + live)
        families = mine.filtered(
            lambda m: m.group.group_type_id.namespace_uri == GROUP_TYPE_NS and m.group.group_type_id.code == "family"
        ).mapped("group")
        members = {partner: families[:1]}
        if families:
            for membership in Membership.search([("group", "in", families.ids)] + live, order="group, id"):
                members.setdefault(membership.individual, membership.group)
        return members

    def _resolve_registrant(self, raw, members):
        """The posted family member, or the submitter when nothing was posted."""
        partner = request.env.user.partner_id
        if raw in (None, ""):
            return partner
        try:
            registrant_id = int(raw)
        except (TypeError, ValueError) as err:
            raise BadRequest() from err
        for member in members:
            if member.id == registrant_id:
                return member
        raise BadRequest()

    @http.route(["/my/ticket/new"], type="http", auth="user", website=True)
    def portal_ticket_new(self, **kw):
        categories = request.env["spp.grm.ticket.category"].search([])
        channels = request.env["spp.grm.ticket.channel"].search([])
        return request.render(
            "spp_grm.portal_create_ticket",
            {
                "categories": categories,
                "channels": channels,
                "page_name": "tickets",
                "ticket": "new",
                "family_members": list(self._portal_family_members()),
                "default_member": request.env.user.partner_id,
            },
        )

    @http.route(["/my/ticket/submit"], type="http", auth="user", website=True, csrf=True)
    def portal_ticket_submit(self, **kw):
        partner = request.env.user.partner_id
        members = self._portal_family_members()
        registrant = self._resolve_registrant(kw.get("registrant_id"), members)
        household = members.get(registrant) or request.env["res.partner"].sudo().browse()
        vals = {
            "name": kw.get("ticket_name"),
            "description": kw.get("description"),
            "category_id": kw.get("category_id"),
            "channel_id": request.env.ref("spp_grm.grm_ticket_channel_web").id,
            "partner_id": partner.id,
            "registrant_id": registrant.id,
            "household_id": household.id if household else False,
        }
        area = getattr(registrant.sudo(), "area_id", False)
        if area:
            vals["area_id"] = area.id
        # nosemgrep: semgrep.odoo-sudo-without-context -- portal users need sudo to create tickets
        ticket = request.env["spp.grm.ticket"].sudo().create(vals)

        ticket.send_ticket_confirmation_email(ticket)

        # nosemgrep: semgrep.odoo-unvalidated-redirect -- fixed internal URL
        return request.redirect("/my/tickets")
