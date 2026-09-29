# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Every API path that creates or resolves identifiers handles ambiguity (#554 item I).

Complements test_identifier_ambiguity.py with the paths found in review:
batch/transaction bundles, group create/split, search filters, bulk export,
soft-removed IDs in responses, and individual/group kind filtering.
"""

import json
import logging

from .common import ApiV2HttpTestCase

NATIONAL_ID = "urn:openspp:vocab:id-type#test_national_id"
HOUSEHOLD_ID = "urn:openspp:vocab:id-type#test_household_id"
GROUP_PATH = "/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_household_id|PATH-HH"

SCOPES = [
    {"resource": "individual", "action": "read"},
    {"resource": "individual", "action": "create"},
    {"resource": "individual", "action": "update"},
    {"resource": "group", "action": "read"},
    {"resource": "group", "action": "create"},
    {"resource": "group", "action": "update"},
]


class TestIdentifierAmbiguityPaths(ApiV2HttpTestCase):
    def setUp(self):
        super().setUp()
        self.first = self.create_test_individual(name="Original", identifier_value="PATH-DUP")
        self.second = self.create_test_individual(name="Copy", identifier_value="PATH-DUP")
        self.head = self.create_test_individual(name="Path Head", identifier_value="PATH-HEAD")
        self.mover = self.create_test_individual(name="Path Mover", identifier_value="PATH-MOVER")
        self.group = self.create_test_group(
            name="Path Household",
            identifier_value="PATH-HH",
            members=[(self.head, self.relationship_head), (self.mover, None)],
        )
        self.dup_group_a = self.create_test_group(name="Dup Household A", identifier_value="PATH-HH-DUP")
        self.dup_group_b = self.create_test_group(name="Dup Household B", identifier_value="PATH-HH-DUP")
        self.client = self.create_api_client(
            name="Legal Basis Client",
            scopes=SCOPES,
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

    def _count_ids(self, value):
        self.env.invalidate_all()
        return self.env["spp.registry.id"].search_count([("value", "=", value)])

    def _consent_client_token(self, consented=(), **kwargs):
        client = self.create_api_client(name="Consent Client", scopes=SCOPES, **kwargs)
        for registrant in consented:
            self.create_consent(
                registrant=registrant,
                grantee_partner=client.partner_id,
                resource_type="all",
                field_access="all",
            )
        return self.generate_jwt_token(client)

    # --- creates -----------------------------------------------------------

    def test_http_post_group_with_ambiguous_member_is_409_and_creates_nothing(self):
        response = self._post(
            "/api/v2/spp/Group",
            {
                "type": "Group",
                "identifier": [{"system": HOUSEHOLD_ID, "value": "PATH-NEW-HH"}],
                "name": "New Household",
                "member": [{"entity": {"reference": f"Individual/{NATIONAL_ID}|PATH-DUP"}}],
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self._count_ids("PATH-NEW-HH"), 0)

    def test_batch_post_group_with_ambiguous_member_creates_nothing(self):
        """The batch entry must not leave the group behind while reporting 409"""
        response = self._post(
            "/api/v2/spp/$batch",
            {
                "resourceType": "Bundle",
                "type": "batch",
                "entry": [
                    {
                        "request": {"method": "POST", "url": "Group"},
                        "resource": {
                            "type": "Group",
                            "identifier": [{"system": HOUSEHOLD_ID, "value": "PATH-BATCH-HH"}],
                            "name": "Batch Household",
                            "member": [{"entity": {"reference": f"Individual/{NATIONAL_ID}|PATH-DUP"}}],
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["entry"][0]["response"]["status"], "409 Conflict")
        self.assertEqual(self._count_ids("PATH-BATCH-HH"), 0)

    def test_batch_post_individual_with_identifier_in_use_is_409(self):
        response = self._post(
            "/api/v2/spp/$batch",
            {
                "resourceType": "Bundle",
                "type": "batch",
                "entry": [
                    {
                        "request": {"method": "POST", "url": "Individual"},
                        "resource": {
                            "type": "Individual",
                            "identifier": [{"system": NATIONAL_ID, "value": "PATH-HEAD"}],
                            "name": {"given": "Clash"},
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["entry"][0]["response"]["status"], "409 Conflict")
        self.assertEqual(self._count_ids("PATH-HEAD"), 1)

    def _logged_text(self, records):
        formatter = logging.Formatter("%(message)s")
        return "\n".join(formatter.format(record) for record in records)

    def test_bundles_do_not_log_the_identifier_value_in_use(self):
        """A failed entry is logged; an ID value (often a national ID) must not be"""
        entry = {
            "request": {"method": "POST", "url": "Individual"},
            "resource": {
                "type": "Individual",
                "identifier": [{"system": NATIONAL_ID, "value": "PATH-HEAD"}],
                "name": {"given": "Clash"},
            },
        }
        for bundle_type in ("batch", "transaction"):
            with self.subTest(bundle_type=bundle_type):
                with self.assertLogs("odoo.addons.spp_api_v2", level="WARNING") as logs:
                    response = self._post(
                        "/api/v2/spp/$batch",
                        {"resourceType": "Bundle", "type": bundle_type, "entry": [entry]},
                    )

                self.assertIn(response.status_code, (200, 409), response.text)
                self.assertNotIn("PATH-HEAD", self._logged_text(logs.records))

    def test_bundles_do_not_log_a_malformed_resource(self):
        """Schema validation errors quote the input (input_value=...), so they are logged by type too"""
        entry = {
            "request": {"method": "POST", "url": "Individual"},
            "resource": {
                "type": "Individual",
                "identifier": [{"system": NATIONAL_ID, "value": "PATH-MALFORMED"}],
                "name": "PATH-PII-NAME",
            },
        }
        with self.assertLogs("odoo.addons.spp_api_v2", level="WARNING") as logs:
            self._post("/api/v2/spp/$batch", {"resourceType": "Bundle", "type": "batch", "entry": [entry]})

        self.assertNotIn("PATH-PII-NAME", self._logged_text(logs.records))

    def test_bundles_do_not_log_the_identifier_value_not_found(self):
        entry = {"request": {"method": "GET", "url": f"Individual/{NATIONAL_ID}|PATH-NOBODY-PII"}}
        for bundle_type in ("batch", "transaction"):
            with self.subTest(bundle_type=bundle_type):
                with self.assertLogs("odoo.addons.spp_api_v2", level="WARNING") as logs:
                    response = self._post(
                        "/api/v2/spp/$batch",
                        {"resourceType": "Bundle", "type": bundle_type, "entry": [entry]},
                    )

                self.assertIn(response.status_code, (200, 422), response.text)
                self.assertNotIn("PATH-NOBODY-PII", self._logged_text(logs.records))

    def test_transaction_bundle_with_ambiguous_identifier_is_409(self):
        response = self._post(
            "/api/v2/spp/$batch",
            {
                "resourceType": "Bundle",
                "type": "transaction",
                "entry": [{"request": {"method": "GET", "url": f"Individual/{NATIONAL_ID}|PATH-DUP"}}],
            },
        )

        self.assertEqual(response.status_code, 409, response.text)

    def test_split_to_an_identifier_in_use_is_409_and_creates_nothing(self):
        response = self._post(
            f"{GROUP_PATH}/$split",
            {
                "newGroupIdentifier": [{"system": HOUSEHOLD_ID, "value": "PATH-HH-DUP"}],
                "membersToMove": [{"reference": f"Individual/{NATIONAL_ID}|PATH-MOVER"}],
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self._count_ids("PATH-HH-DUP"), 2)
        self.env.invalidate_all()
        self.assertFalse(self.group.group_membership_ids.filtered(lambda m: m.individual == self.mover).is_ended)

    # --- search filters ----------------------------------------------------

    def test_group_filter_with_ambiguous_group_is_409(self):
        response = self._get("/api/v2/spp/Individual?group=urn:openspp:vocab:id-type%23test_household_id%7CPATH-HH-DUP")

        self.assertEqual(response.status_code, 409, response.text)

    def test_member_filter_with_ambiguous_member_is_409(self):
        response = self._get(
            "/api/v2/spp/Group?member=Individual/urn:openspp:vocab:id-type%23test_national_id%7CPATH-DUP"
        )

        self.assertEqual(response.status_code, 409, response.text)

    def test_ambiguous_filter_looks_like_not_found_to_a_client_without_consent(self):
        """In a search, "not found" is an empty 200, so ambiguity must be too"""
        token = self._consent_client_token(consented=[self.dup_group_a])

        response = self._get(
            "/api/v2/spp/Individual?group=urn:openspp:vocab:id-type%23test_household_id%7CPATH-HH-DUP", token
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["meta"]["total"], 0)

    # --- consent decision --------------------------------------------------

    def test_legal_basis_client_that_requires_consent_flag_gets_409(self):
        """The 409/403 decision uses the read path's rule: a legal basis reads without consent"""
        token = self._consent_client_token(require_consent=True, legal_basis="public_task")

        response = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|PATH-DUP", token)

        self.assertEqual(response.status_code, 409, response.text)

    def test_add_ambiguous_member_as_client_without_consent_is_403(self):
        token = self._consent_client_token(consented=[self.group, self.first])

        response = self._post(
            f"{GROUP_PATH}/$add-member",
            {"entity": {"reference": f"Individual/{NATIONAL_ID}|PATH-DUP"}},
            token,
        )

        self.assertEqual(response.status_code, 403, response.text)

    def test_bulk_export_ambiguous_identifier_for_client_without_consent_is_access_denied(self):
        token = self._consent_client_token(consented=[self.first])

        response = self._post(
            "/api/v2/spp/$bulk/export",
            {"type": "Individual", "identifiers": [f"{NATIONAL_ID}|PATH-DUP"]},
            token,
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["items"][0]["status"], "access_denied")

    # --- soft-removed IDs --------------------------------------------------

    def test_removed_ids_are_not_listed_or_searchable(self):
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.head.id,
                "id_type_id": self.id_type_household.id,
                "value": "PATH-REMOVED",
                "status": "invalid",
            }
        )

        read = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|PATH-HEAD")
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual([ident["value"] for ident in read.json()["identifier"]], ["PATH-HEAD"])

        search = self._get(
            "/api/v2/spp/Individual?identifier=urn:openspp:vocab:id-type%23test_household_id%7CPATH-REMOVED"
        )
        self.assertEqual(search.status_code, 200, search.text)
        self.assertEqual(search.json()["meta"]["total"], 0)

    def test_removed_group_ids_are_not_listed(self):
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.group.id,
                "id_type_id": self.id_type_national.id,
                "value": "PATH-HH-REMOVED",
                "status": "invalid",
            }
        )

        read = self._get(GROUP_PATH)

        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual([ident["value"] for ident in read.json()["identifier"]], ["PATH-HH"])

    # --- individual vs group ------------------------------------------------

    def test_individual_and_group_sharing_a_value_are_resolved_by_kind(self):
        """A value held by one individual and one group is not ambiguous per kind"""
        self.create_test_individual(name="Kind Person", identifier_value="PATH-KIND")
        self.create_test_group(name="Kind Household", identifier_value="PATH-KIND", id_type=self.id_type_national)

        individual = self._get("/api/v2/spp/Individual/urn:openspp:vocab:id-type%23test_national_id|PATH-KIND")
        group = self._get("/api/v2/spp/Group/urn:openspp:vocab:id-type%23test_national_id|PATH-KIND")

        self.assertEqual(individual.status_code, 200, individual.text)
        self.assertEqual(individual.json()["type"], "Individual")
        self.assertEqual(group.status_code, 200, group.text)
        self.assertEqual(group.json()["type"], "Group")


class TestBundleAmbiguityForConsentClient(ApiV2HttpTestCase):
    """A bundle only says "ambiguous" to a client that may read every match

    Anyone else gets what they would get for an identifier nobody holds,
    as on the single-resource endpoints.
    """

    def setUp(self):
        super().setUp()
        self.first = self.create_test_individual(name="Original", identifier_value="BND-DUP")
        self.second = self.create_test_individual(name="Copy", identifier_value="BND-DUP")
        self.consent_client = self.create_api_client(name="Bundle Consent Client", scopes=SCOPES)
        self.create_consent(
            registrant=self.first,
            grantee_partner=self.consent_client.partner_id,
            resource_type="all",
            field_access="all",
        )
        self.token = self.generate_jwt_token(self.consent_client)

    def _bundle(self, bundle_type, entries):
        return self.url_open(
            "/api/v2/spp/$batch",
            data=json.dumps({"resourceType": "Bundle", "type": bundle_type, "entry": entries}),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
        )

    def _read(self, value):
        return {"request": {"method": "GET", "url": f"Individual/{NATIONAL_ID}|{value}"}}

    def test_batch_read_of_an_ambiguous_identifier_looks_like_not_found(self):
        response = self._bundle("batch", [self._read("BND-DUP"), self._read("BND-NOBODY")])

        self.assertEqual(response.status_code, 200, response.text)
        ambiguous, unknown = response.json()["entry"]
        self.assertEqual(ambiguous["response"]["status"], unknown["response"]["status"])
        self.assertEqual(
            ambiguous["resource"]["issue"][0]["diagnostics"].replace("BND-DUP", "X"),
            unknown["resource"]["issue"][0]["diagnostics"].replace("BND-NOBODY", "X"),
        )

    def test_batch_update_and_delete_of_an_ambiguous_identifier_look_like_not_found(self):
        update = {
            "request": {"method": "PUT", "url": f"Individual/{NATIONAL_ID}|BND-DUP"},
            "resource": {"type": "Individual", "name": {"given": "Changed"}},
        }
        delete = {"request": {"method": "DELETE", "url": f"Individual/{NATIONAL_ID}|BND-DUP"}}

        response = self._bundle("batch", [update, delete, self._read("BND-NOBODY")])

        self.assertEqual(response.status_code, 200, response.text)
        statuses = [entry["response"]["status"] for entry in response.json()["entry"]]
        self.assertNotIn("409 Conflict", statuses)
        self.assertEqual(statuses[0], statuses[2])
        self.assertEqual(statuses[1], statuses[2])

    def test_batch_create_with_an_ambiguous_member_is_403(self):
        """As POST /Group answers the same client: the jittered "not found" 403"""
        response = self._bundle(
            "batch",
            [
                {
                    "request": {"method": "POST", "url": "Group"},
                    "resource": {
                        "type": "Group",
                        "identifier": [{"system": HOUSEHOLD_ID, "value": "BND-NEW-HH"}],
                        "name": "Bundle Household",
                        "member": [{"entity": {"reference": f"Individual/{NATIONAL_ID}|BND-DUP"}}],
                    },
                }
            ],
        )

        self.assertEqual(response.status_code, 200, response.text)
        entry = response.json()["entry"][0]
        self.assertEqual(entry["response"]["status"], "403 Forbidden")
        self.assertNotIn("more than one", json.dumps(entry))

    def test_transaction_create_with_an_ambiguous_member_is_403(self):
        response = self._bundle(
            "transaction",
            [
                {
                    "request": {"method": "POST", "url": "Group"},
                    "resource": {
                        "type": "Group",
                        "identifier": [{"system": HOUSEHOLD_ID, "value": "BND-TX-HH"}],
                        "name": "Bundle Household",
                        "member": [{"entity": {"reference": f"Individual/{NATIONAL_ID}|BND-DUP"}}],
                    },
                }
            ],
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertNotIn("more than one", response.text)

    def test_transaction_read_of_an_ambiguous_identifier_looks_like_not_found(self):
        ambiguous = self._bundle("transaction", [self._read("BND-DUP")])
        unknown = self._bundle("transaction", [self._read("BND-NOBODY")])

        self.assertEqual(ambiguous.status_code, unknown.status_code, ambiguous.text)
        self.assertNotEqual(ambiguous.status_code, 409)

    def test_client_that_may_read_every_match_still_gets_409(self):
        self.create_consent(
            registrant=self.second,
            grantee_partner=self.consent_client.partner_id,
            resource_type="all",
            field_access="all",
        )

        response = self._bundle("batch", [self._read("BND-DUP")])

        self.assertEqual(response.json()["entry"][0]["response"]["status"], "409 Conflict")
