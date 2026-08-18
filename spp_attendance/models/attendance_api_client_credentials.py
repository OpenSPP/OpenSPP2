import base64
import calendar
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spp_oauth.tools import calculate_signature

TOKEN_EXPIRATION_MIN = os.getenv("ATTENDANCE_TOKEN_EXPIRATION_MIN", 10)

# scrypt parameters (memory-hard, GPU-resistant) — same construction as
# spp_api_v2's spp.api.client so secret handling is uniform across the stack
SCRYPT_N = 16384  # CPU/memory cost factor (must be power of 2)
SCRYPT_R = 8  # Block size
SCRYPT_P = 1  # Parallelization factor
SCRYPT_DKLEN = 64  # Derived key length


class AttendanceApiClientCredential(models.Model):
    _name = "spp.attendance.api.client.credential"
    _description = "SPP Attendance Client Credential"

    @api.model
    def _generate_client_id(self):
        client_id = str(uuid.uuid4())
        while self.search_count([("client_id", "=", client_id)]):
            client_id = str(uuid.uuid4())

        return f"c-id-{client_id}"

    @api.model
    def _generate_client_secret(self):
        return f"c-secret-{secrets.token_urlsafe(32)}"

    name = fields.Char("Client Name", required=True)

    # bearer fields
    client_id = fields.Char(required=True, readonly=True, default=_generate_client_id)
    # Plaintext secret exists only between creation and the one-time display;
    # it is scrubbed as soon as the credentials are shown. Only the scrypt
    # hash below is kept for authentication.
    client_secret = fields.Char(readonly=True)
    client_secret_hash = fields.Char(readonly=True)

    show_button_clicked = fields.Boolean("Viewed?")

    _name_uniq = models.Constraint("unique(name)", "Client Name must be unique!")
    _client_id_uniq = models.Constraint("unique(client_id)", "Client ID must be unique!")

    ALLOW_EXPORT = False

    @api.model
    def _hash_secret(self, secret):
        """Hash a secret using scrypt.

        Format: $scrypt$salt_base64$hash_base64
        """
        salt = os.urandom(16)
        hash_bytes = hashlib.scrypt(
            secret.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(hash_bytes).decode("ascii")
        return f"$scrypt${salt_b64}${hash_b64}"

    @api.model
    def _verify_secret(self, secret, secret_hash):
        """Verify a secret against its scrypt hash in constant time."""
        if not secret or not secret_hash:
            return False
        try:
            _empty, scheme, salt_b64, hash_b64 = secret_hash.split("$")
            if scheme != "scrypt":
                return False
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(hash_b64)
        except (ValueError, TypeError):
            return False

        candidate = hashlib.scrypt(
            secret.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
        return hmac.compare_digest(candidate, expected)

    @api.model
    def authenticate(self, client_id, client_secret):
        """Return the matching credential record, or an empty recordset.

        Lookup is by client_id only; the secret is verified against the
        stored scrypt hash — plaintext secrets are never compared or stored.
        """
        credential = self.search([("client_id", "=", client_id)], limit=1)
        if not credential:
            return self.browse()
        if not self._verify_secret(client_secret, credential.client_secret_hash):
            return self.browse()
        return credential

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("client_secret"):
                vals["client_secret"] = self._generate_client_secret()
            vals["client_secret_hash"] = self._hash_secret(vals["client_secret"])
            # Plaintext stays only until show_credentials() scrubs it
        return super().create(vals_list)

    @api.model
    def generate_access_token(self):
        today = datetime.today()
        expiry_datetime = today + timedelta(minutes=TOKEN_EXPIRATION_MIN)

        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "iat": calendar.timegm(today.timetuple()),
            "exp": calendar.timegm(expiry_datetime.timetuple()),
            "iss": "openspp:auth-service",
        }

        return calculate_signature(self.env, header, payload)

    def _open_show_credentials_wizard(self, client_secret):
        """Open the one-time display wizard and scrub the stored plaintext."""
        self.ensure_one()
        wizard = self.env["spp.attendance.show.credential.wizard"].create(
            {
                "credential_id": self.id,
                "client_name": self.name,
                "display_client_id": self.client_id,
                "display_client_secret": client_secret,
            }
        )
        # Scrub before the dialog even renders: the wizard record carries the
        # value; the credential record keeps only the hash from here on.
        self.write({"client_secret": False, "show_button_clicked": True})
        return {
            "type": "ir.actions.act_window",
            "name": _("Attendance Client Credentials"),
            "res_model": "spp.attendance.show.credential.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "view_id": self.env.ref("spp_attendance.view_spp_attendance_show_credential_wizard_form").id,
            "target": "new",
        }

    def show_credentials(self):
        self.ensure_one()

        if self.show_button_clicked or not self.client_secret:
            raise UserError(_("Client ID and Client Secret is already showed once."))

        return self._open_show_credentials_wizard(self.client_secret)

    def action_regenerate_secret(self):
        """Rotate the secret: store the new hash, display the plaintext once."""
        self.ensure_one()
        new_secret = self._generate_client_secret()
        self.write({"client_secret_hash": self._hash_secret(new_secret)})
        return self._open_show_credentials_wizard(new_secret)

    def export_data(self, fields_to_export):
        if not self.ALLOW_EXPORT:
            raise UserError(_("Not allowed to export on this model."))

        return super().export_data(fields_to_export)
