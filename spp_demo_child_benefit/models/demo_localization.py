# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Apply a localization pack to the demo environment.

A pack is a JSON document that renames the generated, country-neutral demo
records so a demonstration can be given in a country's own terms. The packs
themselves are supplied by whoever runs the demo; none ship with this module.

Pack format (every key optional):

    {
      "programme_name": "…",
      "company": {"name": "…", "country": "XX", "logo": "<base64 PNG/JPEG>",
                  "appbar_image": "<base64 PNG, shown at the foot of the apps sidebar>"},
      "theme": {"appbar_background": "#rrggbb", "appbar_text": "…", "appbar_active": "…",
                "appsmenu_text": "…", "brand": "…", "primary": "…",
                "success": "…", "info": "…", "warning": "…", "danger": "…"},
      "currency": "XYZ",
      "banks":   {"National Commercial Bank": "…"},
      "areas":   {"CR-HD-RV": "…"},
      "mothers": ["…", "…"],
      "fathers": ["…", "…"],
      "children": ["…", "…"],
      "family_name_template": "{mother_first} Family ({mother})"
    }
"""

import base64
import binascii
import json
import logging
import re

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ORDINALS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]


class DemoLocalization(models.AbstractModel):
    _name = "spp.demo.localization"
    _description = "Demo Localization Pack Applier"

    def _parse_pack(self, raw):
        try:
            pack = json.loads(raw)
        except (ValueError, TypeError) as err:
            raise UserError(_("The localization pack is not valid JSON: %s") % err) from err
        if not isinstance(pack, dict):
            raise UserError(_("The localization pack must be a JSON object."))
        return pack

    def _apply_company_and_currency(self, pack, program, summary):
        """Company identity (name, country) and the currency shown everywhere
        the demo shows money: company, programme, journal (fund, entitlements
        and cycles relate to those)."""
        env = self.env
        company = env.company
        company_pack = pack.get("company") or {}
        if company_pack.get("name"):
            company.name = company_pack["name"]
            # The company partner is what reports and portal footers display.
            company.partner_id.name = company_pack["name"]
            summary.append(_("company renamed"))
        if company_pack.get("country"):
            country = env["res.country"].search([("code", "=", company_pack["country"].upper())], limit=1)
            if country:
                company.country_id = country.id
                company.partner_id.country_id = country.id
                summary.append(_("country set to %s") % country.name)
        if company_pack.get("logo"):
            # The company logo feeds the login page, the portal header and reports.
            try:
                logo = base64.b64decode(company_pack["logo"], validate=True)
            except (ValueError, binascii.Error) as err:
                raise UserError(_("The localization pack's company logo is not valid base64.")) from err
            company.logo = base64.b64encode(logo)
            summary.append(_("logo set"))
        # Apps-sidebar footer image (a theme field; skipped when the theme is absent).
        if company_pack.get("appbar_image") and "appbar_image" in company._fields:
            try:
                image = base64.b64decode(company_pack["appbar_image"], validate=True)
            except (ValueError, binascii.Error) as err:
                raise UserError(_("The localization pack's sidebar image is not valid base64.")) from err
            company.appbar_image = base64.b64encode(image)
            summary.append(_("sidebar image set"))

        currency_code = pack.get("currency")
        if currency_code:
            currency = (
                env["res.currency"].with_context(active_test=False).search([("name", "=", currency_code)], limit=1)
            )
            if currency:
                if not currency.active:
                    currency.active = True
                # The company currency can only move while no journal items
                # exist; the demo has none until a payment run is posted.
                existing_accounting = getattr(company.root_id, "_existing_accounting", None)
                if company.currency_id != currency and not (existing_accounting and existing_accounting()):
                    company.currency_id = currency.id
                if program:
                    program.currency_id = currency.id
                    if program.journal_id:
                        program.journal_id.currency_id = currency.id
                summary.append(_("currency set to %s") % currency_code)

    # Pack key → res.config.settings field (MuK theme + colour settings, light mode).
    THEME_FIELDS = {
        "appbar_background": "theme_color_appbar_background",
        "appbar_text": "theme_color_appbar_text",
        "appbar_active": "theme_color_appbar_active",
        "appsmenu_text": "theme_color_appsmenu_text",
        "brand": "color_brand_light",
        "primary": "color_primary_light",
        "success": "color_success_light",
        "info": "color_info_light",
        "warning": "color_warning_light",
        "danger": "color_danger_light",
    }
    _HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

    def _apply_theme(self, pack, summary):
        """Back-office colours through the theme's own settings, which rewrite
        the SCSS variables and rebuild the asset bundle. Keys whose settings
        field is not installed are skipped, so the pack works on any stack."""
        theme = pack.get("theme") or {}
        if not theme:
            return
        Settings = self.env["res.config.settings"]
        values = {}
        for key, field in self.THEME_FIELDS.items():
            color = theme.get(key)
            if not color or field not in Settings._fields:
                continue
            if not self._HEX_COLOR.match(color):
                raise UserError(_("Theme colour %(key)s must be a #rrggbb value, got %(value)s.", key=key, value=color))
            values[field] = color.lower()
        if not values:
            return
        settings = Settings.create(values)
        settings.execute()
        summary.append(_("%s theme colour(s) set") % len(values))

    def _refresh_open_change_requests(self, registrant):
        """Re-issue the registrant's pending change requests under their new name.

        A request's detail is prefilled at creation and applied in full on
        approval, so a request created before the pack would write the old name
        back over the localized one. The proposed values are locked once
        submitted (by design), so the request is recreated: same reference,
        type, applicant, description and requested changes, prefilled from the
        renamed registrant, and submitted again by its original author."""
        ChangeRequest = self.env.get("spp.change.request")
        if ChangeRequest is None:
            return
        pending = ChangeRequest.search(
            [("registrant_id", "=", registrant.id), ("approval_state", "in", ("pending", "revision"))]
        )
        for old in pending:
            detail = old.get_detail()
            if not detail or old.request_type_id.apply_strategy != "field_mapping":
                continue
            mapped = [m.source_field for m in old.request_type_id.apply_mapping_ids if m.source_field]
            carried = {
                field: (detail[field].id if hasattr(detail[field], "id") else detail[field])
                for field in mapped
                if field in detail._fields and field not in ("given_name", "family_name") and detail[field]
            }
            vals = {
                "name": old.name,
                "request_type_id": old.request_type_id.id,
                "registrant_id": registrant.id,
                "applicant_id": old.applicant_id.id,
                "applicant_phone": old.applicant_phone,
                "description": old.description,
                "source_reference": old.source_reference,
            }
            author = old.create_uid
            self.env["spp.approval.review"].sudo().search([("model", "=", old._name), ("res_id", "=", old.id)]).unlink()
            old.unlink()
            fresh = ChangeRequest.with_user(author).create(vals)
            fresh_detail = fresh.get_detail()
            fresh_detail.prefill_from_registrant()
            if carried:
                fresh_detail.write(carried)
            fresh.action_submit_for_approval()

    def apply_pack(self, raw):
        """Apply a localization pack. Idempotent — renames already applied are
        simply not found the second time."""
        pack = self._parse_pack(raw)
        env = self.env
        summary = []

        programme_name = pack.get("programme_name")
        program = env["spp.program"].search([("name", "=", "Child Benefit Programme")], limit=1)
        if programme_name and program:
            program.name = programme_name
            summary.append(_("programme renamed"))

        self._apply_company_and_currency(pack, program, summary)
        self._apply_theme(pack, summary)

        for old, new in (pack.get("banks") or {}).items():
            bank = env["res.bank"].search([("name", "=", old)], limit=1)
            if bank:
                bank.name = new
        if pack.get("banks"):
            summary.append(_("%s bank(s) renamed") % len(pack["banks"]))

        for code, name in (pack.get("areas") or {}).items():
            area = env["spp.area"].search([("code", "=", code)], limit=1)
            if area:
                area.draft_name = name
        if pack.get("areas"):
            summary.append(_("%s area(s) renamed") % len(pack["areas"]))

        Partner = env["res.partner"]
        mothers = pack.get("mothers") or []
        fathers = pack.get("fathers") or []
        template = pack.get("family_name_template") or "{mother} Family"
        renamed_people = 0

        def rename_person(record, full_name):
            """Keep the display name AND the given/family name parts in sync.

            Passing the explicit name alongside the parts preserves the natural
            "Given Family" display (the registry would otherwise recompose it
            as "Family, Given")."""
            parts = full_name.split(None, 1)
            record.write(
                {
                    "name": full_name,
                    "given_name": parts[0],
                    "family_name": parts[1] if len(parts) > 1 else "",
                }
            )
            self._refresh_open_change_requests(record)

        for index, ordinal in enumerate(ORDINALS):
            if index < len(mothers):
                mother = Partner.search([("name", "=", f"Mother {ordinal}")], limit=1)
                if mother:
                    rename_person(mother, mothers[index])
                    renamed_people += 1
                family = Partner.search([("name", "=", f"Demo Family {ordinal}")], limit=1)
                if family:
                    family.name = template.format(mother=mothers[index], mother_first=mothers[index].split()[0])
            if index < len(fathers):
                father = Partner.search([("name", "=", f"Father {ordinal}")], limit=1)
                if father:
                    rename_person(father, fathers[index])
                    renamed_people += 1

        children_names = pack.get("children") or []
        if children_names:
            children = Partner.search([("name", "like", "Child %-%"), ("is_group", "=", False)], order="id")
            for index, child in enumerate(children):
                rename_person(child, children_names[index % len(children_names)])
                renamed_people += 1
        if renamed_people:
            summary.append(_("%s person record(s) renamed") % renamed_people)

        _logger.info("Demo localization applied: %s", ", ".join(summary) or "nothing matched")
        return summary
