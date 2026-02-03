import base64
import hashlib
import io
import json
import logging
from datetime import timedelta

import qrcode

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Claim169Credential(models.Model):
    """
    Stored Claim 169 credentials with QR codes.

    Tracks generated credentials, their validity, and provides
    QR code generation and verification capabilities.
    """

    _name = "spp.claim169.credential"
    _description = "Claim 169 Credential"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issued_at desc"
    _rec_name = "display_name"

    name = fields.Char(
        string="Credential ID",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        help="Unique identifier for this credential",
    )

    display_name = fields.Char(
        string="Display Name", compute="_compute_display_name", store=True, help="Human-readable credential identifier"
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Registrant",
        required=True,
        ondelete="restrict",
        help="Partner this credential was issued to",
    )

    issuer_config_id = fields.Many2one(
        comodel_name="spp.claim169.issuer.config",
        string="Issuer",
        required=True,
        ondelete="restrict",
        help="Issuer configuration used for this credential",
    )

    signing_key_id = fields.Many2one(
        comodel_name="spp.asymmetric.key",
        string="Signing Key",
        related="issuer_config_id.signing_key_id",
        store=True,
        help="Cryptographic key used to sign this credential",
    )

    signing_key_type = fields.Selection(
        related="signing_key_id.key_type",
        string="Key Type",
        help="Type of cryptographic key (RSA, EC, Ed25519)",
    )

    signing_key_curve = fields.Selection(
        related="signing_key_id.curve",
        string="Key Curve",
        help="Elliptic curve for EC keys",
    )

    # Public key fields for verification
    public_key_jwk = fields.Text(
        string="Public Key (JWK)",
        related="signing_key_id.public_key_jwk",
        help="Public key in JWK format for verification tools",
    )

    public_key_pem = fields.Text(
        string="Public Key (PEM)",
        compute="_compute_public_key_pem",
        help="Public key in PEM format for display",
    )

    # Decoded claims from QR data
    decoded_claims = fields.Text(
        string="Decoded Claims (JSON)",
        compute="_compute_decoded_claims",
        help="Claims embedded in this credential",
    )

    decoded_claims_display = fields.Html(
        string="Credential Data",
        compute="_compute_decoded_claims",
        help="Human-readable display of credential claims",
    )

    cwt_bytes = fields.Binary(string="CWT Bytes", attachment=True, help="Raw CWT (CBOR Web Token) bytes")

    qr_data = fields.Text(string="QR Data", help="Base45 encoded data for QR code")

    qr_image = fields.Binary(
        string="QR Code Image",
        attachment=True,
        compute="_compute_qr_image",
        store=True,
        help="Generated QR code image (PNG)",
    )

    issued_at = fields.Datetime(
        string="Issued At", required=True, default=fields.Datetime.now, help="Timestamp when credential was issued"
    )

    expires_at = fields.Datetime(string="Expires At", required=True, help="Timestamp when credential expires")

    status = fields.Selection(
        selection=[
            ("active", "Active"),
            ("revoked", "Revoked"),
            ("expired", "Expired"),
        ],
        string="Status",
        required=True,
        default="active",
        compute="_compute_status",
        store=True,
        help="Current status of the credential",
    )

    credential_hash = fields.Char(
        string="Credential Hash",
        compute="_compute_credential_hash",
        store=True,
        help="SHA256 hash of CWT for verification",
    )

    revocation_reason = fields.Text(string="Revocation Reason", help="Reason for credential revocation")

    revoked_at = fields.Datetime(string="Revoked At", help="Timestamp when credential was revoked")

    revoked_by_id = fields.Many2one(
        comodel_name="res.users", string="Revoked By", help="User who revoked the credential"
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="issuer_config_id.company_id",
        store=True,
        help="Company of the issuer",
    )

    @api.depends("partner_id", "issued_at")
    def _compute_display_name(self):
        """Compute human-readable display name."""
        for record in self:
            if record.partner_id and record.issued_at:
                date_str = record.issued_at.strftime("%Y-%m-%d")
                record.display_name = f"{record.partner_id.name} - {date_str}"
            else:
                record.display_name = record.name

    @api.depends("cwt_bytes", "qr_data")
    def _compute_credential_hash(self):
        """Compute SHA256 hash of credential data.

        Uses cwt_bytes if available (legacy), otherwise uses qr_data.
        """
        for record in self:
            if record.cwt_bytes:
                cwt_data = base64.b64decode(record.cwt_bytes)
                hash_obj = hashlib.sha256(cwt_data)
                record.credential_hash = hash_obj.hexdigest()
            elif record.qr_data:
                # Hash the QR data for credentials generated with claim169 library
                hash_obj = hashlib.sha256(record.qr_data.encode("utf-8"))
                record.credential_hash = hash_obj.hexdigest()
            else:
                record.credential_hash = False

    @api.depends("expires_at", "revoked_at")
    def _compute_status(self):
        """Compute credential status based on expiration and revocation."""
        now = fields.Datetime.now()
        for record in self:
            if record.revoked_at:
                record.status = "revoked"
            elif record.expires_at and record.expires_at < now:
                record.status = "expired"
            else:
                record.status = "active"

    @api.depends("qr_data")
    def _compute_qr_image(self):
        """Generate QR code image from qr_data."""
        for record in self:
            if record.qr_data:
                record.qr_image = record._generate_qr_image()
            else:
                record.qr_image = False

    @api.depends("public_key_jwk")
    def _compute_public_key_pem(self):
        """Convert public key from JWK to PEM format for display."""
        for record in self:
            if not record.public_key_jwk:
                record.public_key_pem = False
                continue

            try:
                from jwcrypto import jwk

                key = jwk.JWK.from_json(record.public_key_jwk)
                # Export as PEM (public key only)
                pem_bytes = key.export_to_pem(private_key=False, password=None)
                record.public_key_pem = pem_bytes.decode("utf-8")
            except Exception as e:
                _logger.warning("Failed to convert public key to PEM: %s", e)
                record.public_key_pem = False

    @api.depends("qr_data")
    def _compute_decoded_claims(self):
        """Decode claims from QR data for display.

        Uses attribute mappings from database for human-readable labels.
        """
        # Build claim number to label mapping from database
        mappings = self.env["spp.claim169.attribute.mapping"].search([("is_active", "=", True)])
        claim_labels = {}
        for mapping in mappings:
            # Use mapping name as label (more descriptive than claim_name)
            claim_labels[mapping.claim_number] = mapping.name
            if mapping.claim_name:
                claim_labels[mapping.claim_name] = mapping.name

        # Metadata fields to skip in display
        metadata_fields = {"iss", "issuer", "exp", "iat", "nbf", "sub", "version", "id"}

        for record in self:
            if not record.qr_data:
                record.decoded_claims = False
                record.decoded_claims_display = False
                continue

            try:
                service = self.env["spp.claim169.service"]
                claims = service.decode_from_qr(record.qr_data)

                # Store raw JSON
                record.decoded_claims = json.dumps(claims, indent=2, default=str)

                # Build human-readable HTML display
                html_parts = ['<table class="table table-sm table-borderless">']
                for key, value in claims.items():
                    # Skip metadata fields
                    if key in metadata_fields:
                        continue

                    # Get human-readable label from mappings
                    if isinstance(key, int):
                        label = claim_labels.get(key, f"Attribute {key}")
                    elif isinstance(key, str) and key.isdigit():
                        label = claim_labels.get(int(key), f"Attribute {key}")
                    else:
                        # Try claim_name lookup, fallback to title case
                        label = claim_labels.get(key, key.replace("_", " ").title())

                    # Format value for display
                    if value is None:
                        display_value = "<em>Not provided</em>"
                    elif isinstance(value, bool):
                        display_value = "Yes" if value else "No"
                    else:
                        display_value = str(value)

                    html_parts.append(
                        f'<tr><td class="text-muted" style="width:40%">{label}</td>'
                        f"<td><strong>{display_value}</strong></td></tr>"
                    )

                html_parts.append("</table>")
                record.decoded_claims_display = "".join(html_parts)

            except Exception as e:
                _logger.warning("Failed to decode claims for credential %s: %s", record.name, e)
                record.decoded_claims = False
                record.decoded_claims_display = (
                    '<div class="alert alert-warning">Unable to decode credential data</div>'
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate credential ID sequence on create."""
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("spp.claim169.credential") or _("New")
        return super().create(vals_list)

    def generate_credential(self):
        """
        Generate CWT and QR code for this credential from partner data.

        This method orchestrates the full credential generation process:
        1. Build claims from attribute mappings
        2. Generate CWT using spp_cbor_cose
        3. Encode for QR code (zlib + Base45)
        4. Store results

        Returns:
            self (for chaining)
        """
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("Cannot generate credential without a partner"))

        if not self.issuer_config_id:
            raise UserError(_("Cannot generate credential without an issuer"))

        try:
            # Get the service and generate credential
            service = self.env["spp.claim169.service"]
            cwt_bytes, qr_data = service.generate_cwt_for_partner(self.partner_id.id, self.issuer_config_id.id)

            # Store results
            # cwt_bytes may be None when using claim169 library (encoding is internal)
            vals = {"qr_data": qr_data}
            if cwt_bytes:
                vals["cwt_bytes"] = base64.b64encode(cwt_bytes)
            self.write(vals)

            _logger.info(
                "Generated Claim 169 credential for partner %s (ID: %s)", self.partner_id.name, self.partner_id.id
            )

            return self

        except Exception as e:
            _logger.error("Failed to generate credential for partner %s: %s", self.partner_id.id, str(e), exc_info=True)
            raise UserError(_("Credential generation failed: %s") % str(e)) from e

    def action_revoke(self):
        """Mark credential as revoked with audit logging."""
        for record in self:
            if record.status == "revoked":
                raise UserError(_("Credential '%s' is already revoked") % record.display_name)

            old_status = record.status
            record.write(
                {
                    "revoked_at": fields.Datetime.now(),
                    "revoked_by_id": self.env.user.id,
                }
            )

            # Log state change to audit
            self.env["spp.audit.rule"].log_lifecycle_action(
                model_name=self._name,
                record_id=record.id,
                action="revoke",
                old_values={"status": old_status},
                new_values={"status": "revoked"},
            )

        # Prefetch partner names to avoid N+1 query
        partner_names = {rec.id: rec.partner_id.name if rec.partner_id else "Unknown" for rec in self}
        user_name = self.env.user.name
        for record in self:
            _logger.info(
                "Revoked credential %s for partner %s by user %s", record.name, partner_names[record.id], user_name
            )

    def action_regenerate(self):
        """Regenerate credential with fresh data."""
        self.ensure_one()

        if self.status == "revoked":
            raise UserError(_("Cannot regenerate revoked credential. Create a new one instead."))

        # Update expiration time
        validity_days = self.issuer_config_id.default_validity_days
        self.write(
            {
                "issued_at": fields.Datetime.now(),
                "expires_at": fields.Datetime.now() + timedelta(days=validity_days),
            }
        )

        # Regenerate credential
        return self.generate_credential()

    def _generate_qr_image(self):
        """
        Generate QR code image from qr_data.

        Returns:
            Base64 encoded PNG image
        """
        if not self.qr_data:
            return False

        try:
            # Create QR code
            # Use ERROR_CORRECT_M (15%) for better scanning reliability on physical documents
            qr = qrcode.QRCode(
                version=None,  # Auto-size
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(self.qr_data)
            qr.make(fit=True)

            # Generate image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to bytes
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_bytes = buffer.getvalue()

            return base64.b64encode(img_bytes)

        except Exception as e:
            _logger.error("Failed to generate QR image for credential %s: %s", self.name, str(e), exc_info=True)
            return False

    @api.constrains("issued_at", "expires_at")
    def _check_validity_dates(self):
        """Validate that expiration is after issuance."""
        for record in self:
            if record.expires_at <= record.issued_at:
                raise ValidationError(_("Expiration date must be after issuance date"))

    def action_download_qr(self):
        """Download QR code image with audit logging."""
        self.ensure_one()

        if not self.qr_image:
            raise UserError(_("No QR code image available for download"))

        # Log download action
        self.env["spp.audit.rule"].log_lifecycle_action(
            model_name=self._name,
            record_id=self.id,
            action="download",
            new_values={"downloaded_by": self.env.user.name},
        )

        _logger.info("QR credential %s downloaded by user %s", self.name, self.env.user.name)

        # Return download action
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/image/{self._name}/{self.id}/qr_image/" f"qr_{self.name}.png?download=true",
            "target": "self",
        }

    def action_download_public_key(self):
        """Download public key as JWK file."""
        self.ensure_one()

        if not self.public_key_jwk:
            raise UserError(_("No public key available for download"))

        # Create attachment for download
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"public_key_{self.name}.jwk",
                "type": "binary",
                "datas": base64.b64encode(self.public_key_jwk.encode("utf-8")),
                "mimetype": "application/json",
            }
        )

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }
