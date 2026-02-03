/** @odoo-module **/

/**
 * CEL Expression Editor Field Widget
 *
 * A form field widget that wraps CelEditor for use in Odoo form views.
 * Handles:
 * - Integration with Odoo's record system
 * - Profile inference from record context
 * - Field value synchronization
 */

import {Component, onWillDestroy} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

import {CelEditor} from "./cel_editor";

export class CelEditorField extends Component {
    static template = "spp_cel_widget.CelEditorField";
    static components = {CelEditor};
    static props = {
        ...standardFieldProps,
        profile: {type: String, optional: true},
        profileField: {type: String, optional: true},
        expressionType: {type: String, optional: true},
        expressionTypeField: {type: String, optional: true},
        outputType: {type: String, optional: true},
        outputTypeField: {type: String, optional: true},
        showSymbolBrowser: {type: Boolean, optional: true},
        showValidationCount: {type: Boolean, optional: true},
        placeholder: {type: String, optional: true},
        minHeight: {type: String, optional: true},
    };

    setup() {
        this.editorApi = null;
        this.updateDebounceTimer = null;

        // Cleanup timer on unmount
        onWillDestroy(() => {
            if (this.updateDebounceTimer) {
                clearTimeout(this.updateDebounceTimer);
            }
        });
    }

    get profile() {
        const record = this.props.record;
        const data = record && record.data ? record.data : {};

        // Check for profile_field option - read profile from a specified field
        if (this.props.profileField && data[this.props.profileField]) {
            return data[this.props.profileField];
        }

        // Check for explicit 'profile' field on the record (e.g., from wizard)
        if (data.profile) {
            return data.profile;
        }

        // Explicit profile from XML attribute (cel_profile)
        if (this.props.profile) {
            return this.props.profile;
        }

        // Logic Studio: use context_type to pick profile
        const contextType = data.context_type;
        if (contextType === "group") {
            return "registry_groups";
        }
        if (contextType === "individual" || contextType === "both") {
            return "registry_individuals";
        }

        // Fallback
        return "registry_individuals";
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get expressionType() {
        const record = this.props.record;
        const data = record && record.data ? record.data : {};

        // Check for expression_type_field option - read from a specified field
        if (this.props.expressionTypeField && data[this.props.expressionTypeField]) {
            return data[this.props.expressionTypeField];
        }

        // Check for explicit 'expression_type' field on the record
        if (data.expression_type) {
            return data.expression_type;
        }

        // Explicit expression_type from XML attribute
        if (this.props.expressionType) {
            return this.props.expressionType;
        }

        // Return undefined (not null) for optional String prop compatibility
        return undefined;
    }

    get outputType() {
        const record = this.props.record;
        const data = record && record.data ? record.data : {};

        // Check for output_type_field option - read from a specified field
        if (this.props.outputTypeField && data[this.props.outputTypeField]) {
            return data[this.props.outputTypeField];
        }

        // Check for explicit 'output_type' field on the record
        if (data.output_type) {
            return data.output_type;
        }

        // Explicit output_type from XML attribute
        if (this.props.outputType) {
            return this.props.outputType;
        }

        // Return undefined (not null) for optional String prop compatibility
        return undefined;
    }

    get isReadonly() {
        return this.props.readonly;
    }

    onChange(value) {
        if (this.isReadonly) {
            return;
        }

        // Debounce the record update to prevent triggering onchange on every keystroke
        // This eliminates flickering when typing quickly
        if (this.updateDebounceTimer) {
            clearTimeout(this.updateDebounceTimer);
        }

        this.updateDebounceTimer = setTimeout(() => {
            this.props.record.update({[this.props.name]: value});
            this.updateDebounceTimer = null;
        }, 800); // 800ms delay after user stops typing
    }

    onEditorReady(api) {
        this.editorApi = api;
    }

    // Forward methods to CelEditor for external access
    triggerAutocomplete() {
        if (this.editorApi) {
            this.editorApi.triggerAutocomplete();
        }
    }

    forceValidate() {
        if (this.editorApi) {
            this.editorApi.forceValidate();
        }
    }
}

// Register the field widget
registry.category("fields").add("cel_expression", {
    component: CelEditorField,
    supportedTypes: ["text", "char"],
    extractProps: ({attrs, options}) => ({
        profile: options.cel_profile || attrs.cel_profile || options.profile,
        profileField: options.profile_field,
        expressionType: options.expression_type || attrs.expression_type,
        expressionTypeField: options.expression_type_field,
        outputType: options.output_type || attrs.output_type,
        outputTypeField: options.output_type_field,
        showSymbolBrowser: attrs.show_symbol_browser !== "false",
        showValidationCount: attrs.show_validation_count !== "false",
        placeholder: attrs.placeholder,
        minHeight: attrs.min_height,
    }),
});
