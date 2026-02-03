/** @odoo-module **/

/**
 * E2E Tour Tests for CEL Expression Widget
 *
 * These tours test the complete user flow of the CEL expression editor widget,
 * including rendering, autocomplete, validation, error handling, and symbol browser.
 */

import {registry} from "@web/core/registry";
import {stepUtils} from "@web_tour/tour_service/tour_utils";

/**
 * Tour 1: Basic Widget Rendering and Initialization
 *
 * Tests that the CEL widget renders correctly when opening a form view.
 * Verifies all UI components are present.
 */
registry.category("web_tour.tours").add("cel_widget_basic_rendering", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Wait for form to load",
            trigger: "div.o_form_view",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Verify CEL editor container is visible",
            trigger: ".o_cel_editor_field",
        },
        {
            content: "Verify editor toolbar exists",
            trigger: ".o_cel_toolbar",
        },
        {
            content: "Verify Symbols button exists",
            trigger: 'button:contains("Symbols")',
        },
        {
            content: "Verify autocomplete trigger button exists",
            trigger: '.o_cel_toolbar button[title*="Show suggestions"]',
        },
        {
            content: "Verify editor container exists",
            trigger: ".o_cel_editor_container",
        },
        {
            content: "Verify help text is shown for empty state",
            trigger: '.o_cel_help_text:contains("Ctrl")',
        },
    ],
});

/**
 * Tour 2: Autocomplete Flow
 *
 * Tests the autocomplete functionality by typing 'me.' and selecting a field.
 */
registry.category("web_tour.tours").add("cel_widget_autocomplete", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click in the editor to focus",
            trigger: ".o_cel_editor_container .cm-content",
            run: "click",
        },
        {
            content: "Type 'me.' to trigger autocomplete",
            trigger: ".o_cel_editor_container .cm-content",
            run: "edit me.",
        },
        {
            content: "Wait for autocomplete menu to appear",
            trigger: ".cm-tooltip-autocomplete",
        },
        {
            content: "Verify autocomplete suggestions contain fields",
            trigger: '.cm-completionLabel:contains("name")',
        },
        {
            content: "Select 'name' from autocomplete",
            trigger: '.cm-completionLabel:contains("name")',
            run: "click",
        },
        {
            content: "Verify text was inserted",
            trigger: '.cm-content:contains("me.name")',
        },
    ],
});

/**
 * Tour 3: Validation - Valid Expression
 *
 * Tests that entering a valid expression shows success validation feedback.
 */
registry.category("web_tour.tours").add("cel_widget_validation_success", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click in the editor to focus",
            trigger: ".o_cel_editor_container .cm-content",
            run: "click",
        },
        {
            content: "Type a valid expression",
            trigger: ".o_cel_editor_container .cm-content",
            run: 'edit me.name == "Test"',
        },
        {
            content: "Wait for validation (debounced)",
            trigger: ".o_cel_validation_status.text-muted",
        },
        {
            content: "Verify validation shows validating state",
            trigger: '.o_cel_validation_status:contains("Validating")',
        },
        {
            content: "Wait for validation to complete with success",
            trigger: ".o_cel_validation_status.text-success",
        },
        {
            content: "Verify success icon is shown",
            trigger: ".o_cel_validation_status .fa-check-circle",
        },
        {
            content: "Verify success message",
            trigger: '.o_cel_validation_status:contains("Valid")',
        },
    ],
});

/**
 * Tour 4: Validation - Invalid Expression (Error Handling)
 *
 * Tests that entering an invalid expression shows error feedback.
 */
registry.category("web_tour.tours").add("cel_widget_validation_error", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click in the editor to focus",
            trigger: ".o_cel_editor_container .cm-content",
            run: "click",
        },
        {
            content: "Type an invalid expression (incomplete)",
            trigger: ".o_cel_editor_container .cm-content",
            run: "edit me.name ==",
        },
        {
            content: "Wait for validation to start",
            trigger: ".o_cel_validation_status.text-muted",
        },
        {
            content: "Wait for validation to complete with error",
            trigger: ".o_cel_validation_status.text-danger",
        },
        {
            content: "Verify error icon is shown",
            trigger: ".o_cel_validation_status .fa-times-circle",
        },
        {
            content: "Verify error message is displayed",
            trigger: '.o_cel_validation_status:contains("Invalid")',
        },
    ],
});

/**
 * Tour 5: Symbol Browser - Navigation and Insertion
 *
 * Tests opening the symbol browser, navigating tabs, searching, and inserting symbols.
 */
registry.category("web_tour.tours").add("cel_widget_symbol_browser", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click Symbols button to open browser",
            trigger: 'button:contains("Symbols")',
            run: "click",
        },
        {
            content: "Verify symbol browser is opened",
            trigger: ".o_cel_symbol_browser",
        },
        {
            content: "Verify Variables tab is active by default",
            trigger: '.o_cel_browser_tabs button.btn-primary:contains("Variables")',
        },
        {
            content: "Verify 'me' variable is shown",
            trigger: '.o_cel_variable_header:contains("me")',
        },
        {
            content: "Click on 'me' variable to expand",
            trigger: '.o_cel_variable_header:contains("me")',
            run: "click",
        },
        {
            content: "Verify fields are shown after expansion",
            trigger: ".o_cel_field_list",
        },
        {
            content: "Verify field items exist",
            trigger: ".o_cel_field_item",
        },
        {
            content: "Click on a field to insert it",
            trigger: '.o_cel_field_item:contains("name")',
            run: "click",
        },
        {
            content: "Verify field was inserted into editor",
            trigger: '.cm-content:contains("me.name")',
        },
        {
            content: "Open symbol browser again",
            trigger: 'button:contains("Symbols")',
            run: "click",
        },
        {
            content: "Switch to Functions tab",
            trigger: '.o_cel_browser_tabs button:contains("Functions")',
            run: "click",
        },
        {
            content: "Verify Functions tab is now active",
            trigger: '.o_cel_browser_tabs button.btn-primary:contains("Functions")',
        },
        {
            content: "Verify function items are displayed",
            trigger: ".o_cel_function_item",
        },
        {
            content: "Verify age_years function exists",
            trigger: '.o_cel_function_item:contains("age_years")',
        },
        {
            content: "Click on age_years function to insert",
            trigger: '.o_cel_function_item:contains("age_years")',
            run: "click",
        },
        {
            content: "Verify function was inserted into editor",
            trigger: '.cm-content:contains("age_years")',
        },
        {
            content: "Close symbol browser",
            trigger: ".o_cel_browser_header .btn-link .fa-times",
            run: "click",
        },
        {
            content: "Verify symbol browser is closed",
            trigger: ".o_cel_editor_field",
            run: function () {
                // Check that browser is not visible
                const browser = this.anchor.querySelector(".o_cel_symbol_browser");
                if (browser) {
                    throw new Error("Symbol browser should be closed");
                }
            },
        },
    ],
});

/**
 * Tour 6: Symbol Browser - Search Functionality
 *
 * Tests the search/filter functionality within the symbol browser.
 */
registry.category("web_tour.tours").add("cel_widget_symbol_search", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click Symbols button to open browser",
            trigger: 'button:contains("Symbols")',
            run: "click",
        },
        {
            content: "Verify symbol browser is opened",
            trigger: ".o_cel_symbol_browser",
        },
        {
            content: "Expand 'me' variable to see fields",
            trigger: '.o_cel_variable_header:contains("me")',
            run: "click",
        },
        {
            content: "Type in search box to filter",
            trigger: '.o_cel_browser_header input[placeholder*="Search"]',
            run: "edit birth",
        },
        {
            content: "Verify search filters the fields",
            trigger: '.o_cel_field_item:contains("birthdate")',
        },
        {
            content: "Clear search",
            trigger: '.o_cel_browser_header input[placeholder*="Search"]',
            run: "edit ",
        },
        {
            content: "Switch to Functions tab",
            trigger: '.o_cel_browser_tabs button:contains("Functions")',
            run: "click",
        },
        {
            content: "Search for specific function",
            trigger: '.o_cel_browser_header input[placeholder*="Search"]',
            run: "edit age",
        },
        {
            content: "Verify age_years function is shown",
            trigger: '.o_cel_function_item:contains("age_years")',
        },
        {
            content: "Verify search is case-insensitive and partial match works",
            trigger: '.o_cel_function_item:contains("age")',
        },
    ],
});

/**
 * Tour 7: Manual Autocomplete Trigger
 *
 * Tests that clicking the autocomplete button (Ctrl+Space alternative) works.
 */
registry.category("web_tour.tours").add("cel_widget_manual_autocomplete", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click in the editor to focus",
            trigger: ".o_cel_editor_container .cm-content",
            run: "click",
        },
        {
            content: "Type 'me' (without dot)",
            trigger: ".o_cel_editor_container .cm-content",
            run: "edit me",
        },
        {
            content: "Click autocomplete trigger button",
            trigger: '.o_cel_toolbar button[title*="Show suggestions"]',
            run: "click",
        },
        {
            content: "Verify autocomplete menu appears",
            trigger: ".cm-tooltip-autocomplete",
        },
        {
            content: "Verify suggestions are shown",
            trigger: ".cm-completionLabel",
        },
    ],
});

/**
 * Tour 8: Readonly Mode
 *
 * Tests that the widget properly disables editing in readonly mode.
 */
registry.category("web_tour.tours").add("cel_widget_readonly", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Open an existing record (if any)",
            trigger: ".o_data_row",
            run: "click",
        },
        {
            content: "Wait for form view",
            trigger: ".o_form_view",
        },
        {
            content: "Verify form is in readonly mode initially",
            trigger: ".o_form_view.o_form_readonly",
        },
        {
            content: "Check if CEL mode is selected",
            trigger: 'input[type="radio"][data-value="cel"][checked]',
        },
        {
            content: "Verify editor has readonly class",
            trigger: ".o_cel_editor_readonly",
        },
    ],
});

/**
 * Tour 9: Empty Expression Validation
 *
 * Tests that empty expressions don't show validation errors initially.
 */
registry.category("web_tour.tours").add("cel_widget_empty_validation", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Verify validation status is empty (no icon or message)",
            trigger: ".o_cel_validation_status",
            run: function () {
                const statusText = this.anchor.textContent.trim();
                if (statusText && statusText !== "") {
                    throw new Error("Validation status should be empty for new record");
                }
            },
        },
        {
            content: "Type valid expression then delete it",
            trigger: ".o_cel_editor_container .cm-content",
            run: "click",
        },
        {
            content: "Enter text",
            trigger: ".o_cel_editor_container .cm-content",
            run: "edit test",
        },
        {
            content: "Clear the text",
            trigger: ".o_cel_editor_container .cm-content",
            run: "edit ",
        },
        {
            content: "Verify validation cleared for empty expression",
            trigger: ".o_cel_validation_status",
            run: function () {
                const icon = this.anchor.querySelector(".fa");
                if (icon && !icon.classList.contains("fa-spinner")) {
                    throw new Error("Validation icon should be cleared for empty expression");
                }
            },
        },
    ],
});

/**
 * Tour 10: Complex Expression with Multiple Operators
 *
 * Tests entering a complex expression with operators, functions, and field access.
 */
registry.category("web_tour.tours").add("cel_widget_complex_expression", {
    test: true,
    url: "/web",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Programs menu",
            trigger: '.o_app[data-menu-xmlid="spp_programs.spp_manager_menu_root"]',
            run: "click",
        },
        {
            content: "Open Eligibility Managers",
            trigger: 'a[data-menu-xmlid="spp_programs.menu_eligibility_managers"]',
            run: "click",
        },
        {
            content: "Click Create button",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select CEL mode",
            trigger: 'input[type="radio"][data-value="cel"]',
            run: "click",
        },
        {
            content: "Wait for CEL editor to be ready",
            trigger: ".o_cel_editor_container .cm-editor",
        },
        {
            content: "Click in the editor to focus",
            trigger: ".o_cel_editor_container .cm-content",
            run: "click",
        },
        {
            content: "Type complex expression",
            trigger: ".o_cel_editor_container .cm-content",
            run: 'edit age_years(me.birthdate) >= 18 and me.gender == "female"',
        },
        {
            content: "Wait for validation to complete",
            trigger: ".o_cel_validation_status:not(.text-muted)",
        },
        {
            content: "Verify complex expression validates successfully",
            trigger: ".o_cel_validation_status.text-success",
        },
        {
            content: "Verify expression is displayed correctly in editor",
            trigger: '.cm-content:contains("age_years")',
        },
        {
            content: "Verify operators are in the expression",
            trigger: '.cm-content:contains(">=")',
        },
        {
            content: "Verify 'and' operator is present",
            trigger: '.cm-content:contains("and")',
        },
    ],
});
