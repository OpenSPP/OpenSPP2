/** @odoo-module **/

import {Component, onMounted, onPatched, useRef} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

/**
 * Custom widget that renders HTML search results and handles row clicks.
 * When a row with class "o_cr_search_result" is clicked, it writes the
 * partner ID to the _selected_partner_id bridge field, which triggers
 * a server-side onchange to set registrant_id.
 */
export class CrSearchResultsField extends Component {
    static template = "spp_change_request_v2.CrSearchResultsField";
    static props = {...standardFieldProps};

    setup() {
        this.containerRef = useRef("container");
        onMounted(() => this._attachClickHandler());
        onPatched(() => this._attachClickHandler());
    }

    get htmlContent() {
        return this.props.record.data[this.props.name] || "";
    }

    _attachClickHandler() {
        const el = this.containerRef.el;
        if (!el) return;
        // Row selection
        el.querySelectorAll(".o_cr_search_result").forEach((row) => {
            row.onclick = (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                const partnerId = parseInt(row.dataset.partnerId, 10);
                if (partnerId) {
                    this.props.record.update({_selected_partner_id: partnerId});
                }
            };
        });
        // Pagination
        el.querySelectorAll(".o_cr_page_prev, .o_cr_page_next").forEach((link) => {
            link.onclick = (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                const page = parseInt(link.dataset.page);
                if (!isNaN(page) && page >= 0) {
                    this.props.record.update({_search_page: page});
                }
            };
        });
    }
}

export const crSearchResultsField = {
    component: CrSearchResultsField,
    displayName: _t("CR Search Results"),
    supportedTypes: ["html"],
};

registry.category("fields").add("cr_search_results", crSearchResultsField);
