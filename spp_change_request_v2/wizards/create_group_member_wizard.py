# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Add Member wizard for the Create Group CR (OP#876).

A single transient model handles two cases:
- ``mode = 'existing'`` — pick an individual already in the registry.
- ``mode = 'new'``      — collect the minimum field set for a new individual,
                          which the apply strategy later creates.

The wizard is opened from two buttons on the detail form (one per mode) and
can also be re-opened pre-populated to edit an existing **new** row. Existing
rows are immutable once added: to change them the user deletes and re-adds.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SPPCRCreateGroupMemberWizard(models.TransientModel):
    _name = "spp.cr.detail.create_group.member.wizard"
    _description = "Create Group — Add Member Wizard"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    mode = fields.Selection(
        [
            ("existing", "Existing Individual"),
            ("new", "New Individual"),
        ],
        required=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # Existing-mode fields
    # ──────────────────────────────────────────────────────────────────
    individual_id = fields.Many2one(
        "res.partner",
        string="Individual",
        domain="[('is_group', '=', False), ('is_registrant', '=', True)]",
    )

    # ──────────────────────────────────────────────────────────────────
    # New-mode fields (mirror the registry individual overview — OP#876)
    # ──────────────────────────────────────────────────────────────────
    given_name = fields.Char()
    family_name = fields.Char()
    middle_name = fields.Char()
    birthdate = fields.Date(string="Date of Birth")
    is_approximate_birthdate = fields.Boolean(string="Approximate Birthdate")
    birth_place = fields.Char(string="Birth Place")
    occupation_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Occupation",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:ilo:isco-08')]",
    )
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
    )
    civil_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Civil Status",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:un:unsd:pop-census:marital-status')]",
    )
    income = fields.Float(string="Income")
    area_id = fields.Many2one("spp.area", string="Area")
    address = fields.Text(string="Address")
    email = fields.Char(string="Email")
    phone_line_ids = fields.One2many(
        "spp.cr.detail.create_group.member.wizard.phone",
        "wizard_id",
        string="Phone Numbers",
    )

    # ──────────────────────────────────────────────────────────────────
    # Both modes
    # ──────────────────────────────────────────────────────────────────
    membership_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )

    # Edit-mode handle: only meaningful when ``mode == 'new'``. When set,
    # ``_persist`` updates this row instead of creating a new one.
    editing_member_new_id = fields.Many2one(
        "spp.cr.detail.create_group.member_new",
        string="Editing Row",
    )

    # Convenience for the view: show "Edit" vs "Add" labels on buttons.
    is_editing = fields.Boolean(compute="_compute_is_editing")

    @api.depends("editing_member_new_id")
    def _compute_is_editing(self):
        for rec in self:
            rec.is_editing = bool(rec.editing_member_new_id)

    # ──────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────
    def _validate(self):
        self.ensure_one()
        if self.mode == "existing":
            if not self.individual_id:
                raise UserError(_("Pick an individual before adding."))
            already_added = self.detail_id.member_existing_ids.filtered(
                lambda m: m.individual_id.id == self.individual_id.id
            )
            if already_added:
                raise UserError(_("'%s' is already in the existing-members list.") % self.individual_id.name)
        elif self.mode == "new":
            if not self.given_name or not self.family_name:
                raise UserError(_("Given name and family name are both required for a new individual."))

        # Block a second Head of Household with a clear message (the model-level
        # constraint on the member rows is the safety net).
        if self.membership_type_id and self.membership_type_id.code == "head":
            existing_heads, new_heads = self.detail_id._heads()
            if self.editing_member_new_id:
                new_heads = new_heads.filtered(lambda m: m.id != self.editing_member_new_id.id)
            if existing_heads or new_heads:
                raise UserError(_("This group already has a Head of Household. Only one member can be Head."))

    # ──────────────────────────────────────────────────────────────────
    # Persist the wizard's payload to the detail's O2M tables
    # ──────────────────────────────────────────────────────────────────
    def _persist(self):
        self._validate()
        if self.mode == "existing":
            self.env["spp.cr.detail.create_group.member_existing"].create(
                {
                    "detail_id": self.detail_id.id,
                    "individual_id": self.individual_id.id,
                    "membership_type_id": self.membership_type_id.id if self.membership_type_id else False,
                }
            )
            return

        # mode == 'new'
        # Copy the wizard's transient phone lines onto the member_new row.
        # detail_id is forced False: the wizard is opened with a
        # default_detail_id context (for the member row), and the phone model
        # also has a detail_id field, so that default would otherwise leak onto
        # the phone rows and give them two parents (detail_id + member_new_id).
        phone_cmds = [
            (0, 0, {"phone_no": pl.phone_no, "country_id": pl.country_id.id, "detail_id": False})
            for pl in self.phone_line_ids
            if pl.phone_no
        ]
        vals = {
            "given_name": self.given_name,
            "family_name": self.family_name,
            "middle_name": self.middle_name,
            "birthdate": self.birthdate,
            "is_approximate_birthdate": self.is_approximate_birthdate,
            "birth_place": self.birth_place,
            "occupation_id": self.occupation_id.id if self.occupation_id else False,
            "gender_id": self.gender_id.id if self.gender_id else False,
            "civil_status_id": self.civil_status_id.id if self.civil_status_id else False,
            "income": self.income,
            "area_id": self.area_id.id if self.area_id else False,
            "address": self.address,
            "email": self.email,
            "membership_type_id": self.membership_type_id.id if self.membership_type_id else False,
        }
        if self.editing_member_new_id:
            # Replace the existing phone rows with the wizard's current set.
            # Delete (2) the old rows rather than clear (5): clearing a
            # one2many only nulls the inverse FK, which would orphan the rows
            # and trip the phone row's exactly-one-parent constraint.
            delete_cmds = [(2, p.id, 0) for p in self.editing_member_new_id.phone_line_ids]
            vals["phone_line_ids"] = delete_cmds + phone_cmds
            self.editing_member_new_id.write(vals)
        else:
            vals["detail_id"] = self.detail_id.id
            vals["phone_line_ids"] = phone_cmds
            self.env["spp.cr.detail.create_group.member_new"].create(vals)

    # ──────────────────────────────────────────────────────────────────
    # Buttons
    # ──────────────────────────────────────────────────────────────────
    def action_add(self):
        """Persist + reopen the wizard fresh so the user can add another row."""
        self.ensure_one()
        self._persist()
        if self.is_editing:
            # Editing is a one-shot operation; close after saving even on the
            # plain "Save" button.
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_detail_id": self.detail_id.id,
                "default_mode": self.mode,
            },
        }

    def action_add_close(self):
        self.ensure_one()
        self._persist()
        return {"type": "ir.actions.act_window_close"}


class SPPCRCreateGroupMemberWizardPhone(models.TransientModel):
    """Transient phone row for the Add Member wizard's editable list.

    Persisted onto ``member_new.phone_line_ids`` when the wizard saves; on apply
    the new individual's phone numbers are concatenated into the partner's
    single header phone field.
    """

    _name = "spp.cr.detail.create_group.member.wizard.phone"
    _description = "Create Group — Add Member Wizard Phone"
    _order = "is_primary desc, id"

    wizard_id = fields.Many2one(
        "spp.cr.detail.create_group.member.wizard",
        required=True,
        ondelete="cascade",
    )
    phone_no = fields.Char(string="Phone Number", required=True)
    country_id = fields.Many2one("res.country", string="Country")
    is_primary = fields.Boolean(string="Primary")
