# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Social Registry Search Service - Maps Odoo partners to DCI schemas."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from odoo import _
from odoo.api import Environment
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.spp_dci.schemas.common import Address, Identifier, Name
from odoo.addons.spp_dci.schemas.constants import SearchStatusReasonCode
from odoo.addons.spp_dci.schemas.group import Group, Member
from odoo.addons.spp_dci.schemas.person import Person
from odoo.addons.spp_dci.schemas.search import (
    Pagination,
    SearchRequest,
    SearchRequestItem,
    SearchResponse,
    SearchResponseData,
    SearchResponseItem,
)
from odoo.addons.spp_dci.services import DCIErrorMessages

_logger = logging.getLogger(__name__)


class DCISocialSearchService:
    """Service for DCI Social Registry search operations.

    Integrates with spp_api_v2 consent and vocabulary services:
    - DCIConsentAdapter: Consent-based data filtering
    - DCIVocabularyAdapter: Code system mapping
    """

    def __init__(self, env: Environment, sender_registry=None):
        """Initialize service with Odoo environment.

        Args:
            env: Odoo environment
            sender_registry: spp.dci.sender.registry record for consent checks
        """
        self.env = env
        self.sender = sender_registry
        self._consent_adapter = None
        self._vocabulary_adapter = None

    @property
    def consent_adapter(self):
        """Lazy-load consent adapter."""
        if self._consent_adapter is None:
            try:
                from odoo.addons.spp_dci_server.services import DCIConsentAdapter

                self._consent_adapter = DCIConsentAdapter(self.env, self.sender)
            except ImportError:
                _logger.debug("DCIConsentAdapter not available")
        return self._consent_adapter

    @property
    def vocabulary_adapter(self):
        """Lazy-load vocabulary adapter."""
        if self._vocabulary_adapter is None:
            try:
                from odoo.addons.spp_dci_server.services import DCIVocabularyAdapter

                self._vocabulary_adapter = DCIVocabularyAdapter(self.env)
            except ImportError:
                _logger.debug("DCIVocabularyAdapter not available")
        return self._vocabulary_adapter

    def set_sender(self, sender_registry):
        """Set the DCI sender for consent checks.

        Args:
            sender_registry: spp.dci.sender.registry record
        """
        self.sender = sender_registry
        if self._consent_adapter:
            self._consent_adapter.set_sender(sender_registry)

    def execute_search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute DCI search request and return response.

        Args:
            request: DCI SearchRequest with transaction_id and search_request items

        Returns:
            SearchResponse with matching records
        """
        response_items = []

        for search_req in request.search_request:
            try:
                response_item = self._process_search_item(search_req)
                response_items.append(response_item)
            except Exception:
                _logger.exception("Error processing search item %s", search_req.reference_id)
                # Return error response for this item
                response_items.append(
                    SearchResponseItem(
                        reference_id=search_req.reference_id,
                        timestamp=datetime.now(UTC),
                        status="rjct",
                        status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                        status_reason_message=DCIErrorMessages.PROCESSING_ERROR,
                        data=None,
                        pagination=None,
                    )
                )

        # Use correlation_id from request if present, otherwise generate new one
        correlation_id = getattr(request, "correlation_id", None) or str(uuid.uuid4())
        return SearchResponse(
            transaction_id=request.transaction_id,
            correlation_id=correlation_id,
            search_response=response_items,
        )

    def _process_search_item(self, search_req: SearchRequestItem) -> SearchResponseItem:
        """
        Process a single search request item.

        Args:
            search_req: SearchRequestItem with criteria

        Returns:
            SearchResponseItem with results or error
        """
        criteria = search_req.search_criteria

        # Default reg_type to SOCIAL_REGISTRY if not provided (optional per SPDCI spec)
        reg_type = criteria.reg_type or "SOCIAL_REGISTRY"

        # Validate registry type
        if reg_type != "SOCIAL_REGISTRY":
            return SearchResponseItem(
                reference_id=search_req.reference_id,
                timestamp=datetime.now(UTC),
                status="rjct",
                status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                status_reason_message=f"Expected SOCIAL_REGISTRY, got {reg_type}",
                data=None,
                pagination=None,
            )

        # Build Odoo domain from query
        try:
            domain = self._build_domain(criteria)
        except Exception:
            _logger.exception("Query parsing failed for reference_id %s", search_req.reference_id)
            return SearchResponseItem(
                reference_id=search_req.reference_id,
                timestamp=datetime.now(UTC),
                status="rjct",
                status_reason_code=SearchStatusReasonCode.FILTER_INVALID.value,
                status_reason_message=DCIErrorMessages.INVALID_QUERY,
                data=None,
                pagination=None,
            )

        # Apply consent filtering if available
        domain = self._apply_consent_filter(domain)

        # Get pagination parameters
        page_size = criteria.pagination.page_size if criteria.pagination else 20
        page_number = criteria.pagination.page_number if criteria.pagination else 1

        # OpenSPP extension: cursor-based pagination
        # When cursor is provided, use keyset pagination (more efficient for large datasets)
        cursor = getattr(criteria.pagination, "cursor", None) if criteria.pagination else None
        use_cursor = cursor is not None

        if use_cursor:
            # Decode cursor to get last ID
            try:
                last_id = self._decode_cursor(cursor)
                # Add keyset condition: id > last_id
                domain = domain + [("id", ">", last_id)]
                offset = 0  # No offset needed with keyset pagination
            except (ValueError, TypeError):
                _logger.warning("Invalid cursor: %s, falling back to page_number", cursor)
                use_cursor = False
                offset = (page_number - 1) * page_size
        else:
            offset = (page_number - 1) * page_size

        # Execute search
        # Only registry viewers/managers are allowed to expose Social Registry
        # data via the DCI server.
        if not self.env.user.has_group("spp_registry.group_registry_viewer"):
            raise AccessError(
                _(
                    "You do not have permission to perform Social Registry DCI searches. "
                    "Contact a registry administrator."
                )
            )

        Partner = self.env[
            "res.partner"
        ].sudo()  # nosemgrep: odoo-sudo-on-sensitive-models - Read-only Social Registry search restricted to spp_registry.group_registry_viewer; DCI output uses schema objects, not raw partner records.
        total_count = Partner.search_count(domain)
        # NOTE: Offset-based pagination required by SPDCI specification (PaginationRequest schema)
        # The DCI spec mandates page_number/page_size pagination, not cursor-based last_id
        # Always order by id for consistent cursor pagination (OpenSPP extension)
        partners = Partner.search(domain, limit=page_size, offset=offset, order="id asc")  # noqa: openspp-pagination

        # Convert to DCI records
        reg_records = []
        for partner in partners:
            try:
                if partner.is_group:
                    dci_record = self._to_dci_group(partner)
                else:
                    dci_record = self._to_dci_person(partner)
                # Convert Pydantic model to dict for response
                # Use mode="json" to ensure datetime objects are serialized as ISO strings
                reg_records.append(dci_record.model_dump(mode="json", by_alias=True, exclude_none=True))
            except Exception as e:
                _logger.warning("Failed to convert partner %s to DCI: %s", partner.id, str(e))
                continue

        # Determine record type
        if partners and partners[0].is_group:
            reg_record_type = "GROUP"
        else:
            reg_record_type = "PERSON"

        # Generate next_cursor if there are more records
        next_cursor = None
        if partners and len(partners) == page_size:
            # Check if there are more records
            last_partner_id = partners[-1].id
            has_more = Partner.search_count(domain + [("id", ">", last_partner_id)]) > 0
            if has_more:
                next_cursor = self._encode_cursor(last_partner_id)

        return SearchResponseItem(
            reference_id=search_req.reference_id,
            timestamp=datetime.now(UTC),
            status="succ",
            data=SearchResponseData(
                reg_type="SOCIAL_REGISTRY",
                reg_event_type=criteria.reg_event_type,
                reg_record_type=reg_record_type,
                reg_records=reg_records,
            ),
            pagination=Pagination(
                page_size=page_size,
                page_number=page_number,
                total_count=total_count,
                next_cursor=next_cursor,
            ),
            locale=search_req.locale,
        )

    def _build_domain(self, criteria) -> list:
        """
        Build Odoo domain from DCI search criteria.

        Args:
            criteria: SearchCriteria object

        Returns:
            Odoo domain list
        """
        # Base domain - only registrants
        domain = [("is_registrant", "=", True)]

        query_type = criteria.query_type.lower()

        if query_type == "idtype-value":
            # Simple identifier lookup
            query = criteria.query
            if isinstance(query, dict):
                id_type = query.get("type")
                id_value = query.get("value")
            else:
                id_type = query.type
                id_value = query.value

            # Match by identifier type and value
            # Note: Assuming id_type is a namespace URI
            domain.extend(
                [
                    ("reg_ids.id_type_id.namespace_uri", "=", id_type),
                    ("reg_ids.value", "=", id_value),
                ]
            )

        elif query_type == "expression":
            # Complex expression query
            expression_domain = self._parse_expression(criteria.query)
            domain.extend(expression_domain)

        elif query_type == "predicate":
            # Predicate queries use CEL expressions
            predicate_domain = self._parse_predicate(criteria.query)
            domain.extend(predicate_domain)

        elif query_type == "graphql":
            _logger.warning("GraphQL query type not yet implemented")
            raise ValueError("GraphQL query type not supported")

        else:
            raise ValueError(f"Unknown query_type: {query_type}")

        return domain

    def _parse_predicate(self, predicate) -> list:
        """
        Parse DCI predicate query using CEL expression service.

        Predicate queries use CEL (Common Expression Language) syntax to
        express complex filtering logic. The expression is compiled to
        an Odoo domain using the spp.cel.service.

        Example predicate:
            "age_years(r.birthdate) >= 18 && r.gender == 'female'"

        Args:
            predicate: CEL expression string

        Returns:
            Odoo domain list
        """
        if not predicate:
            return []

        # Get expression string from predicate object or dict
        if isinstance(predicate, dict):
            expression = predicate.get("expression") or predicate.get("value", "")
        elif hasattr(predicate, "expression"):
            expression = predicate.expression
        elif hasattr(predicate, "value"):
            expression = predicate.value
        elif isinstance(predicate, str):
            expression = predicate
        else:
            raise ValueError(f"Invalid predicate format: {type(predicate)}")

        if not expression or not expression.strip():
            return []

        # Use CEL service to compile expression to domain
        cel_service = self.env["spp.cel.service"]

        # Determine profile based on query context (individuals vs groups)
        # Default to registry_individuals for Social Registry
        profile = "registry_individuals"

        result = cel_service.compile_expression(
            expression,
            profile=profile,
            base_domain=[],  # No additional base domain
            limit=0,  # We only need the domain, not IDs
        )

        if not result.get("valid"):
            error_msg = result.get("error", "Unknown CEL compilation error")
            _logger.warning("CEL predicate compilation failed: %s", error_msg)
            raise ValueError(f"Invalid predicate expression: {error_msg}")

        return result.get("domain", [])

    def _parse_expression(self, expression) -> list:
        """
        Parse DCI expression into Odoo domain.

        Expression format:
        {
            "seq": [
                {"attribute": "name", "operator": "=", "value": "John"},
                {"attribute": "age", "operator": ">=", "value": 18}
            ],
            "or": [
                {...another expression...}
            ]
        }

        Args:
            expression: Expression object or dict

        Returns:
            Odoo domain list
        """
        domain = []

        if isinstance(expression, dict):
            seq = expression.get("seq", [])
            or_exprs = expression.get("or", [])
        else:
            seq = expression.seq or []
            or_exprs = expression.or_ or []

        # Process sequential conditions (AND logic)
        for condition in seq:
            if isinstance(condition, dict):
                attr = condition.get("attribute")
                op = condition.get("operator")
                val = condition.get("value")
            else:
                attr = condition.attribute
                op = condition.operator
                val = condition.value

            domain_item = self._condition_to_domain(attr, op, val)
            domain.append(domain_item)

        # Process OR expressions
        if or_exprs:
            or_domain = []
            for or_expr in or_exprs:
                sub_domain = self._parse_expression(or_expr)
                if sub_domain:
                    # Add OR operator before each alternative (except first)
                    if or_domain:
                        or_domain.append("|")
                    or_domain.extend(sub_domain)
            domain.extend(or_domain)

        return domain

    def _condition_to_domain(self, attribute: str, operator: str, value: Any) -> tuple:
        """
        Convert DCI condition to Odoo domain tuple.

        Maps DCI attribute names to Odoo field names.

        Args:
            attribute: DCI attribute name
            operator: Comparison operator (=, >, <, >=, <=, in, contains)
            value: Value to compare

        Returns:
            Odoo domain tuple (field, operator, value)
        """
        # Map DCI attributes to Odoo fields
        attribute_map = {
            "name": "name",
            "given_name": "given_name",
            "surname": "family_name",
            "family_name": "family_name",
            "birth_date": "birthdate",
            "birthdate": "birthdate",
            "sex": "gender",
            "gender": "gender",
            "phone": "phone",
            "email": "email",
            "city": "city",
            "locality": "city",
            "region": "state_id.name",
            "country": "country_id.code",
        }

        field = attribute_map.get(attribute, attribute)

        # Map DCI operators to Odoo operators
        operator_map = {
            "=": "=",
            "==": "=",
            ">": ">",
            "<": "<",
            ">=": ">=",
            "<=": "<=",
            "in": "in",
            "contains": "ilike",
            "like": "ilike",
        }

        odoo_op = operator_map.get(operator, operator)

        return (field, odoo_op, value)

    def _apply_consent_filter(self, domain: list) -> list:
        """
        Apply consent filtering to domain using DCIConsentAdapter.

        Uses the consent adapter to build a domain that filters to registrants
        with valid consent for the current DCI sender.

        Args:
            domain: Existing Odoo domain

        Returns:
            Domain with consent filter added (or original if consent not available)
        """
        # Use consent adapter if available
        if self.consent_adapter:
            return self.consent_adapter.build_consented_domain(domain)

        # Fallback: Check if consent model exists
        if "spp.consent" not in self.env:
            return domain

        # Basic fallback - only include partners with active consent
        domain.append(("consent_ids.status", "=", "active"))

        return domain

    def _to_dci_person(self, partner) -> Person:
        """
        Convert Odoo res.partner (individual) to DCI Person schema.

        Args:
            partner: res.partner record (is_group=False)

        Returns:
            DCI Person object
        """
        # Build identifiers
        identifiers = []
        for reg_id in partner.reg_ids:
            if reg_id.id_type_id and reg_id.id_type_id.namespace_uri and reg_id.value:
                identifiers.append(
                    Identifier(
                        identifier_type=reg_id.id_type_id.namespace_uri,
                        identifier_value=reg_id.value,
                    )
                )

        if not identifiers:
            raise ValidationError(f"Partner {partner.name} has no valid identifiers")

        # Build name
        name = None
        if partner.given_name or partner.family_name:
            name = Name(
                given_name=partner.given_name or "",
                surname=partner.family_name or "",
                second_name=partner.addl_name or None,
                prefix=getattr(partner, "name_prefix", None),
                suffix=getattr(partner, "name_suffix", None),
            )

        # Map gender
        sex = self._map_gender(partner)

        # Build addresses
        addresses = []
        if partner.street or partner.city:
            addr = Address(
                address_line_1=partner.street or None,
                address_line_2=partner.street2 or None,
                locality=partner.city or None,
                region_code=partner.state_id.code if partner.state_id else None,
                postal_code=partner.zip or None,
                country_code=partner.country_id.code if partner.country_id else None,
            )
            addresses.append(addr)

        # Build phone numbers
        phone_numbers = []
        if partner.phone:
            phone_numbers.append(partner.phone)
        if partner.mobile:
            phone_numbers.append(partner.mobile)

        # Build emails
        emails = []
        if partner.email:
            emails.append(partner.email)

        return Person(
            identifier=identifiers,
            name=name,
            sex=sex,
            birth_date=partner.birthdate if partner.birthdate else None,
            death_date=getattr(partner, "deathdate", None),
            address=addresses if addresses else None,
            phone_number=phone_numbers if phone_numbers else None,
            email=emails if emails else None,
            registration_date=partner.create_date if partner.create_date else None,
            last_updated=partner.write_date if partner.write_date else None,
        )

    def _to_dci_group(self, partner) -> Group:
        """
        Convert Odoo res.partner (group) to DCI Group schema.

        Args:
            partner: res.partner record (is_group=True)

        Returns:
            DCI Group object
        """
        # Build group identifiers
        group_identifiers = []
        for reg_id in partner.reg_ids:
            if reg_id.id_type_id and reg_id.id_type_id.namespace_uri and reg_id.value:
                group_identifiers.append(
                    Identifier(
                        identifier_type=reg_id.id_type_id.namespace_uri,
                        identifier_value=reg_id.value,
                    )
                )

        # Build addresses
        addresses = []
        if partner.street or partner.city:
            addr = Address(
                address_line_1=partner.street or None,
                address_line_2=partner.street2 or None,
                locality=partner.city or None,
                region_code=partner.state_id.code if partner.state_id else None,
                postal_code=partner.zip or None,
                country_code=partner.country_id.code if partner.country_id else None,
            )
            addresses.append(addr)

        # Build member list
        member_list = []
        if hasattr(partner, "group_membership_ids"):
            for membership in partner.group_membership_ids:
                if membership.individual:
                    member = self._to_dci_member(membership.individual)
                    member_list.append(member)

        # Get group head
        group_head = None

        return Group(
            group_identifier=group_identifiers if group_identifiers else None,
            group_type="Household",  # Default type
            address=addresses if addresses else None,
            poverty_score=getattr(partner, "poverty_score", None),
            group_head_info=group_head,
            group_size=len(member_list) if member_list else None,
            member_list=member_list if member_list else None,
            registration_date=partner.create_date if partner.create_date else None,
            last_updated=partner.write_date if partner.write_date else None,
        )

    def _to_dci_member(self, partner) -> Member:
        """
        Convert Odoo res.partner to DCI Member (used in groups).

        Args:
            partner: res.partner record (individual)

        Returns:
            DCI Member object
        """
        # Build member identifiers
        member_identifiers = []
        for reg_id in partner.reg_ids:
            if reg_id.id_type_id and reg_id.id_type_id.namespace_uri and reg_id.value:
                member_identifiers.append(
                    Identifier(
                        identifier_type=reg_id.id_type_id.namespace_uri,
                        identifier_value=reg_id.value,
                    )
                )

        # Build demographic info (as Person)
        demographic_info = None
        try:
            demographic_info = self._to_dci_person(partner)
        except Exception as e:
            _logger.warning("Failed to build demographic info for member %s: %s", partner.id, str(e))

        return Member(
            member_identifier=member_identifiers if member_identifiers else None,
            demographic_info=demographic_info,
            marital_status=getattr(partner, "marital_status", None),
            registration_date=partner.create_date if partner.create_date else None,
            last_updated=partner.write_date if partner.write_date else None,
        )

    def _map_gender(self, partner) -> str | None:
        """
        Map Odoo gender to DCI sex value using vocabulary adapter.

        DCI supports: male, female, other, unknown

        Args:
            partner: res.partner record

        Returns:
            DCI sex string or None
        """
        # Use vocabulary adapter if available
        if self.vocabulary_adapter:
            # Try gender_id first (Many2one to spp.vocabulary.code)
            if hasattr(partner, "gender_id") and partner.gender_id:
                return self.vocabulary_adapter.map_gender_to_dci(partner.gender_id)

            # Try string gender field
            if hasattr(partner, "gender") and partner.gender:
                return self.vocabulary_adapter.map_gender_from_string(partner.gender)

            return None

        # Fallback to hardcoded mapping
        # Try gender field first (string)
        if hasattr(partner, "gender") and partner.gender:
            gender_lower = partner.gender.lower()
            if gender_lower in ("male", "m", "1"):
                return "male"
            elif gender_lower in ("female", "f", "2"):
                return "female"
            elif gender_lower in ("other", "o", "3"):
                return "other"
            else:
                return "unknown"

        # Try gender_id (Many2one to spp.vocabulary.code)
        if hasattr(partner, "gender_id") and partner.gender_id:
            gender_code = partner.gender_id.code if partner.gender_id.code else None
            if gender_code:
                code_lower = gender_code.lower()
                if code_lower in ("male", "m"):
                    return "male"
                elif code_lower in ("female", "f"):
                    return "female"
                elif code_lower in ("other", "o"):
                    return "other"
                else:
                    return "unknown"

        return None

    def _encode_cursor(self, record_id: int) -> str:
        """
        Encode a record ID into a cursor string.

        Uses base64 encoding for obfuscation.

        Args:
            record_id: The last record's ID

        Returns:
            Encoded cursor string
        """
        import base64

        cursor_data = f"id:{record_id}"
        return base64.urlsafe_b64encode(cursor_data.encode()).decode()

    def _decode_cursor(self, cursor: str) -> int:
        """
        Decode a cursor string back to a record ID.

        Args:
            cursor: Encoded cursor string

        Returns:
            Record ID

        Raises:
            ValueError: If cursor format is invalid or out of bounds
        """
        import base64

        try:
            cursor_data = base64.urlsafe_b64decode(cursor.encode()).decode()
            if not cursor_data.startswith("id:"):
                raise ValueError("Invalid cursor format")
            record_id = int(cursor_data[3:])
            # Bounds checking to prevent integer overflow/DoS
            if record_id < 0 or record_id > 2147483647:  # PostgreSQL max int
                raise ValueError("Record ID out of valid range")
            return record_id
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid cursor: {str(e)}") from e
