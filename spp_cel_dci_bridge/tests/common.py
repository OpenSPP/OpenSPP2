"""Shared test fixtures for spp_cel_dci_bridge.

Follows the precedent in spp_dci_client_dr/tests/test_dr_service.py:
patch DCIClient with a MagicMock returning canned DCI search responses.
A full httpx-level mock server is overkill for the bridge's contract,
which is "DRService returns a dict, the bridge maps a field out of it."
"""

from odoo.tests.common import TransactionCase


def make_dr_search_response(has_disability=True, functional_scores=None, source_registry="Test DR"):
    """Build a canned DCI DR search-response envelope."""
    if functional_scores is None:
        functional_scores = {"Vision": 1, "Mobility": 1, "Cognition": 1}
    return {
        "message": {
            "search_response": [
                {
                    "reference_id": "ref-bridge-test",
                    "status": "succ",
                    "data": [
                        {
                            "has_disability": has_disability,
                            "is_pwd": has_disability,
                            "disability_types": ["Vision", "Mobility"],
                            "functional_scores": functional_scores,
                            "assessment_date": "2026-01-15",
                            "source_registry": source_registry,
                        }
                    ],
                }
            ]
        }
    }


def make_dr_empty_response():
    """Canned 'subject not found in DR' envelope."""
    return {"message": {"search_response": []}}


class BridgeTestBase(TransactionCase):
    """Shared scaffolding for bridge tests that exercise the DR handler.

    Builds the minimum graph needed to drive the dispatcher:
        - Vocabulary code for an identifier type
        - res.partner with one spp.registry.id linking the partner to the code
        - spp.dci.data.source of registry_type='DR'
        - spp.data.provider linked to the DCI source
        - spp.cel.variable with source_type='external' and a DCI attribute path
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Partner = cls.env["res.partner"]
        cls.Variable = cls.env["spp.cel.variable"]
        cls.Provider = cls.env["spp.data.provider"]
        cls.DCISource = cls.env["spp.dci.data.source"]
        cls.IdRecord = cls.env["spp.registry.id"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        vocab_model = cls.env["spp.vocabulary"]
        id_type_vocab = vocab_model.search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = vocab_model.create(
                {
                    "name": "ID Type (bridge tests)",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        cls.id_type_uin = cls.VocabularyCode.create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "UIN_BRIDGE_TEST",
                "display": "UIN (bridge tests)",
                "target_type": "individual",
                "is_local": True,
            }
        )

        cls.partner_a = cls.Partner.create(
            {
                "name": "Bridge Partner A",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.IdRecord.create(
            {
                "partner_id": cls.partner_a.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-BRIDGE-A",
            }
        )

        cls.partner_b = cls.Partner.create(
            {
                "name": "Bridge Partner B",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.IdRecord.create(
            {
                "partner_id": cls.partner_b.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-BRIDGE-B",
            }
        )

        # Partner with no identifier — used to test "not found" paths
        cls.partner_no_id = cls.Partner.create(
            {
                "name": "Bridge Partner (no ID)",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.dci_source = cls.DCISource.create(
            {
                "name": "Bridge DR Source",
                "code": "bridge_dr_source",
                "registry_type": "DR",
                "base_url": "https://dr.test.invalid/api/v1",
                "auth_type": "none",
                "our_sender_id": "bridge.test.openspp.example.org",
            }
        )

        cls.provider = cls.Provider.create(
            {
                "name": "Bridge DR Provider",
                "code": "bridge_dr_provider",
                "dci_data_source_id": cls.dci_source.id,
                "default_ttl_seconds": 300,
            }
        )

        cls.variable = cls.Variable.create(
            {
                "name": "has_disability_test",
                "cel_accessor": "has_disability_test",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": cls.provider.id,
                "dci_attribute_path": "has_disability",
                "cache_strategy": "ttl",
                "cache_ttl_seconds": 300,
            }
        )
