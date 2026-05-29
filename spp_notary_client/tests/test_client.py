# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the pure Python Notary client."""

from dataclasses import dataclass
from unittest.mock import Mock

import httpx
import pytest

from spp_notary_client.services.client import NotaryClient, normalize_config
from spp_notary_client.services.exceptions import (
    NotaryAuthError,
    NotaryClaimNotFound,
    NotaryConfigurationError,
    NotaryPurposeMissing,
    NotaryRateLimited,
    NotarySubjectIdMissing,
    NotarySubjectNotFound,
    NotaryTransportError,
)


class SequenceTransport(httpx.BaseTransport):
    """HTTPX transport returning queued responses and capturing requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def handle_request(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@dataclass
class ProviderLike:
    """Small provider-like object for config normalization tests."""

    base_url: str = "https://notary.example/api"
    auth_type: str = "api_key"
    api_key: str = "provider-key"
    default_purpose_url: str = "https://openspp.example/default-purpose"
    timeout_seconds: float = 7.5
    code: str = "notary_main"
    id: int = 42


def _json_response(status_code=200, payload=None):
    return httpx.Response(status_code, json=payload or {})


def _client(config, responses):
    transport = SequenceTransport(responses)
    http_client = httpx.Client(transport=transport)
    return NotaryClient(config, http_client=http_client, sleep=lambda _: None), transport


def test_normalize_config_accepts_provider_record_and_plain_dict():
    """Client config can come from provider-like records or standalone dicts."""
    record_config = normalize_config(ProviderLike())
    dict_config = normalize_config(
        {
            "base_url": "https://notary.example/api/",
            "auth_type": "bearer",
            "bearer_token": "bearer-token",
            "default_purpose_url": "https://openspp.example/default-purpose",
        }
    )

    assert record_config.base_url == "https://notary.example/api"
    assert record_config.auth_type == "api_key"
    assert record_config.api_key == "provider-key"
    assert record_config.service_code == "notary_main"
    assert record_config.origin_record_id == 42
    assert dict_config.base_url == "https://notary.example/api"
    assert dict_config.auth_type == "bearer"


def test_discover_claims_sends_purpose_and_api_key_headers():
    """Discovery calls still carry the mandatory purpose and auth headers."""
    client, transport = _client(
        {
            "base_url": "https://notary.example/api",
            "auth_type": "api_key",
            "api_key": "secret-key",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [
            _json_response(
                payload={
                    "claims": [
                        {
                            "id": "disability-severity-code",
                            "title": "Disability severity",
                            "unexpected": "accepted",
                        }
                    ],
                    "server_field": "accepted",
                }
            )
        ],
    )

    response = client.discover_claims()

    assert response.claims[0].id == "disability-severity-code"
    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url.path == "/api/claims"
    assert transport.requests[0].headers["data-purpose"] == "https://openspp.example/default-purpose"
    assert transport.requests[0].headers["x-api-key"] == "secret-key"


def test_evaluate_sends_bearer_auth_payload_and_stable_idempotency_key_on_retry():
    """Retryable responses reuse one idempotency key across attempts."""
    client, transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "bearer",
            "bearer_token": "bearer-token",
            "subject_log_secret": "audit-secret",
        },
        [
            _json_response(500, {"error": {"code": "source.unavailable"}}),
            _json_response(
                200,
                {
                    "evaluation_id": "eval-123",
                    "results": [
                        {
                            "claim_id": "disability-severity-code",
                            "value": "severe",
                            "satisfied": True,
                        }
                    ],
                },
            ),
        ],
    )

    response = client.evaluate(
        subject_id="NATIONAL-ID-123",
        claim_refs=["disability-severity-code"],
        purpose="https://openspp.example/purpose",
    )

    assert response.evaluation_id == "eval-123"
    assert len(transport.requests) == 2
    assert transport.requests[0].headers["authorization"] == "Bearer bearer-token"
    assert transport.requests[0].headers["idempotency-key"] == transport.requests[1].headers["idempotency-key"]
    payload = dict(httpx.QueryParams(transport.requests[1].url.query))
    assert payload == {}
    request_json = transport.requests[1].read().decode()
    assert "NATIONAL-ID-123" in request_json
    assert "disability-severity-code" in request_json


def test_evaluate_serializes_versioned_claim_ref_objects():
    """Version-pinned claims are sent as ClaimRef objects after Notary #44."""
    client, transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [
            _json_response(
                200,
                {
                    "evaluation_id": "eval-versioned",
                    "results": [
                        {
                            "claim_id": "disability-severity-code",
                            "claim_version": "2026-01",
                            "value": "severe",
                            "satisfied": True,
                        }
                    ],
                },
            ),
        ],
    )

    client.evaluate(
        subject_id="NATIONAL-ID-123",
        claim_refs=[{"id": "disability-severity-code", "version": "2026-01"}],
    )

    request_json = transport.requests[0].read().decode()
    assert '"claims":[{"id":"disability-severity-code","version":"2026-01"}]' in request_json


def test_evaluate_requires_purpose():
    """Calls fail before network IO when data-purpose cannot be resolved."""
    client, transport = _client(
        {"base_url": "https://notary.example", "auth_type": "none"},
        [_json_response()],
    )

    with pytest.raises(NotaryPurposeMissing):
        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

    assert transport.requests == []


def test_evaluate_requires_subject_id():
    """Subject-scoped calls fail before network IO without a subject ID."""
    client, transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [_json_response()],
    )

    with pytest.raises(NotarySubjectIdMissing):
        client.evaluate(subject_id="", claim_refs=["claim-a"])

    assert transport.requests == []


def test_evaluate_refuses_logged_subject_call_without_hash_secret():
    """Odoo audit logging never falls back to an unkeyed subject hash."""
    client, transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [_json_response()],
    )
    client.log_wrapper = Mock()

    with pytest.raises(NotaryConfigurationError):
        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

    assert transport.requests == []
    client.log_wrapper.log_call.assert_not_called()


def test_context_manager_closes_owned_http_client():
    """Internally-created HTTP clients are closed when used as a context manager."""
    client = NotaryClient(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        }
    )

    with client as managed:
        assert managed is client
        managed._client(managed.config)
        assert not managed._http_client.is_closed

    assert client._http_client.is_closed


def test_context_manager_does_not_close_external_http_client():
    """Callers keep ownership of externally-supplied HTTP clients."""
    http_client = httpx.Client(transport=SequenceTransport([_json_response()]))
    client = NotaryClient(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        http_client=http_client,
    )

    with client:
        pass

    assert not http_client.is_closed
    http_client.close()


def test_batch_evaluate_posts_subjects_and_claims():
    """Batch evaluation uses the batch endpoint and tolerant response model."""
    client, transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [
            _json_response(
                payload={
                    "batch_id": "batch-123",
                    "status": "completed",
                    "items": [
                        {
                            "subject": {"id": "NATIONAL-ID-123"},
                            "status": "succeeded",
                            "results": [{"claim_id": "claim-a", "value": True}],
                        }
                    ],
                }
            )
        ],
    )

    response = client.batch_evaluate(subjects=["NATIONAL-ID-123"], claim_refs=["claim-a"])

    assert response.batch_id == "batch-123"
    assert response.items[0].status == "succeeded"
    assert transport.requests[0].method == "POST"
    assert transport.requests[0].url.path == "/claims/batch-evaluate"
    assert '"subjects":[{"id":"NATIONAL-ID-123"}]' in transport.requests[0].read().decode()


@pytest.mark.parametrize(
    ("status_code", "payload", "exception_type"),
    [
        (404, {"error": {"code": "source.not_found", "message": "missing subject"}}, NotarySubjectNotFound),
        (404, {"error": {"code": "claim.not_found", "message": "missing claim"}}, NotaryClaimNotFound),
        (401, {"error": {"code": "auth.invalid", "message": "bad token"}}, NotaryAuthError),
    ],
)
def test_error_payloads_map_to_typed_exceptions_without_leaking_request_values(status_code, payload, exception_type):
    """Error messages avoid subject IDs and requested claim IDs."""
    client, _transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [_json_response(status_code, payload)],
    )

    with pytest.raises(exception_type) as error:
        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["secret-claim"])

    assert error.value.code == payload["error"]["code"]
    assert "NATIONAL-ID-123" not in str(error.value)
    assert "secret-claim" not in str(error.value)


def test_rate_limit_retries_once_then_raises_with_same_idempotency_key():
    """HTTP 429 retries once and raises NotaryRateLimited if still limited."""
    client, transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [
            _json_response(429, {"error": {"code": "rate_limited"}}),
            _json_response(429, {"error": {"code": "rate_limited"}}),
        ],
    )

    with pytest.raises(NotaryRateLimited):
        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

    assert len(transport.requests) == 2
    assert transport.requests[0].headers["idempotency-key"] == transport.requests[1].headers["idempotency-key"]


def test_transport_errors_raise_typed_exception_without_request_values():
    """Connection failures map to NotaryTransportError and avoid PII in text."""
    request = httpx.Request("POST", "https://notary.example/claims/evaluate")
    client, _transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
        },
        [httpx.ConnectError("connect failed", request=request)],
    )

    with pytest.raises(NotaryTransportError) as error:
        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["secret-claim"])

    assert "NATIONAL-ID-123" not in str(error.value)
    assert "secret-claim" not in str(error.value)


def test_outgoing_log_wrapper_receives_sanitized_summaries():
    """Optional log wrappers get sanitized request context only."""
    log_wrapper = Mock()
    client, _transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
            "subject_log_secret": "audit-secret",
        },
        [
            _json_response(
                payload={
                    "evaluation_id": "eval-123",
                    "results": [{"claim_id": "claim-a", "value": "raw-value"}],
                }
            )
        ],
    )
    client.log_wrapper = log_wrapper

    client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

    request_summary = log_wrapper.log_call.call_args.kwargs["request_summary"]
    assert request_summary["claim_ids"] == ["claim-a"]
    assert request_summary["evaluation_id"] == "eval-123"
    assert "subject_hash" in request_summary
    assert "NATIONAL-ID-123" not in str(request_summary)
    assert "raw-value" not in str(request_summary)


def test_http_errors_are_logged_with_sanitized_request_summary():
    """HTTP error logs keep claim IDs and subject hash without leaking raw subject IDs."""
    log_wrapper = Mock()
    client, _transport = _client(
        {
            "base_url": "https://notary.example",
            "auth_type": "none",
            "default_purpose_url": "https://openspp.example/default-purpose",
            "subject_log_secret": "audit-secret",
        },
        [_json_response(404, {"error": {"code": "source.not_found", "message": "NATIONAL-ID-123 missing"}})],
    )
    client.log_wrapper = log_wrapper

    with pytest.raises(NotarySubjectNotFound):
        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

    request_summary = log_wrapper.log_call.call_args.kwargs["request_summary"]
    assert log_wrapper.log_call.call_args.kwargs["status"] == "http_error"
    assert request_summary["claim_ids"] == ["claim-a"]
    assert "subject_hash" in request_summary
    assert "NATIONAL-ID-123" not in str(request_summary)
