/** @odoo-module */

/**
 * Logic Editor Components Index
 *
 * This module imports and registers all Logic Editor components for the
 * OpenSPP Logic Studio. These components provide the UI for building,
 * testing, and managing logic definitions.
 *
 * Components:
 * - VariablePicker: Dropdown for selecting available variables with search
 * - TestPanel: Test result display and execution interface
 *
 * Field Widgets:
 * - TestPanelField: Field widget wrapper for TestPanel
 *
 * Usage:
 * Import this module to ensure all Logic Editor components are registered
 * and available in the Odoo web client.
 *
 * @module spp_studio/logic_editor
 */

// Import all Logic Editor components
// These will self-register via the registry.category("components").add() calls

export * from "./variable_picker";
export * from "./test_panel";

// Import field widgets
// These will self-register via the registry.category("fields").add() calls
export * from "./test_panel_field";

/**
 * Note: The components are registered automatically when imported.
 * No additional initialization is required.
 *
 * To use these components in other modules:
 *
 * @example
 * import { VariablePicker } from "@spp_studio/logic_editor/variable_picker";
 *
 * // Or import all at once:
 * import * as LogicEditor from "@spp_studio/logic_editor";
 */
