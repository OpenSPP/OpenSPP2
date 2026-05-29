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
from odoo.addons.spp_notary_client.services.exceptions import NotaryTransportError


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
        self.assertEqual(claim.value_type, "boolean")
        self.assertTrue(claim.variable_id)
        self.assertEqual(claim.variable_id.source_type, "external")
        self.assertEqual(claim.variable_id.external_provider_id, self.provider)
        self.assertEqual(claim.variable_id.notary_claim_id, claim)

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
        self.assertEqual(kwargs["subject_id"], f"NID-A-{self._test_id}")
        self.assertEqual(kwargs["subject_id_type"], self.id_type.uri)
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

    def test_missing_subject_id_returns_no_value(self):
        claim = self._create_claim_with_variable("missing-subject-id", value_type="boolean")
        partner = self.env["res.partner"].create(
            {
                "name": f"No ID {self._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )

        with patch.object(type(self.provider), "_notary_client") as mocked_client:
            value = self.provider._refresh_external_value(claim.variable_id, partner.id, "current")

        self.assertIsNone(value)
        mocked_client.assert_not_called()

    def test_stale_if_available_policy_returns_expired_provider_scoped_value(self):
        claim = self._create_claim_with_variable("stale-claim", value_type="string")
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
                    "expires_at": fields.Datetime.now() - timedelta(hours=1),
                }
            ]
        )
        provider = self.provider.with_context(
            cel_cfg={"notary_purpose": "https://openspp.example/purpose/evaluation"}
        )
        provider.notary_unavailable_policy = "stale_if_available"

        with patch.object(type(provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
            )
            value = provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertEqual(value, "cached-stale")

    def test_stale_if_available_does_not_cross_provider_boundary(self):
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
                    "expires_at": fields.Datetime.now() - timedelta(hours=1),
                }
            ]
        )
        provider = self.provider.with_context(
            cel_cfg={"notary_purpose": "https://openspp.example/purpose/evaluation"}
        )
        provider.notary_unavailable_policy = "stale_if_available"

        with patch.object(type(provider), "_notary_client") as mocked_client:
            mocked_client.return_value.evaluate.side_effect = NotaryTransportError(
                code="source.unavailable",
                status_code=503,
            )
            value = provider._refresh_external_value(claim.variable_id, self.partner_a.id, "current")

        self.assertIsNone(value)

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
        self.assertEqual(log.endpoint, "/claims/evaluate")
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

        claim.with_user(user_viewer).read(["name"])
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
                "name": claim_id,
                "subject_type": "individual",
                "value_type": value_type,
                "state": "active",
            }
        )
