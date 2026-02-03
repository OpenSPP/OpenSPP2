# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
import textwrap

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
_type_model = "spp.area.type"


class OpenSPPArea(models.Model):
    """
    Represents an area in the OpenSPP system.

    This model defines the structure and behavior of geographical areas,
    including their hierarchical relationships, names, codes, and other attributes.
    """

    _name = "spp.area"
    _description = "Area"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "parent_id,name"

    parent_id = fields.Many2one(_name, "Parent")
    complete_name = fields.Char(compute="_compute_complete_name", recursive=True, translate=True)
    name = fields.Char(translate=True, compute="_compute_name", store=True)
    draft_name = fields.Char(required=True, translate=True)
    parent_path = fields.Char(index=True)
    code = fields.Char()
    altnames = fields.Char("Alternate Name")
    level = fields.Integer(help="This is the area level for importing")
    area_level = fields.Integer(compute="_compute_area_level", store=True, help="This is the main area level")
    child_ids = fields.One2many(_name, "parent_id", "Child", compute="_compute_get_childs")
    area_type_id = fields.Many2one(_type_model, string="Area Type")
    area_sqkm = fields.Float("Area (sq/km)")
    tag_ids = fields.Many2many(
        "spp.area.tag",
        "spp_area_tag_rel",
        "area_id",
        "tag_id",
        string="Area Tags",
    )

    _code_unique = models.Constraint("unique (code)", "Code is already exists!")

    @api.depends("draft_name", "code")
    def _compute_name(self):
        """
        Compute the name for the area to include the code.

        The name is set as a combination of the code (if present) and the draft name.
        """
        for rec in self:
            name = rec.draft_name or ""

            if rec.code:
                name = f"{name} ({rec.code})"

            rec.name = name

    def _compute_get_childs(self):
        """
        Compute the child areas of the current area.

        This method searches for all areas that have the current area as their parent
        and assigns them to the child_ids field.
        """
        for rec in self:
            child_ids = self.env[self._name].search([("parent_id", "=", rec.id)])
            rec.child_ids = child_ids

    @api.depends("parent_id")
    def _compute_area_level(self):
        """
        Compute the area level based on the parent area.

        If the area has a parent, its level is set to the parent's level plus one.
        If it doesn't have a parent, its level is set to 0.
        """
        for rec in self:
            if rec.parent_id:
                rec.area_level = rec.parent_id.area_level + 1
            else:
                rec.area_level = 0

    @api.onchange("parent_id")
    def _onchange_parent_id(self):
        """
        Validate the area level when the parent area changes.

        Raises a ValidationError if the resulting area level would exceed 10.
        """
        for rec in self:
            if rec.area_level > 10:
                raise ValidationError(
                    _(
                        textwrap.fill(
                            textwrap.dedent(
                                """Max level exceeded! Can't have area with level greater
                        than 10 and your current area is level {}."""
                            ).format(rec.area_level)
                        )
                    )
                )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        """
        Compute the complete name of the area.

        The complete name includes the parent's complete name (if any) and the area's own name.
        """
        for rec in self:
            if rec.id:
                if rec.parent_id:
                    rec.complete_name = f"{rec.parent_id.complete_name} > {rec.name}"
                else:
                    rec.complete_name = rec.name
            else:
                rec.complete_name = None

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create a new area record.

        This method overrides the default create method to add additional validation
        and translation handling.

        :param vals_list: List of dictionaries with values for the new records.
        :return: The newly created area records.
        :raises ValidationError: If an area with the same name and code already exists.
        """
        # Validate each area before creation
        for vals in vals_list:
            area_name = vals.get("name", self.name)
            area_code = vals.get("code", self.code)
            curr_area = self.env[self._name].search(
                [
                    ("name", "=", area_name),
                    ("code", "=", area_code),
                ]
            )
            if curr_area:
                raise ValidationError(_("Area already exist!"))

        # Create all areas
        areas = super().create(vals_list)

        # Create translation records for each area
        languages = self.env["res.lang"].search([("active", "=", True)])
        for area_val in areas:
            trans_vals_list = []
            for lang_code in languages:
                trans_vals_list.append(
                    {
                        "name": "spp.area,draft_name",
                        "lang": lang_code.code,
                        "res_id": area_val.id,
                        "src": area_val.draft_name,
                        "value": None,
                        "state": "to_translate",
                        "type": "model",
                    }
                )

        return areas

    def write(self, vals):
        """
        Update an existing area record.

        This method overrides the default write method to add additional validation.

        :param vals: The values to update.
        :return: The result of the write operation.
        :raises ValidationError: If an area with the same name and code already exists.
        """
        for rec in self:
            domain = []
            if "name" in vals:
                domain.append(("name", "=", vals["name"]))
            if "code" in vals:
                domain.append(("code", "=", vals["code"]))

            if domain:
                domain.append(("id", "!=", rec.id))
                curr_area = self.env[self._name].search(domain)
                if curr_area:
                    raise ValidationError(_("Area already exist!"))

        return super().write(vals)

    def open_area_form(self):
        """
        Open the form view of the area.

        :return: A dictionary containing the action to open the area form view.
        """
        for rec in self:
            return {
                "name": "Area",
                "view_mode": "form",
                "res_model": self._name,
                "res_id": rec.id,
                "view_id": self.env.ref("spp_area.view_spparea_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "flags": {"mode": "readonly"},
            }


class OpenSPPAreaType(models.Model):
    """
    Represents the type of an area in the OpenSPP system.

    This model defines the structure and behavior of area types, including
    their hierarchical relationships and names.
    """

    _name = _type_model
    _description = "Area Type"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "parent_id,name"

    parent_id = fields.Many2one(_type_model, "Parent")
    parent_path = fields.Char(index=True)
    name = fields.Char(required=True)
    complete_name = fields.Char(compute="_compute_complete_name", recursive=True, translate=True, store=True)

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        """
        Compute the complete name of the area type.

        The complete name includes the parent's complete name (if any) and the area type's own name.
        """
        for rec in self:
            if rec.id:
                if rec.parent_id:
                    rec.complete_name = f"{rec.parent_id.complete_name} > {rec.name}"
                else:
                    rec.complete_name = rec.name
            else:
                rec.complete_name = None

    def unlink(self):
        """
        Delete an area type record.

        This method overrides the default unlink method to add additional validation.
        It prevents the deletion of default area types and area types that are in use.

        :raises ValidationError: If trying to delete a default area type or an area type in use.
        """
        for rec in self:
            external_identifier = self.env["ir.model.data"].search(
                [("res_id", "=", rec.id), ("model", "=", _type_model)]
            )
            if external_identifier and external_identifier.name:
                raise ValidationError(_("Can't delete default Area Type"))
            else:
                areas = self.env["spp.area"].search([("area_type_id", "=", rec.id)])
                if areas:
                    raise ValidationError(_("Can't delete used Area Type"))
                else:
                    return super().unlink()

    def write(self, vals):
        """
        Update an existing area type record.

        This method overrides the default write method to prevent editing of default area types.

        :param vals: The values to update.
        :return: The result of the write operation.
        """
        for rec in self:
            external_identifier = self.env["ir.model.data"].search(
                [("res_id", "=", rec.id), ("model", "=", _type_model)]
            )
            if external_identifier and external_identifier.name:
                vals = {}
            return super().write(vals)

    def update_parent(self):
        for rec in self:
            if rec.parent_name and rec.parent_code:
                parent_id = self.env[_type_model].search(
                    [
                        ("code", "=", rec.parent_code),
                    ],
                    limit=1,
                )
                if parent_id:
                    rec.parent_id = parent_id.id


class SPPAreaTag(models.Model):
    """
    Classification tags for areas (e.g., urban, remote, priority).

    These tags provide a data-driven way to categorize areas that can be
    reused in CEL expressions, reporting, and access rules.
    """

    _name = "spp.area.tag"
    _description = "Area Tag"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index")
    area_ids = fields.Many2many(
        "spp.area",
        "spp_area_tag_rel",
        "tag_id",
        "area_id",
        string="Areas",
        readonly=True,
    )

    _code_unique = models.Constraint("unique(code)", "Area tag code must be unique.")
