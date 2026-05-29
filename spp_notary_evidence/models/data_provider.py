# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Notary extensions for CEL data providers."""

import logging
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

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
    notary_min_cache_ttl_seconds = fields.Integer(default=300, tracking=True)
    notary_default_ttl_seconds = fields.Integer(default=86400, tracking=True)
    notary_subject_log_secret = fields.Char(groups="spp_notary_evidence.group_notary_evidence_manager")
    notary_catalog_path = fields.Char(
        string="Notary Catalog Path",
        default="/claims",
        help="Relative endpoint used by older mock clients. The real Notary client uses GET /claims.",
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
                "subject_type": summary.subject_type
                if summary.subject_type in ("individual", "group", "both")
                else "individual",
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

    def _compute_external_values(self, variable, subject_ids, period_key):
        self.ensure_one()
        if self.provider_kind != "notary":
            return super()._compute_external_values(variable, subject_ids, period_key)
        claim = variable.notary_claim_id
        if not claim:
            return {}
        subject_records = self._notary_subjects(subject_ids)
        if not subject_records:
            return {}
        purpose = self._notary_purpose(claim)
        values_by_subject = {}
        with self._managed_notary_client() as client:
            for chunk in self._chunk_notary_subjects(subject_records):
                try:
                    response = client.batch_evaluate(
                        subjects=[subject_ref for _subject_id, subject_ref in chunk],
                        claim_refs=[self._notary_claim_ref(claim)],
                        purpose=purpose,
                        disclosure=claim.default_disclosure,
                    )
                except NotaryError as error:
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
                values_by_subject.update(self._values_from_batch_response(response, chunk, claim))
        self._write_notary_values(variable, values_by_subject, period_key)
        return {subject_id: value_data["value"] for subject_id, value_data in values_by_subject.items()}

    def _refresh_external_value(self, variable, subject_id, period_key):
        self.ensure_one()
        if self.provider_kind != "notary":
            return super()._refresh_external_value(variable, subject_id, period_key)
        claim = variable.notary_claim_id
        subject_ref = self._notary_subject_ref(subject_id)
        if not claim or not subject_ref:
            return None
        purpose = self._notary_purpose(claim)
        try:
            with self._managed_notary_client() as client:
                response = client.evaluate(
                    subject_id=subject_ref["id"],
                    subject_id_type=subject_ref.get("id_type"),
                    claim_refs=[self._notary_claim_ref(claim)],
                    purpose=purpose,
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
        return {"id": reg_id.value, "id_type": self.notary_subject_id_type_id.uri}

    def _notary_purpose(self, claim):
        cfg = self.env.context.get("cel_cfg") or {}
        purpose = (
            cfg.get("notary_purpose")
            or self.env.context.get("notary_purpose")
            or claim.default_purpose_url
            or self.notary_default_purpose_url
        )
        if not purpose:
            raise UserError(_("Notary data-purpose is required before evaluating claim '%s'.") % claim.external_id)
        return purpose

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
            self._log_stale_cache_read(variable, stale_values, period_key, error)
        return stale_values

    def _log_stale_cache_read(self, variable, stale_values, period_key, error):
        if "spp.api.outgoing.log" not in self.env:
            return

        from odoo.addons.spp_api_v2.services.outgoing_api_log_service import OutgoingApiLogService

        claim = variable.notary_claim_id
        request_summary = {
            "purpose": "stale_cache_read",
            "purpose_layer": "cache_policy",
            "claim_ids": [claim.external_id] if claim else [],
            "subject_count": len(stale_values),
            "cache_policy": "stale_cache_with_audit",
            "period_key": period_key or "current",
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
