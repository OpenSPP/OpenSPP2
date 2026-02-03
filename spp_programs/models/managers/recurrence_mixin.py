# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models

from odoo.addons.calendar.models import calendar_recurrence


class RecurrenceMixin(models.Model):
    """Cycle Recurrence mixin."""

    _name = "spp.cycle.recurrence.mixin"
    _description = "Cycle Recurrence Mixin"
    _inherit = "calendar.recurrence"

    # Overwrite field to add readonly to False
    name = fields.Char(required=True, readonly=False)

    # Overwrite field from calendar.recurrence to define string and re-define default value
    rrule_type = fields.Selection(
        calendar_recurrence.RRULE_TYPE_SELECTION,
        string="Recurrence",
        default="monthly",
        help="Let the event automatically repeat at that interval",
        readonly=False,
        required=True,
    )

    # Overwrite field from calendar.recurrence to define default value
    byday = fields.Selection(calendar_recurrence.BYDAY_SELECTION, string="By day", default="1")

    # Overwrite field from calendar.recurrence to define default value
    count = fields.Integer(default=10)

    # Overwrite field from calendar.recurrence to add compute argument,
    #  store = True, and re-define default value
    interval = fields.Integer(default=1, compute="_compute_interval", store=True)

    # Computed field for month-end warning display
    day_warning = fields.Char(compute="_compute_day_warning")

    @api.depends("day")
    def _compute_day_warning(self):
        for rec in self:
            if rec.day and rec.day > 28:
                rec.day_warning = _(
                    "Day %d doesn't exist in all months. Cycles will use the last day of shorter months "
                    "(e.g., Feb 28 instead of Feb %d)."
                ) % (rec.day, rec.day)
            else:
                rec.day_warning = False

    @api.onchange("day")
    def _onchange_day(self):
        """Validate day of month to valid range (1-31)."""
        if self.day and (self.day <= 0 or self.day > 31):
            self.day = 1
            return {
                "warning": {
                    "title": _("Invalid Day of Month"),
                    "message": _("Day of Month must be between 1 and 31. It has been reset to 1."),
                }
            }

    # Overwrite to always return False
    def _is_allday(self):
        return False

    def _get_recurrent_field_values(self):
        for rec in self:
            return {
                "byday": rec.byday,
                "until": rec.until,
                "rrule_type": rec.rrule_type,
                "month_by": rec.month_by,
                "event_tz": rec.event_tz,
                "rrule": rec.rrule,
                "interval": rec.interval,
                "count": rec.count,
                "end_type": rec.end_type,
                "mon": rec.mon,
                "tue": rec.tue,
                "wed": rec.wed,
                "thu": rec.thu,
                "fri": rec.fri,
                "sat": rec.sat,
                "sun": rec.sun,
                "day": rec.day,
                "weekday": rec.weekday,
            }

    def _compute_interval(self):
        """
        Copy value of a field to interval
        """
        raise NotImplementedError()

    def _compute_name(self):
        # Overwrite this function of calendar.recurrence to do nothing
        pass

    def _inverse_rrule(self):
        # Overwrite this function of calendar.recurrence to do nothing
        pass
