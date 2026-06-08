/** @odoo-module **/

/**
 * Registry Access Restriction for Farmer Registry
 *
 * When the config setting "Restrict Registry Edits to Admin Only" is enabled,
 * this patch enforces read-only mode on res.partner views for non-admin users.
 *
 * The restriction check is cached and resolved before the form/list setup
 * so that modelParams can return mode: "readonly" before the model is created.
 */

import {FormController} from "@web/views/form/form_controller";
import {ListController} from "@web/views/list/list_controller";
import {RegistrySearchPortal} from "@spp_registry_search/js/registry_search_portal";
import {patch} from "@web/core/utils/patch";
import {user} from "@web/core/user";
import {rpc} from "@web/core/network/rpc";
import {onMounted, onPatched, onWillStart, onWillUnmount} from "@odoo/owl";

// Models affected by the registry restriction
const REGISTRY_MODELS = ["res.partner"];

// Cache the restriction check to avoid repeated RPC calls within the same session.
// Resolved once at module load time so it's available synchronously in setup().
let _restrictionResult = null;
let _restrictionPromise = null;

function fetchRestriction() {
    if (_restrictionPromise) {
        return _restrictionPromise;
    }
    _restrictionPromise = (async () => {
        try {
            const isAdmin = await user.hasGroup("spp_security.group_spp_admin");
            if (isAdmin) {
                _restrictionResult = false;
                return false;
            }
            const result = await rpc("/spp_farmer_registry/registry_restriction", {});
            _restrictionResult = result.restricted === true;
        } catch {
            _restrictionResult = false;
        }
        // Reset promise after TTL so it re-fetches
        setTimeout(() => {
            _restrictionPromise = null;
        }, 30000);
        return _restrictionResult;
    })();
    return _restrictionPromise;
}

// Eagerly fetch at module load time so the result is available
// synchronously when the first FormController.setup() runs.
fetchRestriction();

// Actions to strip from the action menu when restricted
const BLOCKED_ACTIONS = ["delete", "archive", "unarchive", "duplicate"];

/**
 * Patch FormController to enforce read-only on registry forms when restricted.
 */
patch(FormController.prototype, {
    setup() {
        const modelName = this.props.resModel;
        // Check synchronous cache BEFORE super.setup() creates the model
        this._registryRestricted =
            REGISTRY_MODELS.includes(modelName) && _restrictionResult === true;

        super.setup(...arguments);

        if (!REGISTRY_MODELS.includes(modelName)) {
            return;
        }

        this._restrictionObserver = null;

        onWillStart(async () => {
            const restricted = await fetchRestriction();
            this._registryRestricted = restricted;

            if (this._registryRestricted) {
                this.canEdit = false;
                this.canCreate = false;
            }
        });

        const enforceRestriction = () => {
            if (!this._registryRestricted) return;

            const rootEl = this.rootRef?.el;
            if (!rootEl) return;

            const container =
                rootEl.closest(".o_action") ||
                rootEl.closest(".o_dialog") ||
                document.body;

            const applyRestriction = () => {
                const formView = container.querySelector(".o_form_view");
                if (formView) {
                    formView.classList.remove("o_form_editable");
                    formView.classList.add("o_form_readonly");
                }

                const selectors = [
                    ".o_form_button_create",
                    ".o_form_button_save",
                    ".o_form_button_cancel",
                    ".o_statusbar_buttons",
                ];

                for (const selector of selectors) {
                    container.querySelectorAll(selector).forEach((el) => {
                        el.style.display = "none";
                    });
                }
            };

            applyRestriction();
            setTimeout(applyRestriction, 100);
            setTimeout(applyRestriction, 300);

            if (!this._restrictionObserver) {
                this._restrictionObserver = new MutationObserver(applyRestriction);
                this._restrictionObserver.observe(container, {
                    childList: true,
                    subtree: true,
                });
            }
        };

        onMounted(enforceRestriction);
        onPatched(enforceRestriction);

        onWillUnmount(() => {
            if (this._restrictionObserver) {
                this._restrictionObserver.disconnect();
                this._restrictionObserver = null;
            }
        });
    },

    get modelParams() {
        const params = super.modelParams;
        if (this._registryRestricted) {
            params.config.mode = "readonly";
        }
        return params;
    },

    get actionMenuItems() {
        const menuItems = super.actionMenuItems;

        if (this._registryRestricted && REGISTRY_MODELS.includes(this.props.resModel)) {
            if (menuItems.action) {
                menuItems.action = menuItems.action.filter(
                    (item) => !BLOCKED_ACTIONS.includes(item.key)
                );
            }
        }

        return menuItems;
    },
});

/**
 * Patch ListController to hide Create button on registry lists when restricted.
 */
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);

        const modelName = this.props.resModel;
        if (!REGISTRY_MODELS.includes(modelName)) {
            return;
        }

        this._registryRestricted = false;
        this._restrictionObserver = null;

        onWillStart(async () => {
            this._registryRestricted = await fetchRestriction();
            if (this._registryRestricted) {
                this.canCreate = false;
            }
        });

        const enforceRestriction = () => {
            if (!this._registryRestricted) return;

            const rootEl = this.rootRef?.el;
            if (!rootEl) return;

            const container =
                rootEl.closest(".o_action") ||
                rootEl.closest(".o_dialog") ||
                document.body;

            const hideButtons = () => {
                container.querySelectorAll(".o_list_button_add").forEach((el) => {
                    el.style.display = "none";
                });
                container
                    .querySelectorAll(".o_cp_buttons .btn-primary")
                    .forEach((el) => {
                        if (el.textContent.trim() === "New") {
                            el.style.display = "none";
                        }
                    });
            };

            hideButtons();
            setTimeout(hideButtons, 100);
            setTimeout(hideButtons, 300);

            if (!this._restrictionObserver) {
                this._restrictionObserver = new MutationObserver(hideButtons);
                this._restrictionObserver.observe(container, {
                    childList: true,
                    subtree: true,
                });
            }
        };

        onMounted(enforceRestriction);
        onPatched(enforceRestriction);

        onWillUnmount(() => {
            if (this._restrictionObserver) {
                this._restrictionObserver.disconnect();
                this._restrictionObserver = null;
            }
        });
    },

    get actionMenuItems() {
        const menuItems = super.actionMenuItems;

        if (this._registryRestricted && REGISTRY_MODELS.includes(this.props.resModel)) {
            if (menuItems.action) {
                menuItems.action = menuItems.action.filter(
                    (item) => !BLOCKED_ACTIONS.includes(item.key)
                );
            }
        }

        return menuItems;
    },
});

/**
 * Patch RegistrySearchPortal to hide New Individual/New Group buttons when restricted.
 *
 * OWL runs onWillStart callbacks in parallel (Promise.all), so the original
 * check_access_rights RPC may finish AFTER our cached restriction check and
 * overwrite canCreate back to true. We use onMounted/onPatched as a safety
 * net to enforce the restriction after rendering.
 */
patch(RegistrySearchPortal.prototype, {
    setup() {
        super.setup(...arguments);

        this._registryRestricted = _restrictionResult === true;

        onWillStart(async () => {
            this._registryRestricted = await fetchRestriction();
            if (this._registryRestricted) {
                this.state.canCreate = false;
                this.state.canEdit = false;
            }
        });

        const enforceRestriction = () => {
            if (!this._registryRestricted) return;
            this.state.canCreate = false;
            this.state.canEdit = false;
        };

        onMounted(enforceRestriction);
        onPatched(enforceRestriction);
    },
});
