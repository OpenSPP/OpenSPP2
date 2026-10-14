# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
import uuid
from urllib.parse import urlsplit

import requests

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.spp_api_v2.services.registrant_resolver import primary_registry_id

_logger = logging.getLogger(__name__)

PROTECTION_CONCERN_NS = "urn:openspp:vocab:protection-concern"
PROTECTION_RISK_NS = "urn:openspp:vocab:protection-risk-level"

WEBHOOK_URL_PARAM = "spp_primero.webhook_url"
WEBHOOK_API_KEY_PARAM = "spp_primero.webhook_api_key"
WEBHOOK_ALLOW_INSECURE_PARAM = "spp_primero.allow_insecure_webhook"
# (connect, read) seconds: an unreachable OpenFn must not pin an Odoo worker for long.
WEBHOOK_TIMEOUT = (3.05, 10)
WEBHOOK_EVENT = "protection_concern.referred"
# Plain http is acceptable only when the webhook stays on this machine.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal")
RUN_REF_MAX_LENGTH = 128
# Managers imply officers (spp_registry/security/groups.xml).
REFERRER_GROUP = "spp_registry.group_registry_officer"

# Lightning answers 401 to a missing key but 404 to a wrong one (it hides the trigger's existence).
FAILURE_HINTS = {
    "HTTP 401": "check the API key under Settings > Primero Referral",
    "HTTP 403": "check the API key under Settings > Primero Referral",
    "HTTP 404": "check the webhook URL and the API key under Settings > Primero Referral",
    "ConnectionError": "OpenFn is unreachable from this server",
    "Timeout": "OpenFn did not answer in time",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    # --- protection concern (what the social worker records) -------------
    protection_concern_ids = fields.Many2many(
        "spp.vocabulary.code",
        "res_partner_protection_concern_rel",
        "partner_id",
        "code_id",
        string="Protection Concerns",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{PROTECTION_CONCERN_NS}')]",
        help="Primero protection concern codes that apply to this child.",
    )
    protection_risk_level_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Risk Level",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{PROTECTION_RISK_NS}')]",
        help="Primero risk level: how serious the immediate danger to the child is.",
    )
    is_protection_urgent = fields.Boolean(
        string="Urgent",
        help="The concern needs an immediate response (Primero's urgent protection concern flag).",
    )
    protection_concern_date = fields.Date(string="Date Identified")
    protection_notes = fields.Text()
    has_protection_consent_for_services = fields.Boolean(
        string="Consent to Receive Services",
        help="The child or caregiver consented to receiving services.",
    )
    has_protection_consent_other_organizations = fields.Boolean(
        string="Consent to Share with Other Organizations",
        help="The child or caregiver consented to sharing this information with other organizations.",
    )

    # --- referral outcome (set by the button; read-only in the UI) ------
    primero_referral_state = fields.Selection(
        [("not_referred", "Not Referred"), ("referred", "Referred"), ("failed", "Failed")],
        string="Primero Referral",
        default="not_referred",
        copy=False,
        readonly=True,
    )
    primero_referred_at = fields.Datetime(string="Last Referred", copy=False, readonly=True)
    primero_run_ref = fields.Char(string="OpenFn Run ID", copy=False, readonly=True)
    primero_referral_error = fields.Char(string="Last Error", copy=False, readonly=True)

    def action_refer_to_primero(self):
        """Post this child's identifier to the OpenFn webhook that starts the Primero referral workflow.

        Only the identifier leaves OpenSPP: the workflow reads the child and the concern back
        through the REST API v2. The call is synchronous because the web client saves the form
        before running the button, so everything the workflow reads is already committed.
        """
        self.ensure_one()
        if not self.env.user.has_group(REFERRER_GROUP):
            raise AccessError(_("Only registry officers and managers can refer a child to Primero."))
        if not self.is_registrant or self.is_group:
            raise UserError(_("Only an individual registrant can be referred to Primero."))
        if self.disabled:
            raise UserError(_("A disabled registrant cannot be referred to Primero."))
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

        now = fields.Datetime.now()
        payload = {
            "event": WEBHOOK_EVENT,
            "referralId": str(uuid.uuid4()),
            "identifier": [{"system": reg_id.id_type_id.uri, "value": reg_id.value}],
            "referredAt": now.replace(microsecond=0).isoformat() + "Z",
        }
        headers = {"x-api-key": api_key} if api_key else {}

        try:
            # No redirects: a 307/308 would replay the body and the key to another host.
            response = requests.post(url, json=payload, headers=headers, timeout=WEBHOOK_TIMEOUT, allow_redirects=False)
        except requests.RequestException as exc:
            return self._primero_referral_failed(type(exc).__name__)
        if not 200 <= response.status_code < 300:
            return self._primero_referral_failed(f"HTTP {response.status_code}")

        run_ref = self._primero_run_ref(response)
        self.write(
            {
                "primero_referral_state": "referred",
                "primero_referred_at": now,
                "primero_run_ref": run_ref,
                "primero_referral_error": False,
            }
        )
        if run_ref:
            body = _("Referred to Primero via OpenFn (run %s).", run_ref)
        else:
            body = _("Referred to Primero via OpenFn.")
        self.message_post(body=body, subtype_xmlid="mail.mt_note")
        return self._primero_notification(_("Referral sent"), body, "success")

    def _primero_webhook_config(self):
        """The webhook URL and API key from Settings.

        The URL must be https, or http to a local host, unless the insecure override
        parameter is set: the key and the child's identifier travel in the request.
        """
        # Reading three configuration parameters; none holds personal data.
        # nosemgrep: odoo-sudo-without-context
        params = self.env["ir.config_parameter"].sudo()
        url = (params.get_param(WEBHOOK_URL_PARAM) or "").strip()
        if not url:
            raise UserError(_("The OpenFn webhook URL is not configured. Set it under Settings > Primero Referral."))
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise UserError(_("The OpenFn webhook URL must be an http(s) URL with a host."))
        if (
            parts.scheme == "http"
            and parts.hostname not in LOCAL_HOSTS
            and params.get_param(WEBHOOK_ALLOW_INSECURE_PARAM) != "True"
        ):
            raise UserError(
                _(
                    "The OpenFn webhook URL must use https. Plain http is only allowed for an OpenFn on "
                    "this machine, or when the system parameter %s is set to True.",
                    WEBHOOK_ALLOW_INSECURE_PARAM,
                )
            )
        api_key = (params.get_param(WEBHOOK_API_KEY_PARAM) or "").strip()
        return url, api_key

    @staticmethod
    def _primero_run_ref(response):
        """The OpenFn run reference from Lightning's async reply.

        Lightning puts the run id in the ``x-meta-run-id`` header and only the work order
        id in the JSON body (``run_id`` is also accepted there). Anything else is ignored,
        never stored.
        """
        headers = getattr(response, "headers", None) or {}
        candidates = [headers.get("x-meta-run-id")]
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            candidates += [body.get("run_id"), body.get("work_order_id")]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate:
                return candidate[:RUN_REF_MAX_LENGTH]
        return False

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
        hint = FAILURE_HINTS.get(reason)
        if hint is None and reason.startswith("HTTP 3"):
            hint = "the webhook URL redirects; configure the final URL"
        if hint:
            body = _("Referral to Primero failed (%(reason)s): %(hint)s.", reason=reason, hint=hint)
        else:
            body = _("Referral to Primero failed (%s).", reason)
        self.message_post(body=body, subtype_xmlid="mail.mt_note")
        return self._primero_notification(_("Referral failed"), body, "danger")

    def _primero_notification(self, title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                # A failure stays on screen until dismissed; a success can fade.
                "sticky": notification_type == "danger",
                # The form does not reload a record after a button returns a client action,
                # so refresh it in place (keeps the breadcrumbs) to show the new state and run id.
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
