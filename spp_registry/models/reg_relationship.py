# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPRegistrantRelationship(models.Model):
    _name = "spp.registry.relationship"
    _description = "Registrant Relationship"
    _order = "id desc"
    _inherit = ["mail.thread"]
    _rec_names_search = ["source", "destination"]

    source = fields.Many2one(
        "res.partner",
        required=True,
        domain=[("is_registrant", "=", True)],
    )
    destination = fields.Many2one(
        "res.partner",
        required=True,
        domain=[("is_registrant", "=", True)],
    )
    relation_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Relationship Type",
    )
    available_relation_ids = fields.Many2many(
        "spp.vocabulary.code",
        string="Available Relations",
        compute="_compute_available_relation_ids",
        store=False,
    )
    disabled = fields.Datetime("Date Disabled")
    disabled_by = fields.Many2one("res.users")
    start_date = fields.Datetime()
    end_date = fields.Datetime()
    relation_as_str = fields.Char(
        string="Relationship",
        related="relation_id.display",
        translate=True,
        readonly=True,
    )

    @api.depends("source", "source.is_group", "destination", "destination.is_group")
    def _compute_available_relation_ids(self):
        """Compute available relationship codes based on source and destination types."""
        VocabCode = self.env["spp.vocabulary.code"]

        for rec in self:
            if not rec.source or not rec.destination:
                # Return all relationship codes
                all_codes = VocabCode.search(
                    [
                        (
                            "vocabulary_id.namespace_uri",
                            "=",
                            "urn:openspp:vocab:relationship",
                        )
                    ]
                )
                rec.available_relation_ids = all_codes
                continue

            # Determine the appropriate concept group based on partner types
            source_is_group = rec.source.is_group
            dest_is_group = rec.destination.is_group

            if not source_is_group and not dest_is_group:
                # Individual to Individual
                concept_group_xmlid = "spp_vocabulary.group_rel_individual_to_individual"
            elif source_is_group and dest_is_group:
                # Group to Group
                concept_group_xmlid = "spp_vocabulary.group_rel_group_to_group"
            else:
                # Mixed: Individual to Group
                concept_group_xmlid = "spp_vocabulary.group_rel_mixed"

            # Get the concept group and access only code_ids field (no computation)
            concept_group = self.env.ref(concept_group_xmlid, raise_if_not_found=False)
            if concept_group:
                # Access code_ids directly from database without triggering code_uris computation
                self.env.cr.execute(
                    """
                    SELECT code_id
                    FROM spp_vocab_concept_group_code_rel
                    WHERE group_id = %s
                    """,
                    (concept_group.id,),
                )
                code_ids = [row[0] for row in self.env.cr.fetchall()]
                rec.available_relation_ids = VocabCode.browse(code_ids)
            else:
                # Fallback to all codes
                all_codes = VocabCode.search(
                    [
                        (
                            "vocabulary_id.namespace_uri",
                            "=",
                            "urn:openspp:vocab:relationship",
                        )
                    ]
                )
                rec.available_relation_ids = all_codes

    @api.onchange("source", "destination")
    def _onchange_source_destination_clear_relation(self):
        """Clear relation_id when source or destination changes to avoid invalid selections."""
        if self.relation_id and self.source and self.destination:
            # Check if the current relation_id is still valid for the new source/destination combination
            if self.relation_id not in self.available_relation_ids:
                self.relation_id = False

    @api.constrains("source", "destination")
    def _check_registrants(self):
        for rec in self:
            if rec.source == rec.destination:
                raise ValidationError(_("Registrant 1 and Registrant 2 cannot be the same."))

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The starting date cannot be after the ending date."))

    @api.constrains("source", "relation_id", "destination", "start_date", "end_date")
    def _check_relation_uniqueness(self):
        """Forbid multiple active relations of the same type between the same
        partners
        :raises ValidationError: When constraint is violated
        """
        for record in self:
            domain = [
                ("relation_id", "=", record.relation_id.id),
                ("id", "!=", record.id),
                ("source", "=", record.source.id),
                ("destination", "=", record.destination.id),
            ]
            if record.start_date:
                domain += [
                    "|",
                    ("end_date", "=", False),
                    ("end_date", ">=", record.start_date),
                ]
            if record.end_date:
                domain += [
                    "|",
                    ("start_date", "=", False),
                    ("start_date", "<=", record.end_date),
                ]
            if record.search(domain):
                raise ValidationError(_("There is already a similar relation with overlapping dates"))

    @api.constrains("source", "relation_id")
    def _check_source(self):
        self._check_partner("source")

    @api.constrains("destination", "relation_id")
    def _check_destination(self):
        self._check_partner("destination")

    def _check_partner(self, side):
        """Validate that partners are applicable for the selected relationship type."""
        for record in self:
            assert side in ["source", "destination"]
            if not record.relation_id or not record.source or not record.destination:
                continue

            # Check if the relation_id is in the available_relation_ids
            if record.relation_id not in record.available_relation_ids:
                source_is_group = record.source.is_group
                dest_is_group = record.destination.is_group

                if not source_is_group and not dest_is_group:
                    rel_type = "individual-to-individual"
                elif source_is_group and dest_is_group:
                    rel_type = "group-to-group"
                else:
                    rel_type = "individual-to-group"

                raise ValidationError(
                    _("The relationship type '%s' is not applicable for %s relationships.")
                    % (record.relation_id.display, rel_type)
                )

    def _compute_display_name(self):
        res = super()._compute_display_name()
        for rec in self:
            name = ""
            if rec.source:
                name += rec.source.name
            if rec.destination:
                name += " / " + rec.destination.name
            rec.display_name = name
        return res

    def disable_relationship(self):
        for rec in self:
            if not rec.disabled:
                rec.update(
                    {
                        "disabled": fields.Datetime.now(),
                        "disabled_by": self.env.user,
                    }
                )

    def enable_relationship(self):
        for rec in self:
            if rec.disabled:
                rec.update(
                    {
                        "disabled": None,
                        "disabled_by": None,
                    }
                )

    def open_relationship1_form(self):
        if self.source.is_group:
            return {
                "name": "Related Group",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.source.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
            }
        else:
            return {
                "name": "Related Registrant",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.source.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
            }

    def open_relationship2_form(self):
        if self.destination.is_group:
            return {
                "name": "Other Related Group",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.destination.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
            }
        else:
            return {
                "name": "Other Related Registrant",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.destination.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
            }


class SPPRelationship(models.Model):
    _name = "spp.relationship"
    _description = "Relationship"
    _order = "id desc"

    name = fields.Char(translate=True)
    name_inverse = fields.Char(string="Inverse name", required=True, translate=True)
    bidirectional = fields.Boolean("Bi-directional", default=False)
    source_type = fields.Selection(selection="get_partner_types", string="Source partner type")
    destination_type = fields.Selection(selection="get_partner_types", string="Destination partner type")

    @api.model
    def get_partner_types(self):
        """A partner can be an organisation or an individual."""
        # pylint: disable=no-self-use
        return [("g", _("Group")), ("i", _("Individual"))]

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = "Name should not be empty."
                raise ValidationError(error_message)
