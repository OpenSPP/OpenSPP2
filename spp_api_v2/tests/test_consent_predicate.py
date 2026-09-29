# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""One rule decides whether a client is subject to consent: its legal basis.

A client has two consent settings, edited independently on its form:
``legal_basis`` and ``is_require_consent``. Consent filtering
(``ConsentService.filter_response``) keys off the legal basis. The
"not found" answer must follow the same rule, or the status code tells
an unknown registrant apart from one the client may not read.
"""

import json

from ..services.auth_service import AuthenticatedClient
from ..services.consent_service import NON_CONSENT_BASES, ConsentService
from .common import ApiV2HttpTestCase, ApiV2TestCase

NATIONAL_ID = "urn:openspp:vocab:id-type%23test_national_id"
HOUSEHOLD_ID = "urn:openspp:vocab:id-type%23test_household_id"

SCOPES = [
    {"resource": "individual", "action": "read"},
    {"resource": "individual", "action": "update"},
    {"resource": "group", "action": "read"},
    {"resource": "group", "action": "update"},
]


class TestConsentPredicate(ApiV2HttpTestCase):
    def setUp(self):
        super().setUp()
        self.person = self.create_test_individual(name="Predicate Person", identifier_value="PRED-IND")
        self.household = self.create_test_group(name="Predicate Household", identifier_value="PRED-HH")

    def _token(self, **kwargs):
        client = self.create_api_client(name="Predicate Client", scopes=SCOPES, **kwargs)
        return self.generate_jwt_token(client)

    def _consent_basis_token(self):
        """Consent is its legal basis, but the "require consent" box is unticked"""
        return self._token(require_consent=False, legal_basis="consent")

    def _public_task_token(self):
        """A legal basis that needs no consent, with the "require consent" box ticked"""
        return self._token(require_consent=True, legal_basis="public_task")

    def _get(self, path, token):
        return self.url_open(path, headers={"Authorization": f"Bearer {token}"})

    def _post(self, path, payload, token):
        return self.url_open(
            path,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )

    def _assert_same_answer(self, unknown, existing, status):
        self.assertEqual(unknown.status_code, status, unknown.text)
        self.assertEqual(existing.status_code, status, existing.text)

    # --- consent basis, box unticked: unknown and unconsented look the same

    def test_individual_read(self):
        token = self._consent_basis_token()
        self._assert_same_answer(
            self._get(f"/api/v2/spp/Individual/{NATIONAL_ID}|PRED-NONE", token),
            self._get(f"/api/v2/spp/Individual/{NATIONAL_ID}|PRED-IND", token),
            403,
        )

    def test_group_read(self):
        token = self._consent_basis_token()
        self._assert_same_answer(
            self._get(f"/api/v2/spp/Group/{HOUSEHOLD_ID}|PRED-NONE", token),
            self._get(f"/api/v2/spp/Group/{HOUSEHOLD_ID}|PRED-HH", token),
            403,
        )

    def test_individual_groups(self):
        token = self._consent_basis_token()
        self._assert_same_answer(
            self._get(f"/api/v2/spp/Individual/{NATIONAL_ID}|PRED-NONE/groups", token),
            self._get(f"/api/v2/spp/Individual/{NATIONAL_ID}|PRED-IND/groups", token),
            403,
        )

    def test_group_membership_history(self):
        token = self._consent_basis_token()
        self._assert_same_answer(
            self._get(f"/api/v2/spp/Group/{HOUSEHOLD_ID}|PRED-NONE/membership-history", token),
            self._get(f"/api/v2/spp/Group/{HOUSEHOLD_ID}|PRED-HH/membership-history", token),
            403,
        )

    def test_bulk_export(self):
        token = self._consent_basis_token()
        response = self._post(
            "/api/v2/spp/$bulk/export",
            {
                "type": "Individual",
                "identifiers": [
                    "urn:openspp:vocab:id-type#test_national_id|PRED-NONE",
                    "urn:openspp:vocab:id-type#test_national_id|PRED-IND",
                ],
            },
            token,
        )

        self.assertEqual(response.status_code, 200, response.text)
        statuses = [item["status"] for item in response.json()["items"]]
        self.assertEqual(statuses, ["access_denied", "access_denied"])

    # --- legal basis, box ticked: reads without consent, so unknown is 404

    def test_legal_basis_client_reads_without_consent(self):
        token = self._public_task_token()

        self.assertEqual(self._get(f"/api/v2/spp/Individual/{NATIONAL_ID}|PRED-IND", token).status_code, 200)
        self.assertEqual(self._get(f"/api/v2/spp/Individual/{NATIONAL_ID}|PRED-NONE", token).status_code, 404)

    def test_legal_basis_client_reads_group_history_without_consent(self):
        token = self._public_task_token()

        existing = self._get(f"/api/v2/spp/Group/{HOUSEHOLD_ID}|PRED-HH/membership-history", token)
        unknown = self._get(f"/api/v2/spp/Group/{HOUSEHOLD_ID}|PRED-NONE/membership-history", token)

        self.assertEqual(existing.status_code, 200, existing.text)
        self.assertEqual(unknown.status_code, 404, unknown.text)


class TestOneListOfLegalBases(ApiV2TestCase):
    """The consent checks read one list of the legal bases that need no consent"""

    def test_bypass_and_consent_filtering_agree_for_every_legal_basis(self):
        client = self.create_api_client(name="Basis Client")
        for basis, _label in client._fields["legal_basis"].selection:
            with self.subTest(legal_basis=basis):
                client.legal_basis = basis
                authenticated = AuthenticatedClient(record=client, auth_type="oauth2")

                self.assertEqual(authenticated.has_legal_basis_bypass(), basis in NON_CONSENT_BASES)
                self.assertEqual(ConsentService.is_consent_filtered(client), basis not in NON_CONSENT_BASES)
