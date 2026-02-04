# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Vocabulary API endpoints."""

from urllib.parse import quote

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestVocabularyAPI(TransactionCase):
    """Test Vocabulary API functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Lookup organization types
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        cls.org_type_private = cls.env.ref(
            "spp_consent.org_type_private",
            raise_if_not_found=False,
        )
        if not cls.org_type_private:
            cls.org_type_private = cls.env["spp.consent.org.type"].search([("code", "=", "private")], limit=1)

        # Get or create test vocabulary (search first to avoid duplicates)
        cls.vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:test:vocab:test")], limit=1)
        if not cls.vocab:
            cls.vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Test Vocabulary",
                    "namespace_uri": "urn:test:vocab:test",
                    "domain": "core",
                    "is_hierarchical": False,
                    "description": "A test vocabulary",
                    "version": "1.0",
                    "reference_url": "https://example.com/vocab",
                }
            )

        # Get or create test codes
        cls.code1 = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab.id), ("code", "=", "A")], limit=1
        )
        if not cls.code1:
            cls.code1 = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab.id,
                    "code": "A",
                    "display": "Option A",
                    "definition": "First option",
                    "sequence": 1,
                }
            )
        cls.code2 = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab.id), ("code", "=", "B")], limit=1
        )
        if not cls.code2:
            cls.code2 = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab.id,
                    "code": "B",
                    "display": "Option B",
                    "definition": "Second option",
                    "sequence": 2,
                }
            )
        cls.code3 = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab.id), ("code", "=", "C")], limit=1
        )
        if not cls.code3:
            cls.code3 = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab.id,
                    "code": "C",
                    "display": "Option C (Deprecated)",
                    "deprecated": True,
                    "sequence": 3,
                }
            )

        # Get or create hierarchical vocabulary
        cls.hier_vocab = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:test:vocab:hierarchical")], limit=1
        )
        if not cls.hier_vocab:
            cls.hier_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Hierarchical Test",
                    "namespace_uri": "urn:test:vocab:hierarchical",
                    "domain": "core",
                    "is_hierarchical": True,
                }
            )

        cls.parent_code = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.hier_vocab.id), ("code", "=", "PARENT")],
            limit=1,
        )
        if not cls.parent_code:
            cls.parent_code = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.hier_vocab.id,
                    "code": "PARENT",
                    "display": "Parent Code",
                }
            )
        cls.child_code = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.hier_vocab.id), ("code", "=", "CHILD")], limit=1
        )
        if not cls.child_code:
            cls.child_code = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.hier_vocab.id,
                    "code": "CHILD",
                    "display": "Child Code",
                    "parent_id": cls.parent_code.id,
                }
            )

        # Get or create additional vocabulary for domain filtering
        cls.health_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:test:vocab:health")], limit=1)
        if not cls.health_vocab:
            cls.health_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Health Codes",
                    "namespace_uri": "urn:test:vocab:health",
                    "domain": "health",
                    "is_hierarchical": False,
                }
            )

        # Create test partner and API client
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test API Partner",
            }
        )
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        # Add vocabulary scope
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "vocabulary",
                "action": "read",
            }
        )

    def test_vocabulary_response_schema(self):
        """Test VocabularyResponse schema validates correctly."""
        from ..schemas.vocabulary import VocabularyResponse

        response = VocabularyResponse(
            namespace_uri="urn:test:vocab",
            name="Test",
            domain="core",
            is_hierarchical=False,
            code_count=5,
        )
        assert response.namespace_uri == "urn:test:vocab"
        assert response.name == "Test"
        assert response.code_count == 5

    def test_vocabulary_code_response_schema(self):
        """Test VocabularyCodeResponse schema validates correctly."""
        from ..schemas.vocabulary import VocabularyCodeResponse

        response = VocabularyCodeResponse(
            code="M",
            display="Male",
            definition="Male gender",
            deprecated=False,
            level=0,
        )
        assert response.code == "M"
        assert response.display == "Male"

    def test_vocabulary_list_response_schema(self):
        """Test VocabularyListResponse schema validates correctly."""
        from ..schemas.vocabulary import VocabularyListResponse, VocabularyResponse

        items = [
            VocabularyResponse(
                namespace_uri="urn:test:1",
                name="Test 1",
                domain="core",
                is_hierarchical=False,
                code_count=3,
            ),
            VocabularyResponse(
                namespace_uri="urn:test:2",
                name="Test 2",
                domain="health",
                is_hierarchical=True,
                code_count=10,
            ),
        ]
        response = VocabularyListResponse(total=2, items=items)
        assert response.total == 2
        assert len(response.items) == 2

    def test_vocabulary_codes_response_schema(self):
        """Test VocabularyCodesResponse schema validates correctly."""
        from ..schemas.vocabulary import VocabularyCodeResponse, VocabularyCodesResponse

        items = [
            VocabularyCodeResponse(code="A", display="A", deprecated=False, level=0),
            VocabularyCodeResponse(code="B", display="B", deprecated=False, level=0),
        ]
        response = VocabularyCodesResponse(
            namespace_uri="urn:test",
            vocabulary_name="Test",
            total=2,
            items=items,
        )
        assert response.total == 2
        assert response.vocabulary_name == "Test"

    def test_client_has_vocabulary_scope(self):
        """Test API client has vocabulary read scope."""
        assert self.api_client.has_scope("vocabulary", "read")

    def test_client_without_vocabulary_scope(self):
        """Test API client without vocabulary scope."""
        # Create client without scope
        client = self.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": self.partner.id,
                "organization_type_id": self.org_type_private.id,
            }
        )
        assert not client.has_scope("vocabulary", "read")

    def test_vocabulary_model_exists(self):
        """Test vocabulary record was created correctly."""
        assert self.vocab.name == "Test Vocabulary"
        assert self.vocab.namespace_uri == "urn:test:vocab:test"
        assert self.vocab.code_count == 3  # A, B, C

    def test_vocabulary_codes_exist(self):
        """Test vocabulary codes were created correctly."""
        assert self.code1.code == "A"
        assert self.code2.code == "B"
        assert self.code3.deprecated is True

    def test_hierarchical_vocabulary(self):
        """Test hierarchical vocabulary relationships."""
        assert self.child_code.parent_id == self.parent_code
        assert self.child_code.level == 1
        assert self.parent_code.level == 0

    def test_vocabulary_code_lookup(self):
        """Test looking up code by namespace and code."""
        VocabularyCode = self.env["spp.vocabulary.code"]
        code = VocabularyCode.get_code("urn:test:vocab:test", "A")
        assert code.display == "Option A"

    def test_vocabulary_code_not_found(self):
        """Test looking up non-existent code returns empty."""
        VocabularyCode = self.env["spp.vocabulary.code"]
        code = VocabularyCode.get_code("urn:test:vocab:test", "NONEXISTENT")
        assert not code

    def test_vocabulary_search_by_domain(self):
        """Test searching vocabularies by domain."""
        Vocabulary = self.env["spp.vocabulary"]
        core_vocabs = Vocabulary.search([("domain", "=", "core")])
        assert self.vocab in core_vocabs
        assert self.hier_vocab in core_vocabs

    def test_deprecated_codes_filtered(self):
        """Test that deprecated codes can be filtered."""
        VocabularyCode = self.env["spp.vocabulary.code"]
        active_codes = VocabularyCode.search(
            [
                ("vocabulary_id", "=", self.vocab.id),
                ("deprecated", "=", False),
            ]
        )
        assert self.code1 in active_codes
        assert self.code2 in active_codes
        assert self.code3 not in active_codes

    def test_all_codes_including_deprecated(self):
        """Test that deprecated codes can be included."""
        VocabularyCode = self.env["spp.vocabulary.code"]
        all_codes = VocabularyCode.search(
            [
                ("vocabulary_id", "=", self.vocab.id),
            ]
        )
        assert self.code3 in all_codes

    def test_codes_ordered_by_sequence(self):
        """Test codes are ordered by sequence."""
        VocabularyCode = self.env["spp.vocabulary.code"]
        codes = VocabularyCode.search(
            [("vocabulary_id", "=", self.vocab.id)],
            order="sequence, code",
        )
        codes_list = list(codes)
        assert codes_list[0] == self.code1
        assert codes_list[1] == self.code2
        assert codes_list[2] == self.code3

    def test_child_codes_by_parent(self):
        """Test filtering codes by parent."""
        VocabularyCode = self.env["spp.vocabulary.code"]
        children = VocabularyCode.search(
            [
                ("vocabulary_id", "=", self.hier_vocab.id),
                ("parent_id", "=", self.parent_code.id),
            ]
        )
        assert self.child_code in children
        assert len(children) == 1


class TestVocabularyAPIEndpoints(TransactionCase):
    """Test Vocabulary API router endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create or find test vocabularies (avoid duplicate namespace_uri)
        cls.vocab1 = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=1)
        if not cls.vocab1:
            cls.vocab1 = cls.env["spp.vocabulary"].create(
                {
                    "name": "Gender",
                    "namespace_uri": "urn:iso:std:iso:5218",
                    "domain": "core",
                    "is_hierarchical": False,
                    "description": "ISO 5218 Gender codes",
                    "version": "2004",
                }
            )
        gender_male = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab1.id), ("code", "=", "1")], limit=1
        )
        if not gender_male:
            cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab1.id,
                    "code": "1",
                    "display": "Male",
                    "sequence": 1,
                    "is_local": True,
                }
            )
        gender_female = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab1.id), ("code", "=", "2")], limit=1
        )
        if not gender_female:
            cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab1.id,
                    "code": "2",
                    "display": "Female",
                    "sequence": 2,
                    "is_local": True,
                }
            )

        cls.vocab2 = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:relationship")], limit=1
        )
        if not cls.vocab2:
            cls.vocab2 = cls.env["spp.vocabulary"].create(
                {
                    "name": "Relationship",
                    "namespace_uri": "urn:openspp:vocab:relationship",
                    "domain": "social_assistance",
                    "is_hierarchical": True,
                }
            )
        cls.parent = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab2.id), ("code", "=", "family")], limit=1
        )
        if not cls.parent:
            cls.parent = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab2.id,
                    "code": "family",
                    "display": "Family",
                    "is_local": True,
                }
            )
        cls.child = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", cls.vocab2.id), ("code", "=", "parent")], limit=1
        )
        if not cls.child:
            cls.child = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab2.id,
                    "code": "parent",
                    "display": "Parent",
                    "parent_id": cls.parent.id,
                    "is_local": True,
                }
            )

        # Lookup organization type (required for spp.api.client)
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        # Create API client with scope
        cls.org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": cls.partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "vocabulary",
                "action": "read",
            }
        )

        # Create client without scope
        cls.no_scope_partner = cls.env["res.partner"].create({"name": "No Scope"})
        cls.no_scope_client = cls.env["spp.api.client"].create(
            {
                "name": "No Scope Client",
                "partner_id": cls.no_scope_partner.id,
                "organization_type_id": cls.org_type_government.id,
            }
        )

    async def test_list_vocabularies_success(self):
        """Test GET /Vocabulary returns vocabulary list."""
        from ..routers.vocabulary import list_vocabularies

        result = await list_vocabularies(
            env=self.env,
            api_client=self.api_client,
            domain=None,
            _count=50,
            _offset=0,
        )

        assert result.total >= 2
        assert len(result.items) >= 2
        assert any(v.namespace_uri == "urn:iso:std:iso:5218" for v in result.items)

    async def test_list_vocabularies_with_domain_filter(self):
        """Test GET /Vocabulary?domain=core filters by domain."""
        from ..routers.vocabulary import list_vocabularies

        result = await list_vocabularies(
            env=self.env,
            api_client=self.api_client,
            domain="core",
            _count=50,
            _offset=0,
        )

        assert all(v.domain == "core" for v in result.items)

    async def test_list_vocabularies_pagination(self):
        """Test GET /Vocabulary respects pagination parameters."""
        from ..routers.vocabulary import list_vocabularies

        # Create more vocabularies
        for i in range(5):
            self.env["spp.vocabulary"].create(
                {
                    "name": f"Test Vocab {i}",
                    "namespace_uri": f"urn:test:vocab:{i}",
                    "domain": "core",
                }
            )

        result = await list_vocabularies(
            env=self.env,
            api_client=self.api_client,
            domain=None,
            _count=2,
            _offset=0,
        )

        assert len(result.items) == 2
        assert result.total >= 5

        # Test offset
        result2 = await list_vocabularies(
            env=self.env,
            api_client=self.api_client,
            domain=None,
            _count=2,
            _offset=2,
        )

        assert len(result2.items) <= 2
        # Items should be different
        if len(result2.items) > 0 and len(result.items) > 0:
            assert result2.items[0].namespace_uri != result.items[0].namespace_uri

    async def test_list_vocabularies_no_scope(self):
        """Test GET /Vocabulary without scope returns 403."""
        from ..routers.vocabulary import list_vocabularies

        with self.assertRaises(HTTPException) as cm:
            await list_vocabularies(
                env=self.env,
                api_client=self.no_scope_client,
                domain=None,
                _count=50,
                _offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_vocabulary_success(self):
        """Test GET /Vocabulary/{namespace_uri} returns vocabulary details."""
        from ..routers.vocabulary import get_vocabulary

        result = await get_vocabulary(
            namespace_uri="urn:iso:std:iso:5218",
            env=self.env,
            api_client=self.api_client,
        )

        assert result.name == "Gender"
        assert result.namespace_uri == "urn:iso:std:iso:5218"
        assert result.domain == "core"
        assert result.code_count == 2
        assert result.version == "2004"

    async def test_get_vocabulary_url_encoded(self):
        """Test GET /Vocabulary/{namespace_uri} handles URL encoding."""
        from ..routers.vocabulary import get_vocabulary

        # Test with URL-encoded namespace
        encoded_uri = quote("urn:iso:std:iso:5218", safe="")

        result = await get_vocabulary(
            namespace_uri=encoded_uri,
            env=self.env,
            api_client=self.api_client,
        )

        assert result.namespace_uri == "urn:iso:std:iso:5218"

    async def test_get_vocabulary_not_found(self):
        """Test GET /Vocabulary/{namespace_uri} returns 404 for non-existent vocab."""
        from ..routers.vocabulary import get_vocabulary

        with self.assertRaises(HTTPException) as cm:
            await get_vocabulary(
                namespace_uri="urn:nonexistent:vocab",
                env=self.env,
                api_client=self.api_client,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_vocabulary_no_scope(self):
        """Test GET /Vocabulary/{namespace_uri} without scope returns 403."""
        from ..routers.vocabulary import get_vocabulary

        with self.assertRaises(HTTPException) as cm:
            await get_vocabulary(
                namespace_uri="urn:iso:std:iso:5218",
                env=self.env,
                api_client=self.no_scope_client,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_vocabulary_codes_success(self):
        """Test GET /Vocabulary/{namespace_uri}/codes returns codes."""
        from ..routers.vocabulary import get_vocabulary_codes

        result = await get_vocabulary_codes(
            namespace_uri="urn:iso:std:iso:5218",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code=None,
            _count=100,
            _offset=0,
        )

        assert result.namespace_uri == "urn:iso:std:iso:5218"
        assert result.vocabulary_name == "Gender"
        assert result.total == 2
        assert len(result.items) == 2
        assert any(c.code == "1" and c.display == "Male" for c in result.items)
        assert any(c.code == "2" and c.display == "Female" for c in result.items)

    async def test_get_vocabulary_codes_with_deprecated(self):
        """Test GET /Vocabulary/{namespace_uri}/codes includes deprecated codes."""
        # Create deprecated code
        self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": self.vocab1.id,
                "code": "9",
                "display": "Not applicable",
                "deprecated": True,
            }
        )

        from ..routers.vocabulary import get_vocabulary_codes

        # Without deprecated
        result = await get_vocabulary_codes(
            namespace_uri="urn:iso:std:iso:5218",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code=None,
            _count=100,
            _offset=0,
        )

        assert not any(c.code == "9" for c in result.items)

        # With deprecated
        result = await get_vocabulary_codes(
            namespace_uri="urn:iso:std:iso:5218",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=True,
            parent_code=None,
            _count=100,
            _offset=0,
        )

        assert any(c.code == "9" and c.deprecated for c in result.items)

    async def test_get_vocabulary_codes_hierarchical(self):
        """Test GET /Vocabulary/{namespace_uri}/codes with parent_code filter."""
        from ..routers.vocabulary import get_vocabulary_codes

        # Get all codes
        result = await get_vocabulary_codes(
            namespace_uri="urn:openspp:vocab:relationship",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code=None,
            _count=100,
            _offset=0,
        )

        assert result.total == 2

        # Get only children of 'family'
        result = await get_vocabulary_codes(
            namespace_uri="urn:openspp:vocab:relationship",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code="family",
            _count=100,
            _offset=0,
        )

        assert result.total == 1
        assert result.items[0].code == "parent"
        assert result.items[0].parent_code == "family"
        assert result.items[0].level == 1

    async def test_get_vocabulary_codes_parent_not_found(self):
        """Test GET /Vocabulary/{namespace_uri}/codes with non-existent parent."""
        from ..routers.vocabulary import get_vocabulary_codes

        result = await get_vocabulary_codes(
            namespace_uri="urn:openspp:vocab:relationship",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code="nonexistent",
            _count=100,
            _offset=0,
        )

        # Should return empty result
        assert result.total == 0
        assert len(result.items) == 0

    async def test_get_vocabulary_codes_pagination(self):
        """Test GET /Vocabulary/{namespace_uri}/codes respects pagination."""
        # Create more codes
        for i in range(10):
            self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": self.vocab1.id,
                    "code": f"CODE{i}",
                    "display": f"Code {i}",
                    "sequence": 10 + i,
                }
            )

        from ..routers.vocabulary import get_vocabulary_codes

        result = await get_vocabulary_codes(
            namespace_uri="urn:iso:std:iso:5218",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code=None,
            _count=5,
            _offset=0,
        )

        assert len(result.items) == 5
        assert result.total >= 10

        # Test offset
        result2 = await get_vocabulary_codes(
            namespace_uri="urn:iso:std:iso:5218",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code=None,
            _count=5,
            _offset=5,
        )

        assert len(result2.items) <= 5
        # Items should be different (ordered by sequence, code)
        if len(result2.items) > 0 and len(result.items) > 0:
            assert result2.items[0].code != result.items[0].code

    async def test_get_vocabulary_codes_not_found(self):
        """Test GET /Vocabulary/{namespace_uri}/codes returns 404 for non-existent vocab."""
        from ..routers.vocabulary import get_vocabulary_codes

        with self.assertRaises(HTTPException) as cm:
            await get_vocabulary_codes(
                namespace_uri="urn:nonexistent:vocab",
                env=self.env,
                api_client=self.api_client,
                include_deprecated=False,
                parent_code=None,
                _count=100,
                _offset=0,
            )

        assert cm.exception.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_vocabulary_codes_no_scope(self):
        """Test GET /Vocabulary/{namespace_uri}/codes without scope returns 403."""
        from ..routers.vocabulary import get_vocabulary_codes

        with self.assertRaises(HTTPException) as cm:
            await get_vocabulary_codes(
                namespace_uri="urn:iso:std:iso:5218",
                env=self.env,
                api_client=self.no_scope_client,
                include_deprecated=False,
                parent_code=None,
                _count=100,
                _offset=0,
            )

        assert cm.exception.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_vocabulary_codes_empty_result(self):
        """Test GET /Vocabulary/{namespace_uri}/codes handles empty vocabularies."""
        # Create empty vocabulary
        self.env["spp.vocabulary"].create(
            {
                "name": "Empty Vocabulary",
                "namespace_uri": "urn:test:empty",
                "domain": "core",
            }
        )

        from ..routers.vocabulary import get_vocabulary_codes

        result = await get_vocabulary_codes(
            namespace_uri="urn:test:empty",
            env=self.env,
            api_client=self.api_client,
            include_deprecated=False,
            parent_code=None,
            _count=100,
            _offset=0,
        )

        assert result.total == 0
        assert len(result.items) == 0
        assert result.vocabulary_name == "Empty Vocabulary"

    def test_vocabulary_router_included(self):
        """Test that vocabulary router is included in API V2."""
        endpoint = self.env["fastapi.endpoint"].search(
            [("app", "=", "api_v2")],
            limit=1,
        )
        if not endpoint:
            self.skipTest("No API V2 endpoint found")

        routers = endpoint._get_fastapi_routers()
        router_prefixes = [r.prefix for r in routers]
        self.assertIn("/Vocabulary", router_prefixes)
