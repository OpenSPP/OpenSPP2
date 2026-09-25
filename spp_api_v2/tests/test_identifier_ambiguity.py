# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Identifiers the API cannot resolve to one registrant (#554 item I).

The registry allows two registrants to share an ID type and value (the
ID-document deduplication manager exists to find them), but every API
lookup addresses one record. So the API:

- refuses to create an identifier already live on another registrant (409);
- refuses to guess when a lookup matches several registrants: 409, or,
  for a client that needs consent and lacks it for any of them, the same
  403 as "not found";
- ignores soft-removed (``invalid``) IDs when resolving.
"""

import json

from ..schemas.base import HumanName, Identifier
from ..schemas.individual import Individual
from ..services import registrant_resolver
from ..services.group_service import GroupService
from ..services.individual_service import IndividualService
from .common import ApiV2HttpTestCase, ApiV2TestCase

NATIONAL_ID = "urn:openspp:vocab:id-type#test_national_id"
HOUSEHOLD_ID = "urn:openspp:vocab:id-type#test_household_id"


class TestRegistrantResolver(ApiV2TestCase):
    """Shared resolution of an identifier to one registrant"""

    def setUp(self):
        super().setUp()
        self.individual_service = IndividualService(self.env)
        self.group_service = GroupService(self.env)

    def _invalidate_id(self, partner, value):
        partner.reg_ids.filtered(lambda r: r.value == value).write({"status": "invalid"})

    def test_single_match(self):
        partner = self.create_test_individual(identifier_value="RES-ONE")

        found = registrant_resolver.resolve_registrant(self.env, NATIONAL_ID, "RES-ONE")

        self.assertEqual(found, partner)

    def test_shared_live_identifier_is_ambiguous(self):
        first = self.create_test_individual(name="First", identifier_value="RES-DUP")
        second = self.create_test_individual(name="Second", identifier_value="RES-DUP")

        with self.assertRaises(registrant_resolver.AmbiguousIdentifierError) as ctx:
            registrant_resolver.resolve_registrant(self.env, NATIONAL_ID, "RES-DUP")

        self.assertEqual(ctx.exception.partners, first | second)

    def test_invalid_id_does_not_resolve(self):
        partner = self.create_test_individual(identifier_value="RES-INVALID")
        self._invalidate_id(partner, "RES-INVALID")

        self.assertFalse(registrant_resolver.resolve_registrant(self.env, NATIONAL_ID, "RES-INVALID"))
        self.assertFalse(self.individual_service.find_by_identifier(NATIONAL_ID, "RES-INVALID"))

    def test_invalid_id_does_not_make_a_live_one_ambiguous(self):
        removed = self.create_test_individual(name="Removed", identifier_value="RES-MIXED")
        live = self.create_test_individual(name="Live", identifier_value="RES-MIXED")
        self._invalidate_id(removed, "RES-MIXED")

        self.assertEqual(self.individual_service.find_by_identifier(NATIONAL_ID, "RES-MIXED"), live)

    def test_individual_lookup_raises_on_ambiguity(self):
        self.create_test_individual(name="First", identifier_value="RES-IND-DUP")
        self.create_test_individual(name="Second", identifier_value="RES-IND-DUP")

        with self.assertRaises(registrant_resolver.AmbiguousIdentifierError):
            self.individual_service.find_by_identifier(NATIONAL_ID, "RES-IND-DUP")

    def test_group_lookup_raises_on_ambiguity(self):
        self.create_test_group(name="First", identifier_value="RES-HH-DUP")
        self.create_test_group(name="Second", identifier_value="RES-HH-DUP")

        with self.assertRaises(registrant_resolver.AmbiguousIdentifierError):
            self.group_service.find_by_identifier(HOUSEHOLD_ID, "RES-HH-DUP")

    def _individual_schema(self, value, given="Copy"):
        return Individual(
            identifier=[Identifier(system=NATIONAL_ID, value=value)],
            name=HumanName(given=given, family="Test"),
        )

    def test_create_individual_with_identifier_in_use_is_refused(self):
        self.create_test_individual(identifier_value="RES-TAKEN")

        with self.assertRaises(registrant_resolver.IdentifierInUseError):
            self.individual_service.create(self._individual_schema("RES-TAKEN"), source="test", api_authorized=True)

        self.assertEqual(self.env["spp.registry.id"].search_count([("value", "=", "RES-TAKEN")]), 1)

    def test_create_individual_may_reuse_an_invalid_identifier(self):
        removed = self.create_test_individual(identifier_value="RES-FREED")
        self._invalidate_id(removed, "RES-FREED")

        partner = self.individual_service.create(
            self._individual_schema("RES-FREED"), source="test", api_authorized=True
        )

        self.assertEqual(self.individual_service.find_by_identifier(NATIONAL_ID, "RES-FREED"), partner)


class TestIdentifierAmbiguityAPI(ApiV2HttpTestCase):
    """HTTP contract, for a client with a legal basis (no consent needed)"""

    SCOPES = [
        {"resource": "individual", "action": "read"},
        {"resource": "individual", "action": "create"},
        {"resource": "individual", "action": "update"},
        {"resource": "group", "action": "read"},
        {"resource": "group", "action": "create"},
        {"resource": "group", "action": "update"},
    ]

    def setUp(self):
        super().setUp()
        self.first = self.create_test_individual(name="Original", identifier_value="AMB-DUP")
        self.second = self.create_test_individual(name="Copy", identifier_value="AMB-DUP")
        self.group = self.create_test_group(name="Amb Household", identifier_value="AMB-HH")
        self.client = self.create_api_client(
            name="Legal Basis Client",
            scopes=self.SCOPES,
            require_consent=False,
            legal_basis="public_task",
        )
        self.token = self.generate_jwt_token(self.client)

    def _headers(self, token=None):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {token or self.token}"}

    def _get(self, path, token=None):
        return self.url_open(path, headers=self._headers(token))

    def _post(self, path, payload, token=None):
        return self.url_open(path, data=json.dumps(payload), headers=self._headers(token))

    def test_post_individual_with_identifier_in_use_is_409(self):
        response = self._post(
            "/api/v2/spp/Individual",
            {
                "type": "Individual",
                "identifier": [{"system": NATIONAL_ID, "value": "AMB-TAKEN"}],
                "name": {"given": "Original"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)

        response = self._post(
            "/api/v2/spp/Individual",
            {
                "type": "Individual",
                "identifier": [{"system": NATIONAL_ID, "value": "AMB-TAKEN"}],
                "name": {"given": "Copy"},
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.env.invalidate_all()
        self.assertEqual(self.env["spp.registry.id"].search_count([("value", "=", "AMB-TAKEN")]), 1)

    def test_post_group_with_identifier_in_use_is_409(self):
        response = self._post(
            "/api/v2/spp/Group",
            {
                "type": "Group",
                "identifier": [{"system": HOUSEHOLD_ID, "value": "AMB-HH"}],
                "name": "Copy Household",
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.env.invalidate_all()
        self.assertEqual(self.env["spp.registry.id"].search_count([("value", "=", "AMB-HH")]), 1)

    def test_get_ambiguous_individual_is_409(self):
        response = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|AMB-DUP")

        self.assertEqual(response.status_code, 409, response.text)

    def test_patch_ambiguous_individual_is_409_and_changes_nothing(self):
        """The reported symptom: PATCH deactivated one of the two, arbitrarily"""
        self.env.cr.flush()
        response = self.url_patch(
            "/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|AMB-DUP",
            data=json.dumps({"active": False}),
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.env.invalidate_all()
        self.assertTrue(self.first.active)
        self.assertTrue(self.second.active)

    def test_search_by_ambiguous_identifier_lists_both(self):
        """A search is not a lookup: it lists every match"""
        response = self._get("/api/v2/spp/Individual?identifier=urn:openspp:vocab:id-type%23test_national_id%7CAMB-DUP")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["meta"]["total"], 2)

    def test_invalid_identifier_is_not_found(self):
        partner = self.create_test_individual(identifier_value="AMB-REMOVED")
        partner.reg_ids.write({"status": "invalid"})

        response = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|AMB-REMOVED")

        self.assertEqual(response.status_code, 404, response.text)

    def test_add_ambiguous_member_is_409(self):
        response = self._post(
            "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|AMB-HH/$add-member",
            {"entity": {"reference": f"Individual/{NATIONAL_ID}|AMB-DUP"}},
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.env.invalidate_all()
        self.assertFalse(self.group.group_membership_ids)

    def test_get_ambiguous_group_is_409(self):
        self.create_test_group(name="Amb Copy Household", identifier_value="AMB-HH")

        response = self._get("/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|AMB-HH")

        self.assertEqual(response.status_code, 409, response.text)

    def test_bulk_export_reports_ambiguous_identifier(self):
        response = self._post(
            "/api/v2/spp/$bulk/export",
            {"type": "Individual", "identifiers": [f"{NATIONAL_ID}|AMB-DUP"]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["items"][0]
        self.assertEqual(item["status"], "error")
        self.assertIn("more than one", item["error"])

    def test_batch_read_of_ambiguous_identifier_is_409(self):
        response = self._post(
            "/api/v2/spp/$batch",
            {
                "resourceType": "Bundle",
                "type": "batch",
                "entry": [{"request": {"method": "GET", "url": f"Individual/{NATIONAL_ID}|AMB-DUP"}}],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["entry"][0]["response"]["status"], "409 Conflict")

    # --- clients that need consent ----------------------------------------

    def _consent_client_token(self, consented):
        client = self.create_api_client(name="Consent Client", scopes=self.SCOPES)
        for registrant in consented:
            self.create_consent(
                registrant=registrant,
                grantee_partner=client.partner_id,
                resource_type="all",
                field_access="all",
            )
        return self.generate_jwt_token(client)

    def test_consent_client_without_consent_for_every_match_gets_403(self):
        """Ambiguity is not revealed unless the client may see every match"""
        token = self._consent_client_token(consented=[self.first])

        response = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|AMB-DUP", token)

        self.assertEqual(response.status_code, 403, response.text)

    def test_consent_client_with_consent_for_every_match_gets_409(self):
        token = self._consent_client_token(consented=[self.first, self.second])

        response = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|AMB-DUP", token)

        self.assertEqual(response.status_code, 409, response.text)
