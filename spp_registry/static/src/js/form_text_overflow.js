/** @odoo-module **/

import {Component, onMounted, useEffect, useRef} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {FormController} from "@web/views/form/form_controller";
import {patch} from "@web/core/utils/patch";

/**
 * Add title attribute to text inputs that overflow
 * This allows browser to show full text on hover
 */
function addTitleToOverflowingInputs() {
    const inputs = document.querySelectorAll('.o_form_view input.o_input[type="text"]');

    inputs.forEach((input) => {
        // Check if text is overflowing
        if (input.scrollWidth > input.clientWidth) {
            // Add title with full value
            input.setAttribute("title", input.value);
        } else {
            // Remove title if not overflowing
            input.removeAttribute("title");
        }
    });

    // Also handle readonly span elements
    const spans = document.querySelectorAll(".o_form_view .o_field_widget span");
    spans.forEach((span) => {
        if (span.scrollWidth > span.clientWidth) {
            span.setAttribute("title", span.textContent);
        } else {
            span.removeAttribute("title");
        }
    });
}

// Patch FormController to add overflow detection
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => {
            // Add titles on mount
            addTitleToOverflowingInputs();

            // Re-check when form is updated
            const observer = new MutationObserver(() => {
                addTitleToOverflowingInputs();
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true,
            });

            // Also check on input changes
            document.addEventListener("input", (e) => {
                if (e.target.matches('.o_input[type="text"]')) {
                    if (e.target.scrollWidth > e.target.clientWidth) {
                        e.target.setAttribute("title", e.target.value);
                    } else {
                        e.target.removeAttribute("title");
                    }
                }
            });
        });
    },
});
