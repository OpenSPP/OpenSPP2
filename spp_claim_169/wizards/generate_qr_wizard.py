import logging
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Claim169GenerateQRWizard(models.TransientModel):
    """
    Wizard to generate Claim 169 QR credentials for selected partners.

    Can be invoked from partner list view to batch-generate credentials.
    """

    _name = "spp.claim169.generate.qr.wizard"
    _description = "Generate Claim 169 QR Credentials Wizard"

    partner_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Registrants",
        domain=[("is_registrant", "=", True), ("is_group", "=", False)],
        help="Partners to generate credentials for. Select individual registrants only.",
    )

    partner_count = fields.Integer(
        string="Number of Partners", compute="_compute_partner_count", help="Total number of partners selected"
    )

    issuer_config_id = fields.Many2one(
        comodel_name="spp.claim169.issuer.config", string="Issuer", required=True, help="Issuer configuration to use"
    )

    validity_days = fields.Integer(
        string="Validity (Days)", help="Number of days credentials are valid for (overrides issuer default)"
    )

    generate_mode = fields.Selection(
        selection=[
            ("new_only", "New Only (Skip if exists)"),
            ("replace_expired", "Replace Expired"),
            ("replace_all", "Replace All"),
        ],
        string="Generation Mode",
        required=True,
        default="new_only",
        help="How to handle partners with existing credentials",
    )

    result_message = fields.Html(string="Results", readonly=True, help="Generation results summary")

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("done", "Done"),
        ],
        string="State",
        default="draft",
        help="Wizard state",
    )

    @api.depends("partner_ids")
    def _compute_partner_count(self):
        """Count selected partners."""
        for record in self:
            record.partner_count = len(record.partner_ids)

    @api.onchange("issuer_config_id")
    def _onchange_issuer_config(self):
        """Set default validity from issuer config."""
        if self.issuer_config_id:
            self.validity_days = self.issuer_config_id.default_validity_days

    @api.model
    def default_get(self, fields_list):
        """Set default values from context with issuer validation."""
        res = super().default_get(fields_list)

        # Check for active issuer configuration FIRST
        default_issuer = self.env["spp.claim169.issuer.config"].search(
            [
                ("is_default", "=", True),
                ("active", "=", True),
            ],
            limit=1,
        )

        if not default_issuer:
            # Try any active issuer
            default_issuer = self.env["spp.claim169.issuer.config"].search(
                [
                    ("active", "=", True),
                ],
                limit=1,
            )

        if not default_issuer:
            raise ValidationError(
                _(
                    "No active issuer configuration found.\n\n"
                    "Please configure an issuer before generating credentials:\n"
                    "Registry > Configuration > QR Credentials > Issuer Configurations"
                )
            )

        res["issuer_config_id"] = default_issuer.id
        res["validity_days"] = default_issuer.default_validity_days

        # Get partners from context (from tree view selection or form)
        if self.env.context.get("active_model") == "res.partner":
            partner_ids = self.env.context.get("active_ids", [])
            if partner_ids:
                # Filter to individuals only (not groups)
                partners = self.env["res.partner"].browse(partner_ids)
                individual_ids = partners.filtered(lambda p: p.is_registrant and not p.is_group).ids

                if not individual_ids:
                    raise ValidationError(
                        _(
                            "No individuals selected.\n\n"
                            "QR credentials can only be generated for individual "
                            "registrants, not groups."
                        )
                    )

                res["partner_ids"] = [Command.set(individual_ids)]

                # Log if some were filtered out
                if len(individual_ids) < len(partner_ids):
                    _logger.info(
                        "Filtered %d non-individual records from QR credential generation",
                        len(partner_ids) - len(individual_ids),
                    )

        return res

    def action_generate(self):
        """Generate credentials for all selected partners."""
        self.ensure_one()

        if not self.partner_ids:
            raise UserError(_("No partners selected"))

        if not self.issuer_config_id:
            raise UserError(_("No issuer configuration selected"))

        # Track results
        results = {
            "success": [],
            "skipped": [],
            "failed": [],
        }

        # Calculate expiration
        issued_at = fields.Datetime.now()
        validity_days = self.validity_days or self.issuer_config_id.default_validity_days
        expires_at = issued_at + timedelta(days=validity_days)

        # Process each partner
        for partner in self.partner_ids:
            try:
                # Skip groups (double-check)
                if partner.is_group:
                    results["skipped"].append(
                        {
                            "partner": partner,
                            "reason": _("Groups cannot receive QR credentials"),
                        }
                    )
                    continue

                # Check for existing credentials
                existing = self._get_existing_credential(partner)

                # Determine action based on mode
                action = self._determine_action(existing)

                if action == "skip":
                    results["skipped"].append(
                        {
                            "partner": partner,
                            "reason": _("Active credential exists"),
                        }
                    )
                    continue

                elif action == "replace":
                    # Revoke existing credential with reason
                    existing.write(
                        {
                            "revocation_reason": _("Replaced by new credential"),
                        }
                    )
                    existing.action_revoke()

                # Create new credential
                credential = self.env["spp.claim169.credential"].create(
                    {
                        "partner_id": partner.id,
                        "issuer_config_id": self.issuer_config_id.id,
                        "issued_at": issued_at,
                        "expires_at": expires_at,
                    }
                )

                # Generate CWT and QR
                credential.generate_credential()

                results["success"].append(
                    {
                        "partner": partner,
                        "credential": credential,
                    }
                )

                _logger.info("Generated credential %s for partner %s", credential.name, partner.name)

            except Exception as e:
                _logger.error("Failed to generate credential for partner %s: %s", partner.id, str(e), exc_info=True)
                results["failed"].append({"partner": partner, "error": str(e)})

        # Generate result message
        self.result_message = self._format_results(results)
        self.state = "done"

        # Return wizard view to show results
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_existing_credential(self, partner):
        """Get existing active credential for partner."""
        return self.env["spp.claim169.credential"].search(
            [
                ("partner_id", "=", partner.id),
                ("issuer_config_id", "=", self.issuer_config_id.id),
                ("status", "in", ["active", "expired"]),
            ],
            order="issued_at desc",
            limit=1,
        )

    def _determine_action(self, existing):
        """
        Determine what action to take based on existing credential and mode.

        Returns:
            "create", "skip", or "replace"
        """
        if not existing:
            return "create"

        if self.generate_mode == "new_only":
            if existing.status == "active":
                return "skip"
            else:
                return "create"

        elif self.generate_mode == "replace_expired":
            if existing.status == "expired":
                return "replace"
            else:
                return "skip"

        elif self.generate_mode == "replace_all":
            return "replace"

        return "skip"

    def _format_results(self, results):
        """Format results dictionary as HTML message with summary."""
        success_count = len(results["success"])
        skipped_count = len(results["skipped"])
        failed_count = len(results["failed"])
        total_count = success_count + skipped_count + failed_count

        lines = ["<div class='o_mail_thread'>"]

        # Summary banner
        lines.append("<div class='alert alert-info mb-3' role='alert'>")
        lines.append(
            f"<strong>Summary:</strong> {success_count} generated, "
            f"{skipped_count} skipped, {failed_count} failed "
            f"(of {total_count} total)"
        )
        lines.append("</div>")

        # Success section
        if results["success"]:
            lines.append(
                f"<p><strong class='text-success'>Successfully generated {success_count} credentials</strong></p>"
            )
            lines.append("<ul class='mb-3'>")
            for item in results["success"][:10]:  # Limit display
                partner = item["partner"]
                credential = item["credential"]
                lines.append(
                    f"<li>{partner.name} - "
                    f"<a href='#' data-oe-id='{credential.id}' "
                    f"data-oe-model='spp.claim169.credential'>{credential.name}</a>"
                    f"</li>"
                )
            if success_count > 10:
                lines.append(f"<li><em>... and {success_count - 10} more</em></li>")
            lines.append("</ul>")

        # Skipped section
        if results["skipped"]:
            lines.append(f"<p><strong class='text-warning'>Skipped {skipped_count} registrants</strong></p>")
            lines.append("<ul class='mb-3'>")
            for item in results["skipped"][:5]:  # Limit display
                partner = item["partner"]
                reason = item["reason"]
                lines.append(f"<li>{partner.name} - {reason}</li>")
            if skipped_count > 5:
                lines.append(f"<li><em>... and {skipped_count - 5} more</em></li>")
            lines.append("</ul>")

        # Failed section
        if results["failed"]:
            lines.append(f"<p><strong class='text-danger'>Failed to generate {failed_count} credentials</strong></p>")
            lines.append("<ul class='mb-3'>")
            for item in results["failed"]:
                partner = item["partner"]
                error = item["error"]
                lines.append(f"<li>{partner.name} - {error}</li>")
            lines.append("</ul>")

        lines.append("</div>")
        return "\n".join(lines)

    def action_view_credentials(self):
        """Open tree view of newly generated credentials."""
        self.ensure_one()

        # Get credential IDs from result_message (simplified approach)
        # In production, you might want to store IDs in a separate field
        credentials = self.env["spp.claim169.credential"].search(
            [
                ("partner_id", "in", self.partner_ids.ids),
                ("issuer_config_id", "=", self.issuer_config_id.id),
                ("issued_at", ">=", fields.Datetime.now().replace(hour=0, minute=0, second=0)),
            ]
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Credentials"),
            "res_model": "spp.claim169.credential",
            "view_mode": "list,form",
            "domain": [("id", "in", credentials.ids)],
        }
