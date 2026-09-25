# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for parsing and executing search queries"""

import logging
from datetime import datetime
from typing import Any

from odoo.api import Environment
from odoo.osv import expression

_logger = logging.getLogger(__name__)

# A filter that names nothing (unknown group, role, gender, member) must
# narrow the result to nothing, never drop out and widen it.
MATCH_NOTHING = [("id", "=", 0)]


class InvalidSearchParam(ValueError):
    """A search parameter is malformed; the API answers 400."""


class SearchService:
    """Service for search parameter parsing and execution"""

    def __init__(self, env: Environment):
        self.env = env

    def search_individuals(self, params: dict[str, Any]) -> tuple[list, int]:
        """
        Search for individuals based on query parameters.

        Supported params:
        - identifier: system|value
        - name: string (contains)
        - birthdate: date with prefix (ge, le, eq)
        - gender: system|code
        - address: string
        - group: Group reference (system|value) or "none" for orphans
        - membership-role: Role code for membership filtering
        - _lastUpdated: date with prefix
        - _count: int (page size)
        - _lastId: int (cursor-based pagination)
        - _sort: field name (prefix with - for descending)

        Returns:
            Tuple of (records, total_count)
        """
        domain = [("is_registrant", "=", True), ("is_group", "=", False)]

        # Parse search parameters
        if params.get("identifier"):
            domain.extend(self._parse_identifier_param(params["identifier"]))

        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))

        if params.get("birthdate"):
            domain.extend(self._parse_date_param("birthdate", params["birthdate"]))

        if params.get("gender"):
            domain.extend(self._parse_gender_param(params["gender"]))

        if params.get("address"):
            # Search in street, city, or state
            addr_domain = [
                "|",
                "|",
                ("street", "ilike", params["address"]),
                ("city", "ilike", params["address"]),
                ("state_id.name", "ilike", params["address"]),
            ]
            domain.extend(addr_domain)

        if params.get("group"):
            domain.extend(self._parse_group_param(params["group"]))

        if params.get("membership-role"):
            domain.extend(self._parse_membership_role_param(params["membership-role"]))

        if params.get("_lastUpdated"):
            domain.extend(self._parse_date_param("write_date", params["_lastUpdated"]))

        # Execute search with sudo() to access registry.id via domain
        Partner = self.env["res.partner"]

        # Get total count (before cursor filter)
        total = Partner.sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context

        # Apply cursor-based pagination
        last_id = params.get("_lastId")
        if last_id is not None:
            try:
                last_id_int = int(last_id)
                domain = expression.AND([domain, [("id", ">", last_id_int)]])
            except (ValueError, TypeError):
                _logger.warning("Invalid _lastId parameter: %s, skipping cursor pagination", last_id)

        # Apply pagination
        limit = min(int(params.get("_count", 20)), 100)  # Max 100
        offset = int(params.get("_offset", 0))

        # Apply sorting - always include id for consistent cursor pagination
        order = self._parse_sort_param(params.get("_sort"))
        if "id" not in order.lower():
            order = f"{order}, id"

        # nosemgrep: odoo-sudo-without-context
        records = Partner.sudo().search(domain, limit=limit, offset=offset, order=order)

        return records, total

    def search_groups(self, params: dict[str, Any]) -> tuple[list, int]:
        """
        Search for groups based on query parameters.

        Supported params:
        - identifier: system|value
        - name: string
        - type: household/family/organization/other
        - member: Individual reference
        - _count: int
        - _lastId: int (cursor-based pagination)

        Returns:
            Tuple of (records, total_count)
        """
        domain = [("is_registrant", "=", True), ("is_group", "=", True)]

        if params.get("identifier"):
            domain.extend(self._parse_identifier_param(params["identifier"]))

        if params.get("name"):
            domain.append(("name", "ilike", params["name"]))

        if params.get("member"):
            domain.extend(self._parse_member_param(params["member"]))

        # Execute search with sudo() to access registry.id via domain
        Partner = self.env["res.partner"]
        total = Partner.sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context

        # Apply cursor-based pagination
        last_id = params.get("_lastId")
        if last_id is not None:
            try:
                last_id_int = int(last_id)
                domain = expression.AND([domain, [("id", ">", last_id_int)]])
            except (ValueError, TypeError):
                _logger.warning("Invalid _lastId parameter: %s, skipping cursor pagination", last_id)

        limit = min(int(params.get("_count", 20)), 100)
        order = self._parse_sort_param(params.get("_sort"))
        if "id" not in order.lower():
            order = f"{order}, id"

        records = Partner.sudo().search(domain, limit=limit, order=order)  # nosemgrep: odoo-sudo-without-context

        return records, total

    def _parse_identifier_param(self, identifier: str) -> list:
        """
        Parse identifier parameter (format: system|value).

        Returns Odoo domain for identifier search.
        """
        if "|" not in identifier:
            raise InvalidSearchParam("Invalid identifier format. Expected: {system}|{value}")

        system, value = identifier.split("|", 1)

        # Search via registry.id with id_type_id.uri (full code URI)
        # Format: urn:openspp:vocab:id-type#national_id|VALUE
        # "any" keeps both conditions on the same registry ID; two dotted
        # leaves would match a system from one ID and a value from another.
        return [
            (
                "reg_ids",
                "any",
                [
                    ("id_type_id.uri", "=", system),
                    ("value", "=", value),
                ],
            )
        ]

    def _parse_date_param(self, field: str, value: str) -> list:
        """
        Parse date parameter with prefix (ge, le, eq, gt, lt, ne).

        Examples:
        - "2024-01-01" -> exact match
        - "ge2024-01-01" -> >= 2024-01-01
        - "le2024-12-31" -> <= 2024-12-31
        """
        prefixes = {
            "ge": ">=",
            "le": "<=",
            "gt": ">",
            "lt": "<",
            "eq": "=",
            "ne": "!=",
        }

        # Check for prefix
        operator = "="
        date_str = value

        for prefix, op in prefixes.items():
            if value.startswith(prefix):
                operator = op
                date_str = value[len(prefix) :]
                break

        # Parse date
        try:
            # Try to parse as date
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return [(field, operator, parsed_date)]
        except ValueError as e:
            raise InvalidSearchParam(
                f"Invalid date for {field}: expected an optional prefix (eq, ne, gt, ge, lt, le) and YYYY-MM-DD"
            ) from e

    def _parse_gender_param(self, gender: str) -> list:
        """
        Parse gender parameter (format: system|code).

        Returns domain for gender_id search.
        """
        if "|" not in gender:
            raise InvalidSearchParam("Invalid gender format. Expected: {system}|{code}")

        system, code = gender.split("|", 1)

        # Find gender code
        gender_code = (
            self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("namespace_uri", "=", system),
                    ("code", "=", code),
                ],
                limit=1,
            )
        )

        if gender_code:
            return [("gender_id", "=", gender_code.id)]

        return MATCH_NOTHING

    def _parse_group_param(self, group: str) -> list:
        """
        Parse group parameter.

        Special value "none" returns individuals not in any active group.
        Otherwise expects format: system|value

        Returns domain for group membership search.
        """
        # Special case: find orphan individuals (not in any group)
        if group.lower() == "none":
            # Find all individuals with active memberships
            # nosemgrep: odoo-sudo-without-context
            active_memberships = self.env["spp.group.membership"].sudo().search([("is_ended", "=", False)])
            membered_individual_ids = active_memberships.mapped("individual.id")
            return [("id", "not in", membered_individual_ids)]

        # Standard case: filter by specific group
        if "|" not in group:
            raise InvalidSearchParam('Invalid group format. Expected: {system}|{value} or "none"')

        system, value = group.split("|", 1)

        # Find group by identifier
        # Use id_type_id.uri (full URI with code) instead of namespace_uri
        # (which only contains the vocabulary namespace)
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system),
                    ("value", "=", value),
                ],
                limit=1,
            )
        )

        if not reg_id or not reg_id.partner_id.is_group:
            return MATCH_NOTHING

        # Find individuals with an active membership in this group; "any"
        # keeps both conditions on the same membership row
        return [
            (
                "individual_membership_ids",
                "any",
                [
                    ("group", "=", reg_id.partner_id.id),
                    ("is_ended", "=", False),
                ],
            )
        ]

    def _parse_membership_role_param(self, role: str) -> list:
        """
        Parse membership-role parameter (format: code).

        Returns domain for membership role search.
        """
        if not role:
            return []

        # Find role code in vocabulary
        role_code = (
            self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("namespace_uri", "=", "urn:openspp:vocab:group-membership-type"),
                    ("code", "=", role),
                ],
                limit=1,
            )
        )

        if not role_code:
            return MATCH_NOTHING

        # Find individuals holding this role on an active membership; "any"
        # keeps both conditions on the same membership row
        return [
            (
                "individual_membership_ids",
                "any",
                [
                    ("membership_type_ids", "in", role_code.id),
                    ("is_ended", "=", False),
                ],
            )
        ]

    def _parse_member_param(self, member: str) -> list:
        """
        Parse the groups ``member`` parameter (format: Individual/{system}|{value}).

        Returns domain for groups with an active membership of that individual.
        """
        ident_str = member.removeprefix("Individual/")
        if ident_str == member or "|" not in ident_str:
            raise InvalidSearchParam("Invalid member format. Expected: Individual/{system}|{value}")

        system, value = ident_str.split("|", 1)

        # Use id_type_id.uri (full URI with code) instead of namespace_uri
        # (which only contains the vocabulary namespace)
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system),
                    ("value", "=", value),
                ],
                limit=1,
            )
        )
        if not reg_id:
            return MATCH_NOTHING

        return [
            (
                "group_membership_ids",
                "any",
                [
                    ("individual", "=", reg_id.partner_id.id),
                    ("is_ended", "=", False),
                ],
            )
        ]

    def _parse_sort_param(self, sort: str | None) -> str:
        """
        Parse sort parameter.

        Format: field or -field (descending)

        Returns Odoo order string.
        """
        if not sort:
            return "name"  # Default sort

        # Map API field names to Odoo field names
        field_map = {
            "name": "name",
            "birthDate": "birthdate",
            "lastUpdated": "write_date",
        }

        if sort.startswith("-"):
            field = sort[1:]
            direction = "DESC"
        else:
            field = sort
            direction = "ASC"

        odoo_field = field_map.get(field, "name")
        return f"{odoo_field} {direction}"
