/** @odoo-module **/

import {ListRenderer} from "@web/views/list/list_renderer";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
    },

    async onCellClicked(record, column, ev) {
        if (record.resModel === "spp.program") {
            // Skip custom behavior if in selection mode (e.g., Many2one "Search More..." dialog)
            // In selection mode, don't open form - let dialog handle row selection
            const isSelectionMode =
                this.props.onSelect ||
                this.props.selectRecord ||
                this.props.noOpen ||
                this.env.inDialog ||
                this.env.config?.noOpen;

            if (isSelectionMode) {
                // In selection mode, use default behavior which handles selection
                return super.onCellClicked(record, column, ev);
            }
            // Get the stored action from the server (includes action id for proper routing)
            var action = await this.orm.call("spp.program", "open_program_form", [
                record.resId,
            ]);
            this.actionService.doAction(action);
        } else {
            super.onCellClicked(record, column, ev);
        }
    },
});
