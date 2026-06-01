# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pure Python client for Registry Notary evidence services."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from .audit_log import NotaryOutgoingLogWrapper, build_request_summary, claim_ids_from_refs
from .exceptions import (
    NotaryConfigurationError,
    NotaryError,
    NotaryPurposeMissing,
    NotarySubjectIdMissing,
    NotaryTransportError,
    exception_from_error_payload,
)
from .schemas import (
    BatchEvaluateItemRequest,
    BatchEvaluateRequest,
    BatchEvaluateResponse,
    CatalogResponse,
    ClaimRef,
    EvaluateRequest,
    EvaluateResponse,
    EvidenceEntity,
    EvidenceIdentifier,
    EvidenceServiceMetadata,
    Subject,
)

CLAIM_RESULT_JSON = "application/vnd.registry-notary.claim-result+json"
APPLICATION_JSON = "application/json"

ENDPOINT_CLAIMS = "/v1/claims"
ENDPOINT_EVALUATE = "/v1/evaluations"
ENDPOINT_BATCH_EVALUATE = "/v1/batch-evaluations"
ENDPOINT_METADATA = "/.well-known/evidence-service"
ENDPOINT_JWKS = "/.well-known/evidence/jwks.json"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class NotaryClientConfig:
    """Normalized Notary provider/client configuration."""

    base_url: str
    auth_type: str = "none"
    bearer_token: str | None = None
    api_key: str | None = None
    api_key_header: str = "x-api-key"
    default_purpose_url: str | None = None
    timeout_seconds: float = 30.0
    subject_log_secret: str | None = None
    service_code: str = "notary"
    origin_model: str | None = None
    origin_record_id: int | None = None


def _read_config_value(source: Any, *names: str) -> Any:
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if not isinstance(source, dict) and hasattr(source, name):
            value = getattr(source, name)
            if value not in (False, None):
                return value
    return None


def normalize_config(config: NotaryClientConfig | dict[str, Any] | Any) -> NotaryClientConfig:
    """Normalize a provider-like record or plain dict into NotaryClientConfig."""
    if isinstance(config, NotaryClientConfig):
        return config
    if not config:
        raise NotaryConfigurationError("Notary configuration is required")

    base_url = _read_config_value(config, "base_url", "notary_base_url")
    if not base_url:
        raise NotaryConfigurationError("Notary base_url is required")

    auth_type = (_read_config_value(config, "auth_type", "notary_auth_type") or "none").lower()
    timeout_seconds = _read_config_value(config, "timeout_seconds", "notary_timeout_seconds") or 30.0
    service_code = _read_config_value(config, "code", "service_code", "name") or "notary"

    try:
        origin_record_id = _read_config_value(config, "id")
        origin_record_id = int(origin_record_id) if origin_record_id else None
    except (TypeError, ValueError):
        origin_record_id = None

    normalized = NotaryClientConfig(
        base_url=str(base_url).rstrip("/"),
        auth_type=auth_type,
        bearer_token=_read_config_value(config, "bearer_token", "token", "notary_bearer_token"),
        api_key=_read_config_value(config, "api_key", "notary_api_key"),
        api_key_header=str(_read_config_value(config, "api_key_header", "notary_api_key_header") or "x-api-key"),
        default_purpose_url=_read_config_value(config, "default_purpose_url", "notary_default_purpose_url"),
        timeout_seconds=float(timeout_seconds),
        subject_log_secret=_read_config_value(config, "subject_log_secret", "notary_subject_log_secret"),
        service_code=str(service_code),
        origin_model=_read_config_value(config, "_name", "origin_model"),
        origin_record_id=origin_record_id,
    )
    _validate_config(normalized)
    return normalized


def _validate_config(config: NotaryClientConfig) -> None:
    if config.auth_type not in {"none", "bearer", "api_key"}:
        raise NotaryConfigurationError("Notary auth_type must be one of: none, bearer, api_key")
    if config.auth_type == "bearer" and not config.bearer_token:
        raise NotaryConfigurationError("Notary bearer_token is required for bearer auth")
    if config.auth_type == "api_key" and not config.api_key:
        raise NotaryConfigurationError("Notary api_key is required for api_key auth")


class NotaryClient:
    """Client for Registry Notary discovery and claim evaluation endpoints."""

    def __init__(
        self,
        config: NotaryClientConfig | dict[str, Any] | Any | None = None,
        *,
        http_client: httpx.Client | None = None,
        env=None,
        log_wrapper: Any | None = None,
        sleep=time.sleep,
    ):
        self.config = normalize_config(config) if config else None
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self.sleep = sleep
        self.log_wrapper = log_wrapper
        if not self.log_wrapper and env and self.config:
            self.log_wrapper = NotaryOutgoingLogWrapper(env, service_code=self.config.service_code)

    def close(self) -> None:
        """Close an internally-owned HTTPX client."""
        if self._http_client and self._owns_http_client:
            self._http_client.close()

    def __enter__(self):
        """Return this client for use in a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close owned HTTP resources when leaving a context manager."""
        self.close()

    def discover_claims(
        self,
        config: NotaryClientConfig | dict[str, Any] | Any | None = None,
        *,
        purpose: str | None = None,
    ) -> CatalogResponse:
        """Fetch the Notary claim catalog."""
        active_config = self._resolve_config(config)
        resolved_purpose, purpose_layer = self._resolve_purpose(active_config, purpose)
        response = self._request(
            active_config,
            "GET",
            ENDPOINT_CLAIMS,
            purpose=resolved_purpose,
            purpose_layer=purpose_layer,
        )
        return CatalogResponse.model_validate(response)

    def evaluate(
        self,
        config: NotaryClientConfig | dict[str, Any] | Any | None = None,
        subject_id: str | None = None,
        claim_refs: Iterable[str | ClaimRef | dict[str, Any]] | None = None,
        *,
        subject_id_type: str | None = None,
        disclosure: str | None = None,
        purpose: str | None = None,
        purpose_layer: str | None = None,
        response_format: str | None = None,
        idempotency_key: str | None = None,
    ) -> EvaluateResponse:
        """Evaluate one subject against one or more claims."""
        active_config = self._resolve_config(config)
        if not subject_id:
            raise NotarySubjectIdMissing("Notary subject_id is required")
        if not claim_refs:
            raise NotaryConfigurationError("At least one Notary claim is required")
        if idempotency_key:
            raise NotaryConfigurationError("Notary evaluate does not support idempotency_key")

        normalized_claims = self._normalize_claim_refs(claim_refs)
        resolved_purpose, resolved_purpose_layer = self._resolve_purpose(active_config, purpose, purpose_layer)
        self._validate_audit_subject_hash(active_config, subject_id)
        request_model = EvaluateRequest(
            target=self._target_from_subject(Subject(id=subject_id, id_type=subject_id_type)),
            claims=normalized_claims,
            disclosure=disclosure,
            format=response_format,
            purpose=resolved_purpose,
        )
        request_payload = request_model.model_dump(mode="json", exclude_none=True)
        idempotency_key = idempotency_key or self._build_idempotency_key(
            subject_id,
            normalized_claims,
            resolved_purpose,
        )
        response = self._request(
            active_config,
            "POST",
            ENDPOINT_EVALUATE,
            json_body=request_payload,
            purpose=resolved_purpose,
            purpose_layer=resolved_purpose_layer,
            accept=CLAIM_RESULT_JSON,
            audit_subject_id=subject_id,
            audit_claim_refs=normalized_claims,
        )
        return EvaluateResponse.model_validate(response)

    def batch_evaluate(
        self,
        config: NotaryClientConfig | dict[str, Any] | Any | None = None,
        subjects: Iterable[str | Subject | dict[str, Any]] | None = None,
        claim_refs: Iterable[str | ClaimRef | dict[str, Any]] | None = None,
        *,
        disclosure: str | None = None,
        purpose: str | None = None,
        purpose_layer: str | None = None,
        response_format: str | None = None,
        idempotency_key: str | None = None,
    ) -> BatchEvaluateResponse:
        """Evaluate multiple subjects against one or more claims."""
        active_config = self._resolve_config(config)
        normalized_subjects = self._normalize_subjects(subjects)
        normalized_claims = self._normalize_claim_refs(claim_refs or [])
        if not normalized_subjects:
            raise NotaryConfigurationError("At least one Notary subject is required")
        if not normalized_claims:
            raise NotaryConfigurationError("At least one Notary claim is required")

        resolved_purpose, resolved_purpose_layer = self._resolve_purpose(active_config, purpose, purpose_layer)
        request_model = BatchEvaluateRequest(
            items=[
                BatchEvaluateItemRequest(target=self._target_from_subject(subject)) for subject in normalized_subjects
            ],
            claims=normalized_claims,
            disclosure=disclosure,
            format=response_format,
            purpose=resolved_purpose,
        )
        idempotency_key = idempotency_key or self._build_batch_idempotency_key(
            normalized_subjects,
            normalized_claims,
            resolved_purpose,
        )
        response = self._request(
            active_config,
            "POST",
            ENDPOINT_BATCH_EVALUATE,
            json_body=request_model.model_dump(mode="json", exclude_none=True),
            purpose=resolved_purpose,
            purpose_layer=resolved_purpose_layer,
            accept=CLAIM_RESULT_JSON,
            idempotency_key=idempotency_key,
            audit_claim_refs=normalized_claims,
            audit_subject_count=len(normalized_subjects),
            retry_once=True,
        )
        return BatchEvaluateResponse.model_validate(response)

    def get_metadata(
        self,
        config: NotaryClientConfig | dict[str, Any] | Any | None = None,
        *,
        purpose: str | None = None,
    ) -> EvidenceServiceMetadata:
        """Fetch Notary service metadata."""
        active_config = self._resolve_config(config)
        resolved_purpose, purpose_layer = self._resolve_purpose(active_config, purpose)
        response = self._request(
            active_config,
            "GET",
            ENDPOINT_METADATA,
            purpose=resolved_purpose,
            purpose_layer=purpose_layer,
        )
        return EvidenceServiceMetadata.model_validate(response)

    def get_jwks(
        self,
        config: NotaryClientConfig | dict[str, Any] | Any | None = None,
        *,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Fetch Notary JWKS for downstream signature verification."""
        active_config = self._resolve_config(config)
        resolved_purpose, purpose_layer = self._resolve_purpose(active_config, purpose)
        return self._request(
            active_config,
            "GET",
            ENDPOINT_JWKS,
            purpose=resolved_purpose,
            purpose_layer=purpose_layer,
        )

    def _resolve_config(self, config: NotaryClientConfig | dict[str, Any] | Any | None) -> NotaryClientConfig:
        active_config = normalize_config(config) if config else self.config
        if not active_config:
            raise NotaryConfigurationError("Notary configuration is required")
        return active_config

    def _resolve_purpose(
        self,
        config: NotaryClientConfig,
        purpose: str | None,
        purpose_layer: str | None = None,
    ) -> tuple[str, str]:
        if purpose:
            return purpose, purpose_layer or "evaluation_context"
        if config.default_purpose_url:
            return config.default_purpose_url, "provider_default"
        raise NotaryPurposeMissing("Notary data-purpose is required")

    def _validate_audit_subject_hash(self, config: NotaryClientConfig, subject_id: str | None) -> None:
        if self.log_wrapper and subject_id and not config.subject_log_secret:
            raise NotaryConfigurationError("Notary subject_log_secret is required before logging subject-scoped calls")

    def _request(
        self,
        config: NotaryClientConfig,
        method: str,
        endpoint: str,
        *,
        purpose: str,
        purpose_layer: str,
        json_body: dict[str, Any] | None = None,
        accept: str = APPLICATION_JSON,
        idempotency_key: str | None = None,
        audit_subject_id: str | None = None,
        audit_claim_refs: Iterable[Any] | None = None,
        audit_subject_count: int = 1,
        retry_once: bool = False,
    ) -> dict[str, Any]:
        url = self._build_url(config, endpoint)
        headers = self._headers(config, purpose, accept=accept, idempotency_key=idempotency_key)
        started_at = time.monotonic()
        attempts = 2 if retry_once else 1
        last_response = None
        response_payload = None

        for attempt in range(attempts):
            try:
                response = self._client(config).request(method, url, headers=headers, json=json_body)
                last_response = response
                response_payload = self._response_payload(response)
                if response.status_code < 400:
                    self._log_call(
                        config,
                        url=url,
                        endpoint=endpoint,
                        method=method,
                        purpose=purpose,
                        purpose_layer=purpose_layer,
                        claim_refs=audit_claim_refs,
                        subject_id=audit_subject_id,
                        subject_count=audit_subject_count,
                        response=response_payload,
                        status="success",
                        status_code=response.status_code,
                        started_at=started_at,
                    )
                    return response_payload
                if response.status_code in RETRYABLE_STATUS_CODES and attempt == 0 and retry_once:
                    self.sleep(0.2)
                    continue
                self._log_call(
                    config,
                    url=url,
                    endpoint=endpoint,
                    method=method,
                    purpose=purpose,
                    purpose_layer=purpose_layer,
                    claim_refs=audit_claim_refs,
                    subject_id=audit_subject_id,
                    subject_count=audit_subject_count,
                    response=response_payload,
                    status="http_error",
                    status_code=response.status_code,
                    started_at=started_at,
                    error_detail="Notary HTTP error",
                )
                self._raise_for_response(response.status_code, response_payload)
            except httpx.TimeoutException as error:
                self._log_call(
                    config,
                    url=url,
                    endpoint=endpoint,
                    method=method,
                    purpose=purpose,
                    purpose_layer=purpose_layer,
                    claim_refs=audit_claim_refs,
                    subject_id=audit_subject_id,
                    subject_count=audit_subject_count,
                    response=response_payload,
                    status="timeout",
                    status_code=getattr(last_response, "status_code", None),
                    started_at=started_at,
                    error_detail="Notary request timed out",
                )
                raise NotaryTransportError("Notary request timed out", code="transport.timeout") from error
            except httpx.TransportError as error:
                self._log_call(
                    config,
                    url=url,
                    endpoint=endpoint,
                    method=method,
                    purpose=purpose,
                    purpose_layer=purpose_layer,
                    claim_refs=audit_claim_refs,
                    subject_id=audit_subject_id,
                    subject_count=audit_subject_count,
                    response=response_payload,
                    status="connection_error",
                    status_code=getattr(last_response, "status_code", None),
                    started_at=started_at,
                    error_detail="Notary transport error",
                )
                raise NotaryTransportError("Notary transport error", code="transport.error") from error

        raise NotaryError("Notary request failed")

    def _raise_for_response(self, status_code: int, payload: dict[str, Any] | None) -> None:
        exception_type, code = exception_from_error_payload(status_code, payload)
        raise exception_type(code=code, status_code=status_code, details={"response": payload or {}})

    def _log_call(
        self,
        config: NotaryClientConfig,
        *,
        url: str,
        endpoint: str,
        method: str,
        purpose: str,
        purpose_layer: str,
        claim_refs: Iterable[Any] | None,
        subject_id: str | None,
        subject_count: int,
        response: dict[str, Any] | None,
        status: str,
        status_code: int | None,
        started_at: float,
        error_detail: str | None = None,
    ) -> None:
        if not self.log_wrapper:
            return
        request_summary = build_request_summary(
            purpose=purpose,
            purpose_layer=purpose_layer,
            claim_refs=claim_refs or [],
            subject_id=subject_id,
            subject_count=subject_count,
            subject_hash_secret=config.subject_log_secret,
            response=response,
        )
        self.log_wrapper.log_call(
            url=url,
            endpoint=endpoint,
            http_method=method,
            request_summary=request_summary,
            response_summary=None,
            response_status_code=status_code,
            duration_ms=max(0, int((time.monotonic() - started_at) * 1000)),
            origin_model=config.origin_model,
            origin_record_id=config.origin_record_id,
            status=status,
            error_detail=error_detail,
        )

    def _client(self, config: NotaryClientConfig) -> httpx.Client:
        if not self._http_client:
            self._http_client = httpx.Client(timeout=config.timeout_seconds)
        return self._http_client

    def _headers(
        self,
        config: NotaryClientConfig,
        purpose: str,
        *,
        accept: str = APPLICATION_JSON,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "data-purpose": purpose,
        }
        if config.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {config.bearer_token}"
        elif config.auth_type == "api_key":
            headers[config.api_key_header] = config.api_key or ""
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _build_url(self, config: NotaryClientConfig, endpoint: str) -> str:
        return urljoin(f"{config.base_url}/", endpoint.lstrip("/"))

    def _response_payload(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return payload if isinstance(payload, dict) else {"data": payload}

    def _build_idempotency_key(self, subject_id: str, claim_refs: Iterable[Any], purpose: str) -> str:
        seed = json.dumps(
            {
                "subject_id": subject_id,
                "claim_ids": claim_ids_from_refs(claim_refs),
                "purpose": purpose,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

    def _build_batch_idempotency_key(self, subjects: Iterable[Subject], claim_refs: Iterable[Any], purpose: str) -> str:
        seed = json.dumps(
            {
                "subject_ids": [subject.id for subject in subjects],
                "claim_ids": claim_ids_from_refs(claim_refs),
                "purpose": purpose,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

    def _target_from_subject(self, subject: Subject) -> EvidenceEntity:
        if subject.id_type:
            return EvidenceEntity(
                type="Person",
                identifiers=[EvidenceIdentifier(scheme=subject.id_type, value=subject.id)],
            )
        return EvidenceEntity(type="Person", id=subject.id)

    def _normalize_claim_refs(self, claim_refs: Iterable[str | ClaimRef | dict[str, Any]]) -> list[str | ClaimRef]:
        if isinstance(claim_refs, str | dict | ClaimRef):
            raise NotaryConfigurationError("Notary claim_refs must be a list or iterable of claim references")
        normalized = []
        for claim_ref in claim_refs:
            if isinstance(claim_ref, str):
                normalized.append(claim_ref)
            elif isinstance(claim_ref, ClaimRef):
                normalized.append(claim_ref)
            elif isinstance(claim_ref, dict):
                normalized.append(ClaimRef.model_validate(claim_ref))
            else:
                normalized.append(ClaimRef(id=str(claim_ref.id), version=getattr(claim_ref, "version", None)))
        return normalized

    def _normalize_subjects(self, subjects: Iterable[str | Subject | dict[str, Any]] | None) -> list[Subject]:
        if isinstance(subjects, str | dict | Subject):
            raise NotaryConfigurationError("Notary subjects must be a list or iterable of subject references")
        normalized = []
        for subject in subjects or []:
            if isinstance(subject, str):
                normalized.append(Subject(id=subject))
            elif isinstance(subject, Subject):
                normalized.append(subject)
            elif isinstance(subject, dict):
                normalized.append(Subject.model_validate(subject))
            else:
                normalized.append(Subject(id=str(subject.id), id_type=getattr(subject, "id_type", None)))
        return normalized
