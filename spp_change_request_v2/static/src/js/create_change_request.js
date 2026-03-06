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

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        onWillStart(async () => {
            if (this.model.root.resModel !== "spp.change.request") {
                return;
            }
            const is_admin = await user.hasGroup("spp_security.group_spp_admin");
            const is_cr_user = await user.hasGroup(
                "spp_change_request_v2.group_cr_user"
            );
            if (is_admin || is_cr_user) {
                this.customListCreateButton = {
                    label: "New Request",
                    title: "Create a New Change Request",
                    className: "o_list_button_add_cr",
                };
            }
        });
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
