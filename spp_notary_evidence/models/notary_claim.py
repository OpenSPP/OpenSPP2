# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Notary claim catalog model."""

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    _inherit = ["mail.thread", "mail.activity.mixin"]
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
    claim_version = fields.Char(index=True, tracking=True)
    pinned_version = fields.Char(
        string="Pinned Version",
        tracking=True,
        help="Optional Notary claim version to request. Leave empty to request the latest upstream version.",
    )
    name = fields.Char(string="Name", required=True, tracking=True)
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
    default_disclosure = fields.Char(default="predicate", tracking=True)
    default_purpose_url = fields.Char(tracking=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("deprecated", "Deprecated"),
            ("unavailable", "Unavailable"),
            ("version_drift", "Version Drift"),
            ("needs_alias", "Needs Alias"),
        ],
        default="active",
        required=True,
        tracking=True,
    )
    variable_name = fields.Char(
        compute="_compute_variable_name",
        store=True,
        readonly=True,
        index=True,
    )
    evidence_accessor = fields.Char(
        string="CEL Evidence Path",
        compute="_compute_evidence_accessor",
        help="User-facing CEL path for this Notary claim, for example "
        "r.evidence.registry_lab_civil_notary.person_is_alive.",
    )
    variable_id = fields.Many2one(
        comodel_name="spp.cel.variable",
        string="CEL Variable",
        ondelete="set null",
        copy=False,
        tracking=True,
    )
    effective_purpose_url = fields.Char(
        string="Effective Purpose URL",
        compute="_compute_effective_purpose_url",
        help="Purpose URL used for Notary evaluation before evaluation-context overrides.",
    )
    last_synced_at = fields.Datetime()
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="provider_id.company_id",
        store=True,
        readonly=True,
    )

    _unique_claim_provider_external = models.Constraint(
        "UNIQUE(provider_id, external_id)",
        "Notary claim external ID must be unique per provider.",
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

    @api.depends("provider_id.code", "provider_id.name", "external_id")
    def _compute_evidence_accessor(self):
        for claim in self:
            claim.evidence_accessor = claim._evidence_accessor("r") if claim.provider_id and claim.external_id else ""

    @api.depends("default_purpose_url", "provider_id.notary_default_purpose_url")
    def _compute_effective_purpose_url(self):
        for claim in self:
            claim.effective_purpose_url = claim.default_purpose_url or claim.provider_id.notary_default_purpose_url

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_cel_variable()
        return records

    def write(self, vals):
        if {"external_id", "provider_id"} & set(vals):
            self._check_active_expression_rename_safety()
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

    def _evidence_provider_code(self):
        self.ensure_one()
        return self._slug_part(self.provider_id.code or self.provider_id.name)

    def _evidence_claim_code(self):
        self.ensure_one()
        return self._slug_part(self.external_id)

    def _evidence_accessor(self, subject_alias="r"):
        self.ensure_one()
        return f"{subject_alias}.evidence.{self._evidence_provider_code()}.{self._evidence_claim_code()}"

    def _ensure_cel_variable(self):
        Variable = self.env["spp.cel.variable"]
        claims = self.filtered("variable_name")
        if not claims:
            return

        claims_with_variable = claims.filtered("variable_id")
        for claim in claims_with_variable:
            claim.variable_id.write(claim._cel_variable_values())

        claims_without_variable = claims - claims_with_variable
        existing_by_name = {
            variable.name: variable
            for variable in Variable.search([("name", "in", claims_without_variable.mapped("variable_name"))])
        }
        create_vals_list = []
        create_claims = self.browse()
        for claim in claims_without_variable:
            vals = claim._cel_variable_values()
            variable = existing_by_name.get(claim.variable_name)
            if variable:
                variable.write(vals)
                claim.variable_id = variable.id
            else:
                create_vals_list.append(vals)
                create_claims |= claim
        if create_vals_list:
            for claim, variable in zip(create_claims, Variable.create(create_vals_list), strict=False):
                claim.variable_id = variable.id

    def _cel_variable_values(self):
        self.ensure_one()
        return {
            "name": self.variable_name,
            "cel_accessor": self.variable_name,
            "source_type": "external",
            "external_provider_id": self.provider_id.id,
            "value_type": self.value_type,
            "applies_to": self.subject_type if self.subject_type in ("individual", "group") else "both",
            "state": "active" if self.active and self.state in ("active", "version_drift") else "inactive",
            "active": bool(self.active and self.state in ("active", "version_drift")),
            "cache_strategy": "ttl",
            "cache_ttl_seconds": self.provider_id.notary_default_ttl_seconds or self.provider_id.default_ttl_seconds,
            "notary_claim_id": self.id,
            "notary_value_path": "value",
        }

    def _check_active_expression_rename_safety(self):
        Expression = self.env["spp.cel.expression"]
        for claim in self:
            if not claim.variable_id:
                continue
            expression = Expression.search(
                [
                    ("state", "=", "active"),
                    ("variable_ids", "in", claim.variable_id.id),
                ],
                limit=1,
            )
            if expression:
                raise UserError(
                    _(
                        "Cannot rename Notary claim '%(claim)s' because active CEL expression '%(expression)s' "
                        "references accessor '%(accessor)s'."
                    )
                    % {
                        "claim": claim.display_name,
                        "expression": expression.display_name,
                        "accessor": claim.variable_id.cel_accessor or claim.variable_name,
                    }
                )


def normalize_notary_value_type(value_type):
    normalized = VALUE_TYPE_ALIASES.get(str(value_type or "").lower(), str(value_type or "string").lower())
    return normalized if normalized in CEL_VALUE_TYPES else "string"


def data_value_type_for_cel(value_type):
    if value_type in DATA_VALUE_TYPES:
        return value_type
    if value_type in {"date", "money"}:
        return "string"
    return "json"
