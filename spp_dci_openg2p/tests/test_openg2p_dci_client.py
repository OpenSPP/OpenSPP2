"""OpenG2PDCIClient request-shape regression tests.

Locks in the two delta behaviours vs. upstream DCIClient:
  - idtype-value query nests {id_type, id_value} under value
  - search_criteria carries reg_record_type
"""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci.schemas import QueryType
from odoo.addons.spp_dci_openg2p.services.openg2p_dci_client import (
    DEFAULT_OPENG2P_REG_RECORD_TYPE,
    OpenG2PDCIClient,
)


@tagged("post_install", "-at_install")
class TestOpenG2PDCIClient(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenG2P Test Source",
                "code": "openg2p_test",
                "registry_type": "DR",
                "vendor": "openg2p",
                "base_url": "https://partner-registry.play.openg2p.org",
                "search_endpoint": "/dci/registry/sync/search",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "receiver_id": "openg2p.test",
            }
        )

    def test_parse_query_nests_id_type_and_id_value(self):
        client = OpenG2PDCIClient(self.data_source, self.env)
        query = client._parse_query(QueryType.IDTYPE_VALUE, "UIN:1234")
        self.assertEqual(
            query,
            {
                "type": QueryType.IDTYPE_VALUE,
                "value": {"id_type": "UIN", "id_value": "1234"},
            },
        )

    def test_parse_query_non_idtype_value_falls_through(self):
        client = OpenG2PDCIClient(self.data_source, self.env)
        # Predicate query string is passed through unchanged by upstream
        out = client._parse_query(QueryType.PREDICATE, "some predicate")
        self.assertEqual(out, "some predicate")

    def test_parse_query_invalid_idtype_value_falls_through(self):
        """Malformed query_value (no colon) goes to super, preserving the
        upstream ValidationError behaviour."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            client._parse_query(QueryType.IDTYPE_VALUE, "no-colon-here")

    def test_search_envelope_injects_reg_record_type(self):
        """Search envelope must carry reg_record_type on each
        search_criteria — upstream's SearchCriteria Pydantic model omits
        it, so this is a post-build injection."""
        client = OpenG2PDCIClient(self.data_source, self.env)

        envelope = client._build_search_envelope(
            query_type=QueryType.IDTYPE_VALUE,
            query=client._parse_query(QueryType.IDTYPE_VALUE, "UIN:9999"),
            registry_type="ns:org:RegistryType:Social",
            registry_event_type=None,
            record_type="PERSON",
            page=1,
            page_size=1,
        )

        criterias = [item["search_criteria"] for item in envelope["message"]["search_request"]]
        self.assertTrue(criterias)
        for criteria in criterias:
            self.assertEqual(
                criteria.get("reg_record_type"),
                DEFAULT_OPENG2P_REG_RECORD_TYPE,
            )

    def test_search_envelope_query_is_nested_shape(self):
        """End-to-end: envelope.message.search_request[i].search_criteria.query
        is OpenG2P's nested shape, not the upstream flat shape."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        envelope = client._build_search_envelope(
            query_type=QueryType.IDTYPE_VALUE,
            query=client._parse_query(QueryType.IDTYPE_VALUE, "UIN:7777"),
            registry_type="ns:org:RegistryType:Social",
            registry_event_type=None,
            record_type="PERSON",
            page=1,
            page_size=1,
        )
        query = envelope["message"]["search_request"][0]["search_criteria"]["query"]
        self.assertEqual(query["type"], QueryType.IDTYPE_VALUE)
        self.assertEqual(query["value"]["id_type"], "UIN")
        self.assertEqual(query["value"]["id_value"], "7777")

    def test_custom_reg_record_type_via_constructor(self):
        """The vendor adapter accepts a custom reg_record_type — used
        when OpenG2P's real DR endpoint becomes available and we need
        to point at a non-Farmer record type."""
        client = OpenG2PDCIClient(
            self.data_source,
            self.env,
            reg_record_type="spdci-extensions-dci:PWD_Person",
        )
        envelope = client._build_search_envelope(
            query_type=QueryType.IDTYPE_VALUE,
            query=client._parse_query(QueryType.IDTYPE_VALUE, "UIN:1"),
            registry_type="ns:org:RegistryType:DR",
            registry_event_type=None,
            record_type="PERSON",
            page=1,
            page_size=1,
        )
        criteria = envelope["message"]["search_request"][0]["search_criteria"]
        self.assertEqual(criteria["reg_record_type"], "spdci-extensions-dci:PWD_Person")
