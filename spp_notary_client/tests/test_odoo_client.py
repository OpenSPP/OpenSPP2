# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Odoo-runner coverage for the pure Python Notary client."""

import json
from dataclasses import dataclass
from unittest.mock import Mock

import httpx

try:
    from odoo.tests import TransactionCase, tagged
except ImportError:
    import pytest

    pytest.skip("Odoo test runner is not available", allow_module_level=True)

from odoo.addons.spp_notary_client.services.audit_log import (
    NotaryOutgoingLogWrapper,
    build_request_summary,
    claim_ids_from_refs,
    hmac_subject_hash,
)
from odoo.addons.spp_notary_client.services.client import NotaryClient, normalize_config
from odoo.addons.spp_notary_client.services.exceptions import (
    NotaryAuthError,
    NotaryClaimNotFound,
    NotaryConfigurationError,
    NotaryPurposeMissing,
    NotaryRateLimited,
    NotaryRequestError,
    NotarySourceUnavailable,
    NotarySubjectIdMissing,
    NotarySubjectNotFound,
    NotaryTransportError,
)
from odoo.addons.spp_notary_client.services.schemas import (
    BatchEvaluateResponse,
    CatalogResponse,
    ClaimRef,
    EvaluateRequest,
    EvidenceEntity,
    EvidenceIdentifier,
    Subject,
)


class CaptureTransport(httpx.BaseTransport):
    """HTTPX transport that records requests for assertions."""

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
    transport = CaptureTransport(responses)
    http_client = httpx.Client(transport=transport)
    return NotaryClient(config, http_client=http_client, sleep=lambda _: None), transport


@tagged("post_install", "-at_install")
class TestNotaryClientOdooRunner(TransactionCase):
    def test_normalize_config_accepts_provider_record_and_plain_dict(self):
        record_config = normalize_config(ProviderLike())
        dict_config = normalize_config(
            {
                "base_url": "https://notary.example/api/",
                "auth_type": "bearer",
                "bearer_token": "bearer-token",
                "default_purpose_url": "https://openspp.example/default-purpose",
            }
        )

        self.assertEqual(record_config.base_url, "https://notary.example/api")
        self.assertEqual(record_config.auth_type, "api_key")
        self.assertEqual(record_config.api_key, "provider-key")
        self.assertEqual(record_config.service_code, "notary_main")
        self.assertEqual(record_config.origin_record_id, 42)
        self.assertEqual(dict_config.base_url, "https://notary.example/api")
        self.assertEqual(dict_config.auth_type, "bearer")

    def test_normalize_config_rejects_missing_and_invalid_auth_config(self):
        with self.assertRaises(NotaryConfigurationError):
            normalize_config({})
        with self.assertRaises(NotaryConfigurationError):
            normalize_config({"base_url": "https://notary.example", "auth_type": "oauth2"})
        with self.assertRaises(NotaryConfigurationError):
            normalize_config({"base_url": "https://notary.example", "auth_type": "bearer"})
        with self.assertRaises(NotaryConfigurationError):
            normalize_config({"base_url": "https://notary.example", "auth_type": "api_key"})

    def test_discover_claims_sends_purpose_and_api_key_headers(self):
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
                        "data": [
                            {
                                "id": "disability-severity-code",
                                "name": "Disability severity",
                                "type": "string",
                                "formats": ["json"],
                            }
                        ]
                    }
                )
            ],
        )

        response = client.discover_claims()

        self.assertEqual(response.claims[0].title, "Disability severity")
        self.assertEqual(response.claims[0].value_type, "string")
        self.assertEqual(response.claims[0].supported_formats, ["json"])
        self.assertEqual(transport.requests[0].method, "GET")
        self.assertEqual(transport.requests[0].url.path, "/api/v1/claims")
        self.assertEqual(transport.requests[0].headers["data-purpose"], "https://openspp.example/default-purpose")
        self.assertEqual(transport.requests[0].headers["x-api-key"], "secret-key")

    def test_evaluate_serializes_versioned_claim_ref(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [
                _json_response(
                    payload={
                        "evaluation_id": "eval-versioned",
                        "results": [
                            {
                                "claim_id": "disability-severity-code",
                                "claim_version": "2026-01",
                                "value": "severe",
                            }
                        ],
                    }
                )
            ],
        )

        response = client.evaluate(
            subject_id="NATIONAL-ID-123",
            claim_refs=[{"id": "disability-severity-code", "version": "2026-01"}],
        )

        self.assertEqual(response.evaluation_id, "eval-versioned")
        self.assertEqual(len(transport.requests), 1)
        self.assertIn(
            '"claims":[{"id":"disability-severity-code","version":"2026-01"}]',
            transport.requests[0].read().decode(),
        )

    def test_evaluate_accepts_explicit_purpose_layer_for_audit(self):
        log_wrapper = Mock()
        client, _transport = _client(
            {
                "base_url": "https://notary.example/api",
                "auth_type": "none",
                "subject_log_secret": "audit-secret",
            },
            [
                _json_response(
                    payload={
                        "evaluation_id": "eval-purpose-layer",
                        "results": [{"claim_id": "claim-a", "value": True}],
                    }
                )
            ],
        )
        client.log_wrapper = log_wrapper

        client.evaluate(
            subject_id="NATIONAL-ID-123",
            claim_refs=["claim-a"],
            purpose="https://openspp.example/purpose/claim",
            purpose_layer="claim_default",
        )

        self.assertEqual(log_wrapper.log_call.call_args.kwargs["request_summary"]["purpose_layer"], "claim_default")

    def test_evaluate_sends_bearer_auth_payload_and_does_not_retry(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "bearer",
                "bearer_token": "bearer-token",
                "subject_log_secret": "audit-secret",
            },
            [
                _json_response(500, {"error": {"code": "source.unavailable"}}),
            ],
        )

        with self.assertRaises(NotarySourceUnavailable):
            client.evaluate(
                subject_id="NATIONAL-ID-123",
                claim_refs=["disability-severity-code"],
                purpose="https://openspp.example/purpose",
            )

        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(transport.requests[0].url.path, "/v1/evaluations")
        self.assertEqual(transport.requests[0].headers["authorization"], "Bearer bearer-token")
        self.assertEqual(transport.requests[0].headers["accept"], "application/vnd.registry-notary.claim-result+json")
        self.assertNotIn("idempotency-key", transport.requests[0].headers)
        request_payload = json.loads(transport.requests[0].read().decode())
        self.assertEqual(
            request_payload["target"],
            {
                "type": "Person",
                "id": "NATIONAL-ID-123",
                "identifiers": [],
                "attributes": {},
            },
        )

    def test_batch_evaluate_posts_subjects_and_claims(self):
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
                                "target_ref": {"type": "Person", "handle": "hashed-target"},
                                "status": "succeeded",
                                "claim_results": [{"claim_id": "claim-a", "value": True}],
                            }
                        ],
                    }
                )
            ],
        )

        response = client.batch_evaluate(subjects=["NATIONAL-ID-123"], claim_refs=["claim-a"])

        self.assertEqual(response.batch_id, "batch-123")
        self.assertEqual(response.items[0].results[0].claim_id, "claim-a")
        self.assertEqual(response.items[0].claim_results[0].claim_id, "claim-a")
        self.assertEqual(transport.requests[0].method, "POST")
        self.assertEqual(transport.requests[0].url.path, "/v1/batch-evaluations")
        self.assertEqual(transport.requests[0].headers["accept"], "application/vnd.registry-notary.claim-result+json")
        self.assertIn("idempotency-key", transport.requests[0].headers)
        request_payload = json.loads(transport.requests[0].read().decode())
        self.assertEqual(
            request_payload["items"],
            [
                {
                    "target": {
                        "type": "Person",
                        "id": "NATIONAL-ID-123",
                        "identifiers": [],
                        "attributes": {},
                    }
                }
            ],
        )

    def test_batch_evaluate_requires_subjects_and_claims(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [_json_response()],
        )

        with self.assertRaises(NotaryConfigurationError):
            client.batch_evaluate(subjects=[], claim_refs=["claim-a"])
        with self.assertRaises(NotaryConfigurationError):
            client.batch_evaluate(subjects=["NATIONAL-ID-123"], claim_refs=[])

        self.assertEqual(transport.requests, [])

    def test_metadata_and_jwks_use_well_known_endpoints(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [
                _json_response(
                    payload={
                        "issuer": "notary",
                        "claims_endpoint": "/v1/claims",
                        "evaluate_endpoint": "/v1/evaluations",
                    }
                ),
                _json_response(payload={"keys": [{"kid": "key-1"}]}),
            ],
        )

        metadata = client.get_metadata()
        jwks = client.get_jwks(purpose="https://openspp.example/override")

        self.assertEqual(metadata.issuer, "notary")
        self.assertEqual(jwks["keys"][0]["kid"], "key-1")
        self.assertEqual(transport.requests[0].url.path, "/.well-known/evidence-service")
        self.assertEqual(transport.requests[1].url.path, "/.well-known/evidence/jwks.json")
        self.assertEqual(transport.requests[1].headers["data-purpose"], "https://openspp.example/override")

    def test_metadata_accepts_lab_service_document_shape(self):
        client, _transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [
                _json_response(
                    payload={
                        "api_version": "2026-05",
                        "service_id": "civil-notary",
                        "issuer": {
                            "id": "did:web:civil-evidence.demo.example",
                            "name": "civil-notary",
                        },
                        "claims_url": "/v1/claims",
                        "formats_url": "/v1/formats",
                    }
                ),
            ],
        )

        metadata = client.get_metadata()

        self.assertEqual(metadata.service_id, "civil-notary")
        self.assertEqual(metadata.issuer["id"], "did:web:civil-evidence.demo.example")
        self.assertEqual(metadata.claims_url, "/v1/claims")

    def test_evaluate_requires_subject_claim_and_purpose_before_network_io(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [_json_response()],
        )

        with self.assertRaises(NotarySubjectIdMissing):
            client.evaluate(subject_id="", claim_refs=["claim-a"])
        with self.assertRaises(NotaryConfigurationError):
            client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=[])

        client_without_purpose, purpose_transport = _client(
            {"base_url": "https://notary.example", "auth_type": "none"},
            [_json_response()],
        )
        with self.assertRaises(NotaryPurposeMissing):
            client_without_purpose.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

        self.assertEqual(transport.requests, [])
        self.assertEqual(purpose_transport.requests, [])

    def test_high_level_helpers_reject_single_claim_and_subject_shapes(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [_json_response()],
        )

        with self.assertRaises(NotaryConfigurationError):
            client.evaluate(subject_id="NATIONAL-ID-123", claim_refs="claim-a")
        with self.assertRaises(NotaryConfigurationError):
            client.evaluate(subject_id="NATIONAL-ID-123", claim_refs={"id": "claim-a"})
        with self.assertRaises(NotaryConfigurationError):
            client.batch_evaluate(subjects="NATIONAL-ID-123", claim_refs=["claim-a"])
        with self.assertRaises(NotaryConfigurationError):
            client.batch_evaluate(subjects={"id": "NATIONAL-ID-123"}, claim_refs=["claim-a"])

        self.assertEqual(transport.requests, [])

    def test_evaluate_refuses_logged_subject_call_without_hash_secret(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [_json_response()],
        )
        client.log_wrapper = Mock()

        with self.assertRaises(NotaryConfigurationError):
            client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

        self.assertEqual(transport.requests, [])
        client.log_wrapper.log_call.assert_not_called()

    def test_context_manager_closes_owned_client_but_not_external_client(self):
        owned_client = NotaryClient(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            }
        )

        with owned_client as managed:
            self.assertIs(managed, owned_client)
            managed._client(managed.config)
            self.assertFalse(managed._http_client.is_closed)

        self.assertTrue(owned_client._http_client.is_closed)

        http_client = httpx.Client(transport=CaptureTransport([_json_response()]))
        external_client = NotaryClient(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            http_client=http_client,
        )

        with external_client:
            pass

        self.assertFalse(http_client.is_closed)
        http_client.close()

    def test_http_error_payloads_map_to_typed_exceptions(self):
        cases = [
            (404, {"error": {"code": "target.not_found"}}, NotarySubjectNotFound),
            (404, {"error": {"code": "claim.not_found"}}, NotaryClaimNotFound),
            (401, {"error": {"code": "auth.invalid"}}, NotaryAuthError),
            (400, {"error": {"code": "request.invalid"}}, NotaryRequestError),
        ]
        for status_code, payload, exception_type in cases:
            with self.subTest(status_code=status_code, code=payload["error"]["code"]):
                client, _transport = _client(
                    {
                        "base_url": "https://notary.example",
                        "auth_type": "none",
                        "default_purpose_url": "https://openspp.example/default-purpose",
                    },
                    [_json_response(status_code, payload)],
                )
                with self.assertRaises(exception_type) as error:
                    client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["secret-claim"])
                self.assertNotIn("NATIONAL-ID-123", str(error.exception))
                self.assertNotIn("secret-claim", str(error.exception))

    def test_evaluate_rate_limit_does_not_retry_or_send_idempotency_key(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [
                _json_response(429, {"error": {"code": "rate_limited"}}),
            ],
        )

        with self.assertRaises(NotaryRateLimited):
            client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

        self.assertEqual(len(transport.requests), 1)
        self.assertNotIn("idempotency-key", transport.requests[0].headers)

    def test_batch_rate_limit_retries_once_with_same_idempotency_key(self):
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

        with self.assertRaises(NotaryRateLimited):
            client.batch_evaluate(subjects=["NATIONAL-ID-123"], claim_refs=["claim-a"])

        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(
            transport.requests[0].headers["idempotency-key"],
            transport.requests[1].headers["idempotency-key"],
        )

    def test_transport_and_timeout_errors_are_logged_as_sanitized_transport_errors(self):
        request = httpx.Request("POST", "https://notary.example/v1/evaluations")
        cases = [
            (httpx.TimeoutException("timeout", request=request), "Notary request timed out"),
            (httpx.ConnectError("connect failed", request=request), "Notary transport error"),
        ]
        for transport_error, message in cases:
            with self.subTest(message=message):
                log_wrapper = Mock()
                client, _transport = _client(
                    {
                        "base_url": "https://notary.example",
                        "auth_type": "none",
                        "default_purpose_url": "https://openspp.example/default-purpose",
                        "subject_log_secret": "audit-secret",
                    },
                    [transport_error],
                )
                client.log_wrapper = log_wrapper

                with self.assertRaises(NotaryTransportError) as error:
                    client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["secret-claim"])

                self.assertEqual(str(error.exception), message)
                self.assertNotIn("NATIONAL-ID-123", str(error.exception))
                self.assertNotIn("secret-claim", str(error.exception))
                self.assertIn(
                    log_wrapper.log_call.call_args.kwargs["status"],
                    {"timeout", "connection_error"},
                )

    def test_successful_and_http_error_logs_receive_sanitized_summaries(self):
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
                ),
                _json_response(404, {"error": {"code": "source.not_found"}}),
            ],
        )
        client.log_wrapper = log_wrapper

        client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])
        with self.assertRaises(NotarySubjectNotFound):
            client.evaluate(subject_id="NATIONAL-ID-456", claim_refs=["claim-b"])

        success_summary = log_wrapper.log_call.call_args_list[0].kwargs["request_summary"]
        error_summary = log_wrapper.log_call.call_args_list[1].kwargs["request_summary"]
        self.assertEqual(log_wrapper.log_call.call_args_list[0].kwargs["status"], "success")
        self.assertEqual(log_wrapper.log_call.call_args_list[1].kwargs["status"], "http_error")
        self.assertEqual(success_summary["claim_ids"], ["claim-a"])
        self.assertEqual(success_summary["evaluation_id"], "eval-123")
        self.assertEqual(error_summary["claim_ids"], ["claim-b"])
        self.assertNotIn("NATIONAL-ID", str(success_summary))
        self.assertNotIn("NATIONAL-ID", str(error_summary))

    def test_response_payload_accepts_non_dict_and_invalid_json(self):
        client, transport = _client(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            [
                httpx.Response(200, json=[{"claim_id": "claim-a"}]),
                httpx.Response(200, content=b"not-json"),
            ],
        )

        first = client._request(
            client.config,
            "GET",
            "/list",
            purpose="https://openspp.example/default-purpose",
            purpose_layer="provider_default",
        )
        second = client._request(
            client.config,
            "GET",
            "/invalid-json",
            purpose="https://openspp.example/default-purpose",
            purpose_layer="provider_default",
        )

        self.assertEqual(first, {"data": [{"claim_id": "claim-a"}]})
        self.assertEqual(second, {})
        self.assertEqual(transport.requests[0].url.path, "/list")

    def test_audit_log_helpers_sanitize_and_validate_inputs(self):
        first = hmac_subject_hash("NATIONAL-ID-123", "secret-one")
        second = hmac_subject_hash("NATIONAL-ID-123", "secret-one")
        other_secret = hmac_subject_hash("NATIONAL-ID-123", "secret-two")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other_secret)
        self.assertTrue(first.startswith("hmac:"))
        self.assertNotIn("NATIONAL-ID-123", first)
        with self.assertRaises(ValueError):
            hmac_subject_hash("NATIONAL-ID-123", "")
        with self.assertRaises(ValueError):
            hmac_subject_hash(None, "secret-one")

        class ClaimLike:
            id = "claim-object"

        self.assertEqual(
            claim_ids_from_refs(["claim-a", {"claim_id": "claim-b"}, ClaimLike(), {"missing": "ignored"}]),
            ["claim-a", "claim-b", "claim-object"],
        )

        summary = build_request_summary(
            purpose="https://openspp.example/programs/123/eligibility",
            purpose_layer="evaluation_context",
            claim_refs=["disability-severity-code", {"id": "poverty-band", "version": "2026-01"}],
            subject_id="NATIONAL-ID-123",
            subject_count=1,
            subject_hash_secret="log-secret",
            response={"evaluation_id": "eval-123", "results": [{"value": "severe"}]},
        )
        self.assertEqual(summary["claim_ids"], ["disability-severity-code", "poverty-band"])
        self.assertEqual(summary["evaluation_id"], "eval-123")
        self.assertIn("subject_hash", summary)
        self.assertNotIn("NATIONAL-ID-123", str(summary))
        self.assertNotIn("severe", str(summary))

    def test_outgoing_log_wrapper_ignores_missing_log_model(self):
        class EnvWithoutOutgoingLog(dict):
            def __contains__(self, key):
                return False

        wrapper = NotaryOutgoingLogWrapper(EnvWithoutOutgoingLog(), service_code="notary")

        self.assertIsNone(wrapper.log_call(endpoint="/v1/evaluations"))

    def test_schema_models_accept_aliases_and_extra_fields(self):
        catalog = CatalogResponse.model_validate(
            {
                "data": [
                    {
                        "id": "disability-severity-code",
                        "name": "Disability severity",
                        "value": {"type": "string"},
                        "formats": ["json"],
                        "disclosure": {"default": "value", "allowed": ["value", "redacted"]},
                        "future_field": {"kept": True},
                    }
                ],
                "future_top_level": "kept",
            }
        )
        bare = EvaluateRequest(
            target=EvidenceEntity(type="Person", id="NATIONAL-ID-123"),
            claims=["disability-severity-code"],
            purpose="https://openspp.example/purpose",
        )
        versioned = EvaluateRequest(
            target=EvidenceEntity(
                type="Person",
                identifiers=[EvidenceIdentifier(scheme="national_id", value="NATIONAL-ID-123")],
            ),
            claims=[ClaimRef(id="disability-severity-code", version="2026-01")],
            purpose="https://openspp.example/purpose",
        )
        batch = BatchEvaluateResponse.model_validate(
            {
                "items": [
                    {
                        "status": "succeeded",
                        "results": [{"claim_id": "claim-a"}],
                    }
                ]
            }
        )

        self.assertEqual(catalog.claims[0].title, "Disability severity")
        self.assertEqual(catalog.claims[0].value_type, "string")
        self.assertEqual(catalog.claims[0].default_disclosure, "value")
        self.assertEqual(catalog.claims[0].allowed_disclosures, ["value", "redacted"])
        self.assertEqual(catalog.claims[0].supported_formats, ["json"])
        self.assertEqual(catalog.claims[0].model_extra["future_field"], {"kept": True})
        self.assertEqual(catalog.model_extra["future_top_level"], "kept")
        self.assertEqual(bare.model_dump(exclude_none=True)["target"]["id"], "NATIONAL-ID-123")
        self.assertEqual(bare.model_dump(exclude_none=True)["claims"], ["disability-severity-code"])
        self.assertEqual(
            versioned.model_dump(exclude_none=True)["claims"],
            [{"id": "disability-severity-code", "version": "2026-01"}],
        )
        self.assertEqual(batch.items[0].claim_results[0].claim_id, "claim-a")

    def test_normalizers_accept_subject_and_claim_objects(self):
        class SubjectLike:
            id = "subject-object"
            id_type = "national_id"

        class ClaimLike:
            id = "claim-object"
            version = "2026-01"

        client = NotaryClient(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            }
        )

        subjects = client._normalize_subjects(
            [
                "subject-string",
                {"id": "subject-dict", "id_type": "national_id"},
                Subject(id="subject-model"),
                SubjectLike(),
            ]
        )
        claims = client._normalize_claim_refs(
            ["claim-string", {"id": "claim-dict"}, ClaimRef(id="claim-model"), ClaimLike()]
        )

        self.assertEqual(
            [subject.id for subject in subjects],
            ["subject-string", "subject-dict", "subject-model", "subject-object"],
        )
        self.assertEqual(
            [getattr(claim, "id", claim) for claim in claims],
            ["claim-string", "claim-dict", "claim-model", "claim-object"],
        )
