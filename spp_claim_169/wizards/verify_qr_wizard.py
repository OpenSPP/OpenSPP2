# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Wizard for verifying QR credentials."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Claim169VerifyQRWizard(models.TransientModel):
    """
    Wizard to verify Claim 169 QR credentials.

    Users can paste QR data or scan a QR code to verify credential authenticity.
    """

    _name = "spp.claim169.verify.qr.wizard"
    _description = "Verify Claim 169 QR Credential"

    qr_data = fields.Text(
        string="QR Data",
        help="Paste the Base45-encoded data from a QR code. This is the text content embedded in the QR code image.",
    )

    public_key_id = fields.Many2one(
        comodel_name="spp.asymmetric.key",
        string="Verification Key",
        domain=[("key_type", "in", ["ed25519", "ec"])],
        help="Public key to verify the credential signature. "
        "This should be the public key corresponding to the issuer's signing key.",
    )

    auto_detect_key = fields.Boolean(
        string="Auto-detect Key",
        default=True,
        help="Automatically find the verification key based on the credential's issuer.",
    )

    state = fields.Selection(
        selection=[
            ("input", "Input"),
            ("result", "Result"),
        ],
        string="State",
        default="input",
    )

    # Result fields
    is_valid = fields.Boolean(string="Valid", readonly=True)
    verification_error = fields.Char(string="Error", readonly=True)
    verification_message = fields.Html(string="Result", readonly=True)

    # Decoded claims (stored as JSON for display)
    decoded_claims = fields.Text(string="Decoded Claims", readonly=True)
    decoded_issuer = fields.Char(string="Issuer", readonly=True)
    decoded_expires = fields.Datetime(string="Expires", readonly=True)
    matched_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Matched Registrant",
        readonly=True,
        help="Registrant found in the system matching the credential data.",
    )

    @api.onchange("auto_detect_key")
    def _onchange_auto_detect_key(self):
        """Clear public key when auto-detect is enabled."""
        if self.auto_detect_key:
            self.public_key_id = False

    def action_verify(self):
        """Verify the QR credential data."""
        self.ensure_one()

        if not self.qr_data:
            raise UserError(_("Please enter QR data to verify."))

        qr_data = self.qr_data.strip()

        service = self.env["spp.claim169.service"]

        # First, try to decode without verification to get issuer info
        try:
            unverified = service.decode_from_qr(qr_data)
        except Exception as e:
            self._set_error_result(str(e))
            return self._return_wizard()

        # If auto-detect, find the key based on issuer
        public_key = self.public_key_id
        if self.auto_detect_key:
            public_key = self._find_verification_key(unverified)
            if not public_key:
                self._set_result(
                    is_valid=False,
                    error="Could not auto-detect verification key. Please select a key manually.",
                    claims=unverified,
                )
                return self._return_wizard()

        if not public_key:
            raise UserError(_("Please select a verification key or enable auto-detection."))

        # Verify the credential
        result = service.verify_credential(qr_data, public_key.id)

        # Set result
        self._set_result(
            is_valid=result.get("valid", False),
            error=result.get("error"),
            claims=result.get("claims") or unverified,
        )

        return self._return_wizard()

    def _find_verification_key(self, claims):
        """
        Find a verification key based on decoded claims.

        Looks for issuer config matching the credential's issuer ID.
        """
        issuer_id = claims.get("issuer") or claims.get("iss")
        if not issuer_id:
            return None

        # Find issuer config by issuer_id
        issuer_config = self.env["spp.claim169.issuer.config"].search(
            [("issuer_id", "=", issuer_id), ("active", "=", True)],
            limit=1,
        )

        if issuer_config and issuer_config.signing_key_id:
            # Return the signing key (which should have public key material)
            return issuer_config.signing_key_id

        # Fallback: search for a key with matching kid
        kid = claims.get("kid")
        if kid:
            key = self.env["spp.asymmetric.key"].search(
                [("kid", "=", kid), ("key_type", "in", ["ed25519", "ec"])],
                limit=1,
            )
            if key:
                return key

        return None

    def _set_result(self, is_valid, error=None, claims=None):
        """Set verification result fields."""
        import json
        from datetime import datetime

        self.state = "result"
        self.is_valid = is_valid
        self.verification_error = error

        if claims:
            # Store decoded claims as formatted JSON
            self.decoded_claims = json.dumps(claims, indent=2, default=str)
            self.decoded_issuer = claims.get("issuer") or claims.get("iss", "")

            # Parse expiration if present
            expires = claims.get("exp") or claims.get("expires_at")
            if expires:
                if isinstance(expires, (int, float)):
                    self.decoded_expires = datetime.fromtimestamp(expires)
                elif isinstance(expires, str):
                    try:
                        self.decoded_expires = datetime.fromisoformat(expires)
                    except ValueError:
                        pass

            # Try to match to a registrant
            self._try_match_registrant(claims)

        # Build result message HTML
        self._build_result_message(is_valid, error, claims)

    def _set_error_result(self, error):
        """Set error result for decode failures."""
        self.state = "result"
        self.is_valid = False
        self.verification_error = error
        self.verification_message = f"<div class='alert alert-danger'><strong>Decode Failed</strong><br/>{error}</div>"

    def _try_match_registrant(self, claims):
        """Try to find a registrant matching the credential claims."""
        # Try to match by ID claim
        id_claim = claims.get("id")
        if id_claim:
            # Try as external ID first (spp.reg.id)
            ext_id = self.env["spp.reg.id"].search([("id_value", "=", str(id_claim))], limit=1)
            if ext_id and ext_id.partner_id:
                self.matched_partner_id = ext_id.partner_id
                return

            # Try as partner ID (not recommended but fallback)
            try:
                partner = self.env["res.partner"].browse(int(id_claim))
                if partner.exists() and partner.is_registrant:
                    self.matched_partner_id = partner
                    return
            except (ValueError, TypeError):
                pass

        # Try to match by full_name + date_of_birth
        full_name = claims.get("full_name")
        dob = claims.get("date_of_birth")
        if full_name and dob:
            # Convert YYYYMMDD to date format
            try:
                if len(str(dob)) == 8:
                    dob_str = str(dob)
                    dob_date = f"{dob_str[:4]}-{dob_str[4:6]}-{dob_str[6:8]}"
                else:
                    dob_date = str(dob)

                partner = self.env["res.partner"].search(
                    [
                        ("name", "=", full_name),
                        ("birthdate", "=", dob_date),
                        ("is_registrant", "=", True),
                    ],
                    limit=1,
                )
                if partner:
                    self.matched_partner_id = partner
            except Exception:
                pass

    def _build_result_message(self, is_valid, error, claims):
        """Build HTML result message."""
        lines = []

        if is_valid:
            lines.append(
                "<div class='alert alert-success'>"
                "<i class='fa fa-check-circle'></i> "
                "<strong>Credential Valid</strong><br/>"
                "The signature is authentic and the credential has not expired."
                "</div>"
            )
        else:
            alert_class = "alert-danger"
            icon = "fa-times-circle"
            title = "Verification Failed"

            if error and "expired" in error.lower():
                alert_class = "alert-warning"
                icon = "fa-clock-o"
                title = "Credential Expired"

            lines.append(
                f"<div class='alert {alert_class}'>"
                f"<i class='fa {icon}'></i> "
                f"<strong>{title}</strong><br/>"
                f"{error or 'Unknown error'}"
                f"</div>"
            )

        if claims:
            # Show key claim summary
            lines.append("<div class='mt-3'><strong>Credential Summary:</strong></div>")
            lines.append("<table class='table table-sm'>")

            summary_fields = [
                ("id", "ID"),
                ("full_name", "Full Name"),
                ("date_of_birth", "Date of Birth"),
                ("gender", "Gender"),
                ("nationality", "Nationality"),
                ("issuer", "Issuer"),
            ]

            for field, label in summary_fields:
                value = claims.get(field)
                if value:
                    # Format gender
                    if field == "gender" and isinstance(value, int):
                        value = {1: "Male", 2: "Female", 3: "Other"}.get(value, value)
                    # Format date of birth
                    if field == "date_of_birth" and len(str(value)) == 8:
                        v = str(value)
                        value = f"{v[:4]}-{v[4:6]}-{v[6:8]}"

                    lines.append(f"<tr><td><strong>{label}:</strong></td><td>{value}</td></tr>")

            lines.append("</table>")

        self.verification_message = "\n".join(lines)

    def _return_wizard(self):
        """Return action to display wizard with results."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_reset(self):
        """Reset wizard to input state."""
        self.ensure_one()
        self.write(
            {
                "state": "input",
                "qr_data": False,
                "is_valid": False,
                "verification_error": False,
                "verification_message": False,
                "decoded_claims": False,
                "decoded_issuer": False,
                "decoded_expires": False,
                "matched_partner_id": False,
            }
        )
        return self._return_wizard()

    def action_view_registrant(self):
        """Open the matched registrant form."""
        self.ensure_one()
        if not self.matched_partner_id:
            raise UserError(_("No matched registrant found."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.matched_partner_id.id,
            "view_mode": "form",
            "target": "current",
        }
