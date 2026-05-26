/** @odoo-module **/
import {ListRenderer} from "@web/views/list/list_renderer";
import {patch} from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    getRowClass(record) {
        const base = super.getRowClass(record);
        if (record.resModel !== "spp.drims.inspection.wizard.line") {
            return base;
        }
        if (record.data.is_split) {
            return `${base} o_is_split`;
        }
        if (record.data.has_splits) {
            return `${base} o_split_parent`;
        }
        return base;
    },
});
