# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Wizard for previewing and applying Notary claim catalog sync."""

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spp_notary_client.services.exceptions import NotaryError
from odoo.addons.spp_notary_client.services.schemas import CatalogResponse

from ..models.notary_claim import normalize_notary_value_type


class NotaryCatalogSyncWizard(models.TransientModel):
    """Preview Notary catalog differences before committing metadata changes."""

    _name = "spp.notary.catalog.sync.wizard"
    _description = "Sync Notary Claim Catalog"

    provider_id = fields.Many2one(
        comodel_name="spp.data.provider",
        string="Notary Provider",
        required=True,
        domain=[("provider_kind", "=", "notary")],
    )
    state = fields.Selection(
        selection=[("draft", "Draft"), ("preview", "Preview Ready"), ("done", "Done")],
        default="draft",
        required=True,
    )
    catalog_payload = fields.Json(readonly=True)
    summary = fields.Text(readonly=True)
    line_ids = fields.One2many(
        comodel_name="spp.notary.catalog.sync.wizard.line",
        inverse_name="wizard_id",
        string="Preview",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "spp.data.provider" and active_id and "provider_id" in fields_list:
            values["provider_id"] = active_id
        return values

    def action_load_preview(self):
        self.ensure_one()
        if self.provider_id.provider_kind != "notary":
            raise UserError(_("Only Notary providers can sync a Notary claim catalog."))
        try:
            catalog = self.provider_id._fetch_notary_catalog()
        except NotaryError as error:
            raise UserError(_("Notary catalog preview failed: %(error)s") % {"error": error}) from error

        line_values = self._preview_line_values(catalog)
        self.write(
            {
                "catalog_payload": catalog.model_dump(mode="json", exclude_none=True),
                "line_ids": [Command.clear(), *(Command.create(values) for values in line_values)],
                "summary": self._summary_from_lines(line_values),
                "state": "preview",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Notary Catalog"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_sync_catalog(self):
        self.ensure_one()
        if self.state != "preview" or not self.catalog_payload:
            raise UserError(_("Load a Notary catalog preview before confirming sync."))
        blocked = self.line_ids.filtered("blocking")
        if blocked:
            raise UserError(
                _("Resolve %(count)s blocking Notary catalog preview issue(s) before confirming sync.")
                % {"count": len(blocked)}
            )

        catalog = CatalogResponse.model_validate(self.catalog_payload)
        result = self.provider_id._apply_notary_claim_catalog(catalog)
        self.action_validate()
        return result

    def action_validate(self):
        """Mark the transient wizard as complete after a confirmed sync."""
        self.write({"state": "done"})

    def _preview_line_values(self, catalog):
        self.ensure_one()
        existing_by_external_id = {claim.external_id: claim for claim in self.provider_id.notary_claim_ids}
        seen_claim_ids = set()
        values = []

        for summary in catalog.claims:
            claim_id = summary.id
            claim_version = summary.version or ""
            seen_claim_ids.add(claim_id)
            claim = existing_by_external_id.get(claim_id)
            action = "create" if not claim else "no_change"
            state_after = "active"
            message = ""

            if claim:
                version_changed = claim.claim_version != claim_version
                pinned_elsewhere = claim.pinned_version and claim.pinned_version != claim_version
                if version_changed and pinned_elsewhere:
                    action = "version_drift"
                    state_after = "version_drift"
                    message = _("Catalog version changed while pinned to %(version)s.") % {
                        "version": claim.pinned_version
                    }
                elif self._summary_differs(claim, summary):
                    action = "update"
            else:
                message = self._accessor_collision_message(claim_id)
                if message:
                    action = "blocked"

            values.append(
                {
                    "claim_id": claim_id,
                    "title": summary.title or claim_id,
                    "catalog_version": claim_version,
                    "pinned_version": claim.pinned_version if claim else claim_version,
                    "action": action,
                    "state_after": state_after,
                    "blocking": action == "blocked",
                    "message": message,
                }
            )

        for claim in self.provider_id.notary_claim_ids:
            if claim.active and claim.external_id not in seen_claim_ids:
                values.append(
                    {
                        "claim_id": claim.external_id,
                        "title": claim.name,
                        "catalog_version": claim.claim_version,
                        "pinned_version": claim.pinned_version,
                        "action": "unavailable",
                        "state_after": "unavailable",
                        "blocking": False,
                        "message": _("Claim is no longer present in the upstream catalog."),
                    }
                )

        return values

    def _summary_differs(self, claim, summary):
        subject_type = self.provider_id._notary_subject_type(summary.subject_type)
        default_disclosure = summary.default_disclosure or self.provider_id._notary_default_disclosure(summary)
        return any(
            [
                claim.name != (summary.title or summary.id),
                (claim.description or "") != (summary.description or ""),
                claim.claim_version != (summary.version or ""),
                claim.subject_type != subject_type,
                claim.value_type != normalize_notary_value_type(summary.value_type),
                claim.default_disclosure != default_disclosure,
            ]
        )

    def _accessor_collision_message(self, claim_id):
        Claim = self.env["spp.notary.claim"]
        variable_name = Claim._build_variable_name(self.provider_id.code or self.provider_id.name, claim_id)
        variable = self.env["spp.cel.variable"].search([("name", "=", variable_name)], limit=1)
        if variable and (
            not variable.notary_claim_id
            or variable.notary_claim_id.provider_id != self.provider_id
            or variable.notary_claim_id.external_id != claim_id
        ):
            return _("Internal Notary CEL variable '%(name)s' is already used by another variable.") % {
                "name": variable_name
            }
        return ""

    def _summary_from_lines(self, line_values):
        counts = {}
        for values in line_values:
            counts[values["action"]] = counts.get(values["action"], 0) + 1
        return _(
            "Create: %(create)s\nUpdate: %(update)s\nVersion drift: %(version_drift)s\n"
            "Unavailable: %(unavailable)s\nNo change: %(no_change)s\nBlocked: %(blocked)s"
        ) % {
            "create": counts.get("create", 0),
            "update": counts.get("update", 0),
            "version_drift": counts.get("version_drift", 0),
            "unavailable": counts.get("unavailable", 0),
            "no_change": counts.get("no_change", 0),
            "blocked": counts.get("blocked", 0),
        }


class NotaryCatalogSyncWizardLine(models.TransientModel):
    """One preview row for a Notary catalog sync."""

    _name = "spp.notary.catalog.sync.wizard.line"
    _description = "Sync Notary Claim Catalog Preview Line"

    wizard_id = fields.Many2one(
        comodel_name="spp.notary.catalog.sync.wizard",
        required=True,
        ondelete="cascade",
    )
    claim_id = fields.Char(readonly=True)
    title = fields.Char(readonly=True)
    catalog_version = fields.Char(readonly=True)
    pinned_version = fields.Char(readonly=True)
    action = fields.Selection(
        selection=[
            ("create", "Create"),
            ("update", "Update"),
            ("version_drift", "Version Drift"),
            ("unavailable", "Unavailable"),
            ("no_change", "No Change"),
            ("blocked", "Blocked"),
        ],
        readonly=True,
    )
    state_after = fields.Char(readonly=True)
    blocking = fields.Boolean(readonly=True)
    message = fields.Char(readonly=True)
