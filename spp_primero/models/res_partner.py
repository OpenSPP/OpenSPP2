# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.spp_api_v2.services.registrant_resolver import primary_registry_id

_logger = logging.getLogger(__name__)

PROTECTION_CONCERN_NS = "urn:openspp:vocab:protection-concern"
PROTECTION_RISK_NS = "urn:openspp:vocab:protection-risk-level"

WEBHOOK_URL_PARAM = "spp_primero.webhook_url"
WEBHOOK_API_KEY_PARAM = "spp_primero.webhook_api_key"
WEBHOOK_TIMEOUT = 10
WEBHOOK_EVENT = "protection_concern.referred"

REFERRER_GROUPS = (
    "spp_registry.group_registry_officer",
    "spp_registry.group_registry_manager",
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # --- protection concern (what the social worker records) -------------
    protection_concern_ids = fields.Many2many(
        "spp.vocabulary.code",
        "res_partner_protection_concern_rel",
        "partner_id",
        "code_id",
        string="Protection Concerns",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:protection-concern')]",
        help="Primero protection concern codes that apply to this child.",
    )
    protection_risk_level_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Risk Level",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:protection-risk-level')]",
    )
    protection_urgent = fields.Boolean(string="Urgent Protection Concern")
    protection_concern_date = fields.Date(string="Date Identified")
    protection_notes = fields.Text(string="Protection Notes")
    protection_consent_for_services = fields.Boolean(
        string="Consent for Services",
        help="The child or caregiver consented to receiving services.",
    )
    protection_disclosure_other_orgs = fields.Boolean(
        string="Consent to Share with Other Organisations",
        help="The child or caregiver consented to sharing this information with other organisations.",
    )

    # --- referral outcome (set by the button, read-only in the UI) ------
    primero_referral_state = fields.Selection(
        [("none", "Not Referred"), ("referred", "Referred"), ("failed", "Failed")],
        string="Primero Referral",
        default="none",
        copy=False,
        readonly=True,
    )
    primero_referred_at = fields.Datetime(string="Referred At", copy=False, readonly=True)
    primero_run_ref = fields.Char(string="OpenFn Run", copy=False, readonly=True)
    primero_referral_error = fields.Char(string="Referral Error", copy=False, readonly=True)

    def action_refer_to_primero(self):
        """Post this child's identifier to the OpenFn webhook that starts the Primero referral workflow.

        Only the identifier leaves OpenSPP: the workflow reads the child and the concern back
        through the REST API v2. The call is synchronous because the web client saves the form
        before running the button, so everything the workflow reads is already committed.
        """
        self.ensure_one()
        if not any(self.env.user.has_group(group) for group in REFERRER_GROUPS):
            raise AccessError(_("Only registry officers and managers can refer a child to Primero."))
        if not self.is_registrant or self.is_group:
            raise UserError(_("Only an individual registrant can be referred to Primero."))
        if not self.protection_concern_ids:
            raise UserError(_("Record at least one protection concern before referring the child to Primero."))
        # The outcome is written to the registrant after the POST. Refuse now rather than
        # send a referral OpenSPP would then roll back (e.g. "Restrict Registry Edits to
        # Admin Only" in spp_starter_sp_mis withholds write from non-admins).
        self.check_access("write")

        url, api_key = self._primero_webhook_config()
        reg_id = primary_registry_id(self)
        if not reg_id:
            raise UserError(_("The child needs an identifier before a referral can be sent."))

        payload = {
            "event": WEBHOOK_EVENT,
            "identifier": [{"system": reg_id.id_type_id.uri, "value": reg_id.value}],
            "referredAt": fields.Datetime.now().replace(microsecond=0).isoformat() + "Z",
        }
        headers = {"x-api-key": api_key} if api_key else {}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=WEBHOOK_TIMEOUT)
        except requests.RequestException as exc:
            return self._primero_referral_failed(type(exc).__name__)
        if not 200 <= response.status_code < 300:
            return self._primero_referral_failed(f"HTTP {response.status_code}")

        try:
            run_ref = response.json().get("run_id") or False
        except (ValueError, AttributeError):
            run_ref = False
        self.write(
            {
                "primero_referral_state": "referred",
                "primero_referred_at": fields.Datetime.now(),
                "primero_run_ref": run_ref,
                "primero_referral_error": False,
            }
        )
        if run_ref:
            body = _("Referred to Primero via OpenFn (run %s).", run_ref)
        else:
            body = _("Referred to Primero via OpenFn.")
        self.message_post(body=body)
        return self._primero_notification(_("Referral sent"), body, "success")

    def _primero_webhook_config(self):
        """The webhook URL and API key from Settings; the URL is required and must be http(s)."""
        # Reading two configuration parameters; neither holds personal data.
        params = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        url = (params.get_param(WEBHOOK_URL_PARAM) or "").strip()
        if not url:
            raise UserError(_("The OpenFn webhook URL is not configured. Set it under Settings > Primero Referral."))
        if not url.startswith(("http://", "https://")):
            raise UserError(_("The OpenFn webhook URL must start with http:// or https://."))
        api_key = (params.get_param(WEBHOOK_API_KEY_PARAM) or "").strip()
        return url, api_key

    def _primero_referral_failed(self, reason):
        # Only the record id and a short reason: never the child's data or the response body.
        _logger.warning("Primero referral failed for partner id=%s: %s", self.id, reason)
        self.write(
            {
                "primero_referral_state": "failed",
                "primero_run_ref": False,
                "primero_referral_error": reason,
            }
        )
        body = _("Referral to Primero failed (%s).", reason)
        self.message_post(body=body)
        return self._primero_notification(_("Referral failed"), body, "danger")

    @staticmethod
    def _primero_notification(title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
