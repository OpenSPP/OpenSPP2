# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Resolve an external identifier to exactly one registrant.

The registry allows two registrants to hold the same ID type and value
(imported data awaiting deduplication; see the ID-document deduplication
manager in spp_programs), but an API lookup addresses one record. These
helpers never pick one of several matches: they raise, and the API refuses.

Only *live* IDs count. A soft-removed ID (``status = 'invalid'``) neither
resolves nor blocks reuse; a NULL status is an ID added straight through
the registry and is live, the same rule as ``spp.registry.id``'s own
uniqueness index.
"""

from odoo.exceptions import ValidationError

LIVE_ID = ("status", "!=", "invalid")


class AmbiguousIdentifierError(Exception):
    """The identifier is live on more than one registrant."""

    def __init__(self, partners):
        super().__init__("Identifier matches more than one registrant")
        self.partners = partners


class IdentifierInUseError(ValidationError):
    """The identifier is already live on another registrant."""


def live_registry_ids(partner):
    """The registrant's IDs that resolve (not soft-removed), in ``reg_ids`` order."""
    return partner.reg_ids.filtered(lambda reg_id: reg_id.status != "invalid")


def primary_registry_id(partner):
    """The ID references to this registrant are built from: its first live one (or empty)."""
    return live_registry_ids(partner)[:1]


def _registry_ids(env):
    # sudo: resolution is about the registry's data, not the API user's
    # visibility; consent and scope are enforced by the caller
    return env["spp.registry.id"].sudo()  # nosemgrep: odoo-sudo-without-context


def resolve_registrant(env, system_uri, value, is_group=None, system_field="id_type_id.uri"):
    """
    Return the one registrant holding a live ID ``system_uri|value``.

    Args:
        env: Odoo environment
        system_uri: Full code URI of the ID type (e.g. urn:openspp:vocab:id-type#national_id)
        value: Identifier value
        is_group: True/False to restrict to groups/individuals, None for either
        system_field: registry ID field ``system_uri`` is matched on

    Returns:
        res.partner record (sudo), or an empty recordset

    Raises:
        AmbiguousIdentifierError: several registrants hold the identifier
    """
    domain = [(system_field, "=", system_uri), ("value", "=", value), LIVE_ID]
    if is_group is not None:
        domain.append(("partner_id.is_group", "=", is_group))
    partners = _registry_ids(env).search(domain).partner_id
    if len(partners) > 1:
        raise AmbiguousIdentifierError(partners)
    return partners


def resolve_registrants(env, identifiers, is_group=None):
    """
    Batch form of :func:`resolve_registrant`.

    Args:
        identifiers: list of (system_uri, value) tuples

    Returns:
        dict mapping "system_uri|value" to the res.partner record, or to an
        AmbiguousIdentifierError when several registrants hold it; keys with
        no match are absent
    """
    if not identifiers:
        return {}
    or_domains = []
    for system_uri, value in identifiers:
        or_domains += ["&", ("id_type_id.uri", "=", system_uri), ("value", "=", value)]
    domain = ["|"] * (len(identifiers) - 1) + or_domains
    domain = ["&", LIVE_ID] + domain
    if is_group is not None:
        domain = ["&", ("partner_id.is_group", "=", is_group)] + domain

    matches = {}
    for reg_id in _registry_ids(env).search(domain):
        key = f"{reg_id.id_type_id.uri}|{reg_id.value}"
        # reg_id is sudo, so its partner_id is too: the union stays in sudo
        matches[key] = matches[key] | reg_id.partner_id if key in matches else reg_id.partner_id
    return {
        key: partners if len(partners) == 1 else AmbiguousIdentifierError(partners) for key, partners in matches.items()
    }


def assert_identifier_free(env, id_type, value, exclude_partner=None):
    """
    Raise unless no other registrant holds a live ID of ``id_type`` with ``value``.

    Args:
        id_type: spp.vocabulary.code record of the ID type
        value: Identifier value
        exclude_partner: registrant allowed to hold it (the one being written)

    Raises:
        IdentifierInUseError: another registrant holds the identifier
    """
    domain = [("id_type_id", "=", id_type.id), ("value", "=", value), LIVE_ID]
    if exclude_partner:
        domain.append(("partner_id", "!=", exclude_partner.id))
    if _registry_ids(env).search_count(domain, limit=1):
        raise IdentifierInUseError(f"Identifier {id_type.uri}|{value} is already in use by another registrant")


def assert_new_identifiers_free(env, reg_id_commands):
    """
    Check the ``reg_ids`` create commands of a new registrant.

    A second registrant with an identifier someone else holds could never be
    addressed unambiguously afterwards, so creation is refused instead.

    Raises:
        IdentifierInUseError: another registrant holds one of the identifiers
    """
    # nosemgrep: odoo-sudo-without-context
    id_types = env["spp.vocabulary.code"].sudo()
    for command in reg_id_commands:
        reg_vals = command[2]
        assert_identifier_free(env, id_types.browse(reg_vals["id_type_id"]), reg_vals["value"])
