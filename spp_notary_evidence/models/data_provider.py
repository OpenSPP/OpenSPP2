# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Notary extensions for CEL data providers."""

import logging
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spp_notary_client.services.audit_log import hmac_subject_hash
from odoo.addons.spp_notary_client.services.client import NotaryClient
from odoo.addons.spp_notary_client.services.exceptions import NotaryError, NotarySubjectIdMissing
from odoo.addons.spp_notary_client.services.schemas import CatalogResponse

from .notary_claim import data_value_type_for_cel, normalize_notary_value_type

_logger = logging.getLogger(__name__)


class DataProvider(models.Model):
    """Extend external providers with Notary catalog and execution behavior."""

    _name = "spp.data.provider"
    _inherit = ["spp.data.provider", "mail.thread", "mail.activity.mixin"]
    _description = "External Data Provider"

    provider_kind = fields.Selection(
        selection_add=[("notary", "Notary")],
        ondelete={"notary": "set default"},
    )
    auth_type = fields.Selection(selection_add=[("bearer", "Bearer Token")], ondelete={"bearer": "set default"})
    notary_bearer_token = fields.Char(
        string="Notary Bearer Token",
        groups="spp_notary_evidence.group_notary_evidence_manager",
    )
    notary_default_purpose_url = fields.Char(string="Default Data Purpose", tracking=True)
    notary_unavailable_policy = fields.Selection(
        selection=[
            ("raise", "Raise"),
            ("stale_cache_with_audit", "Use Stale Cache With Audit"),
            ("null", "Return Null"),
        ],
        default="raise",
        required=True,
        tracking=True,
    )
    notary_subject_id_type_id = fields.Many2one(
        comodel_name="spp.vocabulary.code",
        string="Notary Subject ID Type",
        domain=[("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:id-type")],
        tracking=True,
    )
    notary_sensitive_subject_id_type = fields.Boolean(compute="_compute_notary_sensitive_subject_id_type")
    notary_min_cache_ttl_seconds = fields.Integer(default=300, tracking=True)
    notary_default_ttl_seconds = fields.Integer(default=86400, tracking=True)
    notary_subject_log_secret = fields.Char(groups="spp_notary_evidence.group_notary_evidence_manager")
    notary_catalog_path = fields.Char(
        string="Notary Catalog Path",
        default="/v1/claims",
        help="Relative endpoint used by older mock clients. The real Notary client uses GET /v1/claims.",
    )
    notary_catalog_synced_at = fields.Datetime(readonly=True)
    notary_sync_log = fields.Text(readonly=True)
    notary_claim_ids = fields.One2many(
        comodel_name="spp.notary.claim",
        inverse_name="provider_id",
        string="Notary Claims",
    )
    notary_claim_count = fields.Integer(compute="_compute_notary_claim_count")

    def _compute_notary_claim_count(self):
        for provider in self:
            provider.notary_claim_count = len(provider.notary_claim_ids)

    @api.depends("notary_subject_id_type_id.code", "notary_subject_id_type_id.display", "notary_subject_id_type_id.uri")
    def _compute_notary_sensitive_subject_id_type(self):
        sensitive_markers = ("national", "national_id", "nid")
        for provider in self:
            id_type = provider.notary_subject_id_type_id
            text = " ".join(str(value or "").lower() for value in (id_type.code, id_type.display, id_type.uri))
            provider.notary_sensitive_subject_id_type = bool(
                provider.provider_kind == "notary" and any(marker in text for marker in sensitive_markers)
            )

    def _notary_client(self):
        self.ensure_one()
        mock_client = self.env.context.get("notary_client")
        if mock_client:
            return mock_client
        return NotaryClient(
            {
                "base_url": self.base_url,
                "auth_type": self.auth_type,
                "api_key": self.api_key,
                "bearer_token": self.notary_bearer_token,
                "default_purpose_url": self.notary_default_purpose_url,
                "timeout_seconds": (self.timeout_ms or 5000) / 1000.0,
                "code": self.code,
                "id": self.id,
                "origin_model": self._name,
                "notary_subject_log_secret": self.notary_subject_log_secret,
                "max_retries": self.retry_max,
            },
            env=self.env,
        )

    def _managed_notary_client(self):
        client = self._notary_client()
        if isinstance(client, NotaryClient):
            return client
        return nullcontext(client)

    def _fetch_notary_catalog(self):
        self.ensure_one()
        with self._managed_notary_client() as client:
            if hasattr(client, "discover_claims"):
                return client.discover_claims()
            if hasattr(client, "get_claim_catalog"):
                return CatalogResponse.model_validate({"claims": client.get_claim_catalog()})
            if hasattr(client, "fetch_claim_catalog"):
                return CatalogResponse.model_validate({"claims": client.fetch_claim_catalog(self.notary_catalog_path)})
        raise UserError(
            _("Notary client must expose discover_claims(), get_claim_catalog(), or fetch_claim_catalog().")
        )

    def action_sync_notary_catalog(self):
        return self.action_sync_notary_claim_catalog()

    def action_sync_notary_claim_catalog(self):
        self.ensure_one()
        if self.provider_kind != "notary":
            raise UserError(_("Only Notary providers can sync a Notary claim catalog."))
        try:
            catalog = self._fetch_notary_catalog()
        except NotaryError as error:
            raise UserError(_("Notary catalog sync failed: %(error)s") % {"error": error}) from error

        return self._apply_notary_claim_catalog(catalog)

    def action_open_notary_catalog_sync_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Notary Catalog"),
            "res_model": "spp.notary.catalog.sync.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_provider_id": self.id},
        }

    def action_test_connection(self):
        self.ensure_one()
        if self.provider_kind != "notary":
            return super().action_test_connection()
        if not self.base_url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No URL Configured"),
                    "message": _("Please configure a base URL first."),
                    "type": "warning",
                },
            }

        try:
            catalog = self._fetch_notary_catalog()
        except NotaryError as error:
            message = str(error)
            if error.status_code:
                message = _("Server returned status %(status)s: %(error)s") % {
                    "status": error.status_code,
                    "error": error,
                }
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": message,
                    "type": "warning",
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection Successful"),
                "message": _("Connected to %(url)s and fetched %(count)s Notary claim(s).")
                % {
                    "url": self.base_url,
                    "count": len(catalog.claims),
                },
                "type": "success",
            },
        }

    def _apply_notary_claim_catalog(self, catalog):
        self.ensure_one()
        Claim = self.env["spp.notary.claim"]
        created = updated = deactivated = 0
        now = fields.Datetime.now()
        seen_claim_ids = set()
        catalog_claim_ids = [summary.id for summary in catalog.claims]
        existing_claims = Claim.search(
            [
                ("provider_id", "=", self.id),
                ("external_id", "in", catalog_claim_ids),
            ]
        )
        existing_by_external_id = {claim.external_id: claim for claim in existing_claims}
        create_vals_list = []
        for summary in catalog.claims:
            claim_id = summary.id
            claim_version = summary.version or ""
            seen_claim_ids.add(claim_id)
            values = {
                "provider_id": self.id,
                "external_id": claim_id,
                "claim_version": claim_version,
                "name": summary.title or claim_id,
                "description": summary.description,
                "subject_type": self._notary_subject_type(summary.subject_type),
                "value_type": normalize_notary_value_type(summary.value_type),
                "default_disclosure": summary.default_disclosure or self._notary_default_disclosure(summary),
                "last_synced_at": now,
                "active": True,
                "state": "active",
            }
            claim = existing_by_external_id.get(claim_id)
            if claim:
                version_changed = claim.claim_version != claim_version
                pinned_elsewhere = claim.pinned_version and claim.pinned_version != claim_version
                if version_changed and pinned_elsewhere:
                    values["state"] = "version_drift"
                if not claim.pinned_version and claim_version:
                    values["pinned_version"] = claim_version
                claim.write(values)
                updated += 1
            else:
                if claim_version:
                    values["pinned_version"] = claim_version
                create_vals_list.append(values)
                created += 1
        if create_vals_list:
            Claim.create(create_vals_list)
        for claim in self.notary_claim_ids:
            if claim.active and claim.external_id not in seen_claim_ids:
                claim.write({"active": False, "state": "unavailable"})
                deactivated += 1
        self.write(
            {
                "notary_catalog_synced_at": now,
                "notary_sync_log": _("Synced %(created)s created, %(updated)s updated, %(deactivated)s unavailable.")
                % {"created": created, "updated": updated, "deactivated": deactivated},
            }
        )
        result = {
            "created": created,
            "updated": updated,
            "deactivated": deactivated,
            "total": created + updated,
        }
        result.update(
            {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Notary Catalog Synced"),
                    "message": _(
                        "Created %(created)s, updated %(updated)s, and marked %(deactivated)s unavailable claims.",
                        **result,
                    ),
                    "type": "success",
                },
            }
        )
        return result

    def action_view_notary_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Notary Claims - %s") % self.name,
            "res_model": "spp.notary.claim",
            "view_mode": "list,form",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id},
        }

    def _notary_default_disclosure(self, summary):
        disclosure = getattr(summary, "disclosure", None)
        if isinstance(disclosure, str):
            return disclosure
        if isinstance(disclosure, list) and disclosure:
            return disclosure[0]
        return "predicate"

    def _notary_subject_type(self, subject_type):
        subject_type = str(subject_type or "").lower()
        aliases = {
            "person": "individual",
            "individual": "individual",
            "household": "group",
            "group": "group",
            "both": "both",
        }
        return aliases.get(subject_type, "individual")

    def _compute_external_values(self, variable, subject_ids, period_key):
        self.ensure_one()
        if self.provider_kind != "notary":
            return super()._compute_external_values(variable, subject_ids, period_key)
        claim = variable.notary_claim_id
        if not claim:
            return {}
        purpose, purpose_layer = self._notary_purpose_with_layer(claim)
        values_by_subject = {}
        try:
            subject_records = self._notary_subjects(subject_ids)
        except NotaryError as error:
            _logger.warning("Notary subject resolution failed for provider %s: %s", self.code, error)
            return {
                subject_id: value_data["value"]
                for subject_id, value_data in self._values_for_notary_error(
                    error,
                    variable,
                    subject_ids,
                    period_key,
                ).items()
            }
        if not subject_records:
            return {}
        with self._managed_notary_client() as client:
            for chunk in self._chunk_notary_subjects(subject_records):
                try:
                    response = client.batch_evaluate(
                        subjects=[subject_ref for _subject_id, subject_ref in chunk],
                        claim_refs=[self._notary_claim_ref(claim)],
                        purpose=purpose,
                        purpose_layer=purpose_layer,
                        disclosure=claim.default_disclosure,
                    )
                    values_by_subject.update(self._values_from_batch_response(response, chunk, claim))
                except NotaryError as error:
                    if self._notary_batch_operation_unsupported(error):
                        values_by_subject.update(
                            self._values_from_single_evaluate_fallback(
                                client,
                                variable,
                                chunk,
                                claim,
                                period_key,
                                purpose,
                                purpose_layer,
                            )
                        )
                        continue
                    _logger.warning("Notary batch evaluation failed for provider %s: %s", self.code, error)
                    chunk_subject_ids = [subject_id for subject_id, _subject_ref in chunk]
                    values_by_subject.update(
                        self._values_for_notary_error(
                            error,
                            variable,
                            chunk_subject_ids,
                            period_key,
                        )
                    )
                    continue
        self._write_notary_values(variable, values_by_subject, period_key)
        return {subject_id: value_data["value"] for subject_id, value_data in values_by_subject.items()}

    def _notary_batch_operation_unsupported(self, error):
        return error.status_code == 501 or error.code == "claim.operation_unsupported"

    def _values_from_single_evaluate_fallback(
        self,
        client,
        variable,
        subject_records,
        claim,
        period_key,
        purpose,
        purpose_layer,
    ):
        values_by_subject = {}
        claim_ref = self._notary_claim_ref(claim)
        for subject_id, subject_ref in subject_records:
            try:
                response = client.evaluate(
                    subject_id=subject_ref["id"],
                    subject_id_type=subject_ref.get("id_type"),
                    claim_refs=[claim_ref],
                    purpose=purpose,
                    purpose_layer=purpose_layer,
                    disclosure=claim.default_disclosure,
                )
            except NotaryError as error:
                _logger.warning("Notary single evaluation fallback failed for provider %s: %s", self.code, error)
                values_by_subject.update(self._values_for_notary_error(error, variable, [subject_id], period_key))
                continue
            result = self._first_matching_result(response.results, claim.external_id)
            if result is not None:
                values_by_subject[subject_id] = self._value_data_from_result(result)
        return values_by_subject

    def _refresh_external_value(self, variable, subject_id, period_key):
        self.ensure_one()
        if self.provider_kind != "notary":
            return super()._refresh_external_value(variable, subject_id, period_key)
        claim = variable.notary_claim_id
        subject_ref = self._notary_subject_ref(subject_id)
        if not claim or not subject_ref:
            return None
        purpose, purpose_layer = self._notary_purpose_with_layer(claim)
        try:
            with self._managed_notary_client() as client:
                response = client.evaluate(
                    subject_id=subject_ref["id"],
                    subject_id_type=subject_ref.get("id_type"),
                    claim_refs=[self._notary_claim_ref(claim)],
                    purpose=purpose,
                    purpose_layer=purpose_layer,
                    disclosure=claim.default_disclosure,
                )
        except NotaryError as error:
            _logger.warning("Notary evaluation failed for provider %s: %s", self.code, error)
            fallback = self._values_for_notary_error(error, variable, [subject_id], period_key)
            return fallback.get(subject_id, {}).get("value")
        result = self._first_matching_result(response.results, claim.external_id)
        if result is None:
            return None
        value_data = self._value_data_from_result(result)
        self._write_notary_values(variable, {subject_id: value_data}, period_key)
        return value_data["value"]

    def _notary_subjects(self, subject_ids):
        result = []
        for subject_id in subject_ids:
            subject_ref = self._notary_subject_ref(subject_id)
            result.append((subject_id, subject_ref))
        return result

    def _chunk_notary_subjects(self, subject_records):
        batch_size = self.max_batch_size or 1000
        for index in range(0, len(subject_records), batch_size):
            yield subject_records[index : index + batch_size]

    def _notary_subject_ref(self, subject_id):
        self.ensure_one()
        if not self.notary_subject_id_type_id:
            raise NotarySubjectIdMissing("Notary subject ID type is not configured")
        partner = self.env["res.partner"].browse(subject_id).exists()
        if not partner:
            raise NotarySubjectIdMissing("Notary subject record was not found")
        reg_id = partner.reg_ids.filtered(lambda rec: rec.id_type_id == self.notary_subject_id_type_id)[:1]
        if not reg_id or not reg_id.value:
            raise NotarySubjectIdMissing("Notary subject ID value was not found")
        return {
            "id": reg_id.value,
            "id_type": self.notary_subject_id_type_id.code or self.notary_subject_id_type_id.uri,
        }

    def _notary_purpose(self, claim):
        return self._notary_purpose_with_layer(claim)[0]

    def _notary_purpose_with_layer(self, claim):
        cfg = self.env.context.get("cel_cfg") or {}
        if cfg.get("notary_purpose"):
            return cfg["notary_purpose"], "evaluation_context"
        if self.env.context.get("notary_purpose"):
            return self.env.context["notary_purpose"], "evaluation_context"
        if claim.default_purpose_url:
            return claim.default_purpose_url, "claim_default"
        if self.notary_default_purpose_url:
            return self.notary_default_purpose_url, "provider_default"
        raise UserError(_("Notary data-purpose is required before evaluating claim '%s'.") % claim.external_id)

    def _notary_claim_ref(self, claim):
        if claim.pinned_version:
            return {"id": claim.external_id, "version": claim.pinned_version}
        return claim.external_id

    def _values_from_batch_response(self, response, subject_records, claim):
        values = {}
        by_input_index = {index: subject_id for index, (subject_id, _subject_ref) in enumerate(subject_records)}
        for index, item in enumerate(response.items):
            if item.status != "succeeded":
                continue
            subject_id = by_input_index.get(item.input_index if item.input_index is not None else index)
            results = getattr(item, "claim_results", None) or getattr(item, "results", [])
            result = self._first_matching_result(results, claim.external_id)
            if subject_id is not None and result is not None:
                values[subject_id] = self._value_data_from_result(result)
        return values

    def _first_matching_result(self, results, claim_id):
        for result in results or []:
            if result.claim_id == claim_id:
                return result
        return None

    def _value_data_from_result(self, result):
        value = result.value
        if getattr(result, "satisfied", None) is not None and value is None:
            value = result.satisfied
        return {
            "value": value,
            "expires_at": self._parse_notary_datetime(getattr(result, "expires_at", None)),
        }

    def _write_notary_values(self, variable, values_by_subject, period_key):
        values_list = []
        ttl = max(
            self.notary_min_cache_ttl_seconds or 0,
            self.notary_default_ttl_seconds or self.default_ttl_seconds or 0,
        )
        for subject_id, value_data in values_by_subject.items():
            if value_data.get("stale"):
                continue
            values_list.append(
                {
                    "variable_name": variable.name,
                    "subject_model": "res.partner",
                    "subject_id": subject_id,
                    "period_key": period_key or "current",
                    "value_json": {"value": value_data["value"]},
                    "value_type": data_value_type_for_cel(variable.value_type),
                    "source_type": "external",
                    "provider": self.code,
                    "params": self._notary_cache_params(variable),
                    "expires_at": self._effective_notary_expires_at(value_data.get("expires_at")),
                    "ttl_seconds": ttl,
                }
            )
        if not values_list:
            return
        self.env["spp.data.value"].upsert_values(values_list)

    def _read_stale_notary_values(self, variable, subject_ids, period_key):
        if not subject_ids:
            return {}
        records = self.env["spp.data.value"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("variable_name", "=", variable.name),
                ("subject_id", "in", subject_ids),
                ("period_key", "=", period_key or "current"),
                ("provider", "=", self.code),
                ("params_hash", "=", self.env["spp.data.value"]._hash_params(self._notary_cache_params(variable))),
                ("expires_at", "!=", False),
                ("expires_at", "<=", fields.Datetime.now()),
            ],
            order="expires_at desc",
        )
        values = {}
        for record in records:
            if record.subject_id in values:
                continue
            if isinstance(record.value_json, dict) and "value" in record.value_json:
                values[record.subject_id] = {
                    "value": record.value_json["value"],
                    "expires_at": record.expires_at,
                    "stale": True,
                }
            else:
                values[record.subject_id] = {
                    "value": record.value_json,
                    "expires_at": record.expires_at,
                    "stale": True,
                }
        return values

    def _values_for_notary_error(self, error, variable, subject_ids, period_key):
        if self.notary_unavailable_policy == "raise":
            raise UserError(_("Notary evaluation failed: %(error)s") % {"error": error}) from error
        if self.notary_unavailable_policy == "null":
            return {}
        if self.notary_unavailable_policy != "stale_cache_with_audit":
            return {}

        stale_values = self._read_stale_notary_values(variable, subject_ids, period_key)
        if stale_values:
            if not self.notary_subject_log_secret:
                raise UserError(_("Notary subject log secret is required before logging stale cache reads.")) from error
            self._log_stale_cache_read(variable, stale_values, period_key, error)
        else:
            raise error
        return stale_values

    def _log_stale_cache_read(self, variable, stale_values, period_key, error):
        if "spp.api.outgoing.log" not in self.env:
            return

        from odoo.addons.spp_api_v2.services.outgoing_api_log_service import OutgoingApiLogService

        claim = variable.notary_claim_id
        stale_rows = self._stale_cache_audit_rows(stale_values)
        request_summary = {
            "purpose": "stale_cache_read",
            "purpose_layer": "cache_policy",
            "claim_ids": [claim.external_id] if claim else [],
            "claim_id": claim.external_id if claim else None,
            "subject_count": len(stale_values),
            "cache_policy": "stale_cache_with_audit",
            "period_key": period_key or "current",
            "evaluation_id": (getattr(error, "details", None) or {}).get("evaluation_id"),
            "stale_values": stale_rows,
        }
        service = OutgoingApiLogService(
            self.env,
            service_name="Notary Client",
            service_code=self.code,
        )
        service.log_call(
            url=self.base_url or "notary://stale-cache",
            endpoint="/claims/stale-cache-read",
            http_method="GET",
            request_summary=request_summary,
            response_status_code=getattr(error, "status_code", None),
            origin_model=self._name,
            origin_record_id=self.id,
            status="error",
            error_detail=str(getattr(error, "code", None) or error.__class__.__name__),
        )

    def _stale_cache_audit_rows(self, stale_values):
        rows = []
        now = fields.Datetime.now()
        for subject_id, value_data in stale_values.items():
            expires_at = value_data.get("expires_at")
            try:
                subject_hash_source = self._notary_subject_ref(subject_id)["id"]
            except NotarySubjectIdMissing:
                subject_hash_source = subject_id
            rows.append(
                {
                    "subject_hash": hmac_subject_hash(subject_hash_source, self.notary_subject_log_secret),
                    "stale_age_seconds": int((now - expires_at).total_seconds()) if expires_at else None,
                    "expires_at": fields.Datetime.to_string(expires_at) if expires_at else None,
                }
            )
        return rows

    def _notary_cache_params(self, variable):
        claim = variable.notary_claim_id
        return {"version": claim.pinned_version or ""} if claim else {}

    def _external_value_cache_params(self, variable):
        if self.provider_kind == "notary":
            return self._notary_cache_params(variable)
        return super()._external_value_cache_params(variable)

    def _effective_notary_expires_at(self, expires_at):
        if not expires_at:
            return None
        minimum_ttl = self.notary_min_cache_ttl_seconds or 0
        if minimum_ttl <= 0:
            return expires_at
        minimum_expires_at = fields.Datetime.now() + timedelta(seconds=minimum_ttl)
        return max(expires_at, minimum_expires_at)

    def _parse_notary_datetime(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return fields.Datetime.to_datetime(value)
            except ValueError:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    _logger.warning("Notary returned an unparseable expiration datetime")
                    return None
                if parsed.tzinfo:
                    parsed = parsed.astimezone(UTC).replace(tzinfo=None)
                return parsed
        return None
