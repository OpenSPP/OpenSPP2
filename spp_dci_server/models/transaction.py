# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Transaction model for async operation tracking with queue_job."""

import json
import logging
import uuid
from datetime import UTC, datetime

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci.schemas.constants import SearchStatusReasonCode
from odoo.addons.spp_dci.services import DCIErrorMessages

from ..utils.url_validator import validate_callback_url

_logger = logging.getLogger(__name__)


class DCITransaction(models.Model):
    """Track async DCI transactions with queue_job integration.

    This model stores async DCI requests (search, subscribe, etc.) and
    manages background processing via queue_job. It tracks:
    - Original request payload
    - Processing state transitions
    - Response/callback delivery status
    - Job execution metadata
    """

    _name = "spp.dci.transaction"
    _description = "DCI Async Transaction"
    _rec_name = "transaction_id"
    _order = "create_date desc"

    _transaction_sender_uniq = models.Constraint(
        "UNIQUE(transaction_id, sender_uri)",
        "Transaction ID must be unique per sender",
    )

    # DCI Message Identifiers
    transaction_id = fields.Char(
        required=True,
        index=True,
        string="Transaction ID",
        help="DCI transaction_id from request message",
    )
    message_id = fields.Char(
        required=True,
        string="Message ID",
        help="DCI message_id from request header",
    )
    correlation_id = fields.Char(
        string="Correlation ID",
        help="Generated correlation_id for response tracking",
        default=lambda self: str(uuid.uuid4()),
    )

    # Transaction Type
    action = fields.Selection(
        [
            ("search", "Search"),
            ("subscribe", "Subscribe"),
            ("unsubscribe", "Unsubscribe"),
            ("notify", "Notify"),
            ("txn_status", "Transaction Status"),
        ],
        required=True,
        string="Action",
        help="DCI action type",
    )
    reg_type = fields.Selection(
        [
            ("SOCIAL_REGISTRY", "Social Registry"),
            ("DR", "Disability Registry"),
            ("FR", "Farmer Registry"),
            ("IBR", "Integrated Beneficiary Registry"),
        ],
        string="Registry Type",
    )

    # Sender Information
    sender_id = fields.Many2one(
        "spp.dci.sender.registry",
        string="Sender",
        help="DCI sender who initiated the request",
        ondelete="set null",
    )
    sender_uri = fields.Char(
        string="Sender URI",
        index=True,
        help="Original sender_id string from request",
    )
    callback_uri = fields.Char(
        string="Callback URI",
        help="URL to send async response/callback",
    )

    # Payload Storage
    request_payload = fields.Text(
        string="Request Payload",
        help="Original DCI request as JSON",
    )
    response_payload = fields.Text(
        string="Response Payload",
        help="Generated DCI response as JSON",
    )

    # Processing State
    state = fields.Selection(
        [
            ("received", "Received"),
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("success", "Success"),
            ("rejected", "Rejected"),
            ("callback_sent", "Callback Sent"),
            ("callback_failed", "Callback Failed"),
        ],
        default="received",
        required=True,
        string="State",
        help="DCI status codes: rcvd, pdng, succ, rjct",
    )
    dci_status = fields.Selection(
        [
            ("rcvd", "Received"),
            ("pdng", "Pending"),
            ("succ", "Success"),
            ("rjct", "Rejected"),
        ],
        compute="_compute_dci_status",
        string="DCI Status",
        help="DCI standard status code",
    )

    # Error Handling
    error_code = fields.Char(
        string="Error Code",
        help="DCI status_reason_code",
    )
    error_message = fields.Text(
        string="Error Message",
        help="DCI status_reason_message",
    )
    retry_count = fields.Integer(
        default=0,
        string="Retry Count",
    )
    max_retries = fields.Integer(
        default=3,
        string="Max Retries",
    )

    # queue_job Integration
    job_uuid = fields.Char(
        string="Job UUID",
        help="queue_job UUID for tracking",
        index=True,
    )
    job_state = fields.Char(
        string="Job State",
        compute="_compute_job_state",
        help="Current queue_job state",
    )

    # Timing
    received_at = fields.Datetime(
        default=fields.Datetime.now,
        string="Received At",
    )
    processed_at = fields.Datetime(
        string="Processed At",
    )
    callback_sent_at = fields.Datetime(
        string="Callback Sent At",
    )

    @api.depends("state")
    def _compute_dci_status(self):
        """Map internal state to DCI status code."""
        state_to_dci = {
            "received": "rcvd",
            "pending": "pdng",
            "processing": "pdng",
            "success": "succ",
            "rejected": "rjct",
            "callback_sent": "succ",
            "callback_failed": "succ",  # Processing succeeded, callback failed
        }
        for record in self:
            record.dci_status = state_to_dci.get(record.state, "pdng")

    def _compute_job_state(self):
        """Get queue_job state if available."""
        for record in self:
            if record.job_uuid and "queue.job" in self.env:
                job = self.env["queue.job"].search([("uuid", "=", record.job_uuid)], limit=1)
                record.job_state = job.state if job else "unknown"
            else:
                record.job_state = "n/a"

    def process_async_search(self):
        """Execute search and send callback. Called by queue_job.

        This method is decorated with @job when queue_job is available.
        """
        self.ensure_one()
        self.state = "processing"

        try:
            # Parse request
            request_data = json.loads(self.request_payload)

            # Import search service based on registry type
            if self.reg_type == "SOCIAL_REGISTRY":
                from odoo.addons.spp_dci.schemas.search import SearchRequest
                from odoo.addons.spp_dci_server_social.services import (
                    DCISocialSearchService,
                )

                service = DCISocialSearchService(self.env, self.sender_id)
                # Inject transaction's correlation_id into the message before parsing
                # This ensures the callback uses the same correlation_id as the ACK
                message_data = request_data["message"].copy()
                message_data["correlation_id"] = self.correlation_id
                search_request = SearchRequest(**message_data)
                response = service.execute_search(search_request)
            else:
                raise UserError(_("Unsupported registry type: %s") % self.reg_type)

            # Store response
            self.response_payload = response.model_dump_json()
            self.state = "success"
            self.processed_at = fields.Datetime.now()

            # Send callback
            if self.callback_uri:
                self._send_callback(response)

        except Exception as e:
            self.state = "rejected"
            self.error_code = SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value
            self.error_message = str(e)[:2000]
            _logger.exception("DCI async search failed: %s", self.transaction_id)

    def _send_callback(self, response):
        """Send callback to sender's callback_uri.

        Args:
            response: Pydantic response model
        """
        if not self.callback_uri:
            _logger.warning("No callback_uri for transaction %s", self.transaction_id)
            return

        # SECURITY: Validate callback URL to prevent SSRF
        try:
            config = self.env["ir.config_parameter"].sudo()
            allow_http = config.get_param("dci.allow_http_callbacks", "false").lower() == "true"
            skip_ip_check = config.get_param("dci.allow_internal_callback_ips", "false").lower() == "true"
            validate_callback_url(
                self.callback_uri,
                require_https=not allow_http,
                skip_ip_check=skip_ip_check,
            )
        except ValidationError as e:
            _logger.error(
                "Callback URL validation failed for transaction %s: %s",
                self.transaction_id,
                str(e),
            )
            self.state = "callback_failed"
            self.error_code = SearchStatusReasonCode.REFERENCE_ID_INVALID.value
            self.error_message = "Callback URL validation failed"
            return

        try:
            # Build callback envelope
            callback_data = self._build_callback_envelope(response)

            # Send with timeout (reduced from 30s to 10s per security review)
            resp = requests.post(
                self.callback_uri,
                json=callback_data,
                timeout=10,
                headers={
                    "Content-Type": "application/json",
                    "X-DCI-Transaction-ID": self.transaction_id,
                },
            )
            resp.raise_for_status()

            self.state = "callback_sent"
            self.callback_sent_at = fields.Datetime.now()
            _logger.info("Callback sent for transaction %s", self.transaction_id)

        except requests.exceptions.RequestException as e:
            self.retry_count += 1
            # Log full error internally, store generic message for external
            _logger.warning(
                "Callback failed for transaction %s: %s",
                self.transaction_id,
                str(e),
            )
            self.error_message = DCIErrorMessages.CALLBACK_FAILED

            if self.retry_count < self.max_retries:
                # Queue retry with exponential backoff
                delay = 60 * (2 ** (self.retry_count - 1))  # 60s, 120s, 240s
                _logger.warning(
                    "Callback failed for %s, retrying in %ds (attempt %d/%d)",
                    self.transaction_id,
                    delay,
                    self.retry_count,
                    self.max_retries,
                )
                self.with_delay(
                    channel="root.dci",
                    eta=delay,
                    description=f"DCI Retry Callback {self.transaction_id}",
                )._retry_callback()
            else:
                self.state = "callback_failed"
                _logger.error(
                    "Callback permanently failed for %s after %d attempts",
                    self.transaction_id,
                    self.max_retries,
                )

    def _retry_callback(self):
        """Retry sending callback. Called by queue_job.

        Rebuilds the full DCI envelope from stored response_payload
        to ensure consistent callback format on retries.
        """
        self.ensure_one()
        if not self.response_payload:
            _logger.warning("No response payload for retry: %s", self.transaction_id)
            self.state = "callback_failed"
            return

        if not self.callback_uri:
            _logger.warning("No callback URI for retry: %s", self.transaction_id)
            return

        # SECURITY: Re-validate URL on retry (URL could have changed DNS)
        try:
            config = self.env["ir.config_parameter"].sudo()
            allow_http = config.get_param("dci.allow_http_callbacks", "false").lower() == "true"
            skip_ip_check = config.get_param("dci.allow_internal_callback_ips", "false").lower() == "true"
            validate_callback_url(
                self.callback_uri,
                require_https=not allow_http,
                skip_ip_check=skip_ip_check,
            )
        except ValidationError as e:
            _logger.error("Callback URL validation failed on retry: %s", str(e))
            self.state = "callback_failed"
            self.error_message = "Callback URL validation failed"
            return

        try:
            # Reconstruct response from stored payload
            response_data = json.loads(self.response_payload)

            # CRITICAL FIX: Rebuild full envelope (not just raw response)
            # This ensures retries send the same format as initial callback
            callback_envelope = self._build_callback_envelope_from_dict(response_data)

            resp = requests.post(
                self.callback_uri,
                json=callback_envelope,
                timeout=10,
                headers={
                    "Content-Type": "application/json",
                    "X-DCI-Transaction-ID": self.transaction_id,
                },
            )
            resp.raise_for_status()
            self.state = "callback_sent"
            self.callback_sent_at = fields.Datetime.now()
            _logger.info("Retry callback sent for transaction %s", self.transaction_id)

        except requests.exceptions.RequestException as e:
            _logger.warning("Retry callback failed for %s: %s", self.transaction_id, str(e))
            self.error_message = DCIErrorMessages.CALLBACK_FAILED
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                delay = 60 * (2 ** (self.retry_count - 1))
                self.with_delay(
                    channel="root.dci",
                    eta=delay,
                    description=f"DCI Retry Callback {self.transaction_id}",
                )._retry_callback()
            else:
                self.state = "callback_failed"
                _logger.error(
                    "Retry callback permanently failed for %s after %d attempts",
                    self.transaction_id,
                    self.max_retries,
                )

    def _build_callback_envelope_from_dict(self, response_data: dict) -> dict:
        """Build DCI callback envelope from response dict (for retries).

        Args:
            response_data: Response data dict (from stored JSON)

        Returns:
            Full DCI envelope dict
        """
        from ..services.response_signer import DCIResponseSigner

        sender_id = self.env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")

        # Build header with required fields per SPDCI spec
        # Map action to callback action name per DCI spec
        callback_action = self._get_callback_action()
        header = {
            "version": "1.0.0",
            "message_id": str(uuid.uuid4()),
            "message_ts": datetime.now(UTC).isoformat(),
            "action": callback_action,
            "status": self.dci_status,
            "sender_id": sender_id,
            "receiver_id": self.sender_uri,
            "total_count": 1,  # Required by SPDCI OpenAPI spec for callbacks
        }
        # Only add error fields if they have actual string values
        if self.error_code and isinstance(self.error_code, str):
            header["status_reason_code"] = self.error_code
        if self.error_message and isinstance(self.error_message, str):
            header["status_reason_message"] = str(self.error_message)[:999]

        # Sign the envelope
        try:
            signer = DCIResponseSigner(self.env)
            signature = signer.sign_envelope(header, response_data)
        except Exception as e:
            _logger.warning("Failed to sign callback envelope: %s. Sending unsigned.", str(e))
            signature = ""

        return {
            "signature": signature,
            "header": header,
            "message": response_data,
        }

    def _get_callback_action(self) -> str:
        """Get the callback action name per DCI spec.

        DCI spec uses specific action names for callbacks:
        - search -> on-search
        - subscribe -> on-subscribe
        - unsubscribe -> on-unsubscribe
        - txn_status -> txn-on-status

        Returns:
            str: The callback action name
        """
        action_map = {
            "search": "on-search",
            "subscribe": "on-subscribe",
            "unsubscribe": "on-unsubscribe",
            "txn_status": "txn-on-status",
            "notify": "on-notify",
        }
        return action_map.get(self.action, f"on-{self.action}")

    def _build_callback_envelope(self, response) -> dict:
        """Build DCI callback envelope from response.

        Args:
            response: Pydantic response model

        Returns:
            DCI envelope dict with signature, header, message
        """
        from ..services.response_signer import DCIResponseSigner

        sender_id = self.env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")

        # Build header with required fields per SPDCI spec
        callback_action = self._get_callback_action()
        header = {
            "version": "1.0.0",
            "message_id": str(uuid.uuid4()),
            "message_ts": datetime.now(UTC).isoformat(),
            "action": callback_action,
            "status": self.dci_status,
            "sender_id": sender_id,
            "receiver_id": self.sender_uri,
            "total_count": 1,  # Required by SPDCI OpenAPI spec for callbacks
        }
        # Only add error fields if they have actual string values
        if self.error_code and isinstance(self.error_code, str):
            header["status_reason_code"] = self.error_code
        if self.error_message and isinstance(self.error_message, str):
            header["status_reason_message"] = str(self.error_message)[:999]

        message = (
            response.model_dump(mode="json", by_alias=True, exclude_none=True)
            if hasattr(response, "model_dump")
            else response
        )

        # Sign the envelope
        try:
            signer = DCIResponseSigner(self.env)
            signature = signer.sign_envelope(header, message)
        except Exception as e:
            _logger.warning("Failed to sign callback envelope: %s. Sending unsigned.", str(e))
            signature = ""

        return {
            "signature": signature,
            "header": header,
            "message": message,
        }

    def process_async_subscribe(self):
        """Process subscribe request and send callback. Called by queue_job.

        For subscribe operations, the subscription is already created during
        the initial request. This method builds the response and sends callback.
        """
        self.ensure_one()
        self.state = "processing"

        try:
            # Parse request to get subscription details
            request_data = json.loads(self.request_payload)
            message = request_data.get("message", {})
            transaction_id = message.get("transaction_id", self.transaction_id)

            # Build subscribe response based on stored data
            # The subscription records were created during the initial request
            subscribe_response = {
                "transaction_id": transaction_id,
                "correlation_id": self.correlation_id,
                "subscribe_response": [],
            }

            # Look up subscriptions created for this transaction
            subscriptions = (
                self.env["spp.dci.subscription"].sudo().search([("original_transaction_id", "=", transaction_id)])
            )

            for sub in subscriptions:
                subscribe_response["subscribe_response"].append(
                    {
                        "reference_id": f"ref-{sub.subscription_code}",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "status": "succ" if sub.state == "confirmed" else "pdng",
                        "subscription_code": sub.subscription_code,
                    }
                )

            # If no subscriptions found, add a placeholder
            if not subscribe_response["subscribe_response"]:
                subscribe_response["subscribe_response"].append(
                    {
                        "reference_id": f"ref-{transaction_id}",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "status": "succ",
                    }
                )

            # Store response
            self.response_payload = json.dumps(subscribe_response)
            self.state = "success"
            self.processed_at = fields.Datetime.now()

            # Send callback
            if self.callback_uri:
                self._send_callback_dict(subscribe_response)

        except Exception as e:
            self.state = "rejected"
            self.error_code = "rjct.subscribe.error"
            self.error_message = str(e)[:2000]
            _logger.exception("DCI async subscribe failed: %s", self.transaction_id)

    def process_async_unsubscribe(self):
        """Process unsubscribe request and send callback. Called by queue_job.

        For unsubscribe operations, subscriptions are already cancelled during
        the initial request. This method builds the response and sends callback.
        """
        self.ensure_one()
        self.state = "processing"

        try:
            # Parse request
            request_data = json.loads(self.request_payload)
            message = request_data.get("message", {})
            transaction_id = message.get("transaction_id", self.transaction_id)
            subscription_codes = message.get("subscription_codes", [])

            # Build unsubscribe response
            unsubscribe_response = {
                "transaction_id": transaction_id,
                "correlation_id": self.correlation_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "succ",
                "subscription_status": [],
            }

            for code in subscription_codes:
                unsubscribe_response["subscription_status"].append(
                    {
                        "code": code,
                        "status": "unsubscribe",
                    }
                )

            # Store response
            self.response_payload = json.dumps(unsubscribe_response)
            self.state = "success"
            self.processed_at = fields.Datetime.now()

            # Send callback
            if self.callback_uri:
                self._send_callback_dict(unsubscribe_response)

        except Exception as e:
            self.state = "rejected"
            self.error_code = "rjct.unsubscribe.error"
            self.error_message = str(e)[:2000]
            _logger.exception("DCI async unsubscribe failed: %s", self.transaction_id)

    def process_async_txn_status(self):
        """Process transaction status request and send callback. Called by queue_job.

        Looks up the status of the referenced transaction and sends callback.
        """
        self.ensure_one()
        self.state = "processing"

        try:
            # Parse request
            request_data = json.loads(self.request_payload)
            message = request_data.get("message", {})
            transaction_id = message.get("transaction_id", self.transaction_id)
            txnstatus_request = message.get("txnstatus_request", {})

            # Look up the referenced transaction
            attr_type = txnstatus_request.get("attribute_type", "transaction_id")
            attr_value = txnstatus_request.get("attribute_value", "")
            txn_type = txnstatus_request.get("txn_type", "search")

            domain = [("sender_uri", "=", self.sender_uri)]
            if attr_type == "transaction_id":
                domain.append(("transaction_id", "=", attr_value))
            elif attr_type == "correlation_id":
                domain.append(("correlation_id", "=", attr_value))

            referenced_txn = self.env["spp.dci.transaction"].sudo().search(domain, limit=1)

            # Build response
            if referenced_txn and referenced_txn.response_payload:
                try:
                    txn_status_obj = json.loads(referenced_txn.response_payload)
                except (json.JSONDecodeError, TypeError):
                    txn_status_obj = self._build_minimal_txn_status(
                        referenced_txn.transaction_id,
                        referenced_txn.dci_status,
                        txn_type,
                    )
            elif referenced_txn:
                txn_status_obj = self._build_minimal_txn_status(
                    referenced_txn.transaction_id,
                    referenced_txn.dci_status,
                    txn_type,
                )
            else:
                txn_status_obj = self._build_minimal_txn_status(
                    str(attr_value),
                    "rjct",
                    txn_type,
                    "rjct.reference_id.invalid",
                    "Transaction not found",
                )

            txnstatus_response = {
                "transaction_id": transaction_id,
                "correlation_id": self.correlation_id,
                "txnstatus_response": {
                    "txn_type": txn_type,
                    "txn_status": txn_status_obj,
                },
            }

            # Store response
            self.response_payload = json.dumps(txnstatus_response)
            self.state = "success"
            self.processed_at = fields.Datetime.now()

            # Send callback
            if self.callback_uri:
                self._send_callback_dict(txnstatus_response)

        except Exception as e:
            self.state = "rejected"
            self.error_code = "rjct.txnstatus.error"
            self.error_message = str(e)[:2000]
            _logger.exception("DCI async txn status failed: %s", self.transaction_id)

    def _build_minimal_txn_status(
        self,
        transaction_id: str,
        status: str,
        txn_type: str,
        status_reason_code: str | None = None,
        status_reason_message: str | None = None,
    ) -> dict:
        """Build a minimal status response object."""
        response = {
            "transaction_id": transaction_id,
            "correlation_id": str(uuid.uuid4()),
        }
        # Add type-specific response field
        if txn_type == "search":
            response["search_response"] = [
                {
                    "reference_id": f"ref-{transaction_id}",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "status": status,
                }
            ]
            if status_reason_code:
                response["search_response"][0]["status_reason_code"] = status_reason_code
            if status_reason_message:
                response["search_response"][0]["status_reason_message"] = status_reason_message
        elif txn_type == "subscribe":
            response["subscribe_response"] = [
                {
                    "reference_id": f"ref-{transaction_id}",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "status": status,
                }
            ]
        return response

    def _send_callback_dict(self, response_dict: dict):
        """Send callback with dict response (for subscribe/unsubscribe/txn-status).

        Args:
            response_dict: Response data as dict
        """
        if not self.callback_uri:
            _logger.warning("No callback_uri for transaction %s", self.transaction_id)
            return

        # SECURITY: Validate callback URL to prevent SSRF
        try:
            config = self.env["ir.config_parameter"].sudo()
            allow_http = config.get_param("dci.allow_http_callbacks", "false").lower() == "true"
            skip_ip_check = config.get_param("dci.allow_internal_callback_ips", "false").lower() == "true"
            validate_callback_url(
                self.callback_uri,
                require_https=not allow_http,
                skip_ip_check=skip_ip_check,
            )
        except ValidationError as e:
            _logger.error(
                "Callback URL validation failed for transaction %s: %s",
                self.transaction_id,
                str(e),
            )
            self.state = "callback_failed"
            self.error_code = "rjct.callback.invalid_url"
            self.error_message = "Callback URL validation failed"
            return

        try:
            # Build callback envelope
            callback_data = self._build_callback_envelope_from_dict(response_dict)

            # Send with timeout
            resp = requests.post(
                self.callback_uri,
                json=callback_data,
                timeout=10,
                headers={
                    "Content-Type": "application/json",
                    "X-DCI-Transaction-ID": self.transaction_id,
                },
            )
            resp.raise_for_status()

            self.state = "callback_sent"
            self.callback_sent_at = fields.Datetime.now()
            _logger.info("Callback sent for transaction %s", self.transaction_id)

        except requests.exceptions.RequestException as e:
            self.retry_count += 1
            _logger.warning(
                "Callback failed for transaction %s: %s",
                self.transaction_id,
                str(e),
            )
            self.error_message = DCIErrorMessages.CALLBACK_FAILED

            if self.retry_count < self.max_retries:
                delay = 60 * (2 ** (self.retry_count - 1))
                _logger.warning(
                    "Callback failed for %s, retrying in %ds (attempt %d/%d)",
                    self.transaction_id,
                    delay,
                    self.retry_count,
                    self.max_retries,
                )
                self.with_delay(
                    channel="root.dci",
                    eta=delay,
                    description=f"DCI Retry Callback {self.transaction_id}",
                )._retry_callback()
            else:
                self.state = "callback_failed"
                _logger.error(
                    "Callback permanently failed for %s after %d attempts",
                    self.transaction_id,
                    self.max_retries,
                )

    def action_retry_callback(self):
        """Manual action to retry callback."""
        self.ensure_one()
        if self.state in ("callback_failed", "success") and self.response_payload:
            self.retry_count = 0
            self._retry_callback()

    def action_view_job(self):
        """View the queue_job record."""
        self.ensure_one()
        if not self.job_uuid:
            raise UserError(_("No job associated with this transaction"))

        job = self.env["queue.job"].search([("uuid", "=", self.job_uuid)], limit=1)
        if not job:
            raise UserError(_("Job not found"))

        return {
            "type": "ir.actions.act_window",
            "res_model": "queue.job",
            "res_id": job.id,
            "view_mode": "form",
            "target": "current",
        }
