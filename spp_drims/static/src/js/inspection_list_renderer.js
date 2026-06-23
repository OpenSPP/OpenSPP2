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
            // Tag the parent row when any of its split children still has
            // qty == 0. CSS uses this to hide "+ Add split" until the
            // pending child is filled — prevents operators from stacking
            // empty split rows.
            const lines = (this.props.list && this.props.list.records) || [];
            const myId = record.resId;
            const hasZeroChild = lines.some((line) => {
                const parentRef = line.data.parent_line_id;
                if (!parentRef) {
                    return false;
                }
                const pid =
                    typeof parentRef === "object" &&
                    parentRef !== null &&
                    "id" in parentRef
                        ? parentRef.id
                        : parentRef;
                if (pid !== myId) {
                    return false;
                }
                return !line.data.quantity;
            });
            return hasZeroChild
                ? `${base} o_split_parent o_split_parent_has_zero`
                : `${base} o_split_parent`;
        }
        return base;
    },
});
