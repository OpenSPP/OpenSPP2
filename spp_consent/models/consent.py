# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DPV-Aligned Consent Record Model.

Implements ISO/IEC TS 27560:2023 Consent Record Information Structure
using W3C Data Privacy Vocabulary (DPV) concepts.

Standards alignment:
- ISO/IEC TS 27560:2023 - Consent record information structure
- ISO/IEC 29184:2020 - Online privacy notices and consent
- W3C Data Privacy Vocabulary (DPV) v2 - Consent vocabulary
- GDPR Article 7 - Conditions for consent
"""

import logging
import uuid
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Configuration constants
BATCH_SIZE_EXPIRED_CONSENT = 100  # Number of consents to process per batch in cron job
DEFAULT_RETENTION_DAYS = 1825  # Default retention period (5 years)

# Fields to track in history for audit purposes
TRACKED_FIELDS = [
    "status",
    "effective_date",
    "expiry",
    "legal_basis",
    "controller_id",
]

# Fields protected from modification after consent is given (immutable consent terms)
# These fields define the legal agreement and cannot be changed retroactively.
# Evidence and withdrawal mechanism fields are intentionally excluded - they can be updated.
PROTECTED_FIELDS = frozenset(
    {
        # Parties (who is involved)
        "signatory_id",
        "group_id",
        "controller_id",
        "indicated_by_id",
        "delegation_type",
        # Recipients (who can receive data)
        "recipient_mode",
        "recipient_ids",
        "allowed_recipient_types",
        # Processing terms (what and why)
        "purpose_ids",
        "personal_data_ids",
        "processing_ids",
        "legal_basis",
        "legal_basis_reference",
        "jurisdiction",
        # Privacy notice (what was shown)
        "notice_id",
        "notice_version",
        # Storage conditions
        "storage_duration",
        "storage_location",
        # Validity period
        "effective_date",
        "expiry",
        # Collection method
        "collection_method",
    }
)

# Valid status transitions to prevent status reversion attacks
# Key: current status, Value: set of valid next statuses
# This prevents attacks where someone tries to revert a 'given' consent back to 'requested'
# to unlock protected fields for modification
VALID_STATUS_TRANSITIONS = {
    "requested": {"given", "refused"},
    "given": {"withdrawn", "expired", "renewed", "invalidated"},
    "renewed": {"withdrawn", "expired", "invalidated"},
    "refused": set(),  # Terminal state
    "withdrawn": set(),  # Terminal state
    "expired": {"renewed"},  # Can be renewed
    "invalidated": set(),  # Terminal state
}

# Statuses that represent a consent that was once active (cannot be deleted)
# These must be preserved for audit trail and legal compliance
NON_DELETABLE_STATUSES = frozenset({"given", "renewed", "withdrawn", "expired", "invalidated"})


class OpenSPPConsent(models.Model):
    """
    DPV-Aligned Consent Record.

    Implements the four sections of ISO 27560:
    1. Header/Metadata
    2. Parties
    3. Processing
    4. Consent Specifics
    """

    _name = "spp.consent"
    _description = "Consent Record (ISO 27560 / DPV-aligned)"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ========================================================================
    # 1. HEADER / METADATA (ISO 27560 Section 1)
    # ========================================================================
    name = fields.Char(
        "Consent Name",
        required=True,
        tracking=True,
        help="Descriptive name for this consent record",
    )

    external_id = fields.Char(
        string="Record ID",
        copy=False,
        index=True,
        help="dpv:hasIdentifier - Unique external identifier (UUID)",
    )

    schema_version = fields.Char(
        default="dpv-27560:1.0",
        readonly=True,
        help="Schema version for interoperability",
    )

    record_type = fields.Selection(
        [
            ("consent_record", "Consent Record"),
            ("consent_receipt", "Consent Receipt"),
        ],
        default="consent_record",
        help="Type of record per ISO 27560",
    )

    # ========================================================================
    # 2. PARTIES (ISO 27560 Section 2)
    # ========================================================================
    # Data Subject (the beneficiary)
    signatory_id = fields.Many2one(
        "res.partner",
        "Data Subject",
        domain=[("is_registrant", "=", True), ("is_group", "=", False)],
        tracking=True,
        help="The individual (beneficiary) whose personal data will be collected and processed. "
        "This is the person who is giving consent for their data to be used. "
        "For child beneficiaries, this would be the child, even if a parent/guardian signs on their behalf.",
    )

    # Group consent (head of household signs for group)
    group_id = fields.Many2one(
        "res.partner",
        "Group",
        domain=[("is_registrant", "=", True), ("is_group", "=", True)],
        help="Group this consent applies to (if group consent)",
    )

    # Data Controller (organization responsible for processing)
    controller_id = fields.Many2one(
        "res.partner",
        string="Data Controller",
        tracking=True,
        help="The organization that is responsible for collecting and protecting this data. "
        "Under applicable data protection law, this is the organization that decides why and how "
        "personal data is processed. "
        "This is typically your organization/agency running the social protection program. "
        "The data controller has legal obligations to protect the data and respect the "
        "individual's rights.",
    )

    # Third Party Recipients - can be specific orgs OR categories
    recipient_mode = fields.Selection(
        [
            ("specific", "Specific Organizations"),
            ("category", "Organization Categories"),
        ],
        default="specific",
        string="Recipient Mode",
        help="How will data be shared with third parties?\n\n"
        "• Specific Organizations: Consent applies to an exact list of partner organizations "
        "(e.g., 'UNICEF Kenya' and 'Red Cross'). The beneficiary knows exactly who will receive their data.\n\n"
        "• Organization Categories: Consent applies to types of organizations "
        "(e.g., 'All UN Agencies', 'Government Health Departments'). "
        "This is more flexible but less specific about who gets access.",
    )

    # Specific recipients (when mode is 'specific')
    recipient_ids = fields.Many2many(
        "res.partner",
        "spp_consent_recipient_rel",
        "consent_id",
        "partner_id",
        string="Data Recipients",
        help="dpv:hasRecipient - Specific third parties data may be shared with",
    )

    # Category-based recipients (when mode is 'category')
    # E.g., "I consent to share with all NGOs and UN agencies, but NOT private sector"
    allowed_recipient_types = fields.Many2many(
        "spp.consent.org.type",
        string="Allowed Organization Types",
        help="Categories of organizations allowed to receive data. "
        "E.g., 'All NGOs and government agencies, but not private sector'",
    )

    # Who indicated the consent (may differ from data subject for delegation)
    indicated_by_id = fields.Many2one(
        "res.partner",
        string="Indicated By",
        help="Who physically gave the consent? Usually this is the same as the Data Subject. "
        "However, if someone else signed on behalf of the beneficiary (e.g., a parent signing for a child, "
        "or a caretaker signing for an elderly person), select that person here. "
        "Leave empty if the Data Subject signed for themselves.",
    )

    delegation_type = fields.Selection(
        [
            ("self", "Self"),
            ("guardian", "Legal Guardian"),
            ("parent", "Parent/Caretaker"),
            ("poa", "Power of Attorney"),
            ("representative", "Authorized Representative"),
        ],
        default="self",
        help="What is the relationship between the person who gave consent and the beneficiary?\n\n"
        "• Self: The beneficiary signed for themselves (most common)\n"
        "• Legal Guardian: Court-appointed guardian (requires legal documentation)\n"
        "• Parent/Caretaker: Parent or family member signing for a child or dependent\n"
        "• Power of Attorney: Someone authorized by legal document to act on beneficiary's behalf\n"
        "• Authorized Representative: Community leader or other authorized person\n\n"
        "For child beneficiaries under 16, you MUST have parent/guardian consent.",
    )

    delegation_evidence = fields.Binary(
        string="Delegation Evidence",
        help="Documentation proving authority to consent on behalf of data subject",
    )
    delegation_evidence_filename = fields.Char()

    # ========================================================================
    # 3. PROCESSING (ISO 27560 Section 3)
    # ========================================================================
    # Purpose(s) - Multiple allowed per DPV
    purpose_ids = fields.Many2many(
        "spp.consent.purpose",
        string="Purposes",
        help="Why are you collecting this beneficiary's data? Select all that apply.\n\n"
        "Examples: Service Delivery (to provide cash transfers), Identity Verification (to confirm identity), "
        "Fraud Prevention (to detect duplicate registrations), Program Evaluation (to measure impact).\n\n"
        "IMPORTANT: Under applicable data protection law, you can only use data for the purposes you specify here. "
        "If you later want to use the data for a different purpose, you must obtain new consent.",
    )

    # Legal Basis (DPV / GDPR Article 6 aligned)
    legal_basis = fields.Selection(
        [
            ("consent", "Consent"),
            ("contract", "Contract"),
            ("legal_obligation", "Legal Obligation"),
            ("vital_interest", "Vital Interest"),
            ("public_interest", "Public Interest"),
            ("legitimate_interest", "Legitimate Interest"),
        ],
        default="consent",
        required=True,
        tracking=True,
        help="What is the legal justification for processing this data under applicable data protection law "
        "(e.g., GDPR Article 6, Kenya Data Protection Act, POPIA, LGPD)?\n\n"
        "• Consent: The individual has freely given specific permission (most common for voluntary programs)\n"
        "• Contract: Processing is necessary to deliver a service the individual signed up for\n"
        "• Legal Obligation: Required by law (e.g., mandatory reporting to government)\n"
        "• Vital Interest: Necessary to protect someone's life (e.g., medical emergencies)\n"
        "• Public Interest: Required to perform a task in the public interest or official authority\n"
        "• Legitimate Interest: Necessary for legitimate interests (rarely used in social protection)\n\n"
        "If unsure, choose 'Consent' for voluntary social protection programs.",
    )

    legal_basis_reference = fields.Char(
        string="Legal Reference",
        help="Reference to law, regulation, or contract",
    )

    # Personal Data Categories
    personal_data_ids = fields.Many2many(
        "spp.consent.personal.data",
        string="Personal Data Categories",
        help="dpv:hasPersonalData - Types of data covered",
    )

    # Processing Operations
    processing_ids = fields.Many2many(
        "spp.consent.processing",
        string="Processing Operations",
        help="dpv:hasProcessing - What operations are permitted",
    )

    # Storage Conditions
    storage_duration = fields.Integer(
        string="Retention Period (days)",
        help="dpv:hasStorageCondition - How long data is kept",
    )
    storage_location = fields.Char(
        string="Storage Location",
        help="Geographic location of data storage",
    )

    # Jurisdiction
    jurisdiction = fields.Char(
        help="dpv:hasJurisdiction - Applicable legal jurisdiction (e.g., 'EU', 'KE')",
    )

    # Privacy Notice
    notice_id = fields.Many2one(
        "spp.consent.notice",
        string="Privacy Notice",
        help="dpv:hasNotice - Privacy notice shown to data subject",
    )
    notice_version = fields.Char(
        string="Notice Version",
        help="Version of notice shown at time of consent",
    )

    # ========================================================================
    # 4. CONSENT SPECIFICS (ISO 27560 Section 4)
    # ========================================================================
    # Status (DPV ConsentStatus vocabulary)
    status = fields.Selection(
        [
            ("requested", "Requested"),  # dpv:ConsentRequested
            ("given", "Given"),  # dpv:ConsentGiven
            ("renewed", "Renewed"),  # dpv:RenewedConsentGiven
            ("refused", "Refused"),  # dpv:ConsentRefused
            ("withdrawn", "Withdrawn"),  # dpv:ConsentWithdrawn
            ("expired", "Expired"),  # dpv:ConsentExpired
            ("invalidated", "Invalidated"),  # dpv:ConsentInvalidated
        ],
        default="requested",
        required=True,
        tracking=True,
        help="Current state of this consent record:\n\n"
        "• Requested: Consent has been requested but not yet received from beneficiary\n"
        "• Given: Beneficiary has actively given consent (data processing can begin)\n"
        "• Renewed: Consent was re-confirmed/extended (e.g., after expiry or policy change)\n"
        "• Refused: Beneficiary declined to give consent\n"
        "• Withdrawn: Beneficiary gave consent but later withdrew it (must stop processing)\n"
        "• Expired: Consent validity period has ended (check expiry date)\n"
        "• Invalidated: Consent is no longer valid due to breach or other issue\n\n"
        "Status changes are automatically tracked in consent history for audit compliance.",
    )

    # DPV URI for status (computed for interoperability)
    status_dpv_uri = fields.Char(
        compute="_compute_status_dpv_uri",
        string="Status DPV URI",
        help="W3C DPV URI for current status",
    )

    # Validity Period
    effective_date = fields.Date(
        string="Effective From",
        tracking=True,
        help="Date when consent becomes effective",
    )
    expiry = fields.Date(
        "Expiry Date",
        required=True,
        tracking=True,
        help="Date when consent expires",
    )

    # Collection Method
    collection_method = fields.Selection(
        [
            ("written", "Written/Signed Form"),
            ("verbal", "Verbal (Witnessed)"),
            ("electronic", "Electronic/Digital"),
            ("biometric", "Biometric Confirmation"),
        ],
        help="How was this consent collected from the beneficiary?\n\n"
        "• Written/Signed Form: Beneficiary signed a paper consent form (attach scan as evidence)\n"
        "• Verbal (Witnessed): Consent given verbally with a witness present (document in notes)\n"
        "• Electronic/Digital: Consent collected through digital form, tablet, or mobile app\n"
        "• Biometric Confirmation: Consent confirmed using fingerprint or other biometric\n\n"
        "Keep evidence (signed forms, photos, recordings) to prove consent was obtained.",
    )

    # Evidence
    evidence_attachment = fields.Binary(
        string="Evidence Document",
        help="Signed consent form or other proof",
    )
    evidence_filename = fields.Char()

    # Withdrawal mechanism
    withdrawal_uri = fields.Char(
        string="Withdrawal URI",
        help="URI/URL for consent withdrawal",
    )
    withdrawal_instructions = fields.Text(
        string="Withdrawal Instructions",
        translate=True,
        help="Instructions for how to withdraw consent",
    )

    # ========================================================================
    # AUDIT TRAIL
    # ========================================================================
    # Creation tracking
    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    # Verification (for paper/verbal consent)
    verified_by_id = fields.Many2one(
        "res.users",
        string="Verified By",
        readonly=True,
    )
    verified_date = fields.Datetime(
        string="Verified Date",
        readonly=True,
    )

    # Withdrawal tracking
    withdrawn_by_id = fields.Many2one(
        "res.users",
        string="Withdrawn By",
        readonly=True,
    )
    withdrawn_date = fields.Datetime(
        string="Withdrawn Date",
        readonly=True,
    )
    withdrawal_reason = fields.Text(
        string="Withdrawal Reason",
        readonly=True,
    )
    withdrawal_channel = fields.Selection(
        [
            ("web", "Web Portal"),
            ("mobile", "Mobile App"),
            ("api", "API"),
            ("paper", "Paper Form"),
            ("verbal", "Verbal Request"),
            ("other", "Other"),
        ],
        string="Withdrawal Channel",
        readonly=True,
    )

    # Refusal tracking
    refusal_reason = fields.Text(
        string="Refusal Reason",
        readonly=True,
        help="Reason why consent was refused",
    )

    # Version history
    history_ids = fields.One2many(
        "spp.consent.history",
        "consent_id",
        string="Version History",
    )
    history_count = fields.Integer(
        compute="_compute_history_count",
        string="History Count",
    )
    current_version = fields.Integer(
        default=0,
        help="Current version number",
    )

    # ========================================================================
    # COMPUTED FIELDS
    # ========================================================================
    is_valid = fields.Boolean(
        compute="_compute_is_valid",
        string="Is Valid",
        help="Whether consent is currently valid for processing",
    )

    days_until_expiry = fields.Integer(
        compute="_compute_days_until_expiry",
        string="Days Until Expiry",
    )

    # ========================================================================
    # CONSTRAINTS
    # ========================================================================
    _unique_external_id = models.Constraint("UNIQUE(external_id)", "External ID must be unique")

    @api.constrains("signatory_id", "group_id")
    def _check_signatory_or_group(self):
        """Ensure at least one of signatory or group is set."""
        for record in self:
            if not record.signatory_id and not record.group_id:
                raise ValidationError(
                    _("Consent must have either a signatory (individual) or a group, or both for group consent.")
                )

    @api.constrains("recipient_mode", "recipient_ids", "allowed_recipient_types")
    def _check_recipient_consistency(self):
        """Ensure recipient fields match the selected mode."""
        for record in self:
            if record.recipient_mode == "specific" and record.allowed_recipient_types:
                raise ValidationError(
                    _("When using 'Specific Organizations' mode, allowed organization types should be empty.")
                )
            if record.recipient_mode == "category" and record.recipient_ids:
                raise ValidationError(
                    _("When using 'Organization Categories' mode, specific recipients should be empty.")
                )

    @api.constrains("notice_id", "allowed_recipient_types", "purpose_ids", "personal_data_ids")
    def _check_within_notice_boundary(self):
        """
        Ensure consent terms don't exceed what the privacy notice describes.

        This implements the "Notice as Boundary" pattern:
        - The privacy notice defines the MAXIMUM scope (what was legally described)
        - The consent can be a SUBSET (what the beneficiary actually agreed to)
        - The consent CANNOT EXCEED the notice scope (would be uninformed consent)

        This is a compliance requirement under GDPR and ISO 27560/29184.
        """
        for record in self:
            if not record.notice_id:
                continue

            # Check organization types (if notice defines any)
            if record.allowed_recipient_types:
                notice_types = record.notice_id.max_recipient_types
                if notice_types:
                    invalid_types = record.allowed_recipient_types - notice_types
                    if invalid_types:
                        raise ValidationError(
                            _(
                                "Consent includes organization types not covered by the privacy notice: %(types)s\n\n"
                                "The privacy notice only allows: %(allowed)s",
                                types=", ".join(invalid_types.mapped("name")),
                                allowed=", ".join(notice_types.mapped("name")),
                            )
                        )

            # Check purposes (if notice defines any)
            if record.purpose_ids:
                notice_purposes = record.notice_id.purpose_ids
                if notice_purposes:
                    invalid_purposes = record.purpose_ids - notice_purposes
                    if invalid_purposes:
                        raise ValidationError(
                            _(
                                "Consent includes purposes not covered by the privacy notice: %(purposes)s\n\n"
                                "The privacy notice only allows: %(allowed)s",
                                purposes=", ".join(invalid_purposes.mapped("name")),
                                allowed=", ".join(notice_purposes.mapped("name")),
                            )
                        )

            # Check personal data categories (if notice defines any)
            if record.personal_data_ids:
                notice_data = record.notice_id.data_category_ids
                if notice_data:
                    invalid_data = record.personal_data_ids - notice_data
                    if invalid_data:
                        raise ValidationError(
                            _(
                                "Consent includes data categories not covered by the privacy notice: %(categories)s\n\n"
                                "The privacy notice only allows: %(allowed)s",
                                categories=", ".join(invalid_data.mapped("name")),
                                allowed=", ".join(notice_data.mapped("name")),
                            )
                        )

    # ========================================================================
    # COMPUTED METHODS
    # ========================================================================
    @api.depends("status")
    def _compute_status_dpv_uri(self):
        """Compute DPV URI for current status"""
        status_map = {
            "requested": "https://w3id.org/dpv#ConsentRequested",
            "given": "https://w3id.org/dpv#ConsentGiven",
            "renewed": "https://w3id.org/dpv#RenewedConsentGiven",
            "refused": "https://w3id.org/dpv#ConsentRefused",
            "withdrawn": "https://w3id.org/dpv#ConsentWithdrawn",
            "expired": "https://w3id.org/dpv#ConsentExpired",
            "invalidated": "https://w3id.org/dpv#ConsentInvalidated",
        }
        for rec in self:
            rec.status_dpv_uri = status_map.get(rec.status, "")

    @api.depends("status", "effective_date", "expiry")
    def _compute_is_valid(self):
        """Check if consent is currently valid for processing"""
        today = fields.Date.today()
        for rec in self:
            rec.is_valid = (
                rec.status in ("given", "renewed")
                and (not rec.effective_date or rec.effective_date <= today)
                and (not rec.expiry or rec.expiry >= today)
            )

    @api.depends("expiry")
    def _compute_days_until_expiry(self):
        """Calculate days until expiry"""
        today = fields.Date.today()
        for rec in self:
            if rec.expiry:
                delta = rec.expiry - today
                rec.days_until_expiry = delta.days
            else:
                rec.days_until_expiry = 0

    @api.depends("history_ids")
    def _compute_history_count(self):
        for rec in self:
            rec.history_count = len(rec.history_ids)

    # ========================================================================
    # CRUD OVERRIDES
    # ========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate external ID and record history."""
        for vals in vals_list:
            # Generate external ID if not provided
            if not vals.get("external_id"):
                vals["external_id"] = str(uuid.uuid4())

            # Set effective date to today if not provided and status is given
            if vals.get("status") == "given" and not vals.get("effective_date"):
                vals["effective_date"] = fields.Date.today()

        records = super().create(vals_list)

        # Record creation in history
        for record in records:
            self.env["spp.consent.history"].record_action(
                consent=record,
                action="create",
                new_status=record.status,
                new_values={
                    "status": record.status,
                    "legal_basis": record.legal_basis,
                },
            )
            record.current_version = 1

        # Trigger consent summary recomputation on affected registrants
        records._trigger_consent_summary_recompute()

        return records

    def write(self, vals):
        """Override write to track changes in history and protect immutable fields."""
        # Protect consent terms after consent is given (defense-in-depth)
        # This ensures immutability even if UI readonly is bypassed
        attempted_protected = set(vals.keys()) & PROTECTED_FIELDS
        if attempted_protected:
            for record in self:
                if record.status != "requested":
                    raise UserError(
                        _(
                            "Cannot modify consent terms after consent is given. "
                            "To correct errors, invalidate this consent and create a new one.\n\n"
                            "Attempted to modify: %(fields)s",
                            fields=", ".join(sorted(attempted_protected)),
                        )
                    )

        # Validate status transitions to prevent reversion attacks
        if "status" in vals:
            new_status = vals["status"]
            for record in self:
                valid_transitions = VALID_STATUS_TRANSITIONS.get(record.status, set())
                if new_status not in valid_transitions:
                    raise UserError(
                        _(
                            "Invalid status transition from '%(old)s' to '%(new)s'.\n\n"
                            "Valid transitions from '%(old)s' are: %(valid)s",
                            old=record.status,
                            new=new_status,
                            valid=", ".join(sorted(valid_transitions))
                            if valid_transitions
                            else "none (terminal state)",
                        )
                    )

        # Track status changes
        if "status" in vals:
            for record in self:
                action = self._get_action_for_status_change(record.status, vals["status"])

                # Extract reason and channel from vals if present
                # Use withdrawal_reason for withdrawals, refusal_reason for refusals
                reason = vals.get("withdrawal_reason") or vals.get("refusal_reason")
                channel = vals.get("withdrawal_channel")

                self.env["spp.consent.history"].record_action(
                    consent=record,
                    action=action,
                    previous_status=record.status,
                    new_status=vals["status"],
                    reason=reason,
                    channel=channel,
                )

        result = super().write(vals)

        # Update version number after write
        if "status" in vals:
            for record in self:
                record.current_version = len(record.history_ids)

        # Trigger consent summary recomputation if relevant fields changed
        summary_fields = {
            "status",
            "expiry",
            "recipient_mode",
            "allowed_recipient_types",
            "recipient_ids",
            "purpose_ids",
        }
        if summary_fields & set(vals.keys()):
            self._trigger_consent_summary_recompute()

        return result

    def _get_action_for_status_change(self, old_status, new_status):
        """Determine the action type for a status change"""
        action_map = {
            ("requested", "given"): "give",
            ("requested", "refused"): "refuse",
            ("given", "withdrawn"): "withdraw",
            ("given", "expired"): "expire",
            ("given", "invalidated"): "invalidate",
            ("given", "renewed"): "renew",
            ("renewed", "withdrawn"): "withdraw",
            ("renewed", "expired"): "expire",
        }
        return action_map.get((old_status, new_status), "modify")

    def _trigger_consent_summary_recompute(self):
        """Trigger recomputation of consent_summary on affected registrants.

        This is needed because consent_summary depends on consents, but the
        relationship isn't via the consent_ids Many2many for all consents.
        """
        # Collect all affected partners (signatories and groups)
        partners = self.mapped("signatory_id") | self.mapped("group_id")
        # Filter out empty recordsets
        partners = partners.filtered(lambda p: p)
        if partners:
            # Invalidate cache and recompute
            partners.invalidate_recordset(["consent_summary"])
            partners._compute_consent_summary()

    def copy(self, default=None):
        """
        Override copy to prevent duplicating consents that are not in 'requested' status.

        SECURITY: This prevents an attack where someone copies a 'given' consent
        to get an editable version with the same terms. The copied consent would
        be in 'requested' status and have unlocked fields, allowing modification
        of the consent terms.

        Only consents in 'requested' status (not yet given) can be copied.
        """
        self.ensure_one()
        if self.status != "requested":
            raise UserError(
                _(
                    "Consent records cannot be copied after consent has been given.\n\n"
                    "Status '%(status)s' does not allow copying. "
                    "Only consents in 'requested' status can be duplicated.",
                    status=self.status,
                )
            )
        return super().copy(default=default)

    def unlink(self):
        """
        Override unlink to prevent deletion of consents that have been given.

        SECURITY: This prevents deletion of consent records which would:
        - Remove the audit trail of what was consented to
        - Potentially violate legal requirements for consent record retention
        - Allow manipulation of consent history

        Only consents in 'requested' or 'refused' status (never activated) can be deleted.
        Once a consent is given, it must be preserved for compliance.
        """
        for record in self:
            if record.status in NON_DELETABLE_STATUSES:
                raise UserError(
                    _(
                        "Cannot delete consent records that have been given or are in a terminal state.\n\n"
                        "Consent '%(name)s' has status '%(status)s' and must be preserved for "
                        "audit trail and legal compliance.\n\n"
                        "To correct errors, use the 'Invalidate' action instead.",
                        name=record.name,
                        status=record.status,
                    )
                )

        # Trigger consent summary recompute before deletion (for 'requested'/'refused' consents)
        self._trigger_consent_summary_recompute()

        return super().unlink()

    # ========================================================================
    # STATUS ACTIONS
    # ========================================================================
    def action_give(self):
        """Record that consent has been given"""
        self.ensure_one()
        if self.status != "requested":
            return

        self.write(
            {
                "status": "given",
                "effective_date": self.effective_date or fields.Date.today(),
            }
        )

    def action_refuse(self, reason=None):
        """Record that consent was refused"""
        self.ensure_one()
        if self.status != "requested":
            return

        # History is automatically recorded by write() override
        vals = {"status": "refused"}
        if reason:
            vals["refusal_reason"] = reason
        self.write(vals)

    def action_withdraw(self, reason=None, channel=None):
        """Withdraw consent - GDPR Article 7(3) compliant"""
        self.ensure_one()
        if self.status not in ("given", "renewed"):
            return

        # History is automatically recorded by write() override
        self.write(
            {
                "status": "withdrawn",
                "withdrawn_by_id": self.env.user.id,
                "withdrawn_date": fields.Datetime.now(),
                "withdrawal_reason": reason,
                "withdrawal_channel": channel,
            }
        )

    def action_renew(self, new_expiry=None):
        """Renew consent with optional new expiry date"""
        self.ensure_one()
        if self.status not in ("given", "expired"):
            return

        vals = {"status": "renewed"}
        if new_expiry:
            vals["expiry"] = new_expiry

        self.env["spp.consent.history"].record_action(
            consent=self,
            action="renew",
            previous_status=self.status,
            new_status="renewed",
        )
        self.write(vals)

    def action_verify(self):
        """Mark consent as verified (for paper/verbal consent)"""
        self.ensure_one()
        self.write(
            {
                "verified_by_id": self.env.user.id,
                "verified_date": fields.Datetime.now(),
            }
        )

    # ========================================================================
    # EXPIRY MANAGEMENT
    # ========================================================================
    @api.model
    def _cron_check_expired(self):
        """Scheduled action to mark expired consents.

        Processes in batches for performance on large datasets.
        """
        today = fields.Date.today()
        expired = self.search(
            [
                ("status", "in", ("given", "renewed")),
                ("expiry", "<", today),
            ]
        )

        if not expired:
            _logger.info("No expired consents found")
            return

        # Process in batches for better performance
        total_processed = 0

        # nosemgrep: odoo-commit-in-loop — batch consent expiry cron
        for i in range(0, len(expired), BATCH_SIZE_EXPIRED_CONSENT):
            batch = expired[i : i + BATCH_SIZE_EXPIRED_CONSENT]

            # Batch update status - write() override automatically records history
            batch.write({"status": "expired"})
            total_processed += len(batch)

            # Commit after each batch to avoid long transactions
            if i + BATCH_SIZE_EXPIRED_CONSENT < len(expired):
                self.env.cr.commit()

            _logger.info(
                "Expired batch %d-%d of %d consents",
                i + 1,
                min(i + BATCH_SIZE_EXPIRED_CONSENT, len(expired)),
                len(expired),
            )

        _logger.info("Marked %d consents as expired in total", total_processed)

    # ========================================================================
    # CONSENT CHECKING
    # ========================================================================
    @api.model
    def check_consent(
        self,
        registrant_id: int,
        recipient_id: int | None = None,
        recipient_org_type: str | None = None,
        controller_id: int | None = None,
        purpose_code: str | None = None,
    ) -> "models.Model":
        """
        Check if valid consent exists for a registrant.

        Supports two matching modes:
        1. Specific: Consent granted to specific recipient organizations
        2. Category: Consent granted to categories of organizations (e.g., all NGOs)

        Args:
            registrant_id: ID of the data subject (individual or group)
            recipient_id: Optional specific recipient organization ID to check
            recipient_org_type: Optional organization type code for category matching
                               (e.g., 'ngo', 'government', 'private')
            controller_id: Optional controller to check against
            purpose_code: Optional purpose code to check

        Returns:
            spp.consent record if valid consent found, otherwise empty recordset
        """
        # Enforce permission checks to prevent unauthorized API access
        self.check_access_rights("read")
        self.check_access_rule("read")

        today = fields.Date.today()

        # Base domain for valid consent
        base_domain = [
            "|",
            ("signatory_id", "=", registrant_id),
            ("group_id", "=", registrant_id),
            ("status", "in", ("given", "renewed")),
            "|",
            ("effective_date", "=", False),
            ("effective_date", "<=", today),
            "|",
            ("expiry", "=", False),
            ("expiry", ">=", today),
        ]

        if controller_id:
            base_domain.append(("controller_id", "=", controller_id))

        # 1. Try specific recipient consent
        if recipient_id:
            consent = self._find_specific_recipient_consent(base_domain, recipient_id, purpose_code)
            if consent:
                return consent

        # 2. Try category-based consent
        if recipient_org_type:
            consent = self._find_category_recipient_consent(base_domain, recipient_org_type, purpose_code)
            if consent:
                return consent

        # SECURITY: Fail closed if no recipient specified
        # This prevents accidentally returning consent for the wrong recipient
        if not recipient_id and not recipient_org_type:
            _logger.warning(
                "check_consent called without recipient_id or recipient_org_type. "
                "This is unsafe - failing closed. Registrant ID: %s",
                registrant_id,
            )

        return self.env["spp.consent"]

    def _find_specific_recipient_consent(self, base_domain, recipient_id, purpose_code):
        """Find consent that lists a specific recipient organization."""
        domain = base_domain + [
            "|",
            ("recipient_mode", "=", False),  # Legacy consents without mode
            ("recipient_mode", "=", "specific"),
            ("recipient_ids", "in", [recipient_id]),
        ]

        if purpose_code:
            domain.append(("purpose_ids.code", "=", purpose_code))

        return self.search(domain, limit=1) or None

    def _find_category_recipient_consent(self, base_domain, org_type_code, purpose_code):
        """
        Find consent that covers a category of organizations.

        Example: Beneficiary consented to "all NGOs" and org_type_code = "ngo"

        Optimized to use database filtering instead of Python loops to avoid N+1 queries.
        """
        # Build domain to filter at database level
        domain = base_domain + [
            ("recipient_mode", "=", "category"),
            ("allowed_recipient_types.code", "=", org_type_code),
        ]

        # Add purpose filter if specified
        if purpose_code:
            domain.append(("purpose_ids.code", "=", purpose_code))

        # Find matching consent using database query
        return self.search(domain, limit=1) or None

    def is_recipient_allowed(self, recipient_id=None, org_type_code=None):
        """
        Check if a recipient is covered by this consent.

        Args:
            recipient_id: Specific recipient organization ID
            org_type_code: Organization type code for category matching

        Returns:
            True if recipient is allowed, False otherwise
        """
        self.ensure_one()

        # Mode: specific - check if recipient is in the list
        if self.recipient_mode == "specific" or not self.recipient_mode:
            if recipient_id:
                return recipient_id in self.recipient_ids.ids
            return bool(self.recipient_ids)

        # Mode: category - check if org type is in allowed types
        if self.recipient_mode == "category":
            if org_type_code:
                allowed_codes = self.allowed_recipient_types.mapped("code")
                return org_type_code in allowed_codes
            return bool(self.allowed_recipient_types)

        return False

    # ========================================================================
    # RECEIPT GENERATION
    # ========================================================================
    def generate_receipt(self):
        """
        Generate a consent receipt per ISO 27560.

        Returns a dict suitable for JSON serialization and external systems.
        """
        self.ensure_one()

        # Get data subject identifier (external, not DB ID)
        if self.signatory_id:
            data_subject_id = self.signatory_id.spp_id if hasattr(self.signatory_id, "spp_id") else self.external_id
        elif self.group_id:
            data_subject_id = self.group_id.spp_id if hasattr(self.group_id, "spp_id") else self.external_id
        else:
            data_subject_id = self.external_id

        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")

        return {
            # Header
            "receiptId": str(uuid.uuid4()),
            "schemaVersion": self.schema_version,
            "timestamp": fields.Datetime.now().isoformat(),
            "recordType": "consent_receipt",
            # Consent reference
            "consentRecordId": self.external_id,
            "consentDate": self.create_date.isoformat() if self.create_date else None,
            # Parties
            "dataSubject": {"identifier": data_subject_id},
            "dataController": {
                "name": self.controller_id.name if self.controller_id else None,
                "identifier": self.controller_id.vat if self.controller_id else None,
            },
            "recipients": [{"name": r.name, "identifier": r.vat} for r in self.recipient_ids],
            # Processing
            "purposes": [
                {
                    "code": p.code,
                    "name": p.name,
                    "dpvUri": p.dpv_uri,
                }
                for p in self.purpose_ids
            ],
            "legalBasis": {
                "code": self.legal_basis,
                "reference": self.legal_basis_reference,
            },
            "personalDataCategories": [
                {
                    "code": pd.code,
                    "name": pd.name,
                    "isSensitive": pd.is_sensitive,
                }
                for pd in self.personal_data_ids
            ],
            "processingOperations": [{"code": p.code, "name": p.name} for p in self.processing_ids],
            # Validity
            "effectiveDate": self.effective_date.isoformat() if self.effective_date else None,
            "expiryDate": self.expiry.isoformat() if self.expiry else None,
            # Status
            "status": self.status,
            "statusDpvUri": self.status_dpv_uri,
            # Collection
            "collectionMethod": self.collection_method,
            # Rights and withdrawal
            "withdrawalUri": self.withdrawal_uri or f"{base_url}/consent/{self.external_id}/withdraw",
            "dataSubjectRights": [
                "Right to access your data",
                "Right to rectification",
                "Right to erasure",
                "Right to data portability",
                "Right to withdraw consent at any time",
            ],
            # Privacy notice
            "privacyNotice": {
                "version": self.notice_version,
                "url": self.notice_id.full_policy_url if self.notice_id else None,
            },
        }

    # ========================================================================
    # VIEW ACTIONS
    # ========================================================================
    def action_view_history(self):
        """Open history view for this consent"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"History: {self.name}",
            "res_model": "spp.consent.history",
            "view_mode": "tree,form",
            "domain": [("consent_id", "=", self.id)],
            "context": {"default_consent_id": self.id},
        }

    # ========================================================================
    # ISO 27560 / DPV JSON-LD EXPORT
    # ========================================================================
    def to_jsonld(self) -> dict[str, Any]:
        """
        Export consent record as JSON-LD per ISO 27560 / W3C DPV.

        Returns a dict with proper JSON-LD structure including @context
        that can be serialized to JSON for interoperability with other systems.

        See: https://w3id.org/dpv
        See: ISO/IEC TS 27560:2023
        """
        self.ensure_one()

        # Get external identifiers (never expose DB IDs)
        data_subject_id = None
        if self.signatory_id:
            data_subject_id = getattr(self.signatory_id, "spp_id", self.external_id)
        elif self.group_id:
            data_subject_id = getattr(self.group_id, "spp_id", self.external_id)

        controller_id = None
        if self.controller_id:
            controller_id = self.controller_id.vat or self.controller_id.ref

        # Build the JSON-LD structure
        jsonld = {
            "@context": {
                "@vocab": "https://w3id.org/dpv#",
                "dpv": "https://w3id.org/dpv#",
                "dpv-pd": "https://w3id.org/dpv/dpv-pd#",
                "dpv-gdpr": "https://w3id.org/dpv/dpv-gdpr#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "iso27560": "urn:iso:std:iso-iec:ts:27560:",
                "spp": "https://openspp.org/vocab/",
                "hasIdentifier": {"@type": "xsd:string"},
                "hasTimestamp": {"@type": "xsd:dateTime"},
                "hasExpiryDate": {"@type": "xsd:date"},
                "hasEffectiveDate": {"@type": "xsd:date"},
            },
            "@type": [
                "dpv:ConsentRecord",
                "iso27560:ConsentRecordInformationStructure",
            ],
            "@id": f"urn:uuid:{self.external_id}",
            # ----------------------------------------------------------------
            # Section 1: Header/Metadata
            # ----------------------------------------------------------------
            "dpv:hasIdentifier": self.external_id,
            "iso27560:schemaVersion": self.schema_version,
            "iso27560:recordType": self.record_type,
            "dpv:hasTimestamp": self.create_date.isoformat() if self.create_date else None,
            # ----------------------------------------------------------------
            # Section 2: Parties
            # ----------------------------------------------------------------
            "dpv:hasDataSubject": {
                "@type": "dpv:DataSubject",
                "dpv:hasIdentifier": data_subject_id,
            },
            "dpv:hasDataController": {
                "@type": "dpv:DataController",
                "dpv:hasName": self.controller_id.name if self.controller_id else None,
                "dpv:hasIdentifier": controller_id,
                "dpv:hasContact": self.controller_id.email if self.controller_id else None,
            }
            if self.controller_id
            else None,
            "dpv:hasRecipient": [
                {
                    "@type": "dpv:Recipient",
                    "dpv:hasName": r.name,
                    "dpv:hasIdentifier": r.vat or r.ref,
                }
                for r in self.recipient_ids
            ]
            if self.recipient_ids
            else None,
            "dpv:isIndicatedBy": {
                "@type": self._get_delegation_dpv_type(),
                "dpv:hasIdentifier": getattr(self.indicated_by_id, "spp_id", None)
                if self.indicated_by_id
                else data_subject_id,
            }
            if self.delegation_type != "self" or self.indicated_by_id
            else None,
            # ----------------------------------------------------------------
            # Section 3: Processing
            # ----------------------------------------------------------------
            "dpv:hasPurpose": [
                {
                    "@type": p.dpv_concept or "dpv:Purpose",
                    "@id": p.dpv_uri,
                    "dpv:hasName": p.name,
                    "spp:purposeCode": p.code,
                    "spp:isSocialProtection": p.is_social_protection,
                }
                for p in self.purpose_ids
            ]
            if self.purpose_ids
            else None,
            "dpv:hasLegalBasis": {
                "@type": self._get_legal_basis_dpv_type(),
                "dpv:hasDescription": dict(self._fields["legal_basis"].selection).get(self.legal_basis),
                "dpv:hasReference": self.legal_basis_reference,
            },
            "dpv:hasPersonalData": [
                {
                    "@type": pd.dpv_concept or "dpv:PersonalData",
                    "@id": pd.dpv_uri,
                    "dpv:hasName": pd.name,
                    "spp:dataCode": pd.code,
                    "dpv:isSensitivePersonalData": pd.is_sensitive,
                    "dpv:sensitivityReason": pd.sensitivity_reason if pd.is_sensitive else None,
                }
                for pd in self.personal_data_ids
            ]
            if self.personal_data_ids
            else None,
            "dpv:hasProcessing": [
                {
                    "@type": proc.dpv_concept or "dpv:Processing",
                    "@id": proc.dpv_uri,
                    "dpv:hasName": proc.name,
                    "spp:processingCode": proc.code,
                    "dpv:hasRisk": proc.risk_level,
                }
                for proc in self.processing_ids
            ]
            if self.processing_ids
            else None,
            "dpv:hasStorageCondition": {
                "@type": "dpv:StorageCondition",
                "dpv:hasDuration": f"P{self.storage_duration}D" if self.storage_duration else None,
                "dpv:hasLocation": self.storage_location,
            }
            if self.storage_duration or self.storage_location
            else None,
            "dpv:hasJurisdiction": self.jurisdiction,
            "dpv:hasNotice": {
                "@type": "dpv:PrivacyNotice",
                "dpv:hasVersion": self.notice_version,
                "dpv:hasName": self.notice_id.name if self.notice_id else None,
                "dpv:hasURL": self.notice_id.full_policy_url if self.notice_id else None,
            }
            if self.notice_id
            else None,
            # ----------------------------------------------------------------
            # Section 4: Consent Specifics
            # ----------------------------------------------------------------
            "dpv:hasConsentStatus": {
                "@type": self.status_dpv_uri.split("#")[-1] if self.status_dpv_uri else None,
                "@id": self.status_dpv_uri,
            },
            "dpv:hasEffectiveDate": self.effective_date.isoformat() if self.effective_date else None,
            "dpv:hasExpiryDate": self.expiry.isoformat() if self.expiry else None,
            "dpv:isValidFor": self.is_valid,
            "spp:collectionMethod": self.collection_method,
            "dpv:hasWithdrawalMechanism": {
                "@type": "dpv:WithdrawalMechanism",
                "dpv:hasURL": self.withdrawal_uri,
                "dpv:hasDescription": self.withdrawal_instructions,
            }
            if self.withdrawal_uri or self.withdrawal_instructions
            else None,
            # ----------------------------------------------------------------
            # Audit/Provenance
            # ----------------------------------------------------------------
            "dpv:hasProvenance": {
                "@type": "dpv:Provenance",
                "dpv:hasCreatedBy": self.created_by_id.name if self.created_by_id else None,
                "dpv:hasVerifiedBy": self.verified_by_id.name if self.verified_by_id else None,
                "dpv:hasVerifiedDate": (self.verified_date.isoformat() if self.verified_date else None),
                "dpv:versionNumber": self.current_version,
            },
        }

        # Remove None values for cleaner output
        return self._clean_jsonld(jsonld)

    def _get_legal_basis_dpv_type(self):
        """Map legal basis to DPV/GDPR type"""
        mapping = {
            "consent": "dpv-gdpr:A6-1-a",
            "contract": "dpv-gdpr:A6-1-b",
            "legal_obligation": "dpv-gdpr:A6-1-c",
            "vital_interest": "dpv-gdpr:A6-1-d",
            "public_interest": "dpv-gdpr:A6-1-e",
            "legitimate_interest": "dpv-gdpr:A6-1-f",
        }
        return mapping.get(self.legal_basis, "dpv:LegalBasis")

    def _get_delegation_dpv_type(self):
        """Map delegation type to DPV type"""
        mapping = {
            "self": "dpv:DataSubject",
            "guardian": "dpv:Guardian",
            "parent": "dpv:ParentOfDataSubject",
            "poa": "dpv:Representative",
            "representative": "dpv:Representative",
        }
        return mapping.get(self.delegation_type, "dpv:DataSubject")

    def _clean_jsonld(self, obj):
        """Recursively remove None values from JSON-LD structure"""
        if isinstance(obj, dict):
            return {k: self._clean_jsonld(v) for k, v in obj.items() if v is not None and v != [] and v != {}}
        if isinstance(obj, list):
            cleaned = [self._clean_jsonld(item) for item in obj if item is not None]
            return cleaned if cleaned else None
        return obj

    def export_jsonld(self) -> dict[str, Any]:
        """
        Action to export consent as JSON-LD file.

        Returns:
            Dictionary containing action to download the JSON-LD file
        """
        import base64
        import json

        self.ensure_one()
        jsonld_data = self.to_jsonld()
        json_str = json.dumps(jsonld_data, indent=2, ensure_ascii=False)

        # Create attachment
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"consent_{self.external_id}.jsonld",
                "type": "binary",
                "datas": base64.b64encode(json_str.encode("utf-8")),
                "mimetype": "application/ld+json",
            }
        )

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def to_jsonld_batch(self) -> dict[str, Any]:
        """
        Export multiple consent records as JSON-LD array.

        Returns:
            Dictionary with @graph containing array of consent records as JSON-LD
        """
        return {
            "@context": {
                "@vocab": "https://w3id.org/dpv#",
                "dpv": "https://w3id.org/dpv#",
                "dpv-pd": "https://w3id.org/dpv/dpv-pd#",
                "dpv-gdpr": "https://w3id.org/dpv/dpv-gdpr#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "iso27560": "urn:iso:std:iso-iec:ts:27560:",
                "spp": "https://openspp.org/vocab/",
            },
            "@graph": [rec.to_jsonld() for rec in self],
        }
