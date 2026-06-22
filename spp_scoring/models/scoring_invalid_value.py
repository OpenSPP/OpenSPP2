"""Curated list of values that should be treated as missing during
scoring (e.g. ``'No Birthdate!'`` returned by computed fields when their
underlying source is empty). Each entry can match either an exact string
or a regular-expression pattern — useful for catching whole *ranges* of
sentinel values (e.g. ``^N/A.*$``, ``^Not\\s*Provided$``) without
enumerating every variation. Applies globally across every indicator
that selects the entry; each scoring run fetches the active set once
and matches every read field value against it. Toggle ``active`` to
retire a sentinel without losing the audit trail."""

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SppScoringInvalidValue(models.Model):
    _name = "spp.scoring.invalid.value"
    _description = "Scoring Invalid Value"
    _order = "name"

    name = fields.Char(
        string="Value",
        required=True,
        help=(
            "When Match Type is **Exact**, the literal string that should be "
            "treated as missing during scoring (whitespace-trimmed). When "
            "Match Type is **Regex**, a Python regular-expression pattern; "
            "the value is treated as missing when ``re.fullmatch`` succeeds."
        ),
    )
    match_type = fields.Selection(
        [
            ("exact", "Exact"),
            ("regex", "Regex"),
        ],
        default="exact",
        required=True,
        help=(
            "**Exact** — match the literal string in **Value**, "
            "whitespace-trimmed.\n"
            "**Regex** — interpret **Value** as a Python regular-expression "
            "pattern; covers a *range* of sentinel values without enumerating "
            "every one (e.g. ``^N/A.*$`` to catch ``N/A``, ``N/A!``, ``N/A — "
            "missing``)."
        ),
    )
    description = fields.Char(
        help="Optional note explaining why this value is treated as invalid.",
    )
    active = fields.Boolean(
        default=True,
        help=(
            "Untick to disable this entry without deleting it — useful when "
            "a previously-invalid value should be accepted as real data "
            "going forward."
        ),
    )

    _name_uniq = models.Constraint(
        "unique(name)",
        "An invalid-value entry with this string already exists.",
    )

    @api.constrains("name", "match_type")
    def _check_regex_compiles(self):
        """Reject regex entries whose pattern doesn't compile — otherwise
        the scoring engine would explode for every registrant on every run."""
        for rec in self:
            if rec.match_type != "regex" or not rec.name:
                continue
            try:
                re.compile(rec.name)
            except re.error as exc:
                raise ValidationError(
                    _(
                        "Invalid regex pattern in entry '%(name)s': %(err)s",
                        name=rec.name,
                        err=str(exc),
                    )
                ) from exc
