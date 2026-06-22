/** @odoo-module **/

import {FormController} from "@web/views/form/form_controller";
import {patch} from "@web/core/utils/patch";
import {onMounted, onPatched, onWillUnmount} from "@odoo/owl";

/**
 * Patch FormController to hide the form "New" button when the user lacks
 * create permission, or for models where create is contextually forbidden.
 *
 * In Odoo 19, `t-if="canCreate"` on the form template does not always prevent
 * the "New" button from rendering — notably the breadcrumb-area button can
 * leak through when the form arch was first loaded as a privileged user and
 * cached, or in some action navigation flows. This patch enforces hiding via
 * DOM manipulation for:
 *
 * 1. Any view with `context.create === false`.
 * 2. Models in MODELS_WITHOUT_CREATE (always-hide; never should be created
 *    directly from the form, e.g. entitlements).
 * 3. `this.canCreate === false` — i.e. the ACL-derived archInfo.activeActions
 *    .create is false. This is the ACL-aware path that preserves the button
 *    for users who DO have create permission.
 */

// Models that should never show the create button regardless of ACL
const MODELS_WITHOUT_CREATE = [
    "spp.entitlement",
    "spp.entitlement.inkind",
    "spp.program.membership",
    "spp.cycle.membership",
];

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        // Check if create should be disabled
        const modelName = this.props.resModel;
        const shouldHideCreate =
            this.props.context?.create === false ||
            MODELS_WITHOUT_CREATE.includes(modelName) ||
            this.canCreate === false;

        if (shouldHideCreate) {
            this._hideCreateObserver = null;

            const hideCreateButtons = (container) => {
                const createButtons = container.querySelectorAll(
                    ".o_form_button_create"
                );
                createButtons.forEach((btn) => {
                    btn.style.display = "none";
                });
            };

            const setupHiding = () => {
                const rootEl = this.rootRef?.el;
                if (!rootEl) return;

                // Find the action container
                const container =
                    rootEl.closest(".o_action") ||
                    rootEl.closest(".o_dialog") ||
                    document.body;

                // Hide existing buttons immediately
                hideCreateButtons(container);

                // Also hide after a short delay to catch late-rendered buttons
                setTimeout(() => hideCreateButtons(container), 100);
                setTimeout(() => hideCreateButtons(container), 300);

                // Set up observer to catch dynamically added buttons
                if (!this._hideCreateObserver) {
                    this._hideCreateObserver = new MutationObserver(() => {
                        hideCreateButtons(container);
                    });
                    this._hideCreateObserver.observe(container, {
                        childList: true,
                        subtree: true,
                    });
                }
            };

            onMounted(setupHiding);
            onPatched(setupHiding);

            onWillUnmount(() => {
                if (this._hideCreateObserver) {
                    this._hideCreateObserver.disconnect();
                    this._hideCreateObserver = null;
                }
            });
        }
    },
});
