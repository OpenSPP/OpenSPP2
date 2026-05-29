# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Notary claim catalog model."""

import re

from odoo import api, fields, models

CEL_VALUE_TYPES = {"number", "boolean", "string", "date", "money", "list"}
DATA_VALUE_TYPES = {"number", "boolean", "string", "json"}
VALUE_TYPE_ALIASES = {
    "bool": "boolean",
    "integer": "number",
    "float": "number",
    "decimal": "number",
    "text": "string",
    "object": "list",
    "array": "list",
    "json": "list",
}


class NotaryClaim(models.Model):
    """Catalog row for a claim exposed by a Registry Notary provider."""

    _name = "spp.notary.claim"
    _description = "Notary Claim"
    _order = "provider_id, external_id"

    provider_id = fields.Many2one(
        comodel_name="spp.data.provider",
        string="Provider",
        required=True,
        index=True,
        ondelete="cascade",
        domain=[("provider_kind", "=", "notary")],
    )
    external_id = fields.Char(
        string="Claim ID",
        required=True,
        index=True,
        help="Stable upstream identifier for this Notary claim.",
    )
    claim_version = fields.Char(index=True)
    pinned_version = fields.Boolean(default=True)
    name = fields.Char(string="Name", required=True)
    description = fields.Text()
    subject_type = fields.Selection(
        selection=[
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Both"),
        ],
        default="individual",
        required=True,
    )
    value_type = fields.Selection(
        selection=[
            ("number", "Number"),
            ("boolean", "Yes/No"),
            ("string", "Text"),
            ("date", "Date"),
            ("money", "Money"),
            ("list", "List"),
        ],
        default="string",
        required=True,
    )
    default_disclosure = fields.Char(default="predicate")
    default_purpose_url = fields.Char()
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("deprecated", "Deprecated"),
            ("unavailable", "Unavailable"),
        ],
        default="active",
        required=True,
    )
    variable_name = fields.Char(
        compute="_compute_variable_name",
        store=True,
        readonly=True,
        index=True,
    )
    variable_id = fields.Many2one(
        comodel_name="spp.cel.variable",
        string="CEL Variable",
        ondelete="set null",
        copy=False,
    )
    last_synced_at = fields.Datetime()
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="provider_id.company_id",
        store=True,
        readonly=True,
    )

    _unique_claim_provider_external_version = models.Constraint(
        "UNIQUE(provider_id, external_id, claim_version)",
        "Notary claim external ID/version must be unique per provider.",
    )
    _unique_claim_provider_variable = models.Constraint(
        "UNIQUE(provider_id, variable_name)",
        "Notary claim variable name must be unique per provider.",
    )

    @api.depends("provider_id.code", "provider_id.name", "external_id")
    def _compute_variable_name(self):
        for claim in self:
            provider_name = claim.provider_id.code or claim.provider_id.name or ""
            claim.variable_name = self._build_variable_name(provider_name, claim.external_id or "")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_cel_variable()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"external_id", "provider_id", "value_type", "subject_type", "active", "state", "claim_version"} & set(vals):
            self._ensure_cel_variable()
        return result

    @api.model
    def _build_variable_name(self, provider_name, claim_external_id):
        parts = ["notary", provider_name, claim_external_id]
        variable_name = "_".join(part for part in (self._slug_part(part) for part in parts) if part)
        if not variable_name:
            return "notary_claim"
        if variable_name[0].isdigit():
            variable_name = f"notary_{variable_name}"
        return variable_name

    @api.model
    def _slug_part(self, value):
        value = str(value or "").strip().lower()
        value = re.sub(r"[^a-z0-9]+", "_", value)
        return value.strip("_")

    def _ensure_cel_variable(self):
        Variable = self.env["spp.cel.variable"]
        for claim in self:
            if not claim.variable_name:
                continue
            vals = {
                "name": claim.variable_name,
                "cel_accessor": claim.variable_name,
                "source_type": "external",
                "external_provider_id": claim.provider_id.id,
                "value_type": claim.value_type,
                "applies_to": claim.subject_type if claim.subject_type in ("individual", "group") else "both",
                "state": "active" if claim.active and claim.state == "active" else "inactive",
                "active": bool(claim.active and claim.state == "active"),
                "cache_strategy": "ttl",
                "cache_ttl_seconds": claim.provider_id.notary_default_ttl_seconds
                or claim.provider_id.default_ttl_seconds,
                "notary_claim_id": claim.id,
                "notary_value_path": "value",
            }
            if claim.variable_id:
                claim.variable_id.write(vals)
            else:
                variable = Variable.search([("name", "=", claim.variable_name)], limit=1)
                if variable:
                    variable.write(vals)
                else:
                    variable = Variable.create(vals)
                claim.variable_id = variable.id


def normalize_notary_value_type(value_type):
    normalized = VALUE_TYPE_ALIASES.get(str(value_type or "").lower(), str(value_type or "string").lower())
    return normalized if normalized in CEL_VALUE_TYPES else "string"


def data_value_type_for_cel(value_type):
    if value_type in DATA_VALUE_TYPES:
        return value_type
    if value_type in {"date", "money"}:
        return "string"
    return "json"
