/** @odoo-module **/

import {RadioField, radioField} from "@web/views/fields/radio/radio_field";
import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";

/**
 * A radio widget that supports hiding individual options based on
 * boolean fields on the record.
 *
 * Usage in XML views:
 *   <field
 *       name="operation"
 *       widget="filterable_radio"
 *       options="{
 *           'disabled_map': {
 *               'update': 'allow_id_edit',
 *               'remove': 'allow_id_remove'
 *           }
 *       }"
 *   />
 *
 * The `disabled_map` option maps selection values to boolean field names.
 * When the boolean field is falsy, the corresponding radio option is
 * hidden from the user.
 */
export class FilterableRadioField extends RadioField {
    static template = "spp_base_common.FilterableRadioField";
    static props = {
        ...RadioField.props,
        disabledMap: {type: Object, optional: true},
    };
    static defaultProps = {
        ...RadioField.defaultProps,
        disabledMap: {},
    };

    /**
     * Check whether a given selection value should be disabled.
     * @param {any} value - The selection key to check
     * @returns {Boolean}
     */
    isItemDisabled(value) {
        if (this.props.readonly) {
            return true;
        }
        const map = this.props.disabledMap;
        if (!map || !(value in map)) {
            return false;
        }
        const boolField = map[value];
        return !this.props.record.data[boolField];
    }
}

export const filterableRadioField = {
    ...radioField,
    component: FilterableRadioField,
    displayName: _t("Filterable Radio"),
    supportedOptions: [
        ...radioField.supportedOptions,
        {
            label: _t("Disabled map (value → boolean field)"),
            name: "disabled_map",
            type: "object",
        },
    ],
    extractProps: (fieldInfo, dynamicInfo) => {
        const baseProps = radioField.extractProps(fieldInfo, dynamicInfo);
        return {
            ...baseProps,
            disabledMap: fieldInfo.options.disabled_map || {},
        };
    },
};

registry.category("fields").add("filterable_radio", filterableRadioField);
