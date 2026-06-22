/** @odoo-module **/
/*
 * OP#968 round-2 — hide the form-level "New" button when the user opens a
 * DRIMS Dispatch picking from the dedicated action.
 *
 * The list view already disables create (via `view_picking_list_drims_dispatch`
 * with `create="0"`), but Odoo 19's form view renders its own "New" button on
 * the breadcrumb pager that the list-view attribute doesn't reach. Action
 * context `'create': False` is unreliable in Odoo 19 too.
 *
 * The supported pattern in this repo is the `hideFormCreateButton` flag added
 * by `spp_base_common/static/src/xml/custom_list_create_template.xml`. Setting
 * it to `true` in a FormController patch makes the template skip the button.
 *
 * We discriminate on the model + the `default_drims_type` context key the
 * dispatch action sets, so the standard `stock.picking` form on
 * Inventory > Operations is unaffected.
 */

import {FormController} from "@web/views/form/form_controller";
import {patch} from "@web/core/utils/patch";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        const ctx = this.props.context || {};
        if (
            this.props.resModel === "stock.picking" &&
            ctx.default_drims_type === "request_dispatch"
        ) {
            this.hideFormCreateButton = true;
        }
    },
});
