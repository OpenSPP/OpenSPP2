/** @odoo-module **/

import {FormController} from "@web/views/form/form_controller";
import {patch} from "@web/core/utils/patch";
import {onMounted, onWillUnmount} from "@odoo/owl";

/**
 * CEL Builder Wizard - Click-to-use Examples
 *
 * Makes CEL expression examples clickable in the builder wizard.
 * When an example is clicked, it inserts the expression into the CEL expression field.
 */
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        // Only set up for CEL Builder Wizard
        if (this.props.resModel === "spp.cel.builder.wizard") {
            // Add click handler after view is mounted
            onMounted(() => {
                this._setupCelExampleClickHandlers();
            });

            // Clean up on unmount
            onWillUnmount(() => {
                this._cleanupCelClickHandler();
            });
        }
    },

    /**
     * Set up click handlers for CEL example expressions
     */
    _setupCelExampleClickHandlers() {
        // Remove existing listener if any
        this._cleanupCelClickHandler();

        // Create click handler that works with event delegation
        this._celClickHandler = (event) => {
            let target = null;

            // Strategy 1: Check if we clicked directly on a .cel-clickable element
            if (event.target.classList?.contains("cel-clickable")) {
                target = event.target;
            }

            // Strategy 2: Check if we clicked on something inside a .cel-clickable (go up)
            if (!target) {
                target = event.target.closest(".cel-clickable");
            }

            // Strategy 3: Check if we clicked on a parent that contains a .cel-clickable (go down)
            if (!target) {
                const parent = event.target.closest(".cel-example-item");
                if (parent) {
                    target = parent.querySelector(".cel-clickable");
                    if (!target) {
                        // Try to find ANY code element as fallback
                        target = parent.querySelector("code");
                    }
                }
            }

            if (target) {
                event.preventDefault();
                event.stopPropagation();

                // Try to get expression from data-expr attribute
                let expression = target.getAttribute("data-expr");

                // If data-expr is missing, use the text content of the code element
                if (!expression) {
                    expression = target.textContent.trim();
                }

                if (expression) {
                    this._insertCelExpression(expression);
                }
            }
        };

        // Attach to document body for maximum coverage
        document.body.addEventListener("click", this._celClickHandler, true);

        // Also watch for dynamically added content
        this._watchForExamples();
    },

    /**
     * Watch for examples being added to the DOM
     */
    _watchForExamples() {
        // Use MutationObserver to detect when examples are loaded
        this._examplesObserver = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length) {
                    const hasExamples = Array.from(mutation.addedNodes).some((node) => {
                        return (
                            node.nodeType === 1 &&
                            (node.classList?.contains("cel-examples") ||
                                node.querySelector?.(".cel-clickable"))
                        );
                    });
                }
            }
        });

        // Start observing
        const root = this.rootRef?.el || document.body;
        this._examplesObserver.observe(root, {
            childList: true,
            subtree: true,
        });
    },

    /**
     * Clean up click handler
     */
    _cleanupCelClickHandler() {
        if (this._celClickHandler) {
            document.body.removeEventListener("click", this._celClickHandler, true);
            this._celClickHandler = null;
        }
        if (this._examplesObserver) {
            this._examplesObserver.disconnect();
            this._examplesObserver = null;
        }
    },

    /**
     * Insert CEL expression into the expression field
     * @param {String} expression - The CEL expression to insert
     */
    async _insertCelExpression(expression) {
        try {
            // Find the textarea/input field directly
            const expressionField = document.querySelector("[name='cel_expression']");
            if (!expressionField) {
                return;
            }

            // Get current value
            const currentValue = expressionField.value || "";

            // Determine new value:
            // - If field is empty, just set the expression
            // - If field has content, combine with AND operator
            let newValue;
            if (currentValue.trim()) {
                // Wrap existing expression in parentheses if it doesn't have them
                const wrappedCurrent =
                    currentValue.trim().startsWith("(") &&
                    currentValue.trim().endsWith(")")
                        ? currentValue.trim()
                        : `(${currentValue.trim()})`;

                // Wrap new expression in parentheses
                const wrappedNew =
                    expression.startsWith("(") && expression.endsWith(")")
                        ? expression
                        : `(${expression})`;

                newValue = `${wrappedCurrent} && ${wrappedNew}`;
            } else {
                newValue = expression;
            }

            // Set the value directly
            expressionField.value = newValue;

            // Trigger input event so Odoo knows the field changed
            expressionField.dispatchEvent(new Event("input", {bubbles: true}));
            expressionField.dispatchEvent(new Event("change", {bubbles: true}));

            // Focus on the expression field
            expressionField.focus();

            // Move cursor to end
            if (expressionField.setSelectionRange) {
                const len = expressionField.value.length;
                expressionField.setSelectionRange(len, len);
            }

            // Try to update the model if available
            if (this.model?.root) {
                try {
                    await this.model.root.update({
                        cel_expression: newValue,
                    });
                } catch (e) {
                    // Model update not needed
                }
            }
        } catch (error) {
            // Silently handle errors
        }
    },
});
