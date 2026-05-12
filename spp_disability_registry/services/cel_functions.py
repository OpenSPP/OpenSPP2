"""
CEL Functions for Disability Registry.

These functions provide disability-related queries for CEL expressions
used in program eligibility and entitlement calculations.

Functions use env injection pattern from spp_cel_vocabulary.
"""

import logging
from datetime import date

_logger = logging.getLogger(__name__)

# Severity codes indicating severe/profound disability (fallback if concept group unavailable)
SEVERE_SEVERITY_CODES = ("severe", "profound")


def has_disability(env, registrant):
    """Check if registrant has an approved disability status.

    Usage in CEL:
        has_disability(r)
        members.exists(m, has_disability(m))

    Args:
        env: Odoo environment (injected by CEL evaluator)
        registrant: res.partner record

    Returns:
        bool: True if registrant has approved disability assessment
    """
    if not registrant:
        return False

    # Use stored has_disability field from registrant extension
    return registrant.has_disability


def disability_severity(env, registrant):
    """Get the disability severity code for a registrant.

    Usage in CEL:
        disability_severity(r)
        in_group(disability_severity(r), "severe_disability")

    Args:
        env: Odoo environment (injected by CEL evaluator)
        registrant: res.partner record

    Returns:
        spp.vocabulary.code: Severity level code or empty recordset
    """
    if not registrant:
        return env["spp.vocabulary.code"].browse()

    return registrant.disability_severity_id or env["spp.vocabulary.code"].browse()


def is_severe_disability(env, registrant):
    """Check if registrant has severe or profound disability.

    This is a convenience function that checks membership in the
    'severe_disability' concept group.

    Usage in CEL:
        is_severe_disability(r)
        members.exists(m, is_severe_disability(m))

    Args:
        env: Odoo environment (injected by CEL evaluator)
        registrant: res.partner record

    Returns:
        bool: True if registrant has severe or profound disability
    """
    if not registrant:
        return False

    severity = registrant.disability_severity_id
    if not severity:
        return False

    # Check concept group membership
    ConceptGroup = env["spp.vocabulary.concept.group"]
    uri_set = ConceptGroup._get_group_uris_cached("severe_disability")

    if not uri_set:
        # Fallback: check by code
        return severity.code in SEVERE_SEVERITY_CODES

    # Check both uri and reference_uri for group membership
    return (severity.uri and severity.uri in uri_set) or (severity.reference_uri and severity.reference_uri in uri_set)


def household_has_pwd(env, group):
    """Check if household has any member with disability.

    Usage in CEL:
        household_has_pwd(r)  # where r is a group

    Args:
        env: Odoo environment (injected by CEL evaluator)
        group: res.partner record (is_group=True)

    Returns:
        bool: True if any household member has disability
    """
    if not group or not group.is_group:
        return False

    return any(
        not membership.is_ended and membership.individual.has_disability for membership in group.group_membership_ids
    )


def household_pwd_count(env, group):
    """Count members with disability in household.

    Usage in CEL:
        household_pwd_count(r)  # where r is a group
        household_pwd_count(r) >= 2

    Args:
        env: Odoo environment (injected by CEL evaluator)
        group: res.partner record (is_group=True)

    Returns:
        int: Number of members with disability
    """
    if not group or not group.is_group:
        return 0

    return sum(
        1
        for membership in group.group_membership_ids
        if not membership.is_ended and membership.individual.has_disability
    )


def needs_reassessment(env, registrant):
    """Check if registrant's disability assessment is due for review.

    Usage in CEL:
        needs_reassessment(r)

    Args:
        env: Odoo environment (injected by CEL evaluator)
        registrant: res.partner record

    Returns:
        bool: True if next review date is past or today
    """
    if not registrant or not registrant.has_disability:
        return False

    next_review = registrant.disability_next_review
    if not next_review:
        return False

    return next_review <= date.today()


# Export all functions for registration
DISABILITY_FUNCTIONS = {
    "has_disability": has_disability,
    "disability_severity": disability_severity,
    "is_severe_disability": is_severe_disability,
    "household_has_pwd": household_has_pwd,
    "household_pwd_count": household_pwd_count,
    "needs_reassessment": needs_reassessment,
}
