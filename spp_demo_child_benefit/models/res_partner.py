# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class ResPartnerPhoneSync(models.Model):
    """Keep a registrant's Phone Numbers table in step with the phone field.

    The registry stores phone numbers as lines (``phone_number_ids``); the
    ``phone`` field is only the display string those lines refresh. A change
    request's field mapping, and the phone field on the registrant form, write
    ``phone`` directly, so the number never reached the table. Every number
    written to ``phone`` on a registrant now gets its line, unless it is
    already there.

    The value is read before the write runs: other partner extensions rewrite
    the values as they go and ``phone`` is not guaranteed to survive them.
    """

    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        phones = [vals.get("phone") if vals.get("is_registrant") else None for vals in vals_list]
        partners = super().create(vals_list)
        for partner, phone in zip(partners, phones, strict=True):
            if phone:
                partner._sync_phone_number_lines(phone)
        return partners

    def write(self, vals):
        phone = vals.get("phone") if "phone_number_ids" not in vals else None
        result = super().write(vals)
        if phone:
            self.filtered("is_registrant")._sync_phone_number_lines(phone)
        return result

    def _sync_phone_number_lines(self, phone):
        numbers = [number.strip() for number in str(phone).split(",") if number.strip()]
        PhoneNumber = self.env["spp.phone.number"]
        for partner in self:
            existing = set(
                PhoneNumber.search([("partner_id", "=", partner.id), ("disabled", "=", False)]).mapped("phone_no")
            )
            missing = [number for number in numbers if number not in existing]
            if missing:
                PhoneNumber.create([{"partner_id": partner.id, "phone_no": number} for number in missing])
