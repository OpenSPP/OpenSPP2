/** @odoo-module **/

import {FormController} from "@web/views/form/form_controller";
import {ListController} from "@web/views/list/list_controller";
import {onWillStart} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {useService} from "@web/core/utils/hooks";

/**
 * Client action to close modal and then open program form.
 * This ensures proper sequencing with async/await.
 */
async function openProgramCloseModal(env, action) {
    const actionService = env.services.action;
    const programId = action.params?.program_id;
    const programName = action.params?.name || "Program";
    const viewId = action.params?.view_id || false;

    await actionService.doAction(
        {type: "ir.actions.act_window_close"},
        {clearBreadcrumbs: true}
    );

    if (programId) {
        await actionService.doAction({
            type: "ir.actions.act_window",
            name: programName,
            res_model: "spp.program",
            res_id: programId,
            views: [[viewId, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("open_program_close_modal", openProgramCloseModal);

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        onWillStart(async () => {
            if (this.model.root.resModel !== "spp.program") {
                return;
            }
            const is_admin = await user.hasGroup("spp_security.group_spp_admin");
            const is_program_manager = await user.hasGroup(
                "spp_programs.group_programs_manager"
            );
            if (is_admin || is_program_manager) {
                this.customListCreateButton = {
                    label: "Create Program",
                    title: "Create a New Program",
                    className: "o_list_button_add_program",
                };
            }
        });
    },

    /**
     * Opens the Create Program wizard when the custom button is clicked.
     */
    async onCustomListCreate() {
        if (this.model.root.resModel === "spp.program") {
            await this.actionService.doAction(
                "spp_programs.action_create_program_wizard",
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
        if (this.props.resModel === "spp.program") {
            this.hideFormCreateButton = true;
        }
    },
});
