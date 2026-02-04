/** @odoo-module **/

import {FormController} from "@web/views/form/form_controller";
import {patch} from "@web/core/utils/patch";
import {onMounted, onPatched, onWillUnmount} from "@odoo/owl";

/**
 * Patch FormController to respect context.create = false and disable create
 * for specific models (entitlements).
 *
 * In Odoo 19, the "New" button may still appear in various scenarios:
 * - When navigating from list to form view with context.create = false
 * - When expanding a dialog (creates a new action without preserving context)
 *
 * This patch hides the New button via DOM manipulation for:
 * 1. Any view with context.create === false
 * 2. Entitlement models (should only be created from cycles)
 */

// Models that should never show the create button
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
        const shouldHideCreate = this.props.context?.create === false || MODELS_WITHOUT_CREATE.includes(modelName);

        if (shouldHideCreate) {
            this._hideCreateObserver = null;

            const hideCreateButtons = (container) => {
                const createButtons = container.querySelectorAll(".o_form_button_create");
                createButtons.forEach((btn) => {
                    btn.style.display = "none";
                });
            };

            const setupHiding = () => {
                const rootEl = this.rootRef?.el;
                if (!rootEl) return;

                // Find the action container
                const container = rootEl.closest(".o_action") || rootEl.closest(".o_dialog") || document.body;

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
