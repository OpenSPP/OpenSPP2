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
    # New-mode fields
    # ──────────────────────────────────────────────────────────────────
    given_name = fields.Char()
    family_name = fields.Char()
    birthdate = fields.Date(string="Date of Birth")
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
    )
    phone = fields.Char()

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
        vals = {
            "given_name": self.given_name,
            "family_name": self.family_name,
            "birthdate": self.birthdate,
            "gender_id": self.gender_id.id if self.gender_id else False,
            "phone": self.phone,
            "membership_type_id": self.membership_type_id.id if self.membership_type_id else False,
        }
        if self.editing_member_new_id:
            self.editing_member_new_id.write(vals)
        else:
            vals["detail_id"] = self.detail_id.id
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
