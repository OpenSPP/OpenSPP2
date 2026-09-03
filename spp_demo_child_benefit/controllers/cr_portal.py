# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Portal change requests: a citizen updates their own or a family member's
personal information through the standard "Edit Individual Information"
request, which the programme manager approves in the back office.

Security model: no change-request model is opened to the portal group. Every
read and write runs as sudo, hard-scoped to requests whose applicant is the
logged-in partner; anything else is a 404. The registrant is validated against
the family recomputed server-side, posted fields against an allowlist.
"""

from werkzeug.exceptions import BadRequest, NotFound

from odoo import fields, http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

from .portal_family import portal_family_members, resolve_family_member

GENDER_NS = "urn:iso:std:iso:5218"
CR_TYPE_XMLID = "spp_cr_types_base.cr_type_edit_individual"

# (detail field, label, input kind) — the fields the back-office form offers.
FIELDS = [
    ("given_name", "Given name", "text"),
    ("family_name", "Family name", "text"),
    ("birthdate", "Date of birth", "date"),
    ("gender_id", "Gender", "gender"),
    ("phone", "Phone", "text"),
    ("email", "Email", "text"),
    ("address_line1", "Address line 1", "text"),
    ("address_line2", "Address line 2", "text"),
    ("city", "City", "text"),
    ("postal_code", "Postal code", "text"),
]
MAX_LEN = 200


class ChangeRequestPortal(CustomerPortal):
    def _partner(self):
        return request.env.user.partner_id

    def _my_change_requests(self):
        return (
            request.env["spp.change.request"]
            .sudo()
            .search([("applicant_id", "=", self._partner().id)], order="create_date desc, id desc")
        )

    def _genders(self):
        return request.env["spp.vocabulary.code"].sudo().search([("namespace_uri", "=", GENDER_NS)])

    def _current_values(self, registrant):
        """The registrant's current value for each detail field, via the
        detail model's own prefill mapping."""
        mapping = request.env["spp.cr.detail.edit_individual"].sudo()._get_prefill_mapping()
        registrant = registrant.sudo()
        return {detail_field: registrant[partner_field] for detail_field, partner_field in mapping.items()}

    @staticmethod
    def _display(value):
        if not value:
            return ""
        if hasattr(value, "_name"):  # vocabulary code
            return value.display or value.code
        return str(value)

    def _rows(self, cr):
        detail = cr.get_detail()
        current = self._current_values(cr.registrant_id)
        rows = []
        for name, label, _kind in FIELDS:
            before = self._display(current.get(name))
            after = self._display(detail[name]) if detail else ""
            rows.append({"label": label, "current": before, "proposed": after, "changed": before != after})
        return rows

    @staticmethod
    def _state_labels():
        field = request.env["spp.change.request"]._fields["approval_state"]
        return dict(field._description_selection(request.env))

    @http.route(["/my/change-requests"], type="http", auth="user", website=True)
    def portal_my_change_requests(self, **kw):
        return request.render(
            "spp_demo_child_benefit.portal_my_change_requests",
            {
                "change_requests": self._my_change_requests(),
                "state_labels": self._state_labels(),
                "page_name": "change_requests",
            },
        )

    @http.route(["/my/change-requests/new"], type="http", auth="user", website=True)
    def portal_change_request_new(self, registrant_id=None, **kw):
        partner = self._partner()
        members = portal_family_members(request.env, partner)
        registrant = resolve_family_member(registrant_id, members, partner)
        if registrant is None:
            raise BadRequest()
        return request.render(
            "spp_demo_child_benefit.portal_change_request_new",
            {
                "family_members": list(members),
                "registrant": registrant,
                "fields": FIELDS,
                "current": self._current_values(registrant),
                "genders": self._genders(),
                "page_name": "change_requests",
                "change_request": "new",
            },
        )

    def _posted_values(self, kw):
        """The allowlisted, cleaned detail values from the form. Empty inputs
        mean "unchanged" and are skipped, so the prefilled value stays."""
        values = {}
        gender_ids = set(self._genders().ids)
        for name, _label, kind in FIELDS:
            raw = (kw.get(name) or "").strip()
            if not raw:
                continue
            if len(raw) > MAX_LEN:
                raise BadRequest()
            if kind == "date":
                try:
                    values[name] = fields.Date.to_date(raw)
                except ValueError as err:
                    raise BadRequest() from err
            elif kind == "gender":
                try:
                    gender_id = int(raw)
                except ValueError as err:
                    raise BadRequest() from err
                if gender_id not in gender_ids:
                    raise BadRequest()
                values[name] = gender_id
            else:
                values[name] = raw
        return values

    @http.route(["/my/change-requests/submit"], type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def portal_change_request_submit(self, **kw):
        partner = self._partner()
        members = portal_family_members(request.env, partner)
        registrant = resolve_family_member(kw.get("registrant_id"), members, partner)
        if registrant is None:
            raise BadRequest()
        values = self._posted_values(kw)
        cr_type = request.env.ref(CR_TYPE_XMLID)
        # nosemgrep: odoo-sudo-without-context -- portal users hold no access to change requests
        cr = (
            request.env["spp.change.request"]
            .sudo()
            .create(
                {
                    "request_type_id": cr_type.id,
                    "registrant_id": registrant.id,
                    "applicant_id": partner.id,
                    "applicant_phone": partner.phone or False,
                    "description": (kw.get("reason") or "").strip()[:2000] or False,
                    "source_reference": "portal",
                }
            )
        )
        detail = cr.get_detail()
        detail.prefill_from_registrant()
        if values:
            detail.write(values)
        cr.action_submit_for_approval()
        # nosemgrep: odoo-unvalidated-redirect -- fixed internal URL with our own record id
        return request.redirect(f"/my/change-requests/{cr.id}")

    @http.route(["/my/change-requests/<int:cr_id>"], type="http", auth="user", website=True)
    def portal_change_request_detail(self, cr_id, **kw):
        cr = self._my_change_requests().filtered(lambda c: c.id == cr_id)
        if not cr:
            raise NotFound()
        review = cr.approval_review_ids.sorted("id")[-1:] if cr.approval_review_ids else cr.approval_review_ids
        return request.render(
            "spp_demo_child_benefit.portal_change_request_detail",
            {
                "change_request": cr,
                "rows": self._rows(cr),
                "state_label": self._state_labels().get(cr.approval_state, cr.approval_state),
                "review_comment": review.comment if review else "",
                "page_name": "change_requests",
                "change_request_detail": True,
            },
        )
