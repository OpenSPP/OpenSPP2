# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Notary evidence provider integration."""

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_notary_client.services.client import NotaryClient
from odoo.addons.spp_notary_client.services.exceptions import NotaryError, NotarySubjectIdMissing, NotaryTransportError
from odoo.addons.spp_notary_client.services.schemas import CatalogResponse
from odoo.addons.spp_notary_evidence.models.notary_claim import data_value_type_for_cel, normalize_notary_value_type


@tagged("post_install", "-at_install")
class TestNotaryEvidence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.Provider = cls.env["spp.data.provider"]
        cls.Claim = cls.env["spp.notary.claim"]
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": f"Notary Test ID Types {cls._test_id}",
                "namespace_uri": f"urn:openspp:test:notary-id-type:{cls._test_id}",
                "domain": "core",
            }
        )
        cls.id_type = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "national_id",
                "display": "National ID",
                "target_type": "both",
            }
        )
        cls.partner_a = cls.env["res.partner"].create(
            {
                "name": f"Notary A {cls._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.partner_b = cls.env["res.partner"].create(
            {
                "name": f"Notary B {cls._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.partner_c = cls.env["res.partner"].create(
            {
                "name": f"Notary C {cls._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_a.id,
                "id_type_id": cls.id_type.id,
                "value": f"NID-A-{cls._test_id}",
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_b.id,
                "id_type_id": cls.id_type.id,
                "value": f"NID-B-{cls._test_id}",
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_c.id,
                "id_type_id": cls.id_type.id,
                "value": f"NID-C-{cls._test_id}",
            }
        )
        cls.provider = cls.Provider.create(
            {
                "name": "Notary Test Provider",
                "code": f"notary_test_{cls._test_id}",
                "provider_kind": "notary",
                "base_url": "https://notary.example",
                "auth_type": "none",
                "notary_default_purpose_url": "https://openspp.example/purpose/default",
                "notary_subject_id_type_id": cls.id_type.id,
            }
        )

    def test_catalog_sync_creates_claim_and_external_variable(self):
        catalog = SimpleNamespace(
            claims=[
                SimpleNamespace(
                    id="farmer-under-4ha",
                    title="Farmer under 4ha",
                    description="Farm size predicate",
                    version="2026-01",
                    subject_type="individual",
                    disclosure=["predicate"],
                    value_type="boolean",
                    default_disclosure=None,
                )
            ]
        )

        with patch.object(type(self.provider), "_fetch_notary_catalog", return_value=catalog):
            result = self.provider.action_sync_notary_claim_catalog()

        self.assertEqual(result["created"], 1)
        claim = self.Claim.search(
            [
                ("provider_id", "=", self.provider.id),
                ("external_id", "=", "farmer-under-4ha"),
            ],
            limit=1,
        )
        self.assertTrue(claim)
        self.assertEqual(claim.claim_version, "2026-01")
        self.assertEqual(claim.pinned_version, "2026-01")
        self.assertEqual(claim.value_type, "boolean")
        self.assertTrue(claim.variable_id)
        self.assertEqual(claim.variable_id.source_type, "external")
        self.assertEqual(claim.variable_id.external_provider_id, self.provider)
        self.assertEqual(claim.variable_id.notary_claim_id, claim)

    def test_fetch_notary_catalog_supports_legacy_client_shapes(self):
        discover_client = SimpleNamespace(
            discover_claims=lambda: CatalogResponse.model_validate(
                {"claims": [{"id": "discover-claim", "title": "Discover Claim"}]}
            )
        )
        get_client = SimpleNamespace(
            get_claim_catalog=lambda: [
                {
                    "id": "legacy-get",
                    "name": "Legacy Get",
                    "version": "2026-01",
                    "type": "bool",
                }
            ]
        )
        fetch_client = SimpleNamespace(
            fetch_claim_catalog=lambda path: [
                {
                    "id": f"legacy-fetch-{path.strip('/')}",
                    "title": "Legacy Fetch",
                    "formats": ["json"],
                }
            ]
        )

        with patch.object(type(self.provider), "_notary_client", return_value=discover_client):
            discover_catalog = self.provider._fetch_notary_catalog()
        with patch.object(type(self.provider), "_notary_client", return_value=get_client):
            get_catalog = self.provider._fetch_notary_catalog()
        with patch.object(type(self.provider), "_notary_client", return_value=fetch_client):
            fetch_catalog = self.provider._fetch_notary_catalog()

        self.assertEqual(discover_catalog.claims[0].id, "discover-claim")
        self.assertEqual(get_catalog.claims[0].id, "legacy-get")
        self.assertEqual(get_catalog.claims[0].title, "Legacy Get")
        self.assertEqual(get_catalog.claims[0].value_type, "bool")
        self.assertEqual(fetch_catalog.claims[0].id, "legacy-fetch-v1/claims")
        self.assertEqual(fetch_catalog.claims[0].supported_formats, ["json"])
        with patch.object(type(self.provider), "_notary_client", return_value=SimpleNamespace()):
            with self.assertRaises(UserError):
                self.provider._fetch_notary_catalog()

    def test_catalog_sync_rejects_non_notary_and_wraps_notary_error(self):
        generic_provider = self.Provider.create(
            {
                "name": "Generic Provider",
                "code": f"generic_notary_test_{self._test_id}",
                "provider_kind": "generic",
                "base_url": "https://generic.example",
                "auth_type": "none",
            }
        )

        with self.assertRaises(UserError):
            generic_provider.action_sync_notary_claim_catalog()
        with patch.object(type(self.provider), "_fetch_notary_catalog", side_effect=NotaryError("catalog down")):
            with self.assertRaises(UserError):
                self.provider.action_sync_notary_claim_catalog()

    def test_provider_actions_return_wizard_and_claim_windows(self):
        claim = self._create_claim_with_variable("window-claim", value_type="boolean")

        wizard_action = self.provider.action_open_notary_catalog_sync_wizard()
        claim_action = self.provider.action_view_notary_claims()

        self.assertEqual(wizard_action["res_model"], "spp.notary.catalog.sync.wizard")
        self.assertEqual(wizard_action["context"]["default_provider_id"], self.provider.id)
        self.assertEqual(claim_action["res_model"], "spp.notary.claim")
        self.assertIn(("provider_id", "=", self.provider.id), claim_action["domain"])
        self.assertEqual(self.provider.notary_claim_count, 1)
        self.assertEqual(claim.provider_id, self.provider)

    def test_notary_test_connection_fetches_claim_catalog(self):
        catalog = SimpleNamespace(claims=[SimpleNamespace(id="person-is-alive")])

        with patch.object(type(self.provider), "_fetch_notary_catalog", return_value=catalog) as mocked_fetch:
            action = self.provider.action_test_connection()

        mocked_fetch.assert_called_once()
        self.assertEqual(action["params"]["type"], "success")
        self.assertIn("fetched 1 Notary claim", action["params"]["message"])

    def test_notary_test_connection_reports_notary_errors(self):
        error = NotaryError("Notary authentication failed", status_code=401)

        with patch.object(type(self.provider), "_fetch_notary_catalog", side_effect=error):
            action = self.provider.action_test_connection()

        self.assertEqual(action["params"]["type"], "warning")
        self.assertIn("401", action["params"]["message"])

    def test_catalog_sync_marks_missing_claims_unavailable(self):
        claim = self._create_claim_with_variable("removed-claim", value_type="boolean")
        catalog = SimpleNamespace(claims=[])

        with patch.object(type(self.provider), "_fetch_notary_catalog", return_value=catalog):
            result = self.provider.action_sync_notary_claim_catalog()

        claim.invalidate_recordset()
        self.assertEqual(result["deactivated"], 1)
        self.assertFalse(claim.active)
        self.assertEqual(claim.state, "unavailable")
        self.assertFalse(claim.variable_id.active)

    def test_compute_external_values_batches_and_writes_provider_scoped_cache(self):
        claim = self._create_claim_with_variable("poverty-band", value_type="number")
        batch_response = SimpleNamespace(
            items=[
                SimpleNamespace(
                    input_index=0,
                    status="succeeded",
                    claim_results=[
                        SimpleNamespace(
                            claim_id="poverty-band",
                            value=3,
                            satisfied=None,
                            expires_at=None,
                        )
                    ],
                    results=[],
                    errors=[],
                ),
                SimpleNamespace(
                    input_index=1,
                    status="failed",
                    claim_results=[],
                    results=[],
                    errors=[{"code": "source.not_found", "title": "missing"}],
                ),
            ]
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.batch_evaluate.return_value = batch_response
            values = self.provider._compute_external_values(
                claim.variable_id,
                [self.partner_a.id, self.partner_b.id],
                "current",
            )

        self.assertEqual(values, {self.partner_a.id: 3})
        mocked_client.return_value.batch_evaluate.assert_called_once()
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "=", self.partner_a.id),
                ("provider", "=", self.provider.code),
            ],
            limit=1,
        )
        self.assertTrue(cached)
        self.assertEqual(cached.value_json, {"value": 3})

    def test_compute_external_values_falls_back_to_single_evaluate_when_batch_unsupported(self):
        claim = self._create_claim_with_variable("person-is-alive", value_type="boolean")
        unsupported_batch = NotaryError(code="claim.operation_unsupported", status_code=501)
        single_response = SimpleNamespace(
            results=[
                SimpleNamespace(
                    claim_id="person-is-alive",
                    value=True,
                    satisfied=True,
                    expires_at=None,
                )
            ]
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.batch_evaluate.side_effect = unsupported_batch
            mocked_client.return_value.evaluate.return_value = single_response
            values = self.provider._compute_external_values(
                claim.variable_id,
                [self.partner_a.id, self.partner_b.id],
                "current",
            )

        self.assertEqual(values, {self.partner_a.id: True, self.partner_b.id: True})
        mocked_client.return_value.batch_evaluate.assert_called_once()
        self.assertEqual(mocked_client.return_value.evaluate.call_count, 2)
        first_call = mocked_client.return_value.evaluate.call_args_list[0].kwargs
        self.assertEqual(first_call["claim_refs"], [{"id": "person-is-alive", "version": "2026-01"}])
        self.assertEqual(first_call["subject_id_type"], self.id_type.code)
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "in", [self.partner_a.id, self.partner_b.id]),
                ("provider", "=", self.provider.code),
            ]
        )
        self.assertEqual(len(cached), 2)

    def test_compute_external_values_partitions_by_provider_batch_size(self):
        claim = self._create_claim_with_variable("partitioned-claim", value_type="number")
        self.provider.max_batch_size = 2
        responses = [
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        input_index=0,
                        status="succeeded",
                        claim_results=[
                            SimpleNamespace(
                                claim_id="partitioned-claim",
                                value=10,
                                satisfied=None,
                                expires_at=None,
                            )
                        ],
                        results=[],
                        errors=[],
                    ),
                    SimpleNamespace(
                        input_index=1,
                        status="succeeded",
                        claim_results=[
                            SimpleNamespace(
                                claim_id="partitioned-claim",
                                value=20,
                                satisfied=None,
                                expires_at=None,
                            )
                        ],
                        results=[],
                        errors=[],
                    ),
                ]
            ),
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        input_index=0,
                        status="succeeded",
                        claim_results=[
                            SimpleNamespace(
                                claim_id="partitioned-claim",
                                value=30,
                                satisfied=None,
                                expires_at=None,
                            )
                        ],
                        results=[],
                        errors=[],
                    )
                ]
            ),
        ]

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.batch_evaluate.side_effect = responses
            values = self.provider._compute_external_values(
                claim.variable_id,
                [self.partner_a.id, self.partner_b.id, self.partner_c.id],
                "current",
            )

        self.assertEqual(
            values,
            {
                self.partner_a.id: 10,
                self.partner_b.id: 20,
                self.partner_c.id: 30,
            },
        )
        self.assertEqual(mocked_client.return_value.batch_evaluate.call_count, 2)
        first_subjects = mocked_client.return_value.batch_evaluate.call_args_list[0].kwargs["subjects"]
        second_subjects = mocked_client.return_value.batch_evaluate.call_args_list[1].kwargs["subjects"]
        self.assertEqual(len(first_subjects), 2)
        self.assertEqual(len(second_subjects), 1)

    def test_compute_external_values_sends_pinned_claim_version(self):
        claim = self._create_claim_with_variable("versioned-batch", value_type="number")
        batch_response = SimpleNamespace(
            items=[
                SimpleNamespace(
                    input_index=0,
                    status="succeeded",
                    claim_results=[
                        SimpleNamespace(
                            claim_id="versioned-batch",
                            value=10,
                            satisfied=None,
                            expires_at=None,
                        )
                    ],
                    results=[],
                    errors=[],
                )
            ]
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.batch_evaluate.return_value = batch_response
            self.provider._compute_external_values(
                claim.variable_id,
                [self.partner_a.id],
                "current",
            )

        kwargs = mocked_client.return_value.batch_evaluate.call_args.kwargs
        self.assertEqual(kwargs["claim_refs"], [{"id": "versioned-batch", "version": "2026-01"}])
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "=", self.partner_a.id),
                ("provider", "=", self.provider.code),
            ],
            limit=1,
        )
        self.assertEqual(cached.params_hash, self.env["spp.data.value"]._hash_params({"version": "2026-01"}))
        self.assertEqual(
            self.env["spp.data.value"].read_values(
                claim.variable_id.name,
                [self.partner_a.id],
                provider=self.provider.code,
                params={"version": "2026-01"},
            ),
            {self.partner_a.id: 10},
        )
        self.assertEqual(
            self.env["spp.data.value"].read_values(
                claim.variable_id.name,
                [self.partner_a.id],
                provider=self.provider.code,
                params={"version": "2026-02"},
            ),
            {},
        )

    def test_refresh_external_value_uses_evaluate_and_purpose_context(self):
        claim = self._create_claim_with_variable("disability-severity", value_type="string")
        response = SimpleNamespace(
            evaluation_id="eval-123",
            results=[
                SimpleNamespace(
                    claim_id="disability-severity",
                    value="severe",
                    satisfied=True,
                    expires_at=None,
                )
            ],
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.return_value = response
            provider = self.provider.with_context(
                cel_cfg={"notary_purpose": "https://openspp.example/purpose/evaluation"}
            )
            value = provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "severe")
        kwargs = mocked_client.return_value.evaluate.call_args.kwargs
        self.assertEqual(kwargs["purpose"], "https://openspp.example/purpose/evaluation")
        self.assertEqual(kwargs["purpose_layer"], "evaluation_context")
        self.assertEqual(kwargs["subject_id"], f"NID-A-{self._test_id}")
        self.assertEqual(kwargs["subject_id_type"], self.id_type.code)
        self.assertEqual(kwargs["claim_refs"], [{"id": "disability-severity", "version": "2026-01"}])

    def test_refresh_external_value_uses_string_claim_ref_when_unpinned(self):
        claim = self._create_claim_with_variable("latest-claim", value_type="string")
        claim.pinned_version = False
        response = SimpleNamespace(
            evaluation_id="eval-latest",
            results=[
                SimpleNamespace(
                    claim_id="latest-claim",
                    value="latest-ok",
                    satisfied=True,
                    expires_at=None,
                )
            ],
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.return_value = response
            value = self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "latest-ok")
        kwargs = mocked_client.return_value.evaluate.call_args.kwargs
        self.assertEqual(kwargs["claim_refs"], ["latest-claim"])

    def test_refresh_external_value_uses_claim_purpose_before_provider_default(self):
        claim = self._create_claim_with_variable("claim-purpose", value_type="string")
        claim.default_purpose_url = "https://openspp.example/purpose/claim"
        response = SimpleNamespace(
            evaluation_id="eval-claim-purpose",
            results=[
                SimpleNamespace(
                    claim_id="claim-purpose",
                    value="ok",
                    satisfied=True,
                    expires_at=None,
                )
            ],
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.return_value = response
            value = self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "ok")
        kwargs = mocked_client.return_value.evaluate.call_args.kwargs
        self.assertEqual(kwargs["purpose"], "https://openspp.example/purpose/claim")
        self.assertEqual(kwargs["purpose_layer"], "claim_default")
        self.assertEqual(claim.effective_purpose_url, "https://openspp.example/purpose/claim")
        self.assertEqual(claim.variable_id.effective_purpose_url, "https://openspp.example/purpose/claim")

    def test_refresh_external_value_uses_provider_purpose_when_no_context_or_claim_default(self):
        claim = self._create_claim_with_variable("provider-purpose", value_type="string")
        response = SimpleNamespace(
            evaluation_id="eval-provider-purpose",
            results=[
                SimpleNamespace(
                    claim_id="provider-purpose",
                    value="ok",
                    satisfied=True,
                    expires_at=None,
                )
            ],
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.return_value = response
            value = self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "ok")
        kwargs = mocked_client.return_value.evaluate.call_args.kwargs
        self.assertEqual(kwargs["purpose"], "https://openspp.example/purpose/default")
        self.assertEqual(kwargs["purpose_layer"], "provider_default")

    def test_missing_subject_id_raises_before_client_call(self):
        claim = self._create_claim_with_variable("missing-subject-id", value_type="boolean")
        partner = self.env["res.partner"].create(
            {
                "name": f"No ID {self._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            with self.assertRaises(NotarySubjectIdMissing):
                self.provider._refresh_external_value(claim.variable_id, partner.id, "current")

        mocked_client.assert_not_called()

    def test_stale_cache_with_audit_policy_returns_expired_provider_scoped_value(self):
        claim = self._create_claim_with_variable("stale-claim", value_type="string")
        stale_expires_at = fields.Datetime.now() - timedelta(hours=1)
        self.provider.notary_subject_log_secret = "stale-audit-secret"
        self.env["spp.data.value"].upsert_values(
            [
                {
                    "variable_name": claim.variable_id.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": self.provider.code,
                    "value_json": {"value": "cached-stale"},
                    "value_type": "string",
                    "source_type": "external",
                    "params": {"version": "2026-01"},
                    "expires_at": stale_expires_at,
                }
            ]
        )
        provider = self.provider.with_context(cel_cfg={"notary_purpose": "https://openspp.example/purpose/evaluation"})
        provider.notary_unavailable_policy = "stale_cache_with_audit"

        with patch.object(type(provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
                details={"evaluation_id": "eval-stale-failed"},
            )
            value = provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "cached-stale")
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "=", self.partner_a.id),
                ("provider", "=", self.provider.code),
            ],
            limit=1,
        )
        self.assertEqual(cached.expires_at, stale_expires_at)
        log = (
            self.env["spp.api.outgoing.log"]
            .sudo()
            .search(
                [
                    ("service_code", "=", self.provider.code),
                    ("endpoint", "=", "/claims/stale-cache-read"),
                ],
                limit=1,
            )
        )
        self.assertTrue(log)
        self.assertEqual(log.request_summary["cache_policy"], "stale_cache_with_audit")
        self.assertEqual(log.request_summary["subject_count"], 1)
        self.assertEqual(log.request_summary["claim_id"], "stale-claim")
        self.assertEqual(log.request_summary["evaluation_id"], "eval-stale-failed")
        self.assertEqual(len(log.request_summary["stale_values"]), 1)
        self.assertIn("subject_hash", log.request_summary["stale_values"][0])
        self.assertGreaterEqual(log.request_summary["stale_values"][0]["stale_age_seconds"], 3600)
        self.assertNotIn(f"NID-A-{self._test_id}", str(log.request_summary))

    def test_stale_cache_with_audit_does_not_cross_provider_boundary(self):
        claim = self._create_claim_with_variable("stale-other-provider", value_type="string")
        other_provider = self.Provider.create(
            {
                "name": "Other Notary Test Provider",
                "code": f"other_notary_test_{self._test_id}",
                "provider_kind": "notary",
                "base_url": "https://other-notary.example",
                "auth_type": "none",
                "notary_default_purpose_url": "https://openspp.example/purpose/default",
                "notary_subject_id_type_id": self.id_type.id,
            }
        )
        self.env["spp.data.value"].upsert_values(
            [
                {
                    "variable_name": claim.variable_id.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": other_provider.code,
                    "value_json": {"value": "wrong-provider-stale"},
                    "value_type": "string",
                    "source_type": "external",
                    "params": {"version": "2026-01"},
                    "expires_at": fields.Datetime.now() - timedelta(hours=1),
                }
            ]
        )
        provider = self.provider.with_context(cel_cfg={"notary_purpose": "https://openspp.example/purpose/evaluation"})
        provider.notary_unavailable_policy = "stale_cache_with_audit"

        with patch.object(type(provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
            )
            with self.assertRaises(NotaryTransportError):
                provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

    def test_stale_cache_with_audit_requires_subject_log_secret(self):
        claim = self._create_claim_with_variable("stale-missing-secret", value_type="string")
        self.env["spp.data.value"].upsert_values(
            [
                {
                    "variable_name": claim.variable_id.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": self.provider.code,
                    "value_json": {"value": "cached-stale"},
                    "value_type": "string",
                    "source_type": "external",
                    "params": {"version": "2026-01"},
                    "expires_at": fields.Datetime.now() - timedelta(hours=1),
                }
            ]
        )
        self.provider.notary_unavailable_policy = "stale_cache_with_audit"

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
            )
            with self.assertRaises(UserError):
                self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

    def test_provider_helper_short_circuits_and_defaults(self):
        claim = self._create_claim_with_variable("helper-defaults", value_type="boolean")
        provider_purpose = self.provider.with_context(notary_purpose="https://openspp.example/purpose/context")
        no_subject_type_provider = self.Provider.create(
            {
                "name": "No Subject Type Notary",
                "code": f"no_subject_type_notary_{self._test_id}",
                "provider_kind": "notary",
                "base_url": "https://notary.example",
                "auth_type": "none",
                "notary_default_purpose_url": "https://openspp.example/purpose/default",
            }
        )
        empty_variable = SimpleNamespace(notary_claim_id=False)
        no_match_response = SimpleNamespace(
            items=[
                SimpleNamespace(
                    input_index=0,
                    status="succeeded",
                    claim_results=[],
                    results=[SimpleNamespace(claim_id="different-claim", value=True, satisfied=True, expires_at=None)],
                )
            ]
        )

        self.assertEqual(
            self.provider._notary_default_disclosure(SimpleNamespace(disclosure="credential")),
            "credential",
        )
        self.assertEqual(self.provider._notary_default_disclosure(SimpleNamespace(disclosure=[])), "predicate")
        self.assertEqual(provider_purpose._notary_purpose(claim), "https://openspp.example/purpose/context")
        self.assertEqual(self.provider._compute_external_values(empty_variable, [self.partner_a.id], "current"), {})
        self.assertIsNone(self.provider._refresh_external_value(empty_variable, self.partner_a.id, "current"))
        self.assertEqual(
            self.provider._values_from_batch_response(no_match_response, [(self.partner_a.id, {})], claim),
            {},
        )
        self.assertIsNone(self.provider._first_matching_result(None, claim.external_id))
        with self.assertRaises(NotarySubjectIdMissing):
            no_subject_type_provider._notary_subject_ref(self.partner_a.id)
        with self.assertRaises(NotarySubjectIdMissing):
            self.provider._notary_subject_ref(999999999)

    def test_owned_notary_clients_are_closed_after_provider_calls(self):
        class ManagedClient(NotaryClient):
            def __init__(self, response):
                self.response = response
                self.closed = False

            def close(self):
                self.closed = True

            def discover_claims(self):
                return self.response

            def batch_evaluate(self, **_kwargs):
                return self.response

            def evaluate(self, **_kwargs):
                return self.response

        claim = self._create_claim_with_variable("managed-client", value_type="boolean")
        catalog_client = ManagedClient(CatalogResponse.model_validate({"claims": [{"id": "managed-catalog"}]}))
        batch_client = ManagedClient(
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        input_index=0,
                        status="succeeded",
                        claim_results=[
                            SimpleNamespace(
                                claim_id="managed-client",
                                value=True,
                                satisfied=True,
                                expires_at=None,
                            )
                        ],
                        results=[],
                    )
                ]
            )
        )
        evaluate_client = ManagedClient(
            SimpleNamespace(
                results=[
                    SimpleNamespace(
                        claim_id="managed-client",
                        value=False,
                        satisfied=False,
                        expires_at=None,
                    )
                ]
            )
        )

        with patch.object(type(self.provider), "_notary_client", return_value=catalog_client):
            self.provider._fetch_notary_catalog()
        with patch.object(type(self.provider), "_notary_client", return_value=batch_client):
            self.provider._compute_external_values(claim.variable_id, [self.partner_a.id], "current")
        with patch.object(type(self.provider), "_notary_client", return_value=evaluate_client):
            self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertTrue(catalog_client.closed)
        self.assertTrue(batch_client.closed)
        self.assertTrue(evaluate_client.closed)

    def test_null_policy_returns_none_without_cache_write(self):
        claim = self._create_claim_with_variable("null-policy-claim", value_type="string")
        self.provider.notary_unavailable_policy = "null"

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
            )
            value = self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertIsNone(value)
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "=", self.partner_a.id),
                ("provider", "=", self.provider.code),
            ],
            limit=1,
        )
        self.assertFalse(cached)

    def test_error_policy_helpers_handle_unknown_policy_and_empty_stale_reads(self):
        claim = self._create_claim_with_variable("empty-stale-policy", value_type="string")
        error = NotaryTransportError(code="source.unavailable", status_code=503)

        self.provider.notary_unavailable_policy = "stale_cache_with_audit"
        self.assertEqual(self.provider._read_stale_notary_values(claim.variable_id, [], "current"), {})
        with self.assertRaises(NotaryTransportError):
            self.provider._values_for_notary_error(error, claim.variable_id, [self.partner_a.id], "current")

        self.provider.notary_unavailable_policy = "null"
        self.assertEqual(
            self.provider._values_for_notary_error(error, claim.variable_id, [self.partner_a.id], "current"),
            {},
        )

    def test_batch_missing_subject_id_obeys_null_policy_before_client_call(self):
        claim = self._create_claim_with_variable("batch-missing-subject", value_type="string")
        provider = self.Provider.create(
            {
                "name": "Missing Subject Policy",
                "code": f"missing_subject_policy_{self._test_id}",
                "provider_kind": "notary",
                "base_url": "https://notary.example",
                "auth_type": "none",
                "notary_default_purpose_url": "https://openspp.example/purpose/default",
                "notary_unavailable_policy": "null",
            }
        )

        with patch.object(type(provider), "_notary_client") as mocked_client:
            values = provider._compute_external_values(claim.variable_id, [self.partner_a.id], "current")

        self.assertEqual(values, {})
        mocked_client.return_value.batch_evaluate.assert_not_called()

    def test_raise_policy_surfaces_notary_error_as_user_error(self):
        claim = self._create_claim_with_variable("raise-policy-claim", value_type="string")
        self.provider.notary_unavailable_policy = "raise"

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
            )
            with self.assertRaises(UserError):
                self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

    def test_notary_expires_at_is_clamped_to_minimum_cache_ttl(self):
        claim = self._create_claim_with_variable("ttl-clamp", value_type="number")
        self.provider.notary_min_cache_ttl_seconds = 300
        upstream_expires_at = fields.Datetime.now() - timedelta(minutes=1)
        response = SimpleNamespace(
            evaluation_id="eval-ttl-clamp",
            results=[
                SimpleNamespace(
                    claim_id="ttl-clamp",
                    value=99,
                    satisfied=True,
                    expires_at=upstream_expires_at,
                )
            ],
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.return_value = response
            self.provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "=", self.partner_a.id),
                ("provider", "=", self.provider.code),
            ],
            limit=1,
        )
        self.assertGreaterEqual(cached.expires_at, fields.Datetime.now() + timedelta(seconds=250))

    def test_notary_value_helpers_cover_stale_raw_values_and_fallback_shapes(self):
        claim = self._create_claim_with_variable("helper-shapes", value_type="boolean")
        stale_expires_at = fields.Datetime.now() - timedelta(minutes=30)
        self.env["spp.data.value"].upsert_values(
            [
                {
                    "variable_name": claim.variable_id.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "past",
                    "provider": self.provider.code,
                    "value_json": "raw-stale",
                    "value_type": "string",
                    "source_type": "external",
                    "params": {"version": "2026-01"},
                    "expires_at": stale_expires_at,
                }
            ]
        )
        batch_response = SimpleNamespace(
            items=[
                SimpleNamespace(
                    input_index=None,
                    status="succeeded",
                    claim_results=[],
                    results=[
                        SimpleNamespace(
                            claim_id="helper-shapes",
                            value=None,
                            satisfied=False,
                            expires_at="2026-01-02T03:04:05Z",
                        )
                    ],
                ),
                SimpleNamespace(input_index=2, status="failed", claim_results=[], results=[]),
            ]
        )

        stale = self.provider._read_stale_notary_values(claim.variable_id, [self.partner_a.id], "past")
        values = self.provider._values_from_batch_response(batch_response, [(self.partner_b.id, {})], claim)
        self.provider._write_notary_values(
            claim.variable_id,
            {self.partner_c.id: {"value": "do-not-write", "stale": True}},
            "current",
        )

        self.assertEqual(stale[self.partner_a.id]["value"], "raw-stale")
        self.assertEqual(values[self.partner_b.id]["value"], False)
        self.assertTrue(values[self.partner_b.id]["expires_at"])
        self.assertIsNone(self.provider._effective_notary_expires_at(None))
        self.provider.notary_min_cache_ttl_seconds = 0
        upstream_expires_at = fields.Datetime.now() + timedelta(minutes=5)
        self.assertEqual(self.provider._effective_notary_expires_at(upstream_expires_at), upstream_expires_at)
        self.assertIsNone(self.provider._parse_notary_datetime("not a datetime"))
        self.assertIsNone(self.provider._parse_notary_datetime(object()))
        self.assertFalse(
            self.env["spp.data.value"].search(
                [
                    ("variable_name", "=", claim.variable_id.name),
                    ("subject_id", "=", self.partner_c.id),
                    ("provider", "=", self.provider.code),
                ]
            )
        )

    def test_catalog_sync_marks_existing_pinned_claim_as_version_drift(self):
        claim = self._create_claim_with_variable("drifting-claim", value_type="boolean")
        catalog = SimpleNamespace(
            claims=[
                SimpleNamespace(
                    id="drifting-claim",
                    title="Drifting claim",
                    description="Version changed upstream",
                    version="2026-02",
                    subject_type="individual",
                    disclosure=["predicate"],
                    value_type="boolean",
                    default_disclosure=None,
                )
            ]
        )

        with patch.object(type(self.provider), "_fetch_notary_catalog", return_value=catalog):
            self.provider.action_sync_notary_claim_catalog()

        claim.invalidate_recordset()
        self.assertEqual(claim.claim_version, "2026-02")
        self.assertEqual(claim.pinned_version, "2026-01")
        self.assertEqual(claim.state, "version_drift")
        self.assertEqual(
            self.Claim.search_count([("provider_id", "=", self.provider.id), ("external_id", "=", "drifting-claim")]),
            1,
        )

    def test_catalog_sync_wizard_previews_before_confirming(self):
        catalog = CatalogResponse.model_validate(
            {
                "claims": [
                    {
                        "id": "wizard-preview-claim",
                        "title": "Wizard Preview Claim",
                        "description": "Created only after confirm",
                        "version": "2026-01",
                        "subject_type": "individual",
                        "disclosure": ["predicate"],
                        "value_type": "boolean",
                    }
                ]
            }
        )
        wizard = self.env["spp.notary.catalog.sync.wizard"].create({"provider_id": self.provider.id})

        with patch.object(type(self.provider), "_fetch_notary_catalog", return_value=catalog):
            wizard.action_load_preview()

        self.assertEqual(wizard.state, "preview")
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.action, "create")
        self.assertFalse(
            self.Claim.search([("provider_id", "=", self.provider.id), ("external_id", "=", "wizard-preview-claim")])
        )

        wizard.action_sync_catalog()

        self.assertTrue(
            self.Claim.search([("provider_id", "=", self.provider.id), ("external_id", "=", "wizard-preview-claim")])
        )

    def test_catalog_sync_wizard_default_get_guards_and_preview_errors(self):
        generic_provider = self.Provider.create(
            {
                "name": "Generic Wizard Provider",
                "code": f"generic_wizard_notary_{self._test_id}",
                "provider_kind": "generic",
                "base_url": "https://generic-wizard.example",
                "auth_type": "none",
            }
        )
        values = (
            self.env["spp.notary.catalog.sync.wizard"]
            .with_context(active_model="spp.data.provider", active_id=self.provider.id)
            .default_get(["provider_id"])
        )
        wizard = self.env["spp.notary.catalog.sync.wizard"].create({"provider_id": self.provider.id})
        generic_wizard = self.env["spp.notary.catalog.sync.wizard"].create({"provider_id": generic_provider.id})

        self.assertEqual(values["provider_id"], self.provider.id)
        with self.assertRaises(UserError):
            wizard.action_sync_catalog()
        with self.assertRaises(UserError):
            generic_wizard.action_load_preview()
        with patch.object(type(self.provider), "_fetch_notary_catalog", side_effect=NotaryError("preview down")):
            with self.assertRaises(UserError):
                wizard.action_load_preview()

    def test_catalog_sync_wizard_previews_update_no_change_drift_and_unavailable(self):
        no_change = self._create_claim_with_variable("wizard-no-change", value_type="boolean")
        update = self._create_claim_with_variable("wizard-update", value_type="boolean")
        drift = self._create_claim_with_variable("wizard-drift", value_type="number")
        unavailable = self._create_claim_with_variable("wizard-unavailable", value_type="string")
        catalog = CatalogResponse.model_validate(
            {
                "claims": [
                    {
                        "id": no_change.external_id,
                        "title": no_change.name,
                        "description": "",
                        "version": "2026-01",
                        "subject_type": "individual",
                        "disclosure": ["predicate"],
                        "value_type": "boolean",
                    },
                    {
                        "id": update.external_id,
                        "title": "Wizard Update Changed",
                        "description": "Changed description",
                        "version": "2026-01",
                        "subject_type": "individual",
                        "disclosure": ["predicate"],
                        "value_type": "boolean",
                    },
                    {
                        "id": drift.external_id,
                        "title": drift.name,
                        "description": "",
                        "version": "2026-02",
                        "subject_type": "individual",
                        "disclosure": ["predicate"],
                        "value_type": "number",
                    },
                ]
            }
        )
        wizard = self.env["spp.notary.catalog.sync.wizard"].create({"provider_id": self.provider.id})

        line_values = wizard._preview_line_values(catalog)
        by_claim = {values["claim_id"]: values for values in line_values}
        summary = wizard._summary_from_lines(line_values)

        self.assertEqual(by_claim[no_change.external_id]["action"], "no_change")
        self.assertEqual(by_claim[update.external_id]["action"], "update")
        self.assertEqual(by_claim[drift.external_id]["action"], "version_drift")
        self.assertEqual(by_claim[drift.external_id]["state_after"], "version_drift")
        self.assertEqual(by_claim[unavailable.external_id]["action"], "unavailable")
        self.assertIn("Update: 1", summary)
        self.assertIn("Version drift: 1", summary)

    def test_catalog_sync_wizard_blocks_accessor_collision(self):
        catalog = CatalogResponse.model_validate(
            {
                "claims": [
                    {
                        "id": "collision-claim",
                        "title": "Collision Claim",
                        "version": "2026-01",
                        "subject_type": "individual",
                        "value_type": "boolean",
                    }
                ]
            }
        )
        variable_name = self.Claim._build_variable_name(self.provider.code, "collision-claim")
        self.env["spp.cel.variable"].create(
            {
                "name": variable_name,
                "cel_accessor": variable_name,
                "source_type": "constant",
                "value_type": "boolean",
                "applies_to": "individual",
            }
        )
        wizard = self.env["spp.notary.catalog.sync.wizard"].create({"provider_id": self.provider.id})

        with patch.object(type(self.provider), "_fetch_notary_catalog", return_value=catalog):
            wizard.action_load_preview()

        self.assertEqual(wizard.line_ids.action, "blocked")
        self.assertTrue(wizard.line_ids.blocking)
        with self.assertRaises(UserError):
            wizard.action_sync_catalog()

    def test_claim_helpers_normalize_values_and_update_existing_variable(self):
        self.assertEqual(self.Claim._build_variable_name("123 Provider", "Claim!!!"), "notary_123_provider_claim")
        self.assertEqual(normalize_notary_value_type("decimal"), "number")
        self.assertEqual(normalize_notary_value_type("unsupported"), "string")
        self.assertEqual(data_value_type_for_cel("date"), "string")
        self.assertEqual(data_value_type_for_cel("list"), "json")

        claims = self.Claim.create(
            [
                {
                    "provider_id": self.provider.id,
                    "external_id": "helper-batch-a",
                    "claim_version": "2026-01",
                    "name": "helper-batch-a",
                    "subject_type": "individual",
                    "value_type": "boolean",
                    "state": "active",
                },
                {
                    "provider_id": self.provider.id,
                    "external_id": "helper-batch-b",
                    "claim_version": "2026-01",
                    "name": "helper-batch-b",
                    "subject_type": "individual",
                    "value_type": "string",
                    "state": "active",
                },
            ]
        )
        claim = self._create_claim_with_variable("helper-variable", value_type="money")
        claim.write({"state": "deprecated", "active": False, "subject_type": "group"})

        self.assertEqual(len(claims.mapped("variable_id")), 2)
        self.assertFalse(claim.variable_id.active)
        self.assertEqual(claim.variable_id.state, "inactive")
        self.assertEqual(claim.variable_id.applies_to, "group")
        self.assertEqual(claim.variable_id.value_type, "money")

    def test_active_expression_blocks_notary_accessor_rename(self):
        claim = self._create_claim_with_variable("rename-safe", value_type="boolean")
        expression = self.env["spp.cel.expression"].create(
            {
                "name": f"Rename Safety {self._test_id}",
                "code": f"rename_safety_{self._test_id}",
                "expression_type": "filter",
                "context_type": "individual",
                "cel_expression": claim.variable_name,
                "state": "active",
            }
        )
        self.assertIn(claim.variable_id, expression.variable_ids)

        with self.assertRaises(UserError):
            claim.write({"external_id": "renamed-claim"})

    def test_real_client_is_created_with_outgoing_log_context(self):
        provider = self.provider.with_context()
        provider.notary_subject_log_secret = "test-secret"

        client = provider._notary_client()

        self.assertTrue(client.log_wrapper)
        self.assertEqual(client.config.origin_model, "spp.data.provider")
        self.assertEqual(client.config.origin_record_id, provider.id)
        self.assertEqual(client.config.subject_log_secret, "test-secret")

    def test_real_client_writes_sanitized_outgoing_log(self):
        service_code = f"audit_notary_{self._test_id}"

        def handler(_request):
            return httpx.Response(
                200,
                json={
                    "evaluation_id": "eval-audit",
                    "results": [
                        {
                            "claim_id": "audit-claim",
                            "value": "raw-sensitive-value",
                            "satisfied": True,
                        }
                    ],
                },
            )

        client = NotaryClient(
            {
                "base_url": "https://notary.example",
                "auth_type": "none",
                "default_purpose_url": "https://openspp.example/purpose/default",
                "subject_log_secret": "audit-secret",
                "code": service_code,
                "id": self.provider.id,
                "origin_model": "spp.data.provider",
            },
            env=self.env,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            sleep=lambda _seconds: None,
        )

        client.evaluate(
            subject_id=f"NID-A-{self._test_id}",
            subject_id_type=self.id_type.uri,
            claim_refs=["audit-claim"],
        )

        log = self.env["spp.api.outgoing.log"].sudo().search([("service_code", "=", service_code)], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.endpoint, "/v1/evaluations")
        self.assertEqual(log.status, "success")
        self.assertEqual(log.origin_model, "spp.data.provider")
        self.assertEqual(log.origin_record_id, self.provider.id)
        self.assertEqual(log.request_summary["claim_ids"], ["audit-claim"])
        self.assertIn("subject_hash", log.request_summary)
        self.assertNotIn(f"NID-A-{self._test_id}", str(log.request_summary))
        self.assertNotIn("raw-sensitive-value", str(log.request_summary))

    def test_missing_purpose_fails_before_client_call(self):
        provider = self.Provider.create(
            {
                "name": "No Purpose Notary",
                "code": f"no_purpose_notary_{self._test_id}",
                "provider_kind": "notary",
                "base_url": "https://notary.example",
                "auth_type": "none",
                "notary_subject_id_type_id": self.id_type.id,
            }
        )
        claim = self.Claim.create(
            {
                "provider_id": provider.id,
                "external_id": "needs-purpose",
                "claim_version": "2026-01",
                "name": "needs-purpose",
                "subject_type": "individual",
                "value_type": "boolean",
                "state": "active",
            }
        )

        with patch.object(type(provider), "_notary_client") as mocked_client:
            with self.assertRaises(UserError):
                provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        mocked_client.assert_not_called()

    def test_notary_manager_can_refresh_and_write_cache_without_admin(self):
        group_user = self.env.ref("base.group_user")
        group_manager = self.env.ref("spp_notary_evidence.group_notary_evidence_manager")
        user_manager = self.env["res.users"].create(
            {
                "name": f"Notary Exec Manager {self._test_id}",
                "login": f"notary_exec_manager_{self._test_id}",
                "group_ids": [Command.link(group_user.id), Command.link(group_manager.id)],
                "role_line_ids": [],
            }
        )
        claim = self._create_claim_with_variable("manager-refresh", value_type="string")
        response = SimpleNamespace(
            evaluation_id="eval-manager",
            results=[
                SimpleNamespace(
                    claim_id="manager-refresh",
                    value="manager-ok",
                    satisfied=True,
                    expires_at=None,
                )
            ],
        )
        provider = self.provider.with_user(user_manager)

        with patch.object(type(provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.return_value = response
            value = provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "manager-ok")
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", claim.variable_id.name),
                ("subject_id", "=", self.partner_a.id),
                ("provider", "=", self.provider.code),
            ],
            limit=1,
        )
        self.assertTrue(cached)

    def test_odoo_administrator_gets_notary_manager_by_default(self):
        group_system = self.env.ref("base.group_system")
        group_manager = self.env.ref("spp_notary_evidence.group_notary_evidence_manager")
        admin = self.env.ref("base.user_admin")

        self.assertIn(group_manager, group_system.implied_ids)
        self.assertTrue(admin.has_group("spp_notary_evidence.group_notary_evidence_manager"))

    def test_claim_acl_viewer_read_only_manager_create(self):
        group_user = self.env.ref("base.group_user")
        group_viewer = self.env.ref("spp_notary_evidence.group_notary_evidence_viewer")
        group_manager = self.env.ref("spp_notary_evidence.group_notary_evidence_manager")
        user_viewer = self.env["res.users"].create(
            {
                "name": f"Notary Viewer {self._test_id}",
                "login": f"notary_viewer_{self._test_id}",
                "group_ids": [Command.link(group_user.id), Command.link(group_viewer.id)],
                "role_line_ids": [],
            }
        )
        user_manager = self.env["res.users"].create(
            {
                "name": f"Notary Manager {self._test_id}",
                "login": f"notary_manager_{self._test_id}",
                "group_ids": [Command.link(group_user.id), Command.link(group_manager.id)],
                "role_line_ids": [],
            }
        )
        claim = self._create_claim_with_variable("acl-read", value_type="boolean")
        log = (
            self.env["spp.api.outgoing.log"]
            .sudo()
            .log_call(
                url="https://notary.example/v1/evaluations",
                endpoint="/v1/evaluations",
                http_method="POST",
                service_name="Notary Client",
                service_code=self.provider.code,
                status="success",
            )
        )

        claim.with_user(user_viewer).read(["name"])
        log.with_user(user_viewer).read(["display_name", "service_name"])
        with self.assertRaises(AccessError):
            self.Claim.with_user(user_viewer).create(
                {
                    "provider_id": self.provider.id,
                    "external_id": "viewer-created",
                    "claim_version": "2026-01",
                    "name": "viewer-created",
                    "subject_type": "individual",
                    "value_type": "boolean",
                }
            )
        created = self.Claim.with_user(user_manager).create(
            {
                "provider_id": self.provider.id,
                "external_id": "manager-created",
                "claim_version": "2026-01",
                "name": "manager-created",
                "subject_type": "individual",
                "value_type": "boolean",
            }
        )
        self.assertTrue(created.exists())

    def _create_claim_with_variable(self, claim_id, value_type):
        return self.Claim.create(
            {
                "provider_id": self.provider.id,
                "external_id": claim_id,
                "claim_version": "2026-01",
                "pinned_version": "2026-01",
                "name": claim_id,
                "subject_type": "individual",
                "value_type": value_type,
                "state": "active",
            }
        )
