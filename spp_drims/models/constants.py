# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Constants

Vocabulary namespace URIs and the code values within them, used across the DRIMS
module so that neither has to be written as a bare string.

**Every code constant is named after the code it holds.** Four constants used to
be named for a concept that had no matching code in the shipped vocabulary data
(``PRIORITY_LOW``/``MEDIUM``/``HIGH`` and ``DRIMS_TYPE_TRANSFER``), so anything
comparing against them silently never matched — a ``search`` for a non-existent
code returns an empty set rather than raising. Mirroring the code in the name
removes the guesswork (OP#1165).

``CODE_NAMESPACES`` at the bottom records which vocabulary each group of code
constants belongs to. ``spp_drims/tests/test_constants.py`` walks it and asserts
every constant resolves to a real ``spp.vocabulary.code``, so a typo or a renamed
code fails the build instead of quietly never matching. Add new groups there.
"""

# Vocabulary Namespace Base URI
VOCAB_BASE = "urn:openspp:vocab:drims"

# Vocabulary Namespace URIs
VOCAB_AGENCY_TYPES = f"{VOCAB_BASE}:agency-types"
VOCAB_ALERT_TYPES = f"{VOCAB_BASE}:alert-types"
VOCAB_COORDINATION_MODES = f"{VOCAB_BASE}:coordination-modes"
VOCAB_DISTRIBUTION_TYPES = f"{VOCAB_BASE}:distribution-types"
VOCAB_DONATION_STATES = f"{VOCAB_BASE}:donation-states"
VOCAB_DONOR_TYPES = f"{VOCAB_BASE}:donor-types"
VOCAB_DRIMS_TYPES = f"{VOCAB_BASE}:drims-types"
VOCAB_HAZARD_TYPES = f"{VOCAB_BASE}:hazard-types"
VOCAB_ITEM_CATEGORIES = f"{VOCAB_BASE}:item-categories"
VOCAB_ITEM_CONDITIONS = f"{VOCAB_BASE}:item-conditions"
VOCAB_ITEM_DISPOSITIONS = f"{VOCAB_BASE}:item-dispositions"
VOCAB_ORGANIZATION_ROLES = f"{VOCAB_BASE}:organization-roles"
VOCAB_PERSONNEL_ROLES = f"{VOCAB_BASE}:personnel-roles"
VOCAB_POD_STATUSES = f"{VOCAB_BASE}:pod-statuses"
VOCAB_PRIORITY_LEVELS = f"{VOCAB_BASE}:priority-levels"
VOCAB_REQUEST_STATES = f"{VOCAB_BASE}:request-states"
VOCAB_RESTRICTIONS = f"{VOCAB_BASE}:restrictions"
VOCAB_RETURN_CONDITIONS = f"{VOCAB_BASE}:return-conditions"
VOCAB_RETURN_REASONS = f"{VOCAB_BASE}:return-reasons"
VOCAB_TRANSPORT_MODES = f"{VOCAB_BASE}:transport-modes"

# Request state codes (spp.drims.request)
STATE_DRAFT = "draft"
STATE_SUBMITTED = "submitted"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_ALLOCATED = "allocated"
STATE_DISPATCHED = "dispatched"
STATE_DELIVERED = "delivered"
STATE_FULFILLED = "fulfilled"
STATE_CANCELLED = "cancelled"

# Donation state codes (spp.drims.donation)
DONATION_STATE_ANNOUNCED = "announced"
DONATION_STATE_RECEIVED = "received"
DONATION_STATE_INSPECTED = "inspected"
DONATION_STATE_STOCKED = "stocked"
DONATION_STATE_CANCELLED = "cancelled"
DONATION_STATE_REJECTED = "rejected"

# DRIMS type codes (for stock.picking classification)
DRIMS_TYPE_DONATION_RECEIPT = "donation_receipt"
DRIMS_TYPE_REQUEST_DISPATCH = "request_dispatch"
DRIMS_TYPE_INTERNAL_TRANSFER = "internal_transfer"
DRIMS_TYPE_RETURN = "return"

# Alert type codes
ALERT_LOW_STOCK = "low_stock"
ALERT_EXPIRY = "expiry"
ALERT_SLA_BREACH = "sla_breach"
ALERT_SLA_WARNING = "sla_warning"
ALERT_CRITICAL_SHORTAGE = "critical_shortage"
ALERT_QUALITY_ISSUE = "quality_issue"

# Priority level codes
PRIORITY_ROUTINE = "routine"
PRIORITY_URGENT = "urgent"
PRIORITY_CRITICAL = "critical"

#: Which vocabulary each group of code constants draws from, keyed by the name
#: prefix. Walked by ``test_constants.py`` to prove every constant resolves.
#: Keep this in step when adding a group, or the new group goes unchecked.
CODE_NAMESPACES = {
    "STATE_": VOCAB_REQUEST_STATES,
    "DONATION_STATE_": VOCAB_DONATION_STATES,
    "DRIMS_TYPE_": VOCAB_DRIMS_TYPES,
    "ALERT_": VOCAB_ALERT_TYPES,
    "PRIORITY_": VOCAB_PRIORITY_LEVELS,
}
