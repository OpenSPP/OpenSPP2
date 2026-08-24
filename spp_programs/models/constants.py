# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
STATE_DRAFT = "draft"
STATE_TO_APPROVE = "to_approve"
STATE_APPROVED = "approved"
STATE_DISTRIBUTED = "distributed"
# STATE_ACTIVE = "active"
STATE_ENDED = "ended"
STATE_CANCELLED = "cancelled"

MANAGER_ELIGIBILITY = 1
MANAGER_CYCLE = 2
MANAGER_PROGRAM = 3
MANAGER_ENTITLEMENT = 4
MANAGER_DEDUPLICATION = 5
MANAGER_NOTIFICATION = 6
MANAGER_PAYMENT = 7
MANAGER_COMPLIANCE = 8

MANAGER_MODELS = {
    "eligibility_manager_ids": {
        "spp.eligibility.manager": "spp.program.membership.manager.default",
    },
    "cycle_manager_ids": {
        "spp.cycle.manager": "spp.cycle.manager.default",
    },
    "entitlement_manager_ids": {
        "spp.program.entitlement.manager": "spp.program.entitlement.manager.default",
    },
    "deduplication_manager_ids": {
        "spp.deduplication.manager": "spp.deduplication.manager.default",
    },
    # NOTE: notification_manager_ids removed - SMS manager moved to spp_programs_sms bridge module
    "program_manager_ids": {
        "spp.program.manager": "spp.program.manager.default",
    },
    "payment_manager_ids": {
        "spp.program.payment.manager": "spp.program.payment.manager.default",
    },
    "compliance_manager_ids": {
        "spp.compliance.manager": "spp.compliance.manager.default",
    },
}

# The cards on a program's Configuration tab (OP#1172). Each names the field on
# spp.program, the wrapper model behind it, and the wording the Add dialog uses.
# The keys match MANAGER_TYPE_INFO's "category" so the two can be read together:
# this map says where a category lives, MANAGER_TYPE_INFO describes the methods
# inside it.
#
# The concrete methods themselves are deliberately absent. They come from the
# wrapper's `_selection_manager_ref_id()`, which is what other modules extend
# when they add one — spp_program_geofence adds an eligibility method that way,
# and a hard-coded list here would never see it.
MANAGER_CATEGORIES = {
    "eligibility": {
        "field": "eligibility_manager_ids",
        "wrapper": "spp.eligibility.manager",
        "label": "Eligibility Method",
    },
    "entitlement": {
        "field": "entitlement_manager_ids",
        "wrapper": "spp.program.entitlement.manager",
        "label": "Entitlement Type",
        # One per program, and not by choice of this dialog: spp.program's
        # check_managers_limit refuses a second entitlement manager, and the
        # cycle machinery reaches for exactly one — get_manager() calls
        # ensure_one(), and get_managers() raises NotImplementedError for this
        # kind. QA asked for several of the same kind (OP#1172 round 1); that
        # needs the entitlement engine to iterate managers first, so the dialog
        # says what the program can actually do rather than accepting a second
        # method the cycle would then choke on.
        "single_manager": True,
    },
    "cycle": {
        "field": "cycle_manager_ids",
        "wrapper": "spp.cycle.manager",
        "label": "Cycle Schedule",
    },
    "compliance": {
        "field": "compliance_manager_ids",
        "wrapper": "spp.compliance.manager",
        "label": "Compliance Criteria",
    },
    "payment": {
        "field": "payment_manager_ids",
        "wrapper": "spp.program.payment.manager",
        "label": "Payment Method",
    },
    "deduplication": {
        "field": "deduplication_manager_ids",
        "wrapper": "spp.deduplication.manager",
        "label": "Deduplication Method",
    },
    "notification": {
        "field": "notification_manager_ids",
        "wrapper": "spp.program.notification.manager",
        "label": "Notification Channel",
    },
    "program": {
        "field": "program_manager_ids",
        "wrapper": "spp.program.manager",
        "label": "Program Manager",
    },
}
