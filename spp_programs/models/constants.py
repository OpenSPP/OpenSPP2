# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
STATE_DRAFT = "draft"
STATE_TO_APPROVE = "to_approve"
STATE_APPROVED = "approved"
STATE_DISTRIBUTED = "distributed"
# STATE_ACTIVE = "active"
STATE_ENDED = "ended"
STATE_CANCELLED = "cancelled"

#: Membership states that only their own workflow may move a member out of.
#: Re-running eligibility — "Enroll Eligible" / "Verify Eligibility" — must step
#: over these rather than re-deciding them:
#:
#: - ``duplicated`` is resolved by deduplication
#: - ``exited`` is a closed record, reopened only by re-enrolling deliberately
#: - ``paused`` is a program officer's explicit decision, undone only by Resume
#:
#: ``paused`` was missing here, so Enroll Eligible silently resumed paused
#: members and, on the other branch, demoted them to not_eligible (OP#1117).
PROTECTED_MEMBERSHIP_STATES = ("duplicated", "exited", "paused")

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
