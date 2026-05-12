# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for SearchService"""

from datetime import date

from ..services.search_service import SearchService
from .common import ApiV2TestCase


class TestSearchService(ApiV2TestCase):
    """Test SearchService functionality"""

    def setUp(self):
        super().setUp()
        self.service = SearchService(self.env)

        # Create test individuals
        self.ind1 = self.create_test_individual(
            name="Alice Johnson",
            given_name="Alice",
            family_name="Johnson",
            identifier_value="IND-001",
            gender_id=self.gender_female.id,
            birthdate=date(1990, 1, 15),
            city="New York",
        )
        self.ind2 = self.create_test_individual(
            name="Bob Smith",
            given_name="Bob",
            family_name="Smith",
            identifier_value="IND-002",
            gender_id=self.gender_male.id,
            birthdate=date(1985, 6, 20),
            city="Los Angeles",
        )
        self.ind3 = self.create_test_individual(
            name="Alice Brown",
            given_name="Alice",
            family_name="Brown",
            identifier_value="IND-003",
            gender_id=self.gender_female.id,
            birthdate=date(1992, 3, 10),
            city="Chicago",
        )

    def test_search_individuals_no_params(self):
        """Search with no params returns all individuals"""
        records, total = self.service.search_individuals({})

        self.assertGreaterEqual(total, 3)
        self.assertGreaterEqual(len(records), 3)

    def test_search_by_name(self):
        """Search by name (contains)"""
        records, total = self.service.search_individuals({"name": "Alice"})

        self.assertEqual(total, 2)
        self.assertEqual(len(records), 2)
        names = [r.name for r in records]
        self.assertIn("JOHNSON, ALICE", names)
        self.assertIn("BROWN, ALICE", names)

    def test_parse_identifier_param(self):
        """identifier=system|value creates proper domain"""
        domain = self.service._parse_identifier_param("urn:openspp:vocab:id-type#test_national_id|IND-001")

        self.assertEqual(len(domain), 2)
        self.assertIn(
            (
                "reg_ids.id_type_id.uri",
                "=",
                "urn:openspp:vocab:id-type#test_national_id",
            ),
            domain,
        )
        self.assertIn(("reg_ids.value", "=", "IND-001"), domain)

    def test_search_by_identifier(self):
        """Search by identifier finds exact match"""
        records, total = self.service.search_individuals(
            {"identifier": "urn:openspp:vocab:id-type#test_national_id|IND-002"}
        )

        self.assertEqual(total, 1)
        self.assertEqual(records[0], self.ind2)

    def test_parse_date_prefixes_eq(self):
        """Date with no prefix or 'eq' prefix is exact match"""
        domain = self.service._parse_date_param("birthdate", "1990-01-15")

        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][1], "=")
        self.assertEqual(domain[0][2], date(1990, 1, 15))

    def test_parse_date_prefixes_ge(self):
        """'ge' prefix creates >= operator"""
        domain = self.service._parse_date_param("birthdate", "ge1990-01-01")

        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][1], ">=")
        self.assertEqual(domain[0][2], date(1990, 1, 1))

    def test_parse_date_prefixes_le(self):
        """'le' prefix creates <= operator"""
        domain = self.service._parse_date_param("birthdate", "le1990-12-31")

        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][1], "<=")
        self.assertEqual(domain[0][2], date(1990, 12, 31))

    def test_parse_date_prefixes_gt(self):
        """'gt' prefix creates > operator"""
        domain = self.service._parse_date_param("birthdate", "gt1990-01-01")

        self.assertEqual(domain[0][1], ">")

    def test_parse_date_prefixes_lt(self):
        """'lt' prefix creates < operator"""
        domain = self.service._parse_date_param("birthdate", "lt1990-01-01")

        self.assertEqual(domain[0][1], "<")

    def test_search_by_birthdate_exact(self):
        """Search by exact birthdate"""
        records, total = self.service.search_individuals({"birthdate": "1990-01-15"})

        self.assertEqual(total, 1)
        self.assertEqual(records[0], self.ind1)

    def test_search_by_birthdate_range(self):
        """Search by birthdate range using ge and le"""
        # Create search params for individuals born in 1990s
        records, total = self.service.search_individuals({"birthdate": "ge1990-01-01"})

        # Should find ind1 (1990) and ind3 (1992), but not ind2 (1985)
        self.assertGreaterEqual(total, 2)
        ids = records.ids
        self.assertIn(self.ind1.id, ids)
        self.assertIn(self.ind3.id, ids)
        self.assertNotIn(self.ind2.id, ids)

    def test_parse_gender_with_vocabulary(self):
        """Gender search uses vocabulary lookup"""
        domain = self.service._parse_gender_param("urn:iso:std:iso:5218|2")

        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][0], "gender_id")
        self.assertEqual(domain[0][1], "=")
        self.assertEqual(domain[0][2], self.gender_female.id)

    def test_search_by_gender(self):
        """Search by gender code"""
        records, total = self.service.search_individuals(
            {"gender": "urn:iso:std:iso:5218|2"}  # Female
        )

        self.assertGreaterEqual(total, 2)
        ids = records.ids
        self.assertIn(self.ind1.id, ids)
        self.assertIn(self.ind3.id, ids)
        self.assertNotIn(self.ind2.id, ids)

    def test_search_by_address(self):
        """Search by address (city)"""
        records, total = self.service.search_individuals({"address": "Chicago"})

        self.assertEqual(total, 1)
        self.assertEqual(records[0], self.ind3)

    def test_search_pagination(self):
        """Pagination with _count and _offset"""
        # Search with limit
        records, total = self.service.search_individuals({"_count": 2})

        self.assertGreaterEqual(total, 3)
        self.assertEqual(len(records), 2)

        # Search with offset
        records2, total2 = self.service.search_individuals({"_count": 2, "_offset": 2})

        self.assertEqual(total2, total)
        self.assertGreaterEqual(len(records2), 1)
        # Records should be different
        self.assertNotEqual(records[0].id, records2[0].id)

    def test_search_max_count_limit(self):
        """_count is capped at 100"""
        # Request 200 but should get max 100
        params = {"_count": 200}
        records, total = self.service.search_individuals(params)

        # Max should be 100
        self.assertLessEqual(len(records), 100)

    def test_parse_sort_param_ascending(self):
        """Sort parameter without prefix is ascending"""
        order = self.service._parse_sort_param("name")

        self.assertEqual(order, "name ASC")

    def test_parse_sort_param_descending(self):
        """Sort parameter with - prefix is descending"""
        order = self.service._parse_sort_param("-birthDate")

        self.assertEqual(order, "birthdate DESC")

    def test_search_with_sort(self):
        """Search results are sorted"""
        records, total = self.service.search_individuals({"_sort": "name"})

        # Should be sorted by name
        names = [r.name for r in records[:3]]
        self.assertEqual(names, sorted(names))

    def test_search_combined_params(self):
        """Multiple search params are combined"""
        records, total = self.service.search_individuals(
            {
                "name": "Alice",
                "gender": "urn:iso:std:iso:5218|2",
            }
        )

        # Should find Alice Johnson and Alice Brown (both female)
        self.assertEqual(total, 2)
        for record in records:
            self.assertIn("ALICE", record.name)
            self.assertEqual(record.gender_id, self.gender_female)


class TestSearchGroups(ApiV2TestCase):
    """Test group search functionality"""

    def setUp(self):
        super().setUp()
        self.service = SearchService(self.env)

        # Create test individuals and groups
        self.ind1 = self.create_test_individual(identifier_value="IND-001")
        self.ind2 = self.create_test_individual(identifier_value="IND-002")

        self.group1 = self.create_test_group(
            name="Johnson Household",
            identifier_value="HH-001",
            members=[(self.ind1, self.relationship_head)],
        )
        self.group2 = self.create_test_group(
            name="Smith Family",
            identifier_value="HH-002",
            members=[(self.ind2, self.relationship_head)],
        )

    def test_search_groups_by_name(self):
        """Search groups by name"""
        records, total = self.service.search_groups({"name": "Johnson"})

        self.assertEqual(total, 1)
        self.assertEqual(records[0], self.group1)

    def test_search_groups_by_identifier(self):
        """Search groups by identifier"""
        # Groups use household-id namespace, not national-id
        records, total = self.service.search_groups(
            {"identifier": "urn:openspp:vocab:id-type#test_household_id|HH-002"}
        )

        self.assertEqual(total, 1)
        self.assertEqual(records[0], self.group2)

    def test_search_groups_by_member(self):
        """Search groups by member reference"""
        records, total = self.service.search_groups(
            {"member": "Individual/urn:openspp:vocab:id-type#test_national_id|IND-001"}
        )

        self.assertGreaterEqual(total, 1)
        self.assertIn(self.group1.id, records.ids)

    def test_search_groups_pagination(self):
        """Group search supports pagination"""
        records, total = self.service.search_groups({"_count": 1})

        self.assertGreaterEqual(total, 2)
        self.assertEqual(len(records), 1)
