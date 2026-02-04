/** @odoo-module **/

import {Component, onMounted, onWillUnmount, useRef, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

/**
 * CRReviewPanel - Split-pane review component for change requests
 *
 * Provides a side-by-side view of:
 * - Left: Current registrant data
 * - Right: Proposed changes
 *
 * Keyboard shortcuts:
 * - A: Approve
 * - R: Request changes
 * - D: Decline
 * - N: Next in queue
 * - P: Previous in queue
 * - Escape: Close panel
 */
export class CRReviewPanel extends Component {
    static template = "spp_change_request_v2.CRReviewPanel";
    static props = {
        crId: {type: Number, optional: true},
        onClose: {type: Function, optional: true},
        onNavigate: {type: Function, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.rpc = useService("rpc");

        this.state = useState({
            loading: true,
            crData: null,
            registrantData: null,
            previewData: null,
            tierInfo: null,
            canApprove: false,
            canReject: false,
            showApproveComment: false,
            showRejectReason: false,
            showRevisionNotes: false,
            approveComment: "",
            rejectReason: "",
            revisionNotes: "",
        });

        this.panelRef = useRef("panel");

        onMounted(() => {
            this.loadData();
            document.addEventListener("keydown", this.onKeydown.bind(this));
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this.onKeydown.bind(this));
        });
    }

    async loadData() {
        if (!this.props.crId) {
            this.state.loading = false;
            return;
        }

        this.state.loading = true;

        try {
            // Load CR data
            const crData = await this.orm.read(
                "spp.change.request",
                [this.props.crId],
                [
                    "name",
                    "request_type_id",
                    "registrant_id",
                    "display_state",
                    "approval_state",
                    "can_approve",
                    "can_reject",
                    "document_ids",
                    "notes",
                    "create_uid",
                    "create_date",
                    "approval_review_ids",
                ]
            );

            if (crData.length > 0) {
                this.state.crData = crData[0];
                this.state.canApprove = crData[0].can_approve;
                this.state.canReject = crData[0].can_reject;

                // Load registrant data
                if (crData[0].registrant_id) {
                    await this.loadRegistrantData(crData[0].registrant_id[0]);
                }

                // Load preview data
                await this.loadPreviewData();

                // Load tier info for multi-tier approval
                await this.loadTierInfo();
            }
        } catch (error) {
            console.error("Error loading review panel data:", error);
            this.notification.add(_t("Error loading review data"), {
                type: "danger",
            });
        }

        this.state.loading = false;
    }

    async loadRegistrantData(registrantId) {
        const data = await this.orm.read(
            "res.partner",
            [registrantId],
            ["name", "spp_id", "is_group", "street", "city", "group_membership_ids"]
        );
        if (data.length > 0) {
            this.state.registrantData = data[0];
        }
    }

    async loadPreviewData() {
        try {
            const result = await this.orm.call("spp.change.request", "action_preview_changes", [[this.props.crId]]);
            this.state.previewData = result;
        } catch (error) {
            console.warn("Could not load preview data:", error);
        }
    }

    async loadTierInfo() {
        try {
            // Get approval reviews to determine current tier
            if (this.state.crData.approval_review_ids?.length > 0) {
                const reviews = await this.orm.read("spp.approval.review", this.state.crData.approval_review_ids, [
                    "status",
                    "current_tier",
                    "tier_review_ids",
                ]);
                const pendingReview = reviews.find((r) => r.status === "pending");
                if (pendingReview) {
                    this.state.tierInfo = {
                        currentTier: pendingReview.current_tier || 1,
                        totalTiers: pendingReview.tier_review_ids?.length || 1,
                    };
                }
            }
        } catch (error) {
            console.warn("Could not load tier info:", error);
        }
    }

    // Keyboard handler
    onKeydown(event) {
        // Don't handle if we're in an input
        if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") {
            return;
        }

        switch (event.key.toLowerCase()) {
            case "a":
                if (this.state.canApprove) {
                    event.preventDefault();
                    this.onApprove();
                }
                break;
            case "r":
                if (this.state.canReject) {
                    event.preventDefault();
                    this.onRequestChanges();
                }
                break;
            case "d":
                if (this.state.canReject) {
                    event.preventDefault();
                    this.onDecline();
                }
                break;
            case "n":
                event.preventDefault();
                this.onNext();
                break;
            case "p":
                event.preventDefault();
                this.onPrevious();
                break;
            case "escape":
                event.preventDefault();
                this.onClose();
                break;
        }
    }

    // Action handlers
    async onApprove() {
        if (this.state.showApproveComment) {
            // Submit approval with comment
            try {
                await this.orm.call("spp.change.request", "action_approve", [[this.props.crId]], {
                    comment: this.state.approveComment,
                });
                this.notification.add(_t("Request approved"), {type: "success"});
                this.state.showApproveComment = false;
                this.onNext();
            } catch (error) {
                this.notification.add(error.message || _t("Error approving request"), {
                    type: "danger",
                });
            }
        } else {
            this.state.showApproveComment = true;
        }
    }

    async onRequestChanges() {
        if (this.state.showRevisionNotes && this.state.revisionNotes) {
            try {
                await this.orm.call("spp.change.request", "_do_request_revision", [
                    [this.props.crId],
                    this.state.revisionNotes,
                ]);
                this.notification.add(_t("Changes requested"), {type: "success"});
                this.state.showRevisionNotes = false;
                this.onNext();
            } catch (error) {
                this.notification.add(error.message || _t("Error requesting changes"), {
                    type: "danger",
                });
            }
        } else {
            this.state.showRevisionNotes = true;
        }
    }

    async onDecline() {
        if (this.state.showRejectReason && this.state.rejectReason) {
            try {
                await this.orm.call("spp.change.request", "_do_reject", [[this.props.crId], this.state.rejectReason]);
                this.notification.add(_t("Request declined"), {type: "warning"});
                this.state.showRejectReason = false;
                this.onNext();
            } catch (error) {
                this.notification.add(error.message || _t("Error declining request"), {
                    type: "danger",
                });
            }
        } else {
            this.state.showRejectReason = true;
        }
    }

    onNext() {
        if (this.props.onNavigate) {
            this.props.onNavigate("next");
        }
    }

    onPrevious() {
        if (this.props.onNavigate) {
            this.props.onNavigate("previous");
        }
    }

    onClose() {
        if (this.props.onClose) {
            this.props.onClose();
        }
    }

    cancelComment() {
        this.state.showApproveComment = false;
        this.state.showRejectReason = false;
        this.state.showRevisionNotes = false;
        this.state.approveComment = "";
        this.state.rejectReason = "";
        this.state.revisionNotes = "";
    }

    // Getters for template
    get stateLabel() {
        const labels = {
            draft: _t("Draft"),
            pending: _t("Under Review"),
            revision: _t("Needs Changes"),
            approved: _t("Approved"),
            applied: _t("Completed"),
            rejected: _t("Declined"),
        };
        return labels[this.state.crData?.display_state] || "";
    }

    get stateBadgeClass() {
        const classes = {
            draft: "bg-secondary",
            pending: "bg-warning",
            revision: "bg-warning",
            approved: "bg-info",
            applied: "bg-success",
            rejected: "bg-danger",
        };
        return classes[this.state.crData?.display_state] || "bg-secondary";
    }

    get approveButtonLabel() {
        if (this.state.tierInfo && this.state.tierInfo.totalTiers > 1) {
            return _t("Approve (Tier %s)", this.state.tierInfo.currentTier);
        }
        return _t("Approve");
    }
}
