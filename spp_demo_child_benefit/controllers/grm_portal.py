# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Portal grievance form: choose which family member the request concerns.

The submitter stays the ticket contact (``partner_id``), so the own-tickets
record rule and the confirmation e-mail are unchanged. The chosen individual
becomes ``registrant_id`` and their family ``household_id`` — the same fields
the back office fills — so the ticket shows on the registrant's and the
family's records. The posted id is validated against the family recomputed
server-side; anything else is a 400.
"""

from werkzeug.exceptions import BadRequest, NotFound

from odoo import http
from odoo.http import request

from odoo.addons.spp_grm.controllers.grm_portal import SPPGrmPortal

from .portal_family import portal_family_members, resolve_family_member


class GrmPortalFamily(SPPGrmPortal):
    def _portal_family_members(self):
        return portal_family_members(request.env, request.env.user.partner_id)

    def _resolve_registrant(self, raw, members):
        registrant = resolve_family_member(raw, members, request.env.user.partner_id)
        if registrant is None:
            raise BadRequest()
        return registrant

    @http.route(["/my/ticket/<int:ticket_id>"], type="http", auth="user", website=True)
    def portal_ticket_detail(self, ticket_id, **kw):
        """Read-only grievance page with the conversation thread. Scoped to the
        logged-in partner's own grievances; anything else is a 404."""
        partner = request.env.user.partner_id
        ticket = (
            request.env["spp.grm.ticket"]
            .sudo()
            .search([("id", "=", ticket_id), ("partner_id", "=", partner.id)], limit=1)
        )
        if not ticket:
            raise NotFound()
        return request.render(
            "spp_demo_child_benefit.portal_grievance_detail",
            {"ticket": ticket, "page_name": "tickets", "grievance_detail": True},
        )

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

        # nosemgrep: semgrep.odoo-unvalidated-redirect -- fixed internal URL with our own record id
        return request.redirect(f"/my/ticket/{ticket.id}")
