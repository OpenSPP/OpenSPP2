/** @odoo-module **/

/**
 * Hide Archive Action in Form View
 *
 * Patches the FormController to respect the `archive: false` context key.
 * When this context is set, the archive/unarchive actions will be hidden
 * from the form view's action menu (cog icon).
 */

import {FormController} from "@web/views/form/form_controller";
import {patch} from "@web/core/utils/patch";

patch(FormController.prototype, {
    get actionMenuItems() {
        const menuItems = super.actionMenuItems;

        // Check if archive should be hidden via context
        const context = this.props.context || {};
        if (context.archive === false) {
            // Filter out archive and unarchive actions
            if (menuItems.action) {
                menuItems.action = menuItems.action.filter(
                    (item) => item.key !== "archive" && item.key !== "unarchive"
                );
            }
        }

        return menuItems;
    },
});
