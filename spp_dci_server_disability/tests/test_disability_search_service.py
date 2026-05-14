"""DisabilitySearchService unit tests.

Locks in:
  - Expression query (nested search_text shape) is parsed correctly
  - idtype-value query (flat shape) is parsed correctly
  - Unknown identifier produces REG-ERR-001 / REGISTER_NOT_FOUND
  - Empty / malformed query produces SEARCH-ERR-002 / SEARCH_CRITERIA_INVALID
  - Successful match returns disability data under the wire-format keys
  - Multiple request items are processed independently
"""

from datetime import UTC, datetime

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import (
    QueryType,
    SearchStatusReasonCode,
)
from odoo.addons.spp_dci.schemas.search import (
    SearchCriteria,
    SearchRequest,
    SearchRequestItem,
)
from odoo.addons.spp_dci_server_disability.services.disability_search_service import (
    DR_REG_RECORD_TYPE,
    DR_REG_TYPE,
    REGISTER_NOT_FOUND_CODE,
    DisabilitySearchService,
)


def _make_request(query_type, query, reference_id="r1"):
    """Helper to build a one-item SearchRequest."""
    return SearchRequest(
        transaction_id="txn-1",
        search_request=[
            SearchRequestItem(
                reference_id=reference_id,
                timestamp=datetime.now(UTC),
                search_criteria=SearchCriteria(
                    reg_type="DR",
                    query_type=query_type,
                    query=query,
                ),
            )
        ],
    )


def _expression_query(value):
    """OpenG2P-style nested expression query."""
    return {
        "type": "ns:org:QueryType:expression",
        "value": {
            "expression": {
                "query": {
                    "search_text": {"$eq": value},
                },
            },
        },
    }


def _idtype_value_query(id_type, id_value):
    """Upstream flat idtype-value query."""
    return {
        "type": "idtype-value",
        "value": {"id_type": id_type, "id_value": id_value},
    }


@tagged("post_install", "-at_install")
class TestDisabilitySearchService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The UIN vocab code is seeded by data/dr_id_types.xml. Module
        # data load is the only legitimate path for adding codes to a
        # system vocabulary — runtime create is rejected with UserError.
        cls.id_type_uin = cls.env.ref("spp_dci_server_disability.id_type_uin_dr")

        cls.partner_pwd = cls.env["res.partner"].create(
            {
                "name": "PWD Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_pwd.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-DR-1",
            }
        )
        # Stamp the disability flag if the field exists on res.partner.
        # spp_disability_registry exposes it as a computed-stored Boolean
        # derived from the current approved assessment; in test isolation
        # (no assessment record), the field exists but is False. We bypass
        # the related/computed write protection via SQL to set it for the
        # test partner — simpler than constructing a full assessment.
        partner_fields = cls.env["res.partner"]._fields
        if "has_disability" in partner_fields:
            cls.env.cr.execute(
                "UPDATE res_partner SET has_disability = true WHERE id = %s",
                (cls.partner_pwd.id,),
            )
            cls.partner_pwd.invalidate_recordset(["has_disability"])

        cls.partner_no_disability = cls.env["res.partner"].create(
            {
                "name": "Non-PWD Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_no_disability.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-DR-2",
            }
        )

    # ------------------------------------------------------------------
    # Query parsing
    # ------------------------------------------------------------------

    def test_extracts_search_text_from_expression_query(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value, _expression_query("UIN-DR-1")
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "succ")
        self.assertIsNotNone(item.data)
        self.assertEqual(item.data.reg_records[0]["partner_uid"], self.partner_pwd.id)

    def test_extracts_search_text_from_idtype_value_query(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.IDTYPE_VALUE.value, _idtype_value_query("UIN", "UIN-DR-1")
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "succ")
        self.assertEqual(item.data.reg_records[0]["partner_uid"], self.partner_pwd.id)

    def test_idtype_value_with_string_value_is_accepted(self):
        """Some clients send the value as a bare string rather than the
        flat {id_type, id_value} dict. We accept both."""
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.IDTYPE_VALUE.value,
            {"type": "idtype-value", "value": "UIN-DR-1"},
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "succ")

    def test_idtype_value_query_without_id_value_is_rejected(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.IDTYPE_VALUE.value,
            {"type": "idtype-value", "value": {"id_type": "UIN"}},
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "rjct")
        self.assertEqual(
            item.status_reason_code,
            SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
        )

    def test_expression_query_without_eq_is_rejected(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value,
            {
                "type": "ns:org:QueryType:expression",
                "value": {
                    "expression": {"query": {"search_text": {"$ne": "x"}}},
                },
            },
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "rjct")
        self.assertEqual(
            item.status_reason_code,
            SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
        )

    # ------------------------------------------------------------------
    # Partner lookup
    # ------------------------------------------------------------------

    def test_unknown_identifier_returns_register_not_found(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value, _expression_query("UIN-UNKNOWN")
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "rjct")
        self.assertEqual(item.status_reason_code, REGISTER_NOT_FOUND_CODE)
        self.assertIsNone(item.data)

    def test_partner_without_disability_field_returns_false(self):
        """If has_disability is not set / not present, the wire format
        key has_disability is reported as False — the SP side then
        evaluates the variable as False rather than failing."""
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value, _expression_query("UIN-DR-2")
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.status, "succ")
        self.assertEqual(item.data.reg_records[0]["has_disability"], False)

    # ------------------------------------------------------------------
    # Response envelope shape
    # ------------------------------------------------------------------

    def test_response_envelope_carries_dr_reg_type_constants(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value, _expression_query("UIN-DR-1")
        )
        response = service.execute_search(request)
        item = response.search_response[0]
        self.assertEqual(item.data.reg_type, DR_REG_TYPE)
        self.assertEqual(item.data.reg_record_type, DR_REG_RECORD_TYPE)

    def test_reg_record_carries_wire_format_keys(self):
        """The reg_record is shaped for SP-side ``dci_attribute_path``
        lookups. Lock the contract: must contain ``has_disability`` and
        optional disability metadata, must NOT include the local field
        name ``is_person_with_disability`` (which never existed on the
        model — old DRService legacy)."""
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value, _expression_query("UIN-DR-1")
        )
        response = service.execute_search(request)
        record = response.search_response[0].data.reg_records[0]
        self.assertIn("has_disability", record)
        self.assertIn("disability_severity_code", record)
        self.assertIn("disability_review_category", record)
        self.assertIn("disability_next_review", record)
        self.assertNotIn("is_person_with_disability", record)

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def test_multiple_items_processed_independently(self):
        """One item failing must not affect the others. Two requests:
        one valid, one for an unknown identifier — both produce items
        with distinct statuses and reference_ids."""
        service = DisabilitySearchService(self.env)
        request = SearchRequest(
            transaction_id="txn-batch",
            search_request=[
                SearchRequestItem(
                    reference_id="r-ok",
                    timestamp=datetime.now(UTC),
                    search_criteria=SearchCriteria(
                        query_type=QueryType.EXPRESSION.value,
                        query=_expression_query("UIN-DR-1"),
                    ),
                ),
                SearchRequestItem(
                    reference_id="r-missing",
                    timestamp=datetime.now(UTC),
                    search_criteria=SearchCriteria(
                        query_type=QueryType.EXPRESSION.value,
                        query=_expression_query("UIN-UNKNOWN"),
                    ),
                ),
            ],
        )
        response = service.execute_search(request)
        self.assertEqual(len(response.search_response), 2)
        by_ref = {item.reference_id: item for item in response.search_response}
        self.assertEqual(by_ref["r-ok"].status, "succ")
        self.assertEqual(by_ref["r-missing"].status, "rjct")
        self.assertEqual(
            by_ref["r-missing"].status_reason_code,
            REGISTER_NOT_FOUND_CODE,
        )

    def test_correlation_id_is_set_on_response(self):
        service = DisabilitySearchService(self.env)
        request = _make_request(
            QueryType.EXPRESSION.value, _expression_query("UIN-DR-1")
        )
        response = service.execute_search(request)
        self.assertTrue(response.correlation_id)
        self.assertEqual(response.transaction_id, "txn-1")
