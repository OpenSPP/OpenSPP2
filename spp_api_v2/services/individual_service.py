# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Individual resource operations"""

import logging
from typing import Any

from odoo import Command, _
from odoo.api import Environment
from odoo.exceptions import AccessError, ValidationError

from ..schemas.base import (
    Identifier,
)
from ..schemas.individual import Individual
from ..schemas.patch import IndividualPatch
from .membership_utils import membership_to_response

_logger = logging.getLogger(__name__)


class IndividualService:
    """Service for Individual resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, system_uri: str, value: str):
        """
        Lookup partner by external identifier.

        CRITICAL: Uses id_type_id.uri (full code URI), NOT namespace_uri.

        Args:
            system_uri: Full URI of identifier type (e.g., urn:openspp:vocab:id-type#national_id)
            value: Identifier value

        Returns:
            res.partner record or empty recordset (in sudo context)
        """
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context — API auth
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system_uri),
                    ("value", "=", value),
                ],
                limit=1,
            )
        )
        if reg_id and reg_id.partner_id:
            # Return sudo partner - API handlers run as Public user
            # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context — API auth
            return self.env["res.partner"].sudo().browse(reg_id.partner_id.id)
        # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
        return self.env["res.partner"].sudo()

    def find_by_identifiers(self, identifiers: list[tuple[str, str]]):
        """
        Batch lookup partners by external identifiers.

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

        # Combine with OR: need (n-1) | operators for n terms
        if len(identifiers) > 1:
            domain = ["|"] * (len(identifiers) - 1) + or_domains
        else:
            domain = or_domains

        # nosemgrep: odoo-sudo-without-context — API auth; batch identifier lookup
        reg_ids = self.env["spp.registry.id"].sudo().search(domain)

        # Build result map
        result = {}
        for reg_id in reg_ids:
            key = f"{reg_id.id_type_id.uri}|{reg_id.value}"
            if reg_id.partner_id:
                # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context — API auth
                result[key] = self.env["res.partner"].sudo().browse(reg_id.partner_id.id)

        return result

    def to_api_schema(self, partner, extensions=None) -> dict[str, Any]:
        """
        Convert Odoo partner to Individual API schema.

        CRITICAL REQUIREMENTS:
        - NO database IDs exposed
        - Use namespace_uri for identifiers
        - Use gender_id (Many2one to spp.vocabulary.code), NOT gender string
        - Include source tracking in meta

        Args:
            partner: res.partner record
            extensions: List of extension names to include (or None for none)

        Returns:
            Dictionary matching Individual schema
        """
        if not partner:
            return {}

        # Build identifier list (REQUIRED, at least one)
        identifiers = []
        for reg_id in partner.reg_ids:
            # Use id_type_id.uri for full code URI (e.g., urn:openspp:vocab:id-type#national_id)
            # NOT namespace_uri which only returns vocabulary namespace
            if reg_id.id_type_id and reg_id.id_type_id.uri and reg_id.value:
                identifier = {
                    "system": reg_id.id_type_id.uri,
                    "value": reg_id.value,
                }
                identifiers.append(identifier)

        if not identifiers:
            identifiers.append(
                {
                    "system": "urn:openspp:internal",
                    "value": str(partner.id),
                }
            )

        # Build name (REQUIRED)
        name = {
            "family": partner.family_name or "",
            "given": partner.given_name or "",
            "middle": partner.addl_name or "",
            "text": partner.name or "",
        }

        # Build Individual resource
        individual = {
            "type": "Individual",
            "identifier": identifiers,
            "active": partner.active,
            "name": name,
        }

        # Birth date
        if partner.birthdate:
            individual["birthDate"] = partner.birthdate.isoformat()
            individual["birthDateEstimated"] = partner.birthdate_not_exact or False

        # Gender - CRITICAL: Use gender_id (Many2one to spp.vocabulary.code)
        if partner.gender_id:
            individual["gender"] = {
                "coding": [
                    {
                        "system": partner.gender_id.namespace_uri,
                        "code": partner.gender_id.code,
                        "display": partner.gender_id.display,
                    }
                ],
                "text": partner.gender_id.display,
            }

        # Telecom
        telecom = []
        if partner.phone:
            telecom.append(
                {
                    "system": "phone",
                    "value": partner.phone,
                    "use": "home",
                    "rank": 1,
                }
            )
        if hasattr(partner, "mobile") and partner.mobile:
            telecom.append(
                {
                    "system": "phone",
                    "value": partner.mobile,
                    "use": "mobile",
                    "rank": 2,
                }
            )
        if partner.email:
            telecom.append(
                {
                    "system": "email",
                    "value": partner.email,
                    "use": "work",
                    "rank": 3,
                }
            )
        if telecom:
            individual["telecom"] = telecom

        # Address
        if partner.street or partner.city or partner.state_id:
            address = {
                "type": "physical",
                "line": [partner.street] if partner.street else [],
                "city": partner.city,
                "state": partner.state_id.name if partner.state_id else None,
                "country": partner.country_id.code if partner.country_id else None,
                "postalCode": partner.zip,
            }
            # Build text representation
            address_parts = [
                partner.street,
                partner.city,
                partner.state_id.name if partner.state_id else None,
            ]
            address["text"] = ", ".join(filter(None, address_parts))
            individual["address"] = [address]

        # Photo (base64 encoded)
        if partner.image_1920:
            import base64

            individual["photo"] = base64.b64encode(partner.image_1920).decode("utf-8")

        # Group membership
        # Get active group memberships
        active_memberships = partner.individual_membership_ids.filtered(lambda m: not m.is_ended)
        if active_memberships:
            group_refs = []
            for membership in active_memberships:
                group_ref = {
                    "group": self._build_group_reference(membership.group),
                }

                # Add role from membership types
                # membership_type_ids is a Many2many to spp.vocabulary.code, so each item
                # IS already a vocabulary code record - no need to search for it
                if membership.membership_type_ids:
                    vocab_code = membership.membership_type_ids[0]
                    group_ref["role"] = {
                        "coding": [
                            {
                                "system": vocab_code.namespace_uri or "urn:openspp:membership-type",
                                "code": vocab_code.code,
                                "display": vocab_code.display,
                            }
                        ]
                    }
                group_refs.append(group_ref)

            if group_refs:
                individual["groupMembership"] = group_refs

        # Extensions (module-specific fields)
        if extensions:
            individual["extension"] = self._build_extensions(partner, extensions)

        # Metadata (source tracking per ADR-008)
        # Use integer microseconds for versionId to avoid float precision issues
        if partner.write_date:
            version_id = str(int(partner.write_date.timestamp() * 1000000))
            meta = {
                "versionId": version_id,
                "lastUpdated": partner.write_date.isoformat(),
            }
            if hasattr(partner, "source_system") and partner.source_system:
                meta["source"] = partner.source_system
            individual["meta"] = meta

        # Remove None values from individual data (except for required fields like type and identifier)
        filtered_data = {}
        for key, value in individual.items():
            # Always include type and identifier, even if None
            if key in ("type", "identifier"):
                filtered_data[key] = value
            # For other fields, only include if not None
            elif value is not None:
                filtered_data[key] = value

        return filtered_data

    def _build_group_reference(self, group) -> dict:
        """Build Reference to a Group"""
        # Get primary identifier for group
        if group.reg_ids:
            primary_id = group.reg_ids[0]
            ref = f"Group/{primary_id.namespace_uri}|{primary_id.value}"
        else:
            # No identifier - this should not happen in a properly configured system
            _logger.error(
                "Group with id=%s has no external identifiers - cannot create API reference",
                group.id,
            )
            ref = "Group/unknown"

        return {
            "reference": ref,
            "display": group.name,
        }

    def _build_extensions(self, partner, extension_names: list[str]) -> dict[str, Any]:
        """
        Build extension data for specified extensions.

        Args:
            partner: res.partner record
            extension_names: List of extension names/URLs to include (or ["*"] for all)

        Returns:
            Dictionary mapping extension names to their data
        """
        from ..services.extension_service import ExtensionService

        extension_service = ExtensionService(self.env)
        return extension_service.get_extension_data(partner, extension_names, resource_type="individual")

    def from_api_schema(self, schema: Individual) -> dict[str, Any]:
        """
        Convert Individual API schema to Odoo vals dict.

        CRITICAL:
        - Find or create identifier types by namespace_uri
        - Find or create gender code by namespace_uri + code
        - NO database IDs

        Args:
            schema: Individual schema instance

        Returns:
            Dictionary of values for res.partner.create() or write()
        """
        vals = {
            "is_registrant": True,
            "is_group": False,
        }

        # Name
        if schema.name:
            vals["name"] = schema.name.text or f"{schema.name.given or ''} {schema.name.family or ''}".strip()
            vals["family_name"] = schema.name.family
            vals["given_name"] = schema.name.given
            vals["addl_name"] = schema.name.middle

        # Active status
        vals["active"] = schema.active

        # Birth date
        if schema.birth_date:
            vals["birthdate"] = schema.birth_date
            if schema.birth_date_estimated:
                vals["birthdate_not_exact"] = True

        # Gender - CRITICAL: Find gender_id by namespace_uri + code
        if schema.gender and schema.gender.coding:
            gender_coding = schema.gender.coding[0]
            gender_code = (
                self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [
                        ("namespace_uri", "=", gender_coding.system),
                        ("code", "=", gender_coding.code),
                    ],
                    limit=1,
                )
            )
            if gender_code:
                vals["gender_id"] = gender_code.id
            else:
                # Gender code not found - raise validation error with helpful message
                raise ValidationError(
                    f"Invalid gender code: system='{gender_coding.system}', code='{gender_coding.code}'. "
                    f"Expected system 'urn:iso:std:iso:5218' with codes: "
                    f"0 (Not Known), 1 (Male), 2 (Female), 9 (Not Applicable)."
                )

        # Telecom
        for contact in schema.telecom or []:
            if contact.system == "phone":
                if contact.use == "mobile":
                    if hasattr(self.env["res.partner"], "_fields") and "mobile" in self.env["res.partner"]._fields:
                        vals["mobile"] = contact.value
                    else:
                        # Fallback: use phone field if mobile doesn't exist
                        vals["phone"] = contact.value
                else:
                    vals["phone"] = contact.value
            elif contact.system == "email":
                vals["email"] = contact.value

        # Address
        if schema.address:
            addr = schema.address[0]  # Use first address
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
                # Try to find state by name
                state = self.env["res.country.state"].search([("name", "=", addr.state)], limit=1)
                if state:
                    vals["state_id"] = state.id

        # Photo
        if schema.photo:
            import base64

            vals["image_1920"] = base64.b64decode(schema.photo)

        # Identifiers (handle separately via reg_ids)
        vals["reg_ids"] = self._build_registry_ids(schema.identifier)

        # Extensions (custom fields from spp_studio_api_v2)
        if schema.extension:
            try:
                from odoo.addons.spp_studio_api_v2.services.extension_write_service import (
                    ExtensionWriteService,
                )

                ext_service = ExtensionWriteService(self.env)
                ext_vals = ext_service.parse_extension_data(schema.extension, "individual")
                vals.update(ext_vals)
            except ImportError:
                # spp_studio_api_v2 not installed, skip extension data
                _logger.debug("spp_studio_api_v2 not installed, skipping extension data")
            except Exception as e:
                # Log extension parsing errors but don't fail the entire request
                _logger.warning("Failed to parse extension data: %s", e)

        return vals

    def _build_registry_ids(self, identifiers: list[Identifier]) -> list:
        """
        Build reg_ids commands for identifiers.

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
                    f"(e.g., 'urn:openspp:vocab:id-type#national_id')."
                )

            # Create new registry ID
            commands.append(
                Command.create(
                    {
                        "id_type_id": id_type.id,
                        "value": ident.value,
                    }
                )
            )

        return commands

    def create(self, schema: Individual, source: str, api_authorized: bool = False) -> Any:
        """
        Create new Individual with source tracking.

        Args:
            schema: Individual schema
            source: Source system URI (e.g., urn:openspp:api-client:{client_id})
            api_authorized: If True, skip user group check (API scope already verified)

        Returns:
            Created res.partner record
        """
        # For direct programmatic calls, check user group membership.
        # For API calls, the router verifies scope before setting api_authorized=True.
        if not api_authorized and not self.env.user.has_group("spp_api_v2.group_api_v2_manager"):
            raise AccessError(
                _("You do not have permission to create individuals via the API V2 service. Contact an API V2 manager.")
            )

        vals = self.from_api_schema(schema)

        # Add source tracking (ADR-008) - if fields exist
        if hasattr(self.env["res.partner"], "_fields") and "source_system" in self.env["res.partner"]._fields:
            vals["source_system"] = source
        if hasattr(self.env["res.partner"], "_fields") and "collection_method" in self.env["res.partner"]._fields:
            vals["collection_method"] = "api"

        # Use sudo() for cross-program individual creation while enforcing authorization above
        partner = (
            self.env["res.partner"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            .sudo()
            .with_context(
                # Individual creation is restricted to group_api_v2_manager and
                # uses external identifiers only.
                source_system=source
            )
            .create(vals)
        )

        # Log using external identifier, not database ID
        primary_id = partner.reg_ids[0] if partner.reg_ids else None
        identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
        _logger.info("Created individual %s via API from %s", identifier_str, source)
        return partner

    def update(self, partner, schema: Individual, source: str) -> Any:
        """
        Update Individual with source tracking.

        Args:
            partner: Existing res.partner record
            schema: Individual schema with updates
            source: Source system URI

        Returns:
            Updated res.partner record
        """
        vals = self.from_api_schema(schema)

        # Don't overwrite source_system (that's immutable)
        vals.pop("source_system", None)

        # Don't try to recreate registry IDs - they already exist
        # (Identifiers are immutable after creation)
        vals.pop("reg_ids", None)

        # Update with source tracking
        partner.with_context(
            source_system=source,
            source_reference=f"api-update-{partner.write_date.timestamp() if partner.write_date else 0}",
        ).write(vals)

        # Log using external identifier, not database ID
        primary_id = partner.reg_ids[0] if partner.reg_ids else None
        identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
        _logger.info("Updated individual %s via API from %s", identifier_str, source)
        return partner

    def partial_update(self, partner, patch: IndividualPatch, source: str) -> Any:  # noqa: C901
        """
        Partially update Individual with source tracking (JSON Merge Patch).

        Only fields present in the patch are updated. Omitted fields remain unchanged.

        Args:
            partner: Existing res.partner record
            patch: IndividualPatch schema with partial updates
            source: Source system URI

        Returns:
            Updated res.partner record
        """
        vals = {}

        # Process only fields that were explicitly set in the patch
        patch_data = patch.model_dump(exclude_unset=True, by_alias=False)

        # Name
        if "name" in patch_data:
            name = patch_data["name"]
            if name is not None:
                vals["name"] = name.get("text") or f"{name.get('given', '')} {name.get('family', '')}".strip()
                if name.get("family"):
                    vals["family_name"] = name["family"]
                if name.get("given"):
                    vals["given_name"] = name["given"]
                if name.get("middle"):
                    vals["addl_name"] = name["middle"]
            else:
                # RFC 7396: null clears the field
                vals["name"] = False
                vals["family_name"] = False
                vals["given_name"] = False
                vals["addl_name"] = False

        # Active status
        if "active" in patch_data:
            vals["active"] = patch_data["active"]

        # Birth date
        if "birth_date" in patch_data:
            vals["birthdate"] = patch_data["birth_date"]
        if "birth_date_estimated" in patch_data:
            vals["birthdate_not_exact"] = patch_data["birth_date_estimated"]

        # Gender
        if "gender" in patch_data:
            gender = patch_data["gender"]
            if gender:
                if gender.get("coding"):
                    gender_coding = gender["coding"][0]
                    gender_code = self.env["spp.vocabulary.code"].search(
                        [
                            ("namespace_uri", "=", gender_coding.get("system")),
                            ("code", "=", gender_coding.get("code")),
                        ],
                        limit=1,
                    )
                    if gender_code:
                        vals["gender_id"] = gender_code.id
            else:
                # RFC 7396: null clears the field
                vals["gender_id"] = False

        # Telecom
        if "telecom" in patch_data:
            telecom = patch_data["telecom"]
            if telecom:
                for contact in telecom:
                    if contact.get("system") == "phone":
                        if contact.get("use") == "mobile":
                            if "mobile" in self.env["res.partner"]._fields:
                                vals["mobile"] = contact.get("value")
                            else:
                                vals["phone"] = contact.get("value")
                        else:
                            vals["phone"] = contact.get("value")
                    elif contact.get("system") == "email":
                        vals["email"] = contact.get("value")
            else:
                # RFC 7396: null clears contact fields
                vals["phone"] = False
                vals["email"] = False
                if "mobile" in self.env["res.partner"]._fields:
                    vals["mobile"] = False

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

        # Photo
        if "photo" in patch_data:
            if patch_data["photo"]:
                import base64

                # SECURITY: Limit photo size to prevent DoS (5MB max)
                MAX_PHOTO_SIZE = 5 * 1024 * 1024
                if len(patch_data["photo"]) > MAX_PHOTO_SIZE:
                    raise ValidationError(_("Photo exceeds maximum allowed size of 5MB"))
                vals["image_1920"] = base64.b64decode(patch_data["photo"])
            else:
                vals["image_1920"] = False

        # Extensions
        if "extension" in patch_data:
            extension = patch_data["extension"]
            if extension:
                try:
                    from odoo.addons.spp_studio_api_v2.services.extension_write_service import (
                        ExtensionWriteService,
                    )

                    ext_service = ExtensionWriteService(self.env)
                    ext_vals = ext_service.parse_extension_data(extension, "individual")
                    vals.update(ext_vals)
                except ImportError:
                    _logger.debug("spp_studio_api_v2 not installed, skipping extension data")
                except Exception as e:
                    _logger.warning("Failed to parse extension data: %s", e)
            # null extension is ignored (extensions can't be "cleared" to a default)

        # Only write if we have values to update
        if vals:
            partner.with_context(
                source_system=source,
                source_reference=f"api-patch-{partner.write_date.timestamp() if partner.write_date else 0}",
            ).write(vals)

            # Log using external identifier
            primary_id = partner.reg_ids[0] if partner.reg_ids else None
            identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
            _logger.info(
                "Partially updated individual %s via API from %s",
                identifier_str,
                source,
            )

        return partner

    def get_groups(self, individual, status: str | None = None, limit: int = 100) -> list[dict]:
        """
        Get all groups the individual belongs to.

        Args:
            individual: res.partner record (is_group=False)
            status: Optional filter - "active" or "inactive" (default: all)
            limit: Maximum results to return (default: 100)

        Returns:
            List of dictionaries matching MembershipResponse schema
        """
        # Build domain for membership search
        domain = [("individual", "=", individual.id)]

        # Filter by status if provided
        if status == "active":
            domain.append(("status", "=", "active"))
        elif status == "inactive":
            domain.append(("status", "=", "inactive"))

        # Search for memberships
        # nosemgrep: odoo-sudo-without-context — API auth; membership lookup
        memberships = self.env["spp.group.membership"].sudo().search(domain, limit=limit, order="start_date desc")

        # Convert each membership to response format
        results = []
        for membership in memberships:
            try:
                response = membership_to_response(membership)
                if response is not None:
                    results.append(response)
            except Exception as e:
                # Log error but continue processing other memberships
                # Use group/individual names instead of database ID
                membership_desc = f"group={membership.group.name}, individual={membership.individual.name}"
                _logger.warning(
                    "Failed to convert membership (%s) to response: %s",
                    membership_desc,
                    e,
                )

        return results
