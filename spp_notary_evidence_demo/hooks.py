# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Seed the Registry Notary lab demo configuration."""

import logging
import os

from odoo import Command

_logger = logging.getLogger(__name__)

PURPOSE_URL = "https://demo.example.gov/purpose/decentralized-evidence-demo"
ID_TYPE_NAMESPACE = "urn:openspp:vocab:id-type"

PROVIDERS = [
    {
        "code": "registry_lab_civil_notary",
        "name": "Registry Lab Civil Notary",
        "base_url_param": "spp_notary_evidence_demo.civil_notary_url",
        "base_url_env": "REGISTRY_LAB_CIVIL_NOTARY_URL",
        "base_url_default": "http://host.docker.internal:4321",
        "auth_type": "api_key",
        "secret_param": "spp_notary_evidence_demo.civil_api_key",
        "secret_env": "CIVIL_EVIDENCE_CLIENT_TOKEN",
        "secret_field": "api_key",
        "claims": [
            {
                "external_id": "person-is-alive",
                "name": "Person is alive",
                "claim_version": "2026-05",
                "value_type": "boolean",
                "default_disclosure": "predicate",
                "description": "Civil registry predicate proving the person is not recorded as deceased.",
            },
            {
                "external_id": "age-band",
                "name": "Age band",
                "claim_version": "2026-05",
                "value_type": "string",
                "default_disclosure": "value",
                "description": "Civil registry age-band value used by benefit-screening demos.",
            },
        ],
    },
    {
        "code": "registry_lab_shared_eligibility_notary",
        "name": "Registry Lab Shared Eligibility Notary",
        "base_url_param": "spp_notary_evidence_demo.shared_notary_url",
        "base_url_env": "REGISTRY_LAB_SHARED_NOTARY_URL",
        "base_url_default": "http://host.docker.internal:4323",
        "auth_type": "bearer",
        "secret_param": "spp_notary_evidence_demo.shared_bearer_token",
        "secret_env": "SHARED_EVIDENCE_CLIENT_BEARER",
        "secret_field": "notary_bearer_token",
        "claims": [
            {
                "external_id": "eligible-for-combined-support",
                "name": "Eligible for combined support",
                "claim_version": "2026-05",
                "value_type": "boolean",
                "default_disclosure": "predicate",
                "description": "Cross-authority predicate combining civil, social protection, and health evidence.",
            },
            {
                "external_id": "health-service-available",
                "name": "Health service available",
                "claim_version": "2026-05",
                "value_type": "boolean",
                "default_disclosure": "predicate",
                "description": "Health registry predicate used by the shared eligibility Notary.",
            },
        ],
    },
]

PERSONAS = [
    {
        "name": "Amina Diallo",
        "national_id": "NID-1001",
        "birthdate": "2020-04-12",
        "note": "Expected positive path in registry-lab civil and shared Notary demos.",
    },
    {
        "name": "Ben Mensah",
        "national_id": "NID-1002",
        "birthdate": "2017-11-02",
        "note": "Civil record exists, but shared eligibility may fail depending on social/health facts.",
    },
    {
        "name": "Cara Okafor",
        "national_id": "NID-1003",
        "birthdate": "1957-02-14",
        "note": "Civil demo record is marked deceased in registry-lab.",
    },
]

PROGRAMS = [
    {
        "name": "Registry Lab Living Person Grant",
        "description": "Demo program using the civil Notary person-is-alive predicate.",
        "expression": "notary_registry_lab_civil_notary_person_is_alive == true",
    },
    {
        "name": "Registry Lab Combined Support",
        "description": "Demo program using the shared Notary combined-support predicate.",
        "expression": "notary_registry_lab_shared_eligibility_notary_eligible_for_combined_support == true",
    },
    {
        "name": "Registry Lab Health Access Support",
        "description": "Demo program using the shared Notary health-service-available predicate.",
        "expression": "notary_registry_lab_shared_eligibility_notary_health_service_available == true",
    },
]


def post_init_hook(env):
    """Create idempotent Registry Notary lab demo data."""
    id_type = _ensure_national_id_type(env)
    _ensure_providers_and_claims(env, id_type)
    _ensure_personas(env, id_type)
    _ensure_programs(env)


def _config_or_env(env, param_key, env_key, default=None):
    Config = env["ir.config_parameter"].sudo()
    configured = Config.get_param(param_key)
    if configured:
        return configured
    env_value = os.environ.get(env_key)
    if env_value:
        Config.set_param(param_key, env_value)
        return env_value
    if default is not None:
        Config.set_param(param_key, default)
    return default


def _ensure_national_id_type(env):
    Vocabulary = env["spp.vocabulary"].sudo()
    Code = env["spp.vocabulary.code"].sudo().with_context(_test_bypass_system_protection=True)
    vocabulary = Vocabulary.search([("namespace_uri", "=", ID_TYPE_NAMESPACE)], limit=1)
    if not vocabulary:
        vocabulary = Vocabulary.create(
            {
                "name": "Identifier Type",
                "namespace_uri": ID_TYPE_NAMESPACE,
                "domain": "core",
            }
        )
    code = Code.search([("vocabulary_id", "=", vocabulary.id), ("code", "=", "national_id")], limit=1)
    if code:
        return code
    return Code.create(
        {
            "vocabulary_id": vocabulary.id,
            "code": "national_id",
            "display": "National ID",
            "target_type": "both",
            "is_local": True,
        }
    )


def _ensure_providers_and_claims(env, id_type):
    Provider = env["spp.data.provider"].sudo()
    Claim = env["spp.notary.claim"].sudo()
    for provider_def in PROVIDERS:
        secret = _config_or_env(env, provider_def["secret_param"], provider_def["secret_env"])
        values = {
            "name": provider_def["name"],
            "code": provider_def["code"],
            "provider_kind": "notary",
            "base_url": _config_or_env(
                env,
                provider_def["base_url_param"],
                provider_def["base_url_env"],
                provider_def["base_url_default"],
            ),
            "auth_type": provider_def["auth_type"],
            "notary_default_purpose_url": PURPOSE_URL,
            "notary_unavailable_policy": "raise",
            "notary_subject_id_type_id": id_type.id,
            "notary_subject_log_secret": _config_or_env(
                env,
                "spp_notary_evidence_demo.subject_log_secret",
                "REGISTRY_NOTARY_AUDIT_HASH_SECRET",
                "openspp-notary-demo-subject-log-secret",
            ),
            "notary_min_cache_ttl_seconds": 300,
            "notary_default_ttl_seconds": 3600,
            "timeout_ms": 10000,
            "max_batch_size": 20,
        }
        if secret:
            values[provider_def["secret_field"]] = secret

        provider = Provider.search([("code", "=", provider_def["code"])], limit=1)
        if provider:
            provider.write(values)
        else:
            provider = Provider.create(values)

        for claim_def in provider_def["claims"]:
            claim_values = {
                "provider_id": provider.id,
                "external_id": claim_def["external_id"],
                "name": claim_def["name"],
                "description": claim_def["description"],
                "claim_version": claim_def["claim_version"],
                "pinned_version": claim_def["claim_version"],
                "subject_type": "individual",
                "value_type": claim_def["value_type"],
                "default_disclosure": claim_def["default_disclosure"],
                "state": "active",
                "active": True,
            }
            claim = Claim.search(
                [
                    ("provider_id", "=", provider.id),
                    ("external_id", "=", claim_def["external_id"]),
                ],
                limit=1,
            )
            if claim:
                claim.write(claim_values)
            else:
                Claim.create(claim_values)


def _ensure_personas(env, id_type):
    Partner = env["res.partner"].sudo()
    RegistryId = env["spp.registry.id"].sudo()
    for persona in PERSONAS:
        reg_id = RegistryId.search(
            [
                ("id_type_id", "=", id_type.id),
                ("value", "=", persona["national_id"]),
            ],
            limit=1,
        )
        if reg_id:
            partner = reg_id.partner_id
            partner.write(
                {
                    "name": persona["name"],
                    "birthdate": persona["birthdate"],
                    "is_registrant": True,
                    "is_group": False,
                    "comment": persona["note"],
                }
            )
            continue
        partner = Partner.create(
            {
                "name": persona["name"],
                "birthdate": persona["birthdate"],
                "is_registrant": True,
                "is_group": False,
                "comment": persona["note"],
            }
        )
        RegistryId.create(
            {
                "partner_id": partner.id,
                "id_type_id": id_type.id,
                "value": persona["national_id"],
            }
        )


def _ensure_programs(env):
    Program = env["spp.program"].sudo()
    for program_def in PROGRAMS:
        program = Program.search([("name", "=", program_def["name"])], limit=1)
        values = {
            "name": program_def["name"],
            "description": program_def["description"],
            "target_type": "individual",
            "is_one_time_distribution": True,
        }
        if program:
            program.write(values)
        else:
            program = Program.with_context(create_default_managers=True).create(values)
        _ensure_program_eligibility(program, program_def["expression"])


def _ensure_program_eligibility(program, expression):
    if not program.eligibility_manager_ids:
        manager = (
            program.env["spp.program.membership.manager.default"]
            .sudo()
            .create(
                {
                    "name": "Notary Lab Eligibility",
                    "program_id": program.id,
                    "eligibility_mode": "cel",
                    "cel_expression": expression,
                }
            )
        )
        wrapper = (
            program.env["spp.eligibility.manager"]
            .sudo()
            .create(
                {
                    "program_id": program.id,
                    "manager_ref_id": f"spp.program.membership.manager.default,{manager.id}",
                }
            )
        )
        program.write({"eligibility_manager_ids": [Command.link(wrapper.id)]})
        return

    for wrapper in program.eligibility_manager_ids:
        manager = wrapper.manager_ref_id
        if not manager:
            continue
        values = {"name": "Notary Lab Eligibility"}
        if "eligibility_mode" in manager._fields:
            values["eligibility_mode"] = "cel"
        if "cel_expression" in manager._fields:
            values["cel_expression"] = expression
        manager.sudo().write(values)
        return

    _logger.warning("No writable eligibility manager found for Notary demo program %s", program.display_name)
