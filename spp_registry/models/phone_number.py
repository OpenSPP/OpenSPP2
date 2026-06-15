# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, exceptions, fields, models

try:
    from odoo.addons.phone_validation.tools import phone_validation
except ImportError:
    phone_validation = None

_logger = logging.getLogger(__name__)


class SPPPhoneNumber(models.Model):
    _name = "spp.phone.number"
    _description = "Phone Number"
    _order = "id desc"
    _rec_name = "phone_no"

    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        required=True,
        index=True,
        domain=[("is_registrant", "=", True)],
    )
    phone_no = fields.Char("Phone Number", required=True, index=True)
    phone_sanitized = fields.Char(compute="_compute_phone_sanitized", store=True)
    date_collected = fields.Date(
        default=fields.Date.today,
    )
    disabled = fields.Datetime("Date Disabled")
    disabled_by = fields.Many2one("res.users")
    country_id = fields.Many2one("res.country", "Country")

    def init(self):
        """Create trigram index for phone number ILIKE search."""
        self.env.cr.execute("""
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX IF NOT EXISTS spp_phone_number_phone_no_trgm_idx
                ON spp_phone_number USING gin (phone_no gin_trgm_ops);
        """)

    @api.onchange("date_collected")
    def _check_date_collected(self):
        for record in self:
            if record.date_collected and record.date_collected > fields.Date.today():
                raise exceptions.ValidationError(_("Date collected cannot be in the future."))

    @api.depends("phone_no", "country_id")
    def _compute_phone_sanitized(self):
        for rec in self:
            rec.phone_sanitized = ""
            if rec.phone_no:
                number = rec["phone_no"]
                try:
                    sanitized = rec._phone_format(
                        number=number,
                        country=rec.country_id,
                        force_format="E164",
                        raise_exception=False,
                    )
                    if sanitized:
                        rec.phone_sanitized = str(sanitized)
                except Exception as e:
                    _logger.debug("Failed to sanitize phone number: %s", str(e))
                    rec.phone_sanitized = ""

    @api.onchange("phone_no", "country_id")
    def _onchange_phone_validation(self):
        if not self.phone_no:
            return
        formatted_phone = self._phone_format(number=self.phone_no, country=self.country_id)
        if formatted_phone:
            self.phone_no = formatted_phone
        _logger.debug("Phone number validation completed")

    def _phone_format(self, number, country=None, force_format="INTERNATIONAL", raise_exception=False):
        """Format phone number using Odoo's phone_validation tools.

        Args:
            number: Phone number to format
            country: res.country record
            force_format: Format type (INTERNATIONAL, E164, etc.)
            raise_exception: Whether to raise exception on error

        Returns:
            Formatted phone number or None/original number on error
        """
        if not phone_validation:
            _logger.warning("phone_validation module not available, returning original number")
            return number if not raise_exception else None

        try:
            country_param = country or self.country_id or self.env.company.country_id
            return phone_validation.phone_format(
                number,
                country_param.code if country_param else None,
                country_param.phone_code if country_param else None,
                force_format=force_format,
                raise_exception=raise_exception,
            )
        except Exception as e:
            _logger.debug("Failed to format phone number: %s", str(e))
            if raise_exception:
                raise
            return number

    def disable_phone(self):
        for rec in self:
            if not rec.disabled:
                rec.update(
                    {
                        "disabled": fields.Datetime.now(),
                        "disabled_by": self.env.user,
                    }
                )

    def enable_phone(self):
        for rec in self:
            if rec.disabled:
                rec.update(
                    {
                        "disabled": None,
                        "disabled_by": None,
                    }
                )
