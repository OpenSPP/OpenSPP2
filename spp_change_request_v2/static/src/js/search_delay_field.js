/** @odoo-module **/

import {Component, useEffect, useRef, onWillUnmount} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {useDebounced} from "@web/core/utils/timing";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

/**
 * Char field that triggers onchange after a typing delay (500ms).
 * Used for search fields where we want live results without waiting for blur.
 */
export class SearchDelayField extends Component {
    static template = "spp_change_request_v2.SearchDelayField";
    static props = {
        ...standardFieldProps,
        placeholder: {type: String, optional: true},
    };

    setup() {
        this.inputRef = useRef("input");

        this.debouncedCommit = useDebounced((value) => {
            this.props.record.update({[this.props.name]: value});
        }, 500);

        // Keep input in sync when record updates externally (e.g. onchange clears it)
        useEffect(
            () => {
                const el = this.inputRef.el;
                if (el) {
                    const recordValue = this.props.record.data[this.props.name] || "";
                    if (el !== document.activeElement || !recordValue) {
                        el.value = recordValue;
                    }
                }
            },
            () => [this.props.record.data[this.props.name]]
        );
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    onInput(ev) {
        this.debouncedCommit(ev.target.value);
    }
}

export const searchDelayField = {
    component: SearchDelayField,
    displayName: _t("Search with Delay"),
    supportedTypes: ["char"],
    extractProps: ({placeholder}) => ({placeholder}),
};

registry.category("fields").add("search_delay", searchDelayField);
