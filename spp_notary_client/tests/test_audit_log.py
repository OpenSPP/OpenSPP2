# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Notary outgoing log sanitization."""

from spp_notary_client.services.audit_log import build_request_summary, hmac_subject_hash


def test_hmac_subject_hash_is_stable_and_secret_keyed():
    """Subject hashes are stable HMACs, not raw or plain hashes."""
    first = hmac_subject_hash("NATIONAL-ID-123", "secret-one")
    second = hmac_subject_hash("NATIONAL-ID-123", "secret-one")
    other_secret = hmac_subject_hash("NATIONAL-ID-123", "secret-two")

    assert first == second
    assert first != other_secret
    assert first.startswith("hmac:")
    assert "NATIONAL-ID-123" not in first


def test_hmac_subject_hash_requires_secret():
    """Missing secrets fail closed."""
    try:
        hmac_subject_hash("NATIONAL-ID-123", "")
    except ValueError as error:
        assert "secret" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_build_request_summary_excludes_raw_subject_and_claim_values():
    """Audit summary keeps useful context without leaking subject IDs or values."""
    summary = build_request_summary(
        purpose="https://openspp.example/programs/123/eligibility",
        purpose_layer="evaluation_context",
        claim_refs=["disability-severity-code", {"id": "poverty-band", "version": "2026-01"}],
        subject_id="NATIONAL-ID-123",
        subject_count=1,
        subject_hash_secret="log-secret",
        evaluation_id="eval-123",
        response={
            "results": [
                {"claim_id": "disability-severity-code", "value": "severe"},
                {"claim_id": "poverty-band", "value": 3},
            ]
        },
    )

    assert summary == {
        "purpose": "https://openspp.example/programs/123/eligibility",
        "purpose_layer": "evaluation_context",
        "claim_ids": ["disability-severity-code", "poverty-band"],
        "subject_hash": hmac_subject_hash("NATIONAL-ID-123", "log-secret"),
        "evaluation_id": "eval-123",
        "subject_count": 1,
    }
    assert "NATIONAL-ID-123" not in str(summary)
    assert "severe" not in str(summary)
    assert "'value': 3" not in str(summary)
