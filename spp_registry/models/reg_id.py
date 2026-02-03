# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Pattern for validating namespace URIs per ADR-007 (lowercase only)
NAMESPACE_URI_PATTERN = r"^urn:[a-z0-9][a-z0-9-]*:[a-z0-9._-]+(?::[a-z0-9._-]+)*$"


class SPPRegistrantID(models.Model):
    _name = "spp.registry.id"
    _description = "Registrant ID"
    _order = "id desc"

    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        required=True,
        index=True,
        domain=[("is_registrant", "=", True)],
    )
    available_id_type_ids = fields.Many2many("spp.vocabulary.code", compute="_compute_available_id_type_ids")
    id_type_id = fields.Many2one("spp.vocabulary.code", "ID Type", required=True)
    value = fields.Char(size=100)

    expiry_date = fields.Date()
    id_type_as_str = fields.Char(related="id_type_id.display")
    namespace_uri = fields.Char(
        related="id_type_id.namespace_uri",
        store=True,
        index=True,
        string="Namespace",
    )

    status = fields.Selection([("invalid", "Invalid"), ("valid", "Valid")])

    description = fields.Char()

    _unique_partner_id_type = models.Constraint(
        "UNIQUE(partner_id, id_type_id)",
        "A registrant cannot have duplicate ID types",
    )

    def _compute_available_id_type_ids(self):
        for rec in self:
            domain = [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:id-type")]
            if rec.partner_id.is_group:
                domain.append(("target_type", "in", ["group", "both"]))
            else:
                domain.append(("target_type", "in", ["individual", "both"]))
            id_type_ids = self.env["spp.vocabulary.code"].search(domain)
            rec.available_id_type_ids = id_type_ids

    def _compute_display_name(self):
        res = super()._compute_display_name()
        for rec in self:
            name = ""
            if rec.partner_id:
                name = rec.partner_id.name
            rec.display_name = name
        return res

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=100, order=None):
        domain = domain or []
        if name:
            domain = [("partner_id", operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    @api.constrains("value")
    @api.onchange("value")
    def _onchange_id_validation(self):
        for rec in self:
            if not rec.value:
                return
            if rec.id_type_id.id_validation:
                if not re.match(rec.id_type_id.id_validation, rec.value):
                    raise ValidationError(
                        _(
                            "The provided %(id_type)s ID '%(value)s' is invalid.",
                            id_type=rec.id_type_id.name,
                            value=rec.value,
                        )
                    )


class SPPIDType(models.Model):
    _name = "spp.id.type"
    _description = "ID Type"
    _order = "name ASC"

    name = fields.Char()
    id_validation = fields.Char()
    namespace_uri = fields.Char(
        string="Namespace URI",
        index=True,
        copy=False,
        help="Globally unique URI identifying this ID type. " "Example: urn:gov:ph:psa:national-id",
    )

    _unique_namespace_uri = models.Constraint("UNIQUE(namespace_uri)", "Namespace URI must be unique")

    @api.model_create_multi
    def create(self, vals_list):
        """Normalize namespace_uri to lowercase on create."""
        for vals in vals_list:
            if vals.get("namespace_uri"):
                vals["namespace_uri"] = vals["namespace_uri"].lower().strip()
        return super().create(vals_list)

    def write(self, vals):
        """Normalize namespace_uri to lowercase on write."""
        if vals.get("namespace_uri"):
            vals["namespace_uri"] = vals["namespace_uri"].lower().strip()
        return super().write(vals)

    @api.constrains("namespace_uri")
    def _check_namespace_uri_format(self):
        """Validate namespace URI format per ADR-007."""
        for rec in self:
            if rec.namespace_uri and not re.match(NAMESPACE_URI_PATTERN, rec.namespace_uri):
                raise ValidationError(
                    _(
                        "Invalid namespace URI format: %(uri)s\n"
                        "Expected: urn:{namespace}:{type} (e.g., urn:gov:ph:psa:national-id)",
                        uri=rec.namespace_uri,
                    )
                )

    @api.constrains("name")
    def _check_name(self):
        """Validate name is not empty and is unique (case-sensitive)."""
        for record in self:
            if not record.name:
                raise ValidationError(_("ID type name should not be empty."))

            # Use case-sensitive uniqueness to avoid false positives when
            # tests intentionally create differently-cased ID type names
            # (e.g., "NATIONAL ID" versus "National ID").
            duplicate = self.search(
                [
                    ("name", "=", record.name),
                    ("id", "!=", record.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(_("ID type already exists"))
