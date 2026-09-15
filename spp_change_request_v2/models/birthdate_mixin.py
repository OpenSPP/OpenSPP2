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

    def _is_future_birthdate(self, birthdate):
        """Return whether ``birthdate`` is later than this user's today.

        Shared with the callers that must avoid *offering* a value the
        constraint would refuse — prefilling a change request from a
        registrant that predates the guard — so the two cannot disagree.
        """
        return bool(birthdate) and birthdate > fields.Date.context_today(self)

    def _birthdate_record_name(self):
        """Return the person's name for the error message, when there is one.

        The inheriting models are all half-filled forms: a new group member
        line has no database identity, so ``display_name`` would name the
        model rather than the person. The given/family names all four of them
        carry are what tells the user which line to fix.
        """
        self.ensure_one()
        parts = [self[field] for field in ("given_name", "family_name") if field in self._fields and self[field]]
        return " ".join(parts)

    @api.constrains("birthdate")
    def _check_birthdate_not_future(self):
        for record in self:
            if not record._is_future_birthdate(record.birthdate):
                continue
            name = record._birthdate_record_name()
            if name:
                raise ValidationError(
                    _(
                        "Date of birth cannot be in the future: %(name)s has %(date)s.",
                        name=name,
                        date=record.birthdate,
                    )
                )
            raise ValidationError(_("Date of birth cannot be in the future: %(date)s.", date=record.birthdate))
