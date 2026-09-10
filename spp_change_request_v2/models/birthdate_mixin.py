# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared guard against a proposed date of birth in the future.

``res.partner`` refuses a future ``birthdate`` on every write path
(``spp_registry/models/individual.py::_check_birthdate_not_future``), but a
change request stores its proposed birthdate on its own detail and wizard
models first. Without the same guard there the value is only refused when a
strategy writes it to ``res.partner`` at apply time — which rolls back the
whole approval and reports an error the approver cannot trace back to a
field. Mixing this in catches it at data entry instead.

Inheriting models must define a ``birthdate`` date field; the mixin
deliberately does not, so it stays a pure behaviour mixin with no schema
footprint of its own.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPCRBirthdateMixin(models.AbstractModel):
    _name = "spp.cr.birthdate.mixin"
    _description = "Change Request Birthdate Guard Mixin"

    @api.constrains("birthdate")
    def _check_birthdate_not_future(self):
        for record in self:
            if record.birthdate and record.birthdate > fields.Date.context_today(record):
                raise ValidationError(_("Date of birth cannot be in the future: %(date)s.", date=record.birthdate))
