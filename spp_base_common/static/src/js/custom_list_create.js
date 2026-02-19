/** @odoo-module **/

import {ListController} from "@web/views/list/list_controller";
import {patch} from "@web/core/utils/patch";

/**
 * Base handler for the generic custom create button.
 * Modules override this method via patch to handle their specific model.
 *
 * Usage in other modules:
 *   patch(ListController.prototype, {
 *       async onCustomListCreate() {
 *           if (this.model.root.resModel === "my.model") {
 *               // open wizard
 *               return;
 *           }
 *           return super.onCustomListCreate(...arguments);
 *       },
 *   });
 */
patch(ListController.prototype, {
    async onCustomListCreate() {
        // Base no-op — overridden by consuming modules
    },
});
