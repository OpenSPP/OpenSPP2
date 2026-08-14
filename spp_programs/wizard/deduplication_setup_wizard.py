# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Two-step creation for a deduplication manager (OP#1171).

Adding one used to mean editing the wrapper's ``manager_ref_id`` inline: a
Reference field, which asks the user to pick a *model* and then find or create
a record of it. That is a developer's control — it exposes the wrapper/concrete
split, and choosing an existing record belonging to another program silently
mis-wires the manager.

Compliance and Payment were converted to an "Add" button opening a dialog
(#952, #953). Deduplication is the same idea with one extra step, because it
has three methods where those have one: pick the method, then name it.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The concrete model behind each method, with the wording shown to the user.
# Kept here rather than read from MANAGER_TYPE_INFO so the selection stays a
# static list — Odoo needs the values at field-definition time.
DEDUPLICATION_METHODS = [
    (
        "spp.deduplication.manager.default",
        "Shared members",
        "Flags groups that have a member in common.",
    ),
    (
        "spp.deduplication.manager.id_dedup",
        "ID document",
        "Flags registrants sharing an ID document number.",
    ),
    (
        "spp.deduplication.manager.phone_number",
        "Phone number",
        "Flags registrants sharing a phone number.",
    ),
]


class DeduplicationSetupWizard(models.TransientModel):
    _name = "spp.deduplication.setup.wizard"
    _description = "Add a Deduplication Method"

    program_id = fields.Many2one(
        "spp.program",
        required=True,
        readonly=True,
    )
    method = fields.Selection(
        selection=[(model, label) for model, label, _description in DEDUPLICATION_METHODS],
        string="Method",
        required=True,
        default=DEDUPLICATION_METHODS[0][0],
        help="How duplicates are detected. Each method can be added once per program.",
    )
    method_description = fields.Char(compute="_compute_method_description")
    name = fields.Char(
        string="Name",
        required=True,
        help="Shown on the program's configuration page.",
    )

    @api.depends("method")
    def _compute_method_description(self):
        descriptions = {model: description for model, _label, description in DEDUPLICATION_METHODS}
        for wizard in self:
            wizard.method_description = descriptions.get(wizard.method, "")

    @api.onchange("method")
    def _onchange_method_suggests_a_name(self):
        """Pre-fill the name from the method so the second step is one keystroke.

        Only while the user has not typed their own, and only replacing a
        suggestion we made ourselves.
        """
        labels = {model: label for model, label, _description in DEDUPLICATION_METHODS}
        suggestions = set(labels.values())
        if not self.name or self.name in suggestions:
            self.name = labels.get(self.method, "")

    def action_create_manager(self):
        """Create the concrete manager; the wrapper follows automatically.

        ``spp.manager.source.mixin.create`` builds the
        ``spp.deduplication.manager`` wrapper when it sees
        ``_spp_wrapper_model`` in the context, so this creates one record and
        gets both — and dismissing this dialog leaves nothing behind (#953).

        ``_spp_program_m2m_field`` matters as much as the wrapper model here:
        ``spp.program.deduplication_manager_ids`` is a Many2many, so unlike a
        One2many it does not resolve from the wrapper's ``program_id``. Without
        it the manager is created and the program never picks it up — the card
        keeps saying nothing is configured and deduplication never runs.
        """
        self.ensure_one()
        existing = self.env["spp.deduplication.manager"].search(
            [("program_id", "=", self.program_id.id)],
        )
        if any(wrapper.manager_ref_id and wrapper.manager_ref_id._name == self.method for wrapper in existing):
            raise UserError(
                _("This program already has a %s deduplication method.") % dict(self._fields["method"].selection)[self.method]
            )

        self.env[self.method].with_context(
            default_program_id=self.program_id.id,
            _spp_wrapper_model="spp.deduplication.manager",
            _spp_program_m2m_field="deduplication_manager_ids",
        ).create(
            {
                "name": self.name,
                "program_id": self.program_id.id,
            }
        )
        return {"type": "ir.actions.act_window_close"}
