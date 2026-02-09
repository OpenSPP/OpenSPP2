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
            const is_admin = await user.hasGroup("spp_security.group_spp_admin");
            const is_cr_user = await user.hasGroup(
                "spp_change_request_v2.group_cr_user"
            );
            this.canCreateChangeRequest = is_admin || is_cr_user;
        });
    },

    async loadChangeRequestWizard() {
        if (this.model.root.resModel !== "spp.change.request") {
            return;
        }
        await this.actionService.doAction(
            "spp_change_request_v2.action_cr_create_wizard",
            {
                onClose: async () => {
                    await this.model.root.load();
                },
            }
        );
    },
});
