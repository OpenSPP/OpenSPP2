/** @odoo-module **/

import {registry} from "@web/core/registry";

/**
 * Global keyboard shortcut service for Change Requests
 *
 * Registers global shortcuts:
 * - Alt+N: Open New Change Request wizard
 * - A: Approve (when viewing pending CR)
 * - R: Request Changes (when viewing pending CR)
 * - D: Decline (when viewing pending CR)
 */
const globalShortcutsService = {
    dependencies: ["action", "hotkey", "orm", "notification"],

    start(env, {action, hotkey, orm, notification}) {
        /**
         * Check if we're currently viewing a pending change request
         * Returns the CR id if yes, null otherwise
         */
        function getCurrentPendingCRId() {
            // Get the current controller
            const controller = env.services.action?.currentController;
            if (!controller) return null;

            // Check if it's a form view for spp.change.request
            const resModel = controller.props?.resModel;
            const resId = controller.props?.resId;
            if (resModel !== "spp.change.request" || !resId) return null;

            // We'll check approval_state in the action handlers
            return resId;
        }

        /**
         * Check if the CR is in pending state before executing action
         */
        async function executeCRAction(actionName) {
            const crId = getCurrentPendingCRId();
            if (!crId) return;

            try {
                // Read the CR state first
                const [cr] = await orm.read(
                    "spp.change.request",
                    [crId],
                    ["approval_state", "can_approve", "can_reject"]
                );

                if (cr.approval_state !== "pending") {
                    // Not in pending state, ignore shortcut
                    return;
                }

                if (actionName === "approve" && !cr.can_approve) {
                    notification.add(
                        "You don't have permission to approve this request",
                        {
                            type: "warning",
                        }
                    );
                    return;
                }

                if (
                    (actionName === "reject" || actionName === "revision") &&
                    !cr.can_reject
                ) {
                    notification.add(
                        "You don't have permission to reject this request",
                        {
                            type: "warning",
                        }
                    );
                    return;
                }

                // Execute the action
                if (actionName === "approve") {
                    await orm.call("spp.change.request", "action_approve", [[crId]]);
                    notification.add("Request approved", {type: "success"});
                    // Reload the view
                    action.doAction({type: "ir.actions.act_window_close"});
                } else if (actionName === "revision") {
                    // Open the revision dialog
                    action.doAction({
                        type: "ir.actions.act_window",
                        name: "Request Changes",
                        res_model: "spp.approval.revision.wizard",
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "new",
                        context: {
                            default_res_model: "spp.change.request",
                            default_res_id: crId,
                        },
                    });
                } else if (actionName === "reject") {
                    // Open the rejection dialog
                    action.doAction({
                        type: "ir.actions.act_window",
                        name: "Decline Request",
                        res_model: "spp.approval.rejection.wizard",
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "new",
                        context: {
                            default_res_model: "spp.change.request",
                            default_res_id: crId,
                        },
                    });
                }
            } catch (error) {
                notification.add(error.message || `Error executing ${actionName}`, {
                    type: "danger",
                });
            }
        }

        // Register Alt+N shortcut for New Change Request
        hotkey.add(
            "alt+n",
            () => {
                action.doAction({
                    type: "ir.actions.act_window",
                    name: "New Change Request",
                    res_model: "spp.cr.create.wizard",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: {},
                });
            },
            {
                global: true,
                bypassEditableProtection: false,
            }
        );

        // Register A shortcut for Approve (only active on CR form views)
        hotkey.add("a", () => executeCRAction("approve"), {
            global: true,
            bypassEditableProtection: false,
        });

        // Register R shortcut for Request Changes
        hotkey.add("r", () => executeCRAction("revision"), {
            global: true,
            bypassEditableProtection: false,
        });

        // Register D shortcut for Decline
        hotkey.add("d", () => executeCRAction("reject"), {
            global: true,
            bypassEditableProtection: false,
        });

        return {};
    },
};

registry.category("services").add("cr_global_shortcuts", globalShortcutsService);
