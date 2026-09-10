# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""One dialog for adding any program configuration method (OP#1172).

Every card on a program's Configuration tab used to be filled in the same way:
an inline list with a `manager_ref_id` Reference field and an "Add a line" row.
That control asks the user to pick a *model* and then find or create a record
of it, and both halves of it leak — the Reference picker and, on the Many2many
cards, the link dialog behind "Add a line" both list managers belonging to
other programs, which silently wires another program's configuration into this
one.

This wizard asks the two questions that actually matter — which method, and
what to call it — and creates a record that belongs to this program only. The
methods on offer come from the wrapper's ``_selection_manager_ref_id()``, so a
module that adds a method (spp_program_geofence adds an eligibility one) shows
up here without touching this file.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.constants import MANAGER_CATEGORIES
from ..models.program_manager_ui import MANAGER_TYPE_INFO


class ManagerSetupWizard(models.TransientModel):
    _name = "spp.manager.setup.wizard"
    _description = "Add a Configuration Method"

    program_id = fields.Many2one(
        "spp.program",
        required=True,
        readonly=True,
    )
    category = fields.Selection(
        selection=[(key, info["label"]) for key, info in MANAGER_CATEGORIES.items()],
        required=True,
        readonly=True,
        help="Which card on the Configuration tab this method belongs to.",
    )
    method = fields.Selection(
        selection="_selection_method",
        string="Method",
        required=True,
        help="How this part of the program is handled. Each method can be added once per program.",
    )
    method_description = fields.Char(compute="_compute_method_description")
    # Drives whether the Method question is asked at all: a category with one
    # method has nothing to choose, and a radio list of one is just noise.
    method_count = fields.Integer(compute="_compute_method_count")
    name = fields.Char(
        string="Name",
        required=True,
        help="Shown on the program's configuration page.",
    )

    # ------------------------------------------------------------------
    # the methods on offer
    # ------------------------------------------------------------------

    @api.model
    def _methods_for_category(self, category):
        """The concrete manager models a category can offer, as selection pairs.

        Read from the wrapper rather than from a list here so that methods
        added by other modules are included, and so that a method whose module
        has been uninstalled drops out instead of raising when it is picked.
        MANAGER_TYPE_INFO only supplies nicer wording where it has some.
        """
        info = MANAGER_CATEGORIES.get(category)
        if not info or info["wrapper"] not in self.env:
            return []
        methods = []
        for model, label in self.env[info["wrapper"]]._selection_manager_ref_id():
            if model in self.env:
                methods.append((model, MANAGER_TYPE_INFO.get(model, {}).get("name") or label))
        return methods

    @api.model
    def _selection_method(self):
        """Selection values for the Method field.

        A Selection cannot depend on another field's value, so the category
        comes from the context the Add button opens this dialog with.
        """
        return self._methods_for_category(self.env.context.get("default_category"))

    @api.depends("method")
    def _compute_method_description(self):
        for wizard in self:
            wizard.method_description = MANAGER_TYPE_INFO.get(wizard.method, {}).get("description", "")

    @api.depends("category")
    def _compute_method_count(self):
        for wizard in self:
            wizard.method_count = len(self._methods_for_category(wizard.category))

    @api.onchange("method")
    def _onchange_method_suggests_a_name(self):
        """Pre-fill the name from the method, so naming is one keystroke.

        Only while the user has not typed their own, and only replacing a
        suggestion we made ourselves.
        """
        labels = dict(self._methods_for_category(self.category))
        if not self.name or self.name in set(labels.values()):
            self.name = labels.get(self.method, "")

    # ------------------------------------------------------------------
    # creating the method
    # ------------------------------------------------------------------

    def _sweep_removed_methods(self):
        """Delete the methods the card no longer shows.

        Most of these program fields are Many2many, so the ✕ on a row removes
        the *relation* and leaves the manager behind with its ``program_id``
        still pointing here. Those leftovers never run — a program is
        configured through its own field, not through the managers'
        ``program_id`` — but they used to make the duplicate check below refuse
        a method the card no longer showed (OP#1171).

        Only managers that no program links are swept: on a Many2many, one this
        program created but another program links is that program's method now,
        not garbage.
        """
        self.ensure_one()
        field = MANAGER_CATEGORIES[self.category]["field"]
        wrapper = MANAGER_CATEGORIES[self.category]["wrapper"]
        removed = self.env[wrapper].search([("program_id", "=", self.program_id.id)]) - self.program_id[field]
        if not removed:
            return
        linked = self.env["spp.program"].search([(field, "in", removed.ids)])
        for leftover in removed - linked[field]:
            # The concrete record owns the wrapper: spp.manager.source.mixin's
            # unlink() takes the wrapper with it. manager_ref_id is a Reference,
            # so it carries no foreign key and can outlive what it points at —
            # unlinking that blind would raise MissingError on the Add button.
            concrete = leftover.manager_ref_id
            ((concrete and concrete.exists()) or leftover).unlink()

    def action_create_manager(self):
        """Create the concrete manager; the wrapper follows automatically.

        ``spp.manager.source.mixin.create`` builds the wrapper when it sees
        ``_spp_wrapper_model`` in the context, so this creates one record and
        gets both — and dismissing the dialog leaves nothing behind (#953).

        ``_spp_program_m2m_field`` matters as much as the wrapper model on the
        Many2many cards: unlike a One2many they do not resolve from the
        wrapper's ``program_id``, so without it the manager is created and the
        program never picks it up — the card keeps saying nothing is configured
        and the method never runs.
        """
        self.ensure_one()
        self._sweep_removed_methods()

        info = MANAGER_CATEGORIES[self.category]
        field = info["field"]
        labels = dict(self._methods_for_category(self.category))
        configured = self.program_id[field].filtered(lambda wrapper: wrapper.manager_ref_id)

        if info.get("single_manager") and configured:
            # Say what the limit actually is. This is not a duplicate rule: a
            # program supports one entitlement method whatever its kind, because
            # the cycle machinery reaches for exactly one (OP#1172 round 1).
            raise UserError(
                _(
                    "%(program)s already has a %(category)s: %(existing)s. A program supports one "
                    "for now — change that one, or remove it before adding another."
                )
                % {
                    "program": self.program_id.display_name,
                    "category": info["label"].lower(),
                    "existing": ", ".join(configured.mapped("display_name")),
                }
            )

        if configured.filtered(lambda wrapper: wrapper.manager_ref_id._name == self.method):
            raise UserError(
                _("This program already has a %(method)s %(category)s.")
                % {"method": labels.get(self.method, self.method), "category": info["label"].lower()}
            )

        context = {
            "default_program_id": self.program_id.id,
            "_spp_wrapper_model": MANAGER_CATEGORIES[self.category]["wrapper"],
        }
        if self.env["spp.program"]._fields[field].type == "many2many":
            context["_spp_program_m2m_field"] = field
        concrete = (
            self.env[self.method]
            .with_context(**context)
            .create(
                {
                    "name": self.name,
                    "program_id": self.program_id.id,
                }
            )
        )
        wrapper = self.env[MANAGER_CATEGORIES[self.category]["wrapper"]].search(
            [("manager_ref_id", "=", f"{concrete._name},{concrete.id}")],
            limit=1,
        )
        if wrapper:
            # Land on the method's own form rather than back on the card with
            # something unconfigured and a cog to discover. Eligibility filters,
            # entitlement amounts and compliance criteria all live there.
            return wrapper.open_manager_form(title=MANAGER_CATEGORIES[self.category]["label"])
        return {"type": "ir.actions.act_window_close"}
