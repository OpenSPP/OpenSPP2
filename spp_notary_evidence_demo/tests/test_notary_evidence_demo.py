# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the Registry Notary lab demo seed data."""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_notary_client.services.exceptions import NotaryError

from .. import post_init_hook


@tagged("post_install", "-at_install")
class TestNotaryEvidenceDemo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        post_init_hook(cls.env)
        cls.Provider = cls.env["spp.data.provider"]
        cls.Claim = cls.env["spp.notary.claim"]
        cls.Program = cls.env["spp.program"]
        cls.Partner = cls.env["res.partner"]
        cls.RegistryId = cls.env["spp.registry.id"]
        cls.DemoRun = cls.env["spp.notary.demo.run"]

    def test_post_init_hook_is_idempotent(self):
        post_init_hook(self.env)

        self.assertEqual(self.Provider.search_count([("code", "=", "registry_lab_civil_notary")]), 1)
        self.assertEqual(
            self.Provider.search_count([("code", "=", "registry_lab_shared_eligibility_notary")]),
            1,
        )
        self.assertEqual(self.Program.search_count([("name", "=", "Registry Lab Living Person Grant")]), 1)

    def test_seeded_providers_claims_variables_and_personas(self):
        civil_provider = self.Provider.search([("code", "=", "registry_lab_civil_notary")], limit=1)
        shared_provider = self.Provider.search([("code", "=", "registry_lab_shared_eligibility_notary")], limit=1)
        person_alive = self.Claim.search(
            [
                ("provider_id", "=", civil_provider.id),
                ("external_id", "=", "person-is-alive"),
            ],
            limit=1,
        )
        combined_support = self.Claim.search(
            [
                ("provider_id", "=", shared_provider.id),
                ("external_id", "=", "eligible-for-combined-support"),
            ],
            limit=1,
        )

        self.assertTrue(civil_provider)
        self.assertEqual(civil_provider.base_url, "http://host.docker.internal:4321")
        self.assertEqual(civil_provider.auth_type, "api_key")
        self.assertEqual(civil_provider.notary_subject_id_type_id.code, "national_id")
        self.assertTrue(person_alive.variable_id)
        self.assertEqual(person_alive.pinned_version, "2026-05")
        self.assertEqual(person_alive.variable_id.cel_accessor, "notary_registry_lab_civil_notary_person_is_alive")
        self.assertTrue(combined_support.variable_id)
        self.assertEqual(
            combined_support.variable_id.cel_accessor,
            "notary_registry_lab_shared_eligibility_notary_eligible_for_combined_support",
        )
        self.assertTrue(
            self.RegistryId.search(
                [
                    ("id_type_id", "=", civil_provider.notary_subject_id_type_id.id),
                    ("value", "=", "NID-1001"),
                ],
                limit=1,
            )
        )

    def test_seeded_programs_have_notary_cel_eligibility(self):
        expected = {
            "Registry Lab Living Person Grant": "notary_registry_lab_civil_notary_person_is_alive == true",
            "Registry Lab Combined Support": (
                "notary_registry_lab_shared_eligibility_notary_eligible_for_combined_support == true"
            ),
            "Registry Lab Health Access Support": (
                "notary_registry_lab_shared_eligibility_notary_health_service_available == true"
            ),
        }
        for name, expression in expected.items():
            program = self.Program.search([("name", "=", name)], limit=1)
            self.assertTrue(program, name)
            self.assertEqual(program.target_type, "individual")
            self.assertTrue(program.eligibility_manager_ids)
            manager = program.eligibility_manager_ids[0].manager_ref_id
            self.assertEqual(manager.eligibility_mode, "cel")
            self.assertEqual(manager.cel_expression, expression)

    def test_seeded_provider_can_resolve_demo_persona_with_single_fallback(self):
        provider = self.Provider.search([("code", "=", "registry_lab_civil_notary")], limit=1)
        claim = self.Claim.search(
            [
                ("provider_id", "=", provider.id),
                ("external_id", "=", "person-is-alive"),
            ],
            limit=1,
        )
        partner = self.RegistryId.search(
            [
                ("id_type_id", "=", provider.notary_subject_id_type_id.id),
                ("value", "=", "NID-1001"),
            ],
            limit=1,
        ).partner_id

        class Client:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return None

            def batch_evaluate(self, **kwargs):
                raise NotaryError(code="claim.operation_unsupported", status_code=501)

            def evaluate(self, **kwargs):
                class Result:
                    claim_id = "person-is-alive"
                    value = True
                    satisfied = True
                    expires_at = None

                class Response:
                    results = [Result()]

                self.last_evaluate_kwargs = kwargs
                return Response()

        client = Client()
        with patch.object(type(provider), "_notary_client", return_value=client):
            values = provider._compute_external_values(claim.variable_id, [partner.id], "current")

        self.assertEqual(values, {partner.id: True})
        self.assertEqual(client.last_evaluate_kwargs["subject_id"], "NID-1001")
        self.assertEqual(client.last_evaluate_kwargs["subject_id_type"], provider.notary_subject_id_type_id.uri)
        self.assertEqual(client.last_evaluate_kwargs["claim_refs"], [{"id": "person-is-alive", "version": "2026-05"}])

    def test_seeded_program_expression_dispatches_to_notary_variable(self):
        provider = self.Provider.search([("code", "=", "registry_lab_civil_notary")], limit=1)
        partner = self.RegistryId.search(
            [
                ("id_type_id", "=", provider.notary_subject_id_type_id.id),
                ("value", "=", "NID-1001"),
            ],
            limit=1,
        ).partner_id
        program = self.Program.search([("name", "=", "Registry Lab Living Person Grant")], limit=1)
        expression = program.eligibility_manager_ids[0].manager_ref_id.cel_expression

        with patch.object(
            type(provider),
            "_compute_external_values",
            autospec=True,
            return_value={partner.id: True},
        ) as mocked:
            result = self.env["spp.cel.service"].compile_expression(
                expression,
                "registry_individuals",
                base_domain=[("id", "=", partner.id)],
            )

        self.assertTrue(result["valid"], result.get("error"))
        self.assertIn(partner.id, result["ids"])
        mocked.assert_called_once()

    def test_demo_run_records_expected_matrix(self):
        run = self.DemoRun.create({"name": "Test Notary Demo Run"})

        def fake_compile(_service, expression, profile, base_domain=None, **kwargs):
            partner_id = base_domain[0][2]
            national_id = self.RegistryId.search([("partner_id", "=", partner_id)], limit=1).value
            if "person_is_alive" in expression:
                matched = national_id in ("NID-1001", "NID-1002")
            elif "eligible_for_combined_support" in expression:
                matched = national_id == "NID-1001"
            elif "health_service_available" in expression:
                matched = national_id in ("NID-1001", "NID-1003")
            else:
                matched = False
            return {"valid": True, "ids": [partner_id] if matched else []}

        with (
            patch.object(type(run), "_missing_provider_credentials", return_value=None),
            patch.object(
                type(self.env["spp.cel.service"]),
                "compile_expression",
                autospec=True,
                side_effect=fake_compile,
            ),
        ):
            run.action_run_demo()

        self.assertEqual(run.state, "done")
        self.assertEqual(run.pass_count, 9)
        self.assertEqual(run.fail_count, 0)
        self.assertEqual(run.error_count, 0)
        self.assertEqual(run.skipped_count, 0)
        self.assertEqual(len(run.result_ids), 9)
