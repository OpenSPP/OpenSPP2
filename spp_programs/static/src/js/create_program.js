/** @odoo-module **/

import {ListController} from "@web/views/list/list_controller";
import {onWillStart} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {user} from "@web/core/user";
import {useService} from "@web/core/utils/hooks";

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        onWillStart(async () => {
            // Check if user has permission to create programs
            // Groups: spp_security.group_spp_admin OR spp_programs.group_programs_manager
            const is_admin = await user.hasGroup("spp_security.group_spp_admin");
            const is_program_manager = await user.hasGroup(
                "spp_programs.group_programs_manager"
            );
            this.canCreateProgram = is_admin || is_program_manager;
        });
    },

    /**
     * Opens the Create Program wizard when the "Create Program" button is clicked.
     * This is called from the custom button in the Programs list view.
     */
    async load_wizard() {
        // Only proceed if we're on the spp.program model
        if (this.model.root.resModel !== "spp.program") {
            return;
        }

        // Open the create program wizard action
        await this.actionService.doAction("spp_programs.action_create_program_wizard", {
            onClose: async () => {
                // Refresh the list after the wizard closes
                await this.model.root.load();
            },
        });
    },
});
