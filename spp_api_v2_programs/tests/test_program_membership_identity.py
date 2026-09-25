# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests that a ProgramMembership is addressed unambiguously (#554 items A and B).

A beneficiary can be enrolled in several programs, so the beneficiary's
identifier alone does not identify one membership. Reads and updates must
either be told the program (``?program=``) or refuse to guess.
"""

import json
from urllib.parse import quote

from odoo.exceptions import ValidationError

from odoo.addons.spp_api_v2.schemas.base import Reference
from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase, ApiV2TestCase

from ..schemas.program_membership import ProgramMembership
from ..services import program_membership_service
from ..services.program_membership_service import ProgramMembershipService

NATIONAL_ID = "urn:openspp:vocab:id-type#test_national_id"
PROGRAM_1_REF = "Program/urn:openspp:program|first-identity-program"
PROGRAM_2_REF = "Program/urn:openspp:program|second-identity-program"
PROGRAM_3_REF = "Program/urn:openspp:program|third-identity-program"


def _beneficiary_ref(value):
    return f"Individual/{NATIONAL_ID}|{value}"


class TestProgramMembershipIdentityAPI(ApiV2HttpTestCase):
    """HTTP contract for addressing one membership among several"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/ProgramMembership"

        self.program_1 = self.create_test_program(name="First Identity Program")
        self.program_2 = self.create_test_program(name="Second Identity Program")
        self.program_3 = self.create_test_program(name="Third Identity Program")

        # Enrolled in two programs. P1 is created first, so it is the *older*
        # membership: a lookup that ignores the program picks P2 (newest first).
        self.multi = self.create_test_individual(identifier_value="MULTI-001")
        self.multi_p1 = self.create_test_membership(partner=self.multi, program=self.program_1, state="enrolled")
        self.multi_p2 = self.create_test_membership(partner=self.multi, program=self.program_2, state="enrolled")

        # Enrolled in exactly one program.
        self.single = self.create_test_individual(identifier_value="SINGLE-001")
        self.single_p1 = self.create_test_membership(partner=self.single, program=self.program_1, state="enrolled")

        # Not enrolled anywhere.
        self.other = self.create_test_individual(identifier_value="OTHER-001")

        self.client = self.create_api_client(
            name="Membership Identity Client",
            scopes=[
                {"resource": "program_membership", "action": "read"},
                {"resource": "program_membership", "action": "search"},
                {"resource": "program_membership", "action": "create"},
                {"resource": "program_membership", "action": "update"},
            ],
        )
        for registrant in (self.multi, self.single, self.other):
            self.create_consent(
                registrant=registrant,
                grantee_partner=self.client.partner_id,
                resource_type="all",
                field_access="all",
            )
        self.token = self.generate_jwt_token(self.client)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _headers(self, **extra):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        headers.update(extra)
        return headers

    def _url(self, value, program_ref=None):
        url = f"{self.api_base_url}/{quote(NATIONAL_ID, safe=':')}|{value}"
        if program_ref:
            url += f"?program={quote(program_ref, safe=':/|')}"
        return url

    def _put(self, url, payload, **extra_headers):
        # url_put bypasses url_open's flush, so push setUp data to the
        # database the HTTP worker reads, and drop our cache for the reads after.
        self.env.cr.flush()
        self.env.invalidate_all()
        response = self.url_put(url, data=json.dumps(payload), headers=self._headers(**extra_headers))
        self.env.invalidate_all()
        return response

    def _payload(self, program_ref, beneficiary_value, status):
        return {
            "type": "ProgramMembership",
            "program": {"reference": program_ref},
            "beneficiary": {"reference": _beneficiary_ref(beneficiary_value)},
            "status": status,
        }

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def test_get_without_program_is_409_when_beneficiary_has_several_memberships(self):
        """Refuses to pick one of several memberships instead of returning an arbitrary one"""
        response = self.url_open(self._url("MULTI-001"), headers=self._headers())

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("program", response.json()["detail"])

    def test_get_with_program_returns_that_programs_membership(self):
        """?program= selects the membership in that program, not the newest one"""
        response = self.url_open(self._url("MULTI-001", PROGRAM_1_REF), headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["program"]["reference"], PROGRAM_1_REF)

    def test_get_without_program_still_works_for_single_membership(self):
        """Backward compatible: one membership needs no ?program="""
        response = self.url_open(self._url("SINGLE-001"), headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["program"]["reference"], PROGRAM_1_REF)

    def test_get_with_program_the_beneficiary_is_not_in_is_404(self):
        """?program= naming a program without a membership for this beneficiary is 404"""
        response = self.url_open(self._url("MULTI-001", PROGRAM_3_REF), headers=self._headers())

        self.assertEqual(response.status_code, 404, response.text)

    def test_get_with_unknown_program_is_404(self):
        """?program= naming no existing program is 404"""
        response = self.url_open(
            self._url("MULTI-001", "Program/urn:openspp:program|no-such-program"),
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 404, response.text)

    def test_get_with_malformed_program_is_400(self):
        """?program= that is not a Program/{system}|{value} reference is 400"""
        response = self.url_open(self._url("MULTI-001", "not-a-reference"), headers=self._headers())

        self.assertEqual(response.status_code, 400, response.text)

    def test_ambiguity_is_not_revealed_without_consent(self):
        """Consent is checked before ambiguity: no 409 leaks membership counts"""
        no_consent = self.create_test_individual(identifier_value="NOCONSENT-MULTI-001")
        self.create_test_membership(partner=no_consent, program=self.program_1)
        self.create_test_membership(partner=no_consent, program=self.program_2)

        response = self.url_open(self._url("NOCONSENT-MULTI-001"), headers=self._headers())

        self.assertEqual(response.status_code, 403, response.text)

    def test_enrollment_is_not_revealed_without_consent(self):
        """?program= for a program the beneficiary is not in is 403, not 404, without consent"""
        no_consent = self.create_test_individual(identifier_value="NOCONSENT-SINGLE-001")
        self.create_test_membership(partner=no_consent, program=self.program_1)

        response = self.url_open(self._url("NOCONSENT-SINGLE-001", PROGRAM_3_REF), headers=self._headers())

        self.assertEqual(response.status_code, 403, response.text)

    # ------------------------------------------------------------------
    # PUT
    # ------------------------------------------------------------------

    def test_put_with_program_updates_only_that_programs_membership(self):
        """PUT ?program=P1 exits P1 and leaves P2 alone (#554 A reproduction)"""
        response = self._put(
            self._url("MULTI-001", PROGRAM_1_REF),
            self._payload(PROGRAM_1_REF, "MULTI-001", "exited"),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["program"]["reference"], PROGRAM_1_REF)
        self.assertEqual(self.multi_p1.state, "exited")
        self.assertEqual(self.multi_p2.state, "enrolled")
        self.assertEqual(self.multi_p1.program_id, self.program_1)
        self.assertEqual(self.multi_p2.program_id, self.program_2)

    def test_put_without_program_is_409_when_beneficiary_has_several_memberships(self):
        """PUT refuses to guess, and changes nothing"""
        response = self._put(
            self._url("MULTI-001"),
            self._payload(PROGRAM_1_REF, "MULTI-001", "exited"),
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.multi_p1.state, "enrolled")
        self.assertEqual(self.multi_p2.state, "enrolled")

    def test_put_cannot_move_membership_to_another_program(self):
        """Body program different from the addressed membership is 422, not a re-parent"""
        response = self._put(
            self._url("SINGLE-001"),
            self._payload(PROGRAM_3_REF, "SINGLE-001", "enrolled"),
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.single_p1.program_id, self.program_1)
        self.assertFalse(
            self.env["spp.program.membership"].search(
                [("partner_id", "=", self.single.id), ("program_id", "=", self.program_3.id)]
            )
        )

    def test_put_body_program_must_match_query_program(self):
        """?program=P1 with a body naming P2 is 422 and changes nothing"""
        response = self._put(
            self._url("MULTI-001", PROGRAM_1_REF),
            self._payload(PROGRAM_2_REF, "MULTI-001", "exited"),
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.multi_p1.state, "enrolled")
        self.assertEqual(self.multi_p2.state, "enrolled")

    def test_put_cannot_move_membership_to_another_beneficiary(self):
        """Body beneficiary different from the addressed one is 422, not a reassignment"""
        response = self._put(
            self._url("SINGLE-001"),
            self._payload(PROGRAM_1_REF, "OTHER-001", "enrolled"),
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.single_p1.partner_id, self.single)
        self.assertFalse(self.env["spp.program.membership"].search([("partner_id", "=", self.other.id)]))

    # ------------------------------------------------------------------
    # POST Location
    # ------------------------------------------------------------------

    def test_post_location_addresses_the_created_membership(self):
        """Following Location returns the membership just created, even with others present"""
        response = self.url_open(
            self.api_base_url,
            data=json.dumps(self._payload(PROGRAM_3_REF, "MULTI-001", "enrolled")),
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 201, response.text)
        location = response.headers["location"]

        followed = self.url_open(location, headers=self._headers())

        self.assertEqual(followed.status_code, 200, followed.text)
        self.assertEqual(followed.json()["program"]["reference"], PROGRAM_3_REF)

    def test_post_location_skips_a_removed_beneficiary_id(self):
        """A soft-removed ID no longer resolves, so Location must use a live one"""
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.other.id,
                "id_type_id": self.id_type_household.id,
                "value": "OTHER-REMOVED-ID",
                "status": "invalid",
            }
        )
        response = self.url_open(
            self.api_base_url,
            data=json.dumps(self._payload(PROGRAM_1_REF, "OTHER-001", "enrolled")),
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 201, response.text)

        followed = self.url_open(response.headers["location"], headers=self._headers())

        self.assertEqual(followed.status_code, 200, followed.text)
        self.assertEqual(followed.json()["beneficiary"]["reference"], _beneficiary_ref("OTHER-001"))

    # ------------------------------------------------------------------
    # If-Match (#554 B)
    # ------------------------------------------------------------------

    def test_put_accepts_its_own_etag_as_if_match(self):
        """The ETag from GET is accepted by PUT (versionId format matches)"""
        url = self._url("SINGLE-001")
        get_response = self.url_open(url, headers=self._headers())
        self.assertEqual(get_response.status_code, 200, get_response.text)
        etag = get_response.headers["etag"]
        self.assertEqual(etag, f'"{get_response.json()["meta"]["versionId"]}"')

        response = self._put(url, self._payload(PROGRAM_1_REF, "SINGLE-001", "paused"), **{"If-Match": etag})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.single_p1.state, "paused")


class TestProgramMembershipIdentityService(ApiV2TestCase):
    """Service-level resolution and update guards"""

    def setUp(self):
        super().setUp()
        self.service = ProgramMembershipService(self.env)
        self.program_1 = self.create_test_program(name="First Identity Program")
        self.program_2 = self.create_test_program(name="Second Identity Program")
        self.program_3 = self.create_test_program(name="Third Identity Program")
        self.multi = self.create_test_individual(identifier_value="SVC-MULTI-001")
        self.multi_p1 = self.create_test_membership(partner=self.multi, program=self.program_1)
        self.multi_p2 = self.create_test_membership(partner=self.multi, program=self.program_2)
        self.other = self.create_test_individual(identifier_value="SVC-OTHER-001")

    def test_find_by_identifier_with_program(self):
        """The program narrows resolution to that program's membership"""
        found = self.service.find_by_identifier(NATIONAL_ID, "SVC-MULTI-001", program=self.program_1)

        self.assertEqual(found, self.multi_p1)

    def test_find_by_identifier_with_program_without_membership(self):
        """A program the beneficiary is not in resolves to nothing"""
        found = self.service.find_by_identifier(NATIONAL_ID, "SVC-MULTI-001", program=self.program_3)

        self.assertFalse(found)

    def test_find_by_identifier_ambiguous_raises(self):
        """Several memberships and no program: refuse, and report how many"""
        with self.assertRaises(program_membership_service.AmbiguousMembershipError) as ctx:
            self.service.find_by_identifier(NATIONAL_ID, "SVC-MULTI-001")

        self.assertEqual(ctx.exception.count, 2)

    def _schema(self, program_ref, beneficiary_value, status="exited"):
        return ProgramMembership(
            program=Reference(reference=program_ref),
            beneficiary=Reference(reference=_beneficiary_ref(beneficiary_value)),
            status=status,
        )

    def test_update_refuses_program_change(self):
        """update() never re-parents a membership onto another program"""
        with self.assertRaises(ValidationError):
            self.service.update(self.multi_p1, self._schema(PROGRAM_3_REF, "SVC-MULTI-001"), source="test")

        self.assertEqual(self.multi_p1.program_id, self.program_1)
        self.assertEqual(self.multi_p1.state, "enrolled")

    def test_update_refuses_beneficiary_change(self):
        """update() never reassigns a membership to another registrant"""
        with self.assertRaises(ValidationError):
            self.service.update(self.multi_p1, self._schema(PROGRAM_1_REF, "SVC-OTHER-001"), source="test")

        self.assertEqual(self.multi_p1.partner_id, self.multi)
        self.assertEqual(self.multi_p1.state, "enrolled")

    def test_update_matching_identity_writes_status(self):
        """A body matching the membership's program and beneficiary updates it"""
        self.service.update(self.multi_p1, self._schema(PROGRAM_1_REF, "SVC-MULTI-001"), source="test")

        self.assertEqual(self.multi_p1.state, "exited")
        self.assertEqual(self.multi_p2.state, "enrolled")


class TestProgramMembershipAmbiguousBeneficiary(ApiV2HttpTestCase):
    """A beneficiary identifier shared by two registrants addresses nothing (#554 I)"""

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/ProgramMembership"
        self.program = self.create_test_program(name="First Identity Program")
        self.first = self.create_test_individual(name="Original", identifier_value="PM-DUP")
        self.second = self.create_test_individual(name="Copy", identifier_value="PM-DUP")
        self.membership = self.create_test_membership(partner=self.first, program=self.program)
        self.client = self.create_api_client(
            name="Legal Basis Membership Client",
            scopes=[
                {"resource": "program_membership", "action": "read"},
                {"resource": "program_membership", "action": "create"},
                {"resource": "program_membership", "action": "update"},
            ],
            require_consent=False,
            legal_basis="public_task",
        )
        self.token = self.generate_jwt_token(self.client)

    def _headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"}

    def test_get_with_ambiguous_beneficiary_is_409(self):
        response = self.url_open(
            f"{self.api_base_url}/{quote(NATIONAL_ID, safe=':')}|PM-DUP",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 409, response.text)

    def test_post_with_ambiguous_beneficiary_is_409(self):
        response = self.url_open(
            self.api_base_url,
            data=json.dumps(
                {
                    "type": "ProgramMembership",
                    "program": {"reference": PROGRAM_1_REF},
                    "beneficiary": {"reference": _beneficiary_ref("PM-DUP")},
                    "status": "enrolled",
                }
            ),
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.env.invalidate_all()
        self.assertFalse(
            self.env["spp.program.membership"].search([("partner_id", "=", self.second.id)]),
        )
