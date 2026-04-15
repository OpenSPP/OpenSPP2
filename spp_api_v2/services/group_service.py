# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Group resource operations"""

import logging
from datetime import datetime, time
from typing import Any

from odoo import Command, _
from odoo.api import Environment
from odoo.exceptions import AccessError, ValidationError

from ..schemas.base import CodeableConcept, Coding, Reference
from ..schemas.group import Group
from ..schemas.membership import MembershipHistoryEntry
from ..schemas.patch import GroupPatch
from .membership_utils import membership_to_response

_logger = logging.getLogger(__name__)


class GroupService:
    """Service for Group resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, system_uri: str, value: str):
        """
        Lookup group by external identifier.

        Args:
            system_uri: Full URI of identifier type (e.g., urn:openspp:vocab:id-type#household_id)
            value: Identifier value

        Returns:
            res.partner record (group) or empty recordset (in sudo context)
        """
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system_uri),
                    ("value", "=", value),
                    ("partner_id.is_group", "=", True),
                ],
                limit=1,
            )
        )
        if reg_id and reg_id.partner_id:
            # Return sudo partner - API handlers run as Public user
            # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
            return self.env["res.partner"].sudo().browse(reg_id.partner_id.id)
        return self.env["res.partner"].sudo()  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context

    def find_by_identifiers(self, identifiers: list[tuple[str, str]]):
        """
        Batch lookup groups by external identifiers.

        Args:
            identifiers: List of (system_uri, value) tuples

        Returns:
            Dict mapping "system_uri|value" to res.partner record (or None)
        """
        if not identifiers:
            return {}

        # Build OR domain for batch search
        or_domains = []
        for system_uri, value in identifiers:
            or_domains.append("&")
            or_domains.append(("id_type_id.uri", "=", system_uri))
            or_domains.append(("value", "=", value))

        # Combine with OR
        if len(identifiers) > 1:
            domain = ["|"] * (len(identifiers) - 1) + or_domains
        else:
            domain = or_domains

        # Add is_group filter
        domain = ["&", ("partner_id.is_group", "=", True)] + domain

        reg_ids = self.env["spp.registry.id"].sudo().search(domain)  # nosemgrep: odoo-sudo-without-context

        # Build result map
        result = {}
        for reg_id in reg_ids:
            key = f"{reg_id.id_type_id.uri}|{reg_id.value}"
            if reg_id.partner_id:
                # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
                result[key] = self.env["res.partner"].sudo().browse(reg_id.partner_id.id)

        return result

    def to_api_schema(self, group, extensions=None) -> dict[str, Any]:
        """
        Convert Odoo group to Group API schema.

        Args:
            group: res.partner record (is_group=True)
            extensions: List of extension names to include

        Returns:
            Dictionary matching Group schema
        """
        if not group:
            return {}

        # Build identifier list
        identifiers = []
        for reg_id in group.reg_ids:
            # Use id_type_id.uri for full code URI (e.g., urn:openspp:vocab:id-type#household_id)
            # NOT namespace_uri which only returns vocabulary namespace
            if reg_id.id_type_id and reg_id.id_type_id.uri and reg_id.value:
                ident_dict = {
                    "system": reg_id.id_type_id.uri,
                    "value": reg_id.value,
                }
                # Only add period if it exists (not None)
                if hasattr(reg_id, "period") and reg_id.period:
                    ident_dict["period"] = reg_id.period
                identifiers.append(ident_dict)

        if not identifiers:
            _logger.warning(
                "Skipping group (id=%s): no valid external identifiers. Created by uid=%s on %s.",
                group.id,
                group.create_uid.id if group.create_uid else "unknown",
                group.create_date,
            )
            return None

        # Build Group resource
        group_data = {
            "type": "Group",
            "identifier": identifiers,
            "active": group.active,
            "groupType": "household",  # Default group type
        }
        # Only include name if it has a value
        if group.name:
            group_data["name"] = group.name

        # Members - filter by ended_date directly for reliability
        # (is_ended computed field may have timing issues in tests)
        now = datetime.now()
        members = []
        for membership in group.group_membership_ids.filtered(lambda m: not m.ended_date or m.ended_date > now):
            if membership.individual:
                member_data = self._build_member(membership)
                if member_data:
                    members.append(member_data)

        if members:
            group_data["member"] = members
            group_data["quantity"] = len(members)
        # Don't include member/quantity if empty (avoid None values)

        # Address (use group's address)
        if group.street or group.city or group.state_id:
            address = {
                "type": "physical",
                "line": [group.street] if group.street else [],
                "city": group.city,
                "state": group.state_id.name if group.state_id else None,
                "country": group.country_id.code if group.country_id else None,
                "postalCode": group.zip,
            }
            address_parts = [
                group.street,
                group.city,
                group.state_id.name if group.state_id else None,
            ]
            address["text"] = ", ".join(filter(None, address_parts))
            group_data["address"] = [address]

        # Extensions (module-specific fields)
        if extensions:
            group_data["extension"] = self._build_extensions(group, extensions)

        # Metadata - only include if write_date exists
        if group.write_date:
            version_id = str(int(group.write_date.timestamp() * 1000000))
            meta = {
                "versionId": version_id,
                "lastUpdated": group.write_date.isoformat(),
            }
            if hasattr(group, "source_system") and group.source_system:
                meta["source"] = group.source_system
            group_data["meta"] = meta

        # Remove None values from group_data (except for required fields like type and identifier)
        filtered_data = {}
        for key, value in group_data.items():
            # Always include type and identifier, even if None
            if key in ("type", "identifier"):
                filtered_data[key] = value
            # For other fields, only include if not None
            elif value is not None:
                filtered_data[key] = value

        return filtered_data

    def _build_member(self, membership) -> dict[str, Any]:
        """Build GroupMember from spp.group.membership record"""
        individual = membership.individual
        if not individual or not individual.reg_ids:
            return None

        # Build reference to individual
        primary_id = individual.reg_ids[0]
        entity_ref = {
            "reference": f"Individual/{primary_id.namespace_uri}|{primary_id.value}",
            "display": individual.name,
        }

        member = {
            "entity": entity_ref,
            "inactive": membership.is_ended or (membership.status == "inactive"),
        }

        # Add role if available (from membership types)
        # membership_type_ids is a Many2many to spp.vocabulary.code, so each item
        # IS already a vocabulary code record - no need to search for it
        if membership.membership_type_ids:
            vocab_code = membership.membership_type_ids[0]
            member["role"] = {
                "coding": [
                    {
                        "system": vocab_code.namespace_uri or "urn:openspp:membership-type",
                        "code": vocab_code.code,
                        "display": vocab_code.display,
                    }
                ]
            }

        return member

    def _build_extensions(self, group, extension_names: list[str]) -> dict[str, Any]:
        """
        Build extension data for specified extensions.

        Args:
            group: res.partner record (is_group=True)
            extension_names: List of extension names/URLs to include (or ["*"] for all)

        Returns:
            Dictionary mapping extension names to their data
        """
        from ..services.extension_service import ExtensionService

        extension_service = ExtensionService(self.env)
        return extension_service.get_extension_data(group, extension_names, resource_type="group")

    def from_api_schema(self, schema: Group) -> dict[str, Any]:
        """
        Convert Group API schema to Odoo vals dict.

        Args:
            schema: Group schema instance

        Returns:
            Dictionary of values for res.partner.create() or write()
        """
        vals = {
            "is_registrant": True,
            "is_group": True,
            "name": schema.name or "Unnamed Group",
            "active": schema.active,
        }

        # Address
        if schema.address:
            addr = schema.address[0]
            if addr.line:
                vals["street"] = addr.line[0]
            if addr.city:
                vals["city"] = addr.city
            if addr.postal_code:
                vals["zip"] = addr.postal_code
            if addr.country:
                country = self.env["res.country"].search([("code", "=", addr.country)], limit=1)
                if country:
                    vals["country_id"] = country.id
            if addr.state:
                state = self.env["res.country.state"].search([("name", "=", addr.state)], limit=1)
                if state:
                    vals["state_id"] = state.id

        # Identifiers
        vals["reg_ids"] = self._build_registry_ids(schema.identifier)

        # Extensions (custom fields from spp_studio_api_v2)
        if schema.extension:
            try:
                from odoo.addons.spp_studio_api_v2.services.extension_write_service import (
                    ExtensionWriteService,
                )

                ext_service = ExtensionWriteService(self.env)
                ext_vals = ext_service.parse_extension_data(schema.extension, "group")
                vals.update(ext_vals)
            except ImportError:
                # spp_studio_api_v2 not installed, skip extension data
                _logger.debug("spp_studio_api_v2 not installed, skipping extension data")
            except Exception as e:
                # Log extension parsing errors but don't fail the entire request
                _logger.warning("Failed to parse extension data: %s", e)

        return vals

    def _build_registry_ids(self, identifiers) -> list:
        """Build reg_ids commands for identifiers.

        Looks up vocabulary codes by uri to get the id_type_id.
        The spp.registry.id.id_type_id field is Many2one("spp.vocabulary.code").

        Identifier system format: {vocabulary_namespace}#{code}
        Example: urn:openspp:vocab:id-type#national_id
        """
        commands = []
        for ident in identifiers:
            # Find vocabulary code by uri (unique per code)
            # URI format: {vocabulary.namespace_uri}#{code}
            # spp.registry.id.id_type_id expects spp.vocabulary.code, NOT spp.id.type
            id_type = (
                self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [("uri", "=", ident.system)],
                    limit=1,
                )
            )

            if not id_type:
                raise ValidationError(
                    f"Invalid identifier type: system='{ident.system}'. "
                    f"Expected format: 'urn:openspp:vocab:id-type#<code>' "
                    f"(e.g., 'urn:openspp:vocab:id-type#household_id')."
                )

            commands.append(
                Command.create(
                    {
                        "id_type_id": id_type.id,
                        "value": ident.value,
                    }
                )
            )

        return commands

    def create(self, schema: Group, source: str, api_authorized: bool = False) -> Any:
        """
        Create new Group with source tracking.

        Args:
            schema: Group schema
            source: Source system URI
            api_authorized: If True, skip user group check (API scope already verified)

        Returns:
            Created res.partner record
        """
        # For direct programmatic calls, check user group membership.
        # For API calls, the router verifies scope before setting api_authorized=True.
        if not api_authorized and not self.env.user.has_group("spp_api_v2.group_api_v2_manager"):
            raise AccessError(
                _("You do not have permission to create groups via the API V2 service. Contact an API V2 manager.")
            )

        vals = self.from_api_schema(schema)

        # Add source tracking (if field exists)
        if hasattr(self.env["res.partner"], "_fields") and "source_system" in self.env["res.partner"]._fields:
            vals["source_system"] = source
        if hasattr(self.env["res.partner"], "_fields") and "collection_method" in self.env["res.partner"]._fields:
            vals["collection_method"] = "api"

        # Use sudo() for cross-program group creation while enforcing authorization above
        group = (
            self.env["res.partner"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
            # Group creation is restricted by API scope verification
            .sudo()
            .with_context(source_system=source)
            .create(vals)
        )

        # Handle members separately
        if schema.member:
            self._create_members(group, schema.member, source)

        # Log using external identifier, not database ID
        primary_id = group.reg_ids[0] if group.reg_ids else None
        identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
        _logger.info("Created group %s via API from %s", identifier_str, source)
        return group

    def _create_members(self, group, members, source):
        """Create group member relationships"""
        for member_schema in members:
            # Parse reference to get individual
            ref = member_schema.entity.reference
            if not ref.startswith("Individual/"):
                _logger.warning("Invalid member reference: %s", ref)
                continue

            # Extract identifier from reference (format: Individual/system|value)
            ident_str = ref.replace("Individual/", "")
            if "|" not in ident_str:
                _logger.warning("Invalid identifier format in reference: %s", ref)
                continue

            system, value = ident_str.split("|", 1)

            # Find individual
            individual = self._find_individual(system, value)
            if not individual:
                _logger.warning("Individual not found: %s|%s", system, value)
                continue

            # Find relation code if specified
            # Note: relation_id in spp.registry.relationship is a Many2one to spp.vocabulary.code
            relation_id = None
            if member_schema.role and member_schema.role.coding:
                role_coding = member_schema.role.coding[0]
                # Find the vocabulary code by namespace_uri and code
                vocab_code = (
                    self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
                    .sudo()
                    .search(
                        [
                            ("namespace_uri", "=", role_coding.system),
                            ("code", "=", role_coding.code),
                        ],
                        limit=1,
                    )
                )
                if vocab_code:
                    # Use vocab_code.id directly - relation_id IS a spp.vocabulary.code
                    relation_id = vocab_code.id
                else:
                    _logger.warning(
                        "Vocabulary code not found for relationship role: %s|%s",
                        role_coding.system,
                        role_coding.code,
                    )

            # Create relationship
            relationship_vals = {
                "source": individual.id,
                "destination": group.id,
            }
            if relation_id:
                relationship_vals["relation_id"] = relation_id

            # Try to create the relationship - if relation_id fails validation
            # (e.g., not in available_relation_ids for this partner type combo),
            # retry without relation_id rather than failing the entire operation.
            # Use savepoint to properly rollback first attempt if it fails.
            if relation_id:
                try:
                    with self.env.cr.savepoint():
                        # nosemgrep: odoo-sudo-without-context
                        self.env["spp.registry.relationship"].sudo().create(relationship_vals)
                except ValidationError as e:
                    _logger.warning(
                        "Relation type validation failed, creating relationship without type: %s",
                        e,
                    )
                    relationship_vals.pop("relation_id", None)
                    # nosemgrep: odoo-sudo-without-context
                    self.env["spp.registry.relationship"].sudo().create(relationship_vals)
            else:
                # nosemgrep: odoo-sudo-without-context
                self.env["spp.registry.relationship"].sudo().create(relationship_vals)

    def _find_individual(self, system_uri: str, value: str):
        """Find individual by identifier.

        Args:
            system_uri: Full URI (e.g., urn:openspp:vocab:id-type#national_id)
                       or namespace URI (e.g., urn:openspp:vocab:id-type)
            value: Identifier value
        """
        # Try full URI first (id_type_id.uri = namespace#code)
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system_uri),
                    ("value", "=", value),
                    ("partner_id.is_group", "=", False),
                ],
                limit=1,
            )
        )
        if not reg_id and "#" not in system_uri:
            # Fallback: try namespace_uri (without #code suffix)
            reg_id = (
                self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [
                        ("namespace_uri", "=", system_uri),
                        ("value", "=", value),
                        ("partner_id.is_group", "=", False),
                    ],
                    limit=1,
                )
            )
        return reg_id.partner_id if reg_id else self.env["res.partner"]

    def update(self, group, schema: Group, source: str) -> Any:
        """
        Update Group with source tracking.

        Args:
            group: Existing res.partner record
            schema: Group schema with updates
            source: Source system URI

        Returns:
            Updated res.partner record
        """
        vals = self.from_api_schema(schema)
        vals.pop("source_system", None)  # Don't overwrite immutable source
        vals.pop("reg_ids", None)  # Don't try to recreate registry IDs

        group.with_context(
            source_system=source,
            source_reference=f"api-update-{group.write_date.timestamp() if group.write_date else 0}",
        ).write(vals)

        # Log using external identifier, not database ID
        primary_id = group.reg_ids[0] if group.reg_ids else None
        identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
        _logger.info("Updated group %s via API from %s", identifier_str, source)
        return group

    def partial_update(self, group, patch: GroupPatch, source: str) -> Any:
        """
        Partially update Group with source tracking (JSON Merge Patch).

        Only fields present in the patch are updated. Omitted fields remain unchanged.

        Args:
            group: Existing res.partner record
            patch: GroupPatch schema with partial updates
            source: Source system URI

        Returns:
            Updated res.partner record
        """
        vals = {}

        # Process only fields that were explicitly set in the patch
        patch_data = patch.model_dump(exclude_unset=True, by_alias=False)

        # Name
        if "name" in patch_data:
            vals["name"] = patch_data["name"]

        # Active status
        if "active" in patch_data:
            vals["active"] = patch_data["active"]

        # Address
        if "address" in patch_data:
            address = patch_data["address"]
            if address:
                addr = address[0]
                if addr.get("line"):
                    vals["street"] = addr["line"][0]
                if addr.get("city"):
                    vals["city"] = addr["city"]
                if addr.get("postal_code"):
                    vals["zip"] = addr["postal_code"]
                if addr.get("country"):
                    country = self.env["res.country"].search([("code", "=", addr["country"])], limit=1)
                    if country:
                        vals["country_id"] = country.id
                if addr.get("state"):
                    state = self.env["res.country.state"].search([("name", "=", addr["state"])], limit=1)
                    if state:
                        vals["state_id"] = state.id
            else:
                # RFC 7396: null clears address fields
                vals["street"] = False
                vals["city"] = False
                vals["zip"] = False
                vals["country_id"] = False
                vals["state_id"] = False

        # Extensions
        if "extension" in patch_data:
            extension = patch_data["extension"]
            if extension:
                try:
                    from odoo.addons.spp_studio_api_v2.services.extension_write_service import (
                        ExtensionWriteService,
                    )

                    ext_service = ExtensionWriteService(self.env)
                    ext_vals = ext_service.parse_extension_data(extension, "group")
                    vals.update(ext_vals)
                except ImportError:
                    _logger.debug("spp_studio_api_v2 not installed, skipping extension data")
                except Exception as e:
                    _logger.warning("Failed to parse extension data: %s", e)
            # null extension is ignored (extensions can't be "cleared" to a default)

        # Only write if we have values to update
        if vals:
            group.with_context(
                source_system=source,
                source_reference=f"api-patch-{group.write_date.timestamp() if group.write_date else 0}",
            ).write(vals)

            # Log using external identifier
            primary_id = group.reg_ids[0] if group.reg_ids else None
            identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
            _logger.info("Partially updated group %s via API from %s", identifier_str, source)

        return group

    def get_membership(self, group, individual):
        """
        Get the active membership record for an individual in a group.

        Args:
            group: res.partner record (is_group=True)
            individual: res.partner record (is_group=False)

        Returns:
            spp.group.membership record or empty recordset
        """
        return (
            self.env["spp.group.membership"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("group", "=", group.id),
                    ("individual", "=", individual.id),
                    ("is_ended", "=", False),
                ],
                limit=1,
            )
        )

    def add_member(self, group, individual, role_coding=None, start_date=None) -> dict[str, Any]:
        """
        Add an individual to a group.

        Args:
            group: res.partner record (is_group=True)
            individual: res.partner record (is_group=False)
            role_coding: Optional Coding dict with system, code, display for membership role
            start_date: Optional date when membership starts

        Returns:
            Dictionary matching MembershipResponse schema

        Raises:
            ValidationError: If individual is already a member
        """
        # Check if individual is already a member
        existing = self.get_membership(group, individual)
        if existing:
            raise ValidationError(_("Individual is already a member of this group"))

        # Prepare membership values
        vals = {
            "group": group.id,
            "individual": individual.id,
        }

        # Convert date to datetime if provided
        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
            vals["start_date"] = datetime.combine(start_date, time.min)

        # Find role vocabulary code if provided
        if role_coding:
            vocab_code = (
                self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [
                        ("namespace_uri", "=", role_coding.get("system")),
                        ("code", "=", role_coding.get("code")),
                    ],
                    limit=1,
                )
            )
            if vocab_code:
                vals["membership_type_ids"] = [Command.link(vocab_code.id)]
            else:
                _logger.warning(
                    "Vocabulary code not found for role: %s|%s",
                    role_coding.get("system"),
                    role_coding.get("code"),
                )

        # Create membership
        membership = (
            self.env["spp.group.membership"]  # nosemgrep: odoo-sudo-without-context
            # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
            .sudo()
            .create(vals)
        )

        # Log using external identifiers
        group_id = group.reg_ids[0] if group.reg_ids else None
        individual_id = individual.reg_ids[0] if individual.reg_ids else None
        group_str = f"{group_id.namespace_uri}|{group_id.value}" if group_id else "unknown"
        individual_str = f"{individual_id.namespace_uri}|{individual_id.value}" if individual_id else "unknown"
        _logger.info("Added member %s to group %s", individual_str, group_str)

        return membership_to_response(membership)

    def remove_member(self, group, individual, ended_date=None, reason=None) -> dict[str, Any]:
        """
        Remove (end) an individual's membership in a group.

        Args:
            group: res.partner record (is_group=True)
            individual: res.partner record (is_group=False)
            ended_date: Optional date when membership ends (defaults to now)
            reason: Optional reason for removal (currently not stored)

        Returns:
            Dictionary matching MembershipResponse schema

        Raises:
            ValidationError: If individual is not a member or already ended
        """
        # Find membership
        membership = self.get_membership(group, individual)
        if not membership:
            raise ValidationError(_("Individual is not a member of this group"))

        # Set ended date
        if ended_date:
            if isinstance(ended_date, str):
                ended_date = datetime.fromisoformat(ended_date.replace("Z", "+00:00")).date()
            ended_datetime = datetime.combine(ended_date, time.min)
        else:
            ended_datetime = datetime.now()

        membership.sudo().write({"ended_date": ended_datetime})  # nosemgrep: odoo-sudo-without-context

        # Note: reason is not currently stored in spp.group.membership model
        # Could be added as a field in the future if needed
        if reason:
            _logger.info("Membership removal reason: %s", reason)

        # Log using external identifiers
        group_id = group.reg_ids[0] if group.reg_ids else None
        individual_id = individual.reg_ids[0] if individual.reg_ids else None
        group_str = f"{group_id.namespace_uri}|{group_id.value}" if group_id else "unknown"
        individual_str = f"{individual_id.namespace_uri}|{individual_id.value}" if individual_id else "unknown"
        _logger.info("Removed member %s from group %s", individual_str, group_str)

        return membership_to_response(membership)

    def update_member(self, group, individual, role_coding=None, start_date=None, ended_date=None) -> dict[str, Any]:
        """
        Update an individual's membership in a group.

        Args:
            group: res.partner record (is_group=True)
            individual: res.partner record (is_group=False)
            role_coding: Optional Coding dict with system, code, display for new role
            start_date: Optional date when membership starts
            ended_date: Optional date when membership ends

        Returns:
            Dictionary matching MembershipResponse schema

        Raises:
            ValidationError: If individual is not a member
        """
        # Find membership
        membership = self.get_membership(group, individual)
        if not membership:
            raise ValidationError(_("Individual is not a member of this group"))

        # Prepare update values
        vals = {}

        # Update start date
        if start_date is not None:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
            vals["start_date"] = datetime.combine(start_date, time.min)

        # Update ended date
        if ended_date is not None:
            if isinstance(ended_date, str):
                ended_date = datetime.fromisoformat(ended_date.replace("Z", "+00:00")).date()
            vals["ended_date"] = datetime.combine(ended_date, time.min)

        # Update role
        if role_coding:
            vocab_code = (
                self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [
                        ("namespace_uri", "=", role_coding.get("system")),
                        ("code", "=", role_coding.get("code")),
                    ],
                    limit=1,
                )
            )
            if vocab_code:
                # Replace existing roles with new role
                vals["membership_type_ids"] = [Command.set([vocab_code.id])]
            else:
                _logger.warning(
                    "Vocabulary code not found for role: %s|%s",
                    role_coding.get("system"),
                    role_coding.get("code"),
                )

        if vals:
            membership.sudo().write(vals)  # nosemgrep: odoo-sudo-without-context

        # Log using external identifiers
        group_id = group.reg_ids[0] if group.reg_ids else None
        individual_id = individual.reg_ids[0] if individual.reg_ids else None
        group_str = f"{group_id.namespace_uri}|{group_id.value}" if group_id else "unknown"
        individual_str = f"{individual_id.namespace_uri}|{individual_id.value}" if individual_id else "unknown"
        _logger.info("Updated member %s in group %s", individual_str, group_str)

        return membership_to_response(membership)

    def merge_groups(self, source_group, target_group, role_mapping=None) -> dict:
        """
        Merge source group into target group.

        All members from source are moved to target, source is deactivated.

        Args:
            source_group: The group to merge FROM (will be deactivated)
            target_group: The group to merge INTO
            role_mapping: Optional dict mapping source roles to target roles (e.g., {"head": "spouse"})

        Returns:
            dict: API schema for the target group with merged members

        Raises:
            ValidationError: If validation fails
        """
        # Validate groups are different
        if source_group.id == target_group.id:
            raise ValidationError(_("Source and target groups must be different"))

        # Validate source group is active
        if not source_group.active:
            raise ValidationError(_("Source group is already inactive and cannot be merged"))

        # Get the head membership type code
        # nosemgrep: odoo-sudo-without-context
        head_code = self.env["spp.vocabulary.code"].sudo().get_code("urn:openspp:vocab:group-membership-type", "head")
        member_code = (
            # nosemgrep: odoo-sudo-without-context
            self.env["spp.vocabulary.code"].sudo().get_code("urn:openspp:vocab:group-membership-type", "member")
        )

        # Get all active members from source group
        source_members = source_group.group_membership_ids.filtered(lambda m: not m.is_ended)

        # Get existing target members to check for duplicates
        target_member_ids = target_group.group_membership_ids.filtered(lambda m: not m.is_ended).mapped("individual.id")

        # Check if target has a head
        target_has_head = False
        if head_code:
            target_has_head = any(
                head_code in membership.membership_type_ids
                for membership in target_group.group_membership_ids.filtered(lambda m: not m.is_ended)
            )

        # Process each source member
        now = datetime.now()
        for source_membership in source_members:
            individual = source_membership.individual

            # End membership in source group
            source_membership.sudo().write({"ended_date": now})  # nosemgrep: odoo-sudo-without-context

            # Skip if already a member of target group
            if individual.id in target_member_ids:
                _logger.info(
                    "Individual %s already member of target group, skipping",
                    individual.reg_ids[0].value if individual.reg_ids else "unknown",
                )
                continue

            # Determine the role for the new membership
            new_membership_types = []
            source_roles = source_membership.membership_type_ids

            for source_role in source_roles:
                # Apply role mapping if provided
                if role_mapping and source_role.code in role_mapping:
                    mapped_role_code = role_mapping[source_role.code]
                    # Find the vocabulary code for the mapped role
                    mapped_vocab = (
                        self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
                        .sudo()
                        .search(
                            [
                                (
                                    "namespace_uri",
                                    "=",
                                    "urn:openspp:vocab:group-membership-type",
                                ),
                                ("code", "=", mapped_role_code),
                            ],
                            limit=1,
                        )
                    )
                    if mapped_vocab:
                        new_membership_types.append(mapped_vocab.id)
                    else:
                        _logger.warning(
                            "Mapped role code not found: %s, keeping original role",
                            mapped_role_code,
                        )
                        new_membership_types.append(source_role.id)
                # If source role is "head" and target already has head, demote to "member"
                elif head_code and source_role.id == head_code.id and target_has_head:
                    if member_code:
                        new_membership_types.append(member_code.id)
                        _logger.info(
                            "Demoting head from source group to member in target group (target already has head)"
                        )
                    else:
                        # If no member code, just skip the head role
                        _logger.warning("No 'member' code found, creating membership without role")
                else:
                    # Keep original role
                    new_membership_types.append(source_role.id)

            # Create membership in target group
            membership_vals = {
                "group": target_group.id,
                "individual": individual.id,
                "start_date": now,
            }

            if new_membership_types:
                membership_vals["membership_type_ids"] = [Command.set(new_membership_types)]

            try:
                self.env["spp.group.membership"].sudo().create(membership_vals)  # nosemgrep: odoo-sudo-without-context

                # Log using external identifiers
                individual_id = individual.reg_ids[0] if individual.reg_ids else None
                individual_str = f"{individual_id.namespace_uri}|{individual_id.value}" if individual_id else "unknown"
                _logger.info("Moved member %s from source to target group", individual_str)
            except Exception as e:
                # Use external identifier in error log (no database IDs)
                individual_id = individual.reg_ids[0] if individual.reg_ids else None
                individual_str = f"{individual_id.namespace_uri}|{individual_id.value}" if individual_id else "unknown"
                _logger.error(
                    "Failed to create membership for individual %s: %s",
                    individual_str,
                    e,
                )
                # Continue with other members even if one fails
                continue

        # Deactivate source group
        source_group.sudo().write({"active": False})  # nosemgrep: odoo-sudo-without-context

        # Log using external identifiers
        source_id = source_group.reg_ids[0] if source_group.reg_ids else None
        target_id = target_group.reg_ids[0] if target_group.reg_ids else None
        source_str = f"{source_id.namespace_uri}|{source_id.value}" if source_id else "unknown"
        target_str = f"{target_id.namespace_uri}|{target_id.value}" if target_id else "unknown"
        _logger.info(
            "Merged group %s into %s, moved %d members",
            source_str,
            target_str,
            len(source_members),
        )

        # Return the updated target group
        return self.to_api_schema(target_group)

    def split_group(self, source_group, new_identifiers, members_to_move, new_head=None, source=None) -> dict[str, Any]:
        """
        Split a group by moving some members to a new group.

        Args:
            source_group: The group to split from
            new_identifiers: List of Identifier dicts for the new group
            members_to_move: List of individual partners to move
            new_head: Optional individual to be head of new group
            source: Source system URI for tracking

        Returns:
            dict: API schema for the newly created group

        Raises:
            ValidationError: If validation fails
        """
        # Validation: Check for empty members_to_move
        if not members_to_move:
            raise ValidationError(_("Cannot split group: no members specified to move"))

        # Validation: Get all active memberships for source group
        active_memberships = (
            self.env["spp.group.membership"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("group", "=", source_group.id),
                    ("is_ended", "=", False),
                ]
            )
        )

        if not active_memberships:
            raise ValidationError(_("Cannot split group: source group has no active members"))

        # Build dict for quick membership lookup
        membership_by_individual = {m.individual.id: m for m in active_memberships}

        # Validation: Check all members_to_move are in source group
        members_to_move_ids = [m.id for m in members_to_move]
        for individual in members_to_move:
            if individual.id not in membership_by_individual:
                ind_id = individual.reg_ids[0] if individual.reg_ids else None
                ind_str = f"{ind_id.namespace_uri}|{ind_id.value}" if ind_id else individual.name
                raise ValidationError(_("Individual %s is not a member of the source group") % ind_str)

        # Validation: Check new_head is in members_to_move if specified
        if new_head and new_head.id not in members_to_move_ids:
            head_id = new_head.reg_ids[0] if new_head.reg_ids else None
            head_str = f"{head_id.namespace_uri}|{head_id.value}" if head_id else new_head.name
            raise ValidationError(_("New head %s must be in the list of members to move") % head_str)

        # Validation: Ensure source group will have at least one member left
        remaining_count = len(active_memberships) - len(members_to_move)
        if remaining_count < 1:
            raise ValidationError(_("Cannot split group: source group must have at least one member remaining"))

        # Validation: Check if head is being moved from source group
        head_vocab_code = (
            self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("code", "=", "head"),
                ],
                limit=1,
            )
        )

        if head_vocab_code:
            head_membership = active_memberships.filtered(lambda m: head_vocab_code in m.membership_type_ids)
            if head_membership and head_membership.individual.id in members_to_move_ids:
                # Head is being moved - this is an error
                raise ValidationError(
                    _(
                        "Cannot split group: current head of household is being moved. "
                        "Please assign a new head to the source group before splitting."
                    )
                )

        # Create the new group with identifiers
        from ..schemas.base import Identifier as IdentifierSchema
        from ..schemas.group import Group as GroupSchema

        new_group_schema = GroupSchema(
            identifier=[IdentifierSchema(**ident) for ident in new_identifiers],
            name=f"Split from {source_group.name}",
            active=True,
            type="Group",
        )

        # Use existing create method's vals generation
        new_group_vals = self.from_api_schema(new_group_schema)

        # Add source tracking
        source_system = source or "urn:openspp:api-v2:split-operation"
        if hasattr(self.env["res.partner"], "_fields") and "source_system" in self.env["res.partner"]._fields:
            new_group_vals["source_system"] = source_system
        if hasattr(self.env["res.partner"], "_fields") and "collection_method" in self.env["res.partner"]._fields:
            new_group_vals["collection_method"] = "api"

        # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
        new_group = self.env["res.partner"].sudo().create(new_group_vals)

        # Move members to new group
        now = datetime.now()
        for individual in members_to_move:
            membership = membership_by_individual[individual.id]

            # End membership in source group
            membership.sudo().write({"ended_date": now})  # nosemgrep: odoo-sudo-without-context

            # Create membership in new group
            new_membership_vals = {
                "group": new_group.id,
                "individual": individual.id,
                "start_date": now,
            }

            # Set role: if this is the new_head, use head role; otherwise preserve original role
            if new_head and individual.id == new_head.id and head_vocab_code:
                new_membership_vals["membership_type_ids"] = [Command.set([head_vocab_code.id])]
            elif membership.membership_type_ids:
                # Preserve original role
                new_membership_vals["membership_type_ids"] = [Command.set(membership.membership_type_ids.ids)]

            self.env["spp.group.membership"].sudo().create(new_membership_vals)  # nosemgrep: odoo-sudo-without-context

        # Log the operation using external identifiers
        source_id = source_group.reg_ids[0] if source_group.reg_ids else None
        source_str = f"{source_id.namespace_uri}|{source_id.value}" if source_id else source_group.name
        new_id = new_group.reg_ids[0] if new_group.reg_ids else None
        new_str = f"{new_id.namespace_uri}|{new_id.value}" if new_id else new_group.name
        _logger.info(
            "Split group %s into new group %s, moved %d members",
            source_str,
            new_str,
            len(members_to_move),
        )

        # Return API schema for new group
        return self.to_api_schema(new_group)

    def get_membership_history_count(self, group, since=None) -> int:
        """
        Count membership history events for a group at the database level.

        Each membership produces 1 event ("added"), plus 1 more if ended ("removed").

        Args:
            group: res.partner record (is_group=True)
            since: Optional datetime - only count events after this date

        Returns:
            Total number of history events
        """
        domain = [("group", "=", group.id)]

        if since:
            # Count "added" events (create_date >= since)
            added_domain = domain + [("create_date", ">=", since)]
            # nosemgrep: odoo-sudo-without-context
            added_count = self.env["spp.group.membership"].sudo().search_count(added_domain)

            # Count "removed" events (ended_date >= since AND ended_date is set)
            removed_domain = domain + [
                ("ended_date", "!=", False),
                ("ended_date", ">=", since),
            ]
            # nosemgrep: odoo-sudo-without-context
            removed_count = self.env["spp.group.membership"].sudo().search_count(removed_domain)
        else:
            # All memberships produce an "added" event
            # nosemgrep: odoo-sudo-without-context
            added_count = self.env["spp.group.membership"].sudo().search_count(domain)

            # Ended memberships also produce a "removed" event
            removed_domain = domain + [("ended_date", "!=", False)]
            # nosemgrep: odoo-sudo-without-context
            removed_count = self.env["spp.group.membership"].sudo().search_count(removed_domain)

        return added_count + removed_count

    def get_membership_history(self, group, limit=100, offset=0, since=None) -> list[MembershipHistoryEntry]:
        """
        Get membership change history for a group.

        Args:
            group: res.partner record (is_group=True)
            limit: Maximum number of history entries to return
            offset: Number of entries to skip (for pagination)
            since: Optional datetime - only show events after this date

        Returns:
            List of MembershipHistoryEntry instances sorted by timestamp descending
        """
        # List of (entry, membership_id) tuples for stable sorting
        history: list[tuple[MembershipHistoryEntry, int]] = []

        # Build domain for memberships
        domain = [("group", "=", group.id)]

        # Get all memberships (active AND ended) for the group
        # nosemgrep: odoo-sudo-without-context
        memberships = self.env["spp.group.membership"].sudo().search(domain, order="create_date desc")

        # Build history entries
        for membership in memberships:
            individual = membership.individual
            if not individual or not individual.reg_ids:
                continue

            # Build individual reference
            primary_id = individual.reg_ids[0]
            member_ref = Reference(
                reference=f"Individual/{primary_id.namespace_uri}|{primary_id.value}",
                display=individual.name,
            )

            # Build role coding if available
            role_concept = None
            if membership.membership_type_ids:
                vocab_code = membership.membership_type_ids[0]
                role_concept = CodeableConcept(
                    coding=[
                        Coding(
                            system=vocab_code.namespace_uri or "urn:openspp:vocab:group-membership-type",
                            code=vocab_code.code,
                            display=vocab_code.display,
                        )
                    ]
                )

            # Add "added" event
            create_timestamp = membership.create_date
            if not since or create_timestamp >= since:
                entry = MembershipHistoryEntry(
                    timestamp=create_timestamp,
                    action="added",
                    member=member_ref,
                    changed_by=membership.create_uid.name if membership.create_uid else "System",
                    new_role=role_concept,
                )
                history.append((entry, membership.id))

            # Add "removed" event if membership has ended
            if membership.ended_date:
                end_timestamp = membership.ended_date
                if not since or end_timestamp >= since:
                    entry = MembershipHistoryEntry(
                        timestamp=end_timestamp,
                        action="removed",
                        member=member_ref,
                        changed_by=membership.write_uid.name if membership.write_uid else "System",
                        old_role=role_concept,
                    )
                    history.append((entry, membership.id))

        # Sort by timestamp descending (most recent first)
        # Use membership_id as secondary key to ensure stable sorting
        # when timestamps are equal (e.g., created within same second)
        history.sort(key=lambda x: (x[0].timestamp.isoformat(), x[1]), reverse=True)

        # Extract entries and apply offset/limit
        entries = [entry for entry, _ in history]
        if limit is not None:
            return entries[offset : offset + limit]
        return entries[offset:]
