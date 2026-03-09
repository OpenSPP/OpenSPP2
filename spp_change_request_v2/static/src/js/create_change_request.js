/* @odoo-module */

import {FormController} from "@web/views/form/form_controller";
import {ListController} from "@web/views/list/list_controller";
import {onWillStart} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

/**
 * Client action to close wizard modal and then open CR detail form.
 * Uses async/await to ensure the modal is fully closed before navigating.
 */
async function openCRCloseModal(env, action) {
    const actionService = env.services.action;
    const params = action.params || {};

    await actionService.doAction(
        {type: "ir.actions.act_window_close"},
        {clearBreadcrumbs: true}
    );

    if (params.res_id) {
        await actionService.doAction({
            type: "ir.actions.act_window",
            name: params.name || "Change Request Details",
            res_model: params.res_model,
            res_id: params.res_id,
            view_mode: "form",
            views: [[params.view_id || false, "form"]],
            target: "current",
            context: params.context || {},
        });
    }
}

registry.category("actions").add("open_cr_close_modal", openCRCloseModal);

/**
 * Client action for stage navigation that replaces the current breadcrumb
 * instead of pushing a new one. This keeps the breadcrumb clean when
 * navigating between Details → Documents → Review.
 */
async function navigateCRStage(env, action) {
    const actionService = env.services.action;
    const params = action.params || {};

    const windowAction = {
        type: "ir.actions.act_window",
        name: params.name || "Change Request",
        res_model: params.res_model,
        res_id: params.res_id,
        view_mode: "form",
        views: [[false, "form"]],
        target: "current",
        context: params.context || {},
    };

    await actionService.doAction(windowAction, {
        stackPosition: "replaceCurrentAction",
    });
}

registry.category("actions").add("navigate_cr_stage", navigateCRStage);

/**
 * Client action to navigate back to the CR list view, clearing all breadcrumbs.
 */
async function navigateCRList(env) {
    const actionService = env.services.action;

    await actionService.doAction("spp_change_request_v2.action_change_request", {
        clearBreadcrumbs: true,
    });
}

registry.category("actions").add("navigate_cr_list", navigateCRList);

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        onWillStart(async () => {
            if (this.model.root.resModel !== "spp.change.request") {
                return;
            }
            const is_admin = await user.hasGroup("spp_security.group_spp_admin");
            const is_cr_manager = await user.hasGroup(
                "spp_change_request_v2.group_cr_manager"
            );
            if (is_admin || is_cr_manager) {
                this.customListCreateButton = {
                    label: "New Request",
                    title: "Create a New Change Request",
                    className: "o_list_button_add_cr",
                };
            } else {
                this.activeActions = {...this.activeActions, create: false};
            }
        });
    },

    /**
     * Override row-click to route CRs to stage-specific forms.
     *
     * For draft/revision CRs: reads stage + detail info, then opens
     * the appropriate stage form (details/documents/review).
     * For other states: opens the default CR form.
     */
    async openRecord(record) {
        if (this.model.root.resModel === "spp.change.request") {
            // Read the fields we need for routing
            const [crData] = await this.model.orm.read(
                "spp.change.request",
                [record.resId],
                ["stage", "approval_state", "detail_res_model", "detail_res_id"]
            );

            if (crData) {
                const isDraftOrRevision =
                    crData.approval_state === "draft" ||
                    crData.approval_state === "revision";

                if (isDraftOrRevision && crData.stage === "documents") {
                    await this.actionService.doAction({
                        type: "ir.actions.act_window",
                        name: "Documents",
                        res_model: "spp.change.request",
                        res_id: record.resId,
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "current",
                        context: {
                            form_view_ref:
                                "spp_change_request_v2.spp_change_request_documents_form",
                            form_view_initial_mode: "edit",
                        },
                    });
                    return;
                }
                if (crData.stage === "review") {
                    await this.actionService.doAction({
                        type: "ir.actions.act_window",
                        name: "Review",
                        res_model: "spp.change.request",
                        res_id: record.resId,
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "current",
                        context: {
                            form_view_ref:
                                "spp_change_request_v2.spp_change_request_review_form",
                            form_view_initial_mode: "edit",
                        },
                    });
                    return;
                }
                // Default: details stage — open the detail model form
                if (
                    isDraftOrRevision &&
                    crData.detail_res_model &&
                    crData.detail_res_id
                ) {
                    await this.actionService.doAction({
                        type: "ir.actions.act_window",
                        name: "Change Request Details",
                        res_model: crData.detail_res_model,
                        res_id: crData.detail_res_id,
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "current",
                        context: {
                            create: false,
                            delete: false,
                            form_view_initial_mode: "edit",
                        },
                    });
                    return;
                }
            }
        }
        return super.openRecord(record);
    },

    /**
     * Opens the Create Change Request wizard when the custom button is clicked.
     */
    async onCustomListCreate() {
        if (this.model.root.resModel === "spp.change.request") {
            await this.actionService.doAction(
                "spp_change_request_v2.action_cr_create_wizard",
                {
                    onClose: async () => {
                        await this.model.root.load();
                    },
                }
            );
            return;
        }
        return super.onCustomListCreate(...arguments);
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup();
        if (this.props.resModel === "spp.change.request") {
            this.hideFormCreateButton = true;
        }
        // Row click handling for CR create wizard is now in cr_search_results_field.js
    },
});
