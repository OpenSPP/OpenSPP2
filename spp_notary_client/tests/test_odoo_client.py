# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Odoo-runner coverage for the pure Python Notary client."""

import httpx

try:
    from odoo.tests import TransactionCase, tagged
except ImportError:
    import pytest

    pytest.skip("Odoo test runner is not available", allow_module_level=True)

from odoo.addons.spp_notary_client.services.client import NotaryClient
from odoo.addons.spp_notary_client.services.exceptions import NotaryPurposeMissing


class CaptureTransport(httpx.BaseTransport):
    """HTTPX transport that records requests for assertions."""

    def __init__(self, response):
        self.response = response
        self.requests = []

    def handle_request(self, request):
        self.requests.append(request)
        return self.response


@tagged("post_install", "-at_install")
class TestNotaryClientOdooRunner(TransactionCase):
    def test_evaluate_serializes_versioned_claim_ref(self):
        transport = CaptureTransport(
            httpx.Response(
                200,
                json={
                    "evaluation_id": "eval-versioned",
                    "results": [
                        {
                            "claim_id": "disability-severity-code",
                            "claim_version": "2026-01",
                            "value": "severe",
                        }
                    ],
                },
            )
        )
        client = NotaryClient(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/default-purpose",
            },
            http_client=httpx.Client(transport=transport),
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

    def test_evaluate_requires_purpose_before_network_io(self):
        transport = CaptureTransport(httpx.Response(200, json={}))
        client = NotaryClient(
            {"base_url": "https://notary.example", "auth_type": "none"},
            http_client=httpx.Client(transport=transport),
        )

        with self.assertRaises(NotaryPurposeMissing):
            client.evaluate(subject_id="NATIONAL-ID-123", claim_refs=["claim-a"])

        self.assertEqual(transport.requests, [])
