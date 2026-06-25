# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Constants

This module defines vocabulary namespace URIs and other constants used across
the DRIMS module. Using constants ensures consistency and makes URIs easier
to maintain.
"""

# Vocabulary Namespace Base URI
VOCAB_BASE = "urn:openspp:vocab:drims"

# Vocabulary Namespace URIs
VOCAB_ALERT_TYPES = f"{VOCAB_BASE}:alert-types"
VOCAB_DONOR_TYPES = f"{VOCAB_BASE}:donor-types"
VOCAB_DONATION_STATES = f"{VOCAB_BASE}:donation-states"
VOCAB_DRIMS_TYPES = f"{VOCAB_BASE}:drims-types"
VOCAB_PRIORITY_LEVELS = f"{VOCAB_BASE}:priority-levels"
VOCAB_REQUEST_STATES = f"{VOCAB_BASE}:request-states"
VOCAB_RESTRICTIONS = f"{VOCAB_BASE}:restrictions"
VOCAB_TRANSPORT_MODES = f"{VOCAB_BASE}:transport-modes"
VOCAB_ITEM_CONDITIONS = f"{VOCAB_BASE}:item-conditions"
VOCAB_ITEM_DISPOSITIONS = f"{VOCAB_BASE}:item-dispositions"

# Common state codes
STATE_DRAFT = "draft"
STATE_SUBMITTED = "submitted"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_ALLOCATED = "allocated"
STATE_DISPATCHED = "dispatched"
STATE_DELIVERED = "delivered"

# Donation state codes
DONATION_STATE_DRAFT = "draft"
DONATION_STATE_ANNOUNCED = "announced"
DONATION_STATE_RECEIVED = "received"
DONATION_STATE_INSPECTED = "inspected"
DONATION_STATE_STOCKED = "stocked"
DONATION_STATE_CANCELLED = "cancelled"
DONATION_STATE_REJECTED = "rejected"

# DRIMS type codes (for stock.picking classification)
DRIMS_TYPE_DONATION_RECEIPT = "donation_receipt"
DRIMS_TYPE_REQUEST_DISPATCH = "request_dispatch"
DRIMS_TYPE_TRANSFER = "transfer"
DRIMS_TYPE_RETURN = "return"

# Alert type codes
ALERT_LOW_STOCK = "low_stock"
ALERT_EXPIRY = "expiry"
ALERT_SLA_BREACH = "sla_breach"
ALERT_SLA_WARNING = "sla_warning"

# Priority level codes
PRIORITY_LOW = "low"
PRIORITY_MEDIUM = "medium"
PRIORITY_HIGH = "high"
PRIORITY_CRITICAL = "critical"
