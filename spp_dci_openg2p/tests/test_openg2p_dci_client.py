"""OpenG2PDCIClient request-shape regression tests.

Locks in the five delta behaviours vs. upstream DCIClient (see
``services/openg2p_dci_client.py`` module docstring):

  1. ``query_type`` is ``"expression"`` (this client's preferred path)
  2. ``query.type`` carries the namespaced URI ``"ns:org:QueryType:expression"``
  3. ``query.value`` is the nested ``{expression: {query: {search_text: {$eq}}}}`` shape
  4. ``reg_type`` and ``reg_record_type`` are both the literal ``"Individual"``
  5. ``consent`` and ``authorize`` blocks are attached to every search criteria
"""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci.schemas import QueryType
from odoo.addons.spp_dci_openg2p.services.openg2p_dci_client import (
    DEFAULT_CONSENT_PURPOSE,
    DEFAULT_OPENG2P_REG_RECORD_TYPE,
    DEFAULT_OPENG2P_REG_TYPE,
    OPENG2P_QUERY_TYPE_URI,
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
                "registry_type": "SR",
                "vendor": "openg2p",
                "base_url": "https://partner-registry.play.openg2p.org",
                "search_endpoint": "/dci/registry/sync/search",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "receiver_id": "openg2p.test",
            }
        )

    # ------------------------------------------------------------------
    # _parse_query: expression query produces nested search_text shape
    # ------------------------------------------------------------------

    def test_parse_query_expression_produces_nested_search_text_shape(self):
        client = OpenG2PDCIClient(self.data_source, self.env)
        query = client._parse_query(QueryType.EXPRESSION, "IND-NSR-0001")
        self.assertEqual(
            query,
            {
                "type": OPENG2P_QUERY_TYPE_URI,
                "value": {
                    "expression": {
                        "query": {
                            "search_text": {"$eq": "IND-NSR-0001"},
                        },
                    },
                },
            },
        )

    def test_parse_query_non_expression_falls_through_to_super(self):
        """Non-expression query types defer to upstream DCIClient — this
        adapter only owns the expression path."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        out = client._parse_query(QueryType.PREDICATE, "some predicate")
        self.assertEqual(out, "some predicate")

    # ------------------------------------------------------------------
    # _build_search_envelope: reg_type forced, reg_record_type injected,
    # consent + authorize attached
    # ------------------------------------------------------------------

    def _build_envelope(self, client, search_text="IND-NSR-0001", **overrides):
        kwargs = dict(
            query_type=QueryType.EXPRESSION,
            query=client._parse_query(QueryType.EXPRESSION, search_text),
            registry_type="ns:org:RegistryType:Social",
            registry_event_type=None,
            record_type="PERSON",
            page=1,
            page_size=1,
        )
        kwargs.update(overrides)
        return client._build_search_envelope(**kwargs)

    def test_search_envelope_forces_reg_type_to_individual(self):
        """Even if the caller passes a different registry_type (a routing
        concept), the wire reg_type is always Individual."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        envelope = self._build_envelope(client)
        criterias = [item["search_criteria"] for item in envelope["message"]["search_request"]]
        self.assertTrue(criterias)
        for criteria in criterias:
            self.assertEqual(criteria.get("reg_type"), DEFAULT_OPENG2P_REG_TYPE)

    def test_search_envelope_injects_reg_record_type(self):
        """Upstream's SearchCriteria Pydantic model omits reg_record_type,
        so this adapter must inject it post-build."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        envelope = self._build_envelope(client)
        criterias = [item["search_criteria"] for item in envelope["message"]["search_request"]]
        for criteria in criterias:
            self.assertEqual(
                criteria.get("reg_record_type"),
                DEFAULT_OPENG2P_REG_RECORD_TYPE,
            )

    def test_search_envelope_query_is_namespaced_expression_shape(self):
        """End-to-end: envelope.message.search_request[i].search_criteria.query
        carries the namespaced URI type and the nested search_text body."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        envelope = self._build_envelope(client, search_text="IND-NSR-7777")
        query = envelope["message"]["search_request"][0]["search_criteria"]["query"]
        self.assertEqual(query["type"], OPENG2P_QUERY_TYPE_URI)
        self.assertEqual(
            query["value"]["expression"]["query"]["search_text"]["$eq"],
            "IND-NSR-7777",
        )

    def test_search_envelope_attaches_consent_and_authorize(self):
        """Every search_criteria must carry consent + authorize blocks.
        Defaults to ELIGIBILITY_CHECK purpose."""
        client = OpenG2PDCIClient(self.data_source, self.env)
        envelope = self._build_envelope(client)
        criteria = envelope["message"]["search_request"][0]["search_criteria"]
        self.assertIn("consent", criteria)
        self.assertIn("authorize", criteria)
        self.assertEqual(criteria["consent"]["@type"], "Consent")
        self.assertEqual(criteria["authorize"]["@type"], "Authorize")
        self.assertEqual(
            criteria["consent"]["purpose"]["code"],
            DEFAULT_CONSENT_PURPOSE["code"],
        )
        self.assertEqual(
            criteria["authorize"]["purpose"]["code"],
            DEFAULT_CONSENT_PURPOSE["code"],
        )

    def test_consent_and_authorize_blocks_not_overwritten_when_already_set(self):
        """If upstream ever starts populating consent/authorize itself, this
        adapter must not clobber it (setdefault semantics)."""
        client = OpenG2PDCIClient(self.data_source, self.env)

        original_super = client.__class__.__mro__[1]._build_search_envelope

        def upstream_with_consent(self, **kwargs):
            envelope = original_super(self, **kwargs)
            for item in envelope["message"]["search_request"]:
                item["search_criteria"]["consent"] = {"sentinel": "preserved"}
                item["search_criteria"]["authorize"] = {"sentinel": "preserved"}
            return envelope

        # Monkey-patch upstream to populate consent/authorize, then call
        # our adapter's _build_search_envelope and verify it preserved them.
        original_method = client.__class__.__mro__[1]._build_search_envelope
        try:
            client.__class__.__mro__[1]._build_search_envelope = upstream_with_consent
            envelope = self._build_envelope(client)
        finally:
            client.__class__.__mro__[1]._build_search_envelope = original_method

        criteria = envelope["message"]["search_request"][0]["search_criteria"]
        self.assertEqual(criteria["consent"], {"sentinel": "preserved"})
        self.assertEqual(criteria["authorize"], {"sentinel": "preserved"})

    def test_custom_reg_type_via_constructor(self):
        """Operators can override the reg_type/reg_record_type via the
        constructor when OpenG2P serves something other than 'Individual'."""
        client = OpenG2PDCIClient(
            self.data_source,
            self.env,
            reg_type="HouseholdMember",
            reg_record_type="HouseholdMember",
        )
        envelope = self._build_envelope(client)
        criteria = envelope["message"]["search_request"][0]["search_criteria"]
        self.assertEqual(criteria["reg_type"], "HouseholdMember")
        self.assertEqual(criteria["reg_record_type"], "HouseholdMember")
