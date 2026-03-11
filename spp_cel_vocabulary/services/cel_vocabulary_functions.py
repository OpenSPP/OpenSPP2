"""
Pure Python vocabulary functions for CEL expressions.

These functions are stateless and do not depend on Odoo models, making them
suitable for use in CEL evaluation contexts.

ADR-016 Phase 3: CEL Integration for vocabulary-aware expressions.
"""

import logging

_logger = logging.getLogger(__name__)


def code(env, identifier):
    """Resolve a vocabulary code by URI or alias.

    Usage in CEL:
        r.gender == code("urn:iso:std:iso:5218#2")  # By URI
        r.gender == code("female")                   # By alias
        r.gender == code("babae")                    # Local alias (PH)

    Args:
        env: Odoo environment (injected by CEL evaluator)
        identifier (str): Code URI, code value, or display name

    Returns:
        spp.vocabulary.code recordset: Resolved code record or empty recordset

    Note:
        This function is designed to be called from CEL expressions.
        The environment is injected at registration time.
    """
    if not identifier:
        return env["spp.vocabulary.code"].browse()

    # If identifier is a full URI, resolve directly
    if isinstance(identifier, str) and identifier.startswith("urn:"):
        return env["spp.vocabulary.code"].resolve_by_uri(identifier)

    # Otherwise, try alias resolution
    # This searches by code value, display name, or reference_uri
    return env["spp.vocabulary.code"].resolve_alias(identifier)


def in_group(env, code_value, group_name):
    """Check if a vocabulary code is in a concept group.

    Uses cached group URI lookups to avoid N+1 queries during CEL evaluation.
    If a VocabularyCache is present in env.context['_vocab_cache'], uses
    session-level caching for even better performance.

    Usage in CEL:
        in_group(r.gender, "feminine_gender")
        members.exists(m, in_group(m.gender, "feminine_gender"))

    Args:
        env: Odoo environment (injected by CEL evaluator)
        code_value: spp.vocabulary.code record or recordset
        group_name (str): Name of the concept group

    Returns:
        bool: True if code is in the group, False otherwise

    Note:
        Works with local codes via reference_uri mapping.
        E.g., "babae" (PH local) maps to "female" in feminine_gender group.
    """
    if not code_value or not group_name:
        return False

    # Check for session-level cache in context (set by CEL service)
    vocab_cache = env.context.get("_vocab_cache")
    if vocab_cache:
        return vocab_cache.check_membership(code_value, group_name)

    # Fallback: use ormcache directly - O(1) after first access
    ConceptGroup = env["spp.vocabulary.concept.group"]
    uri_set = ConceptGroup._get_group_uris_cached(group_name)

    if uri_set is None:
        _logger.warning("[CEL Vocabulary] Concept group '%s' not found", group_name)
        return False

    if not uri_set:
        return False

    # Direct frozenset membership check - O(1)
    if code_value.uri and code_value.uri in uri_set:
        return True

    if code_value.reference_uri and code_value.reference_uri in uri_set:
        return True

    return False


def code_eq(env, code_field, identifier):
    """Safe code comparison handling local code mappings.

    Usage in CEL:
        code_eq(r.gender, "female")

    This is equivalent to:
        r.gender.uri == "urn:iso:std:iso:5218#2"
        OR r.gender.reference_uri == "urn:iso:std:iso:5218#2"

    Args:
        env: Odoo environment (injected by CEL evaluator)
        code_field: spp.vocabulary.code record to compare
        identifier (str): Code URI, code value, or display name to compare against

    Returns:
        bool: True if codes match (including reference_uri mapping)

    Note:
        This function handles semantic equality, accounting for local
        codes that map to standard codes via reference_uri.
    """
    if not code_field:
        return False

    # Resolve the target code
    target = code(env, identifier)

    if not target:
        return False

    # Direct URI match
    if code_field.uri == target.uri:
        return True

    # Check if code_field's reference_uri matches target's URI
    # (for local code comparing to standard)
    if code_field.reference_uri and code_field.reference_uri == target.uri:
        return True

    # Check if target's reference_uri matches code_field's URI
    # (for standard comparing to local code)
    if target.reference_uri and target.reference_uri == code_field.uri:
        return True

    return False


# Semantic helper functions (syntactic sugar)


def is_female(env, code_value):
    """Check if code is in feminine_gender group.

    Usage in CEL:
        is_female(r.gender_id)
        members.exists(m, is_female(m.gender_id) and age_years(m.birthdate) >= 18)

    Args:
        env: Odoo environment (injected by CEL evaluator)
        code_value: spp.vocabulary.code record

    Returns:
        bool: True if code represents feminine gender
    """
    return in_group(env, code_value, "feminine_gender")


def is_male(env, code_value):
    """Check if code is in masculine_gender group.

    Usage in CEL:
        is_male(r.gender)

    Args:
        env: Odoo environment (injected by CEL evaluator)
        code_value: spp.vocabulary.code record

    Returns:
        bool: True if code represents masculine gender
    """
    return in_group(env, code_value, "masculine_gender")


def is_head(env, code_value):
    """Check if code is in head_of_household group.

    Usage in CEL:
        is_head(r.relationship_type)
        members.exists(m, is_head(m._link.kind))

    Args:
        env: Odoo environment (injected by CEL evaluator)
        code_value: spp.vocabulary.code record

    Returns:
        bool: True if code represents head of household
    """
    return in_group(env, code_value, "head_of_household")


def is_pregnant(env, code_value):
    """Check if code is in pregnant_eligible group.

    Usage in CEL:
        is_pregnant(r.pregnancy_status)

    Args:
        env: Odoo environment (injected by CEL evaluator)
        code_value: spp.vocabulary.code record

    Returns:
        bool: True if code represents pregnant/eligible status
    """
    return in_group(env, code_value, "pregnant_eligible")


def head(env, member, _membership=None, _group=None):
    """Check if a member is the head of household.

    This function is designed for use in member aggregate expressions like:
        members.exists(head(m) && is_female(m.gender_id))

    It checks if the member's membership in the group has the 'head' type.

    Args:
        env: Odoo environment (injected by CEL evaluator)
        member: res.partner record (individual) or membership record
        _membership: Optional membership record (passed from CEL context)
        _group: Optional group context (res.partner)

    Returns:
        bool: True if member is head of household
    """
    if not member:
        return False

    # Get the 'head' vocabulary code
    # nosemgrep: odoo-sudo-without-context
    head_code = env["spp.vocabulary.code"].sudo().get_code("urn:openspp:vocab:group-membership-type", "head")
    if not head_code:
        _logger.debug("[CEL Vocabulary] Head membership type code not found")
        return False

    # If member is a membership record, check directly
    if hasattr(member, "membership_type_ids"):
        return head_code in member.membership_type_ids

    # If _membership was passed directly (from CEL context), use it
    if _membership and hasattr(_membership, "membership_type_ids"):
        return head_code in _membership.membership_type_ids

    # If we have group context, look up the membership
    if _group:
        membership = env["spp.group.membership"].search(
            [
                ("group", "=", _group.id),
                ("individual", "=", member.id),
                ("is_ended", "=", False),
            ],
            limit=1,
        )
        if membership:
            return head_code in membership.membership_type_ids

    # Fallback: check if member has any active membership with head type
    # This is less precise but works when group context isn't available
    if hasattr(member, "individual_membership_ids"):
        for membership in member.individual_membership_ids:
            if not membership.is_ended and head_code in membership.membership_type_ids:
                return True

    return False


# Export all functions for registration
VOCABULARY_FUNCTIONS = {
    "code": code,
    "in_group": in_group,
    "code_eq": code_eq,
    "is_female": is_female,
    "is_male": is_male,
    "is_head": is_head,
    "is_pregnant": is_pregnant,
    "head": head,
}
