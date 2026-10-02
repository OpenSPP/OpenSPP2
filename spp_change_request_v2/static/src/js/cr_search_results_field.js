/** @odoo-module **/

import {Component, onMounted, onPatched, useRef} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

const ROW_SELECTOR = ".o_cr_search_result";
const PAGER_SELECTOR = ".o_cr_page_prev, .o_cr_page_next";
const STATUS_SELECTOR = ".o_cr_search_status";
const CLEAR_BUTTON_SELECTOR = "button[name='action_clear_registrant']";
// Upper bound on waiting for the form to re-render after a record update.
const RENDER_WAIT_MS = 500;

/**
 * Custom widget that renders HTML search results and handles row selection
 * and paging by mouse or keyboard. The rows are options of a listbox: Enter
 * or Space selects the focused row, ArrowUp/ArrowDown/Home/End move between
 * rows. Selecting a row writes the partner ID to the _selected_partner_id
 * bridge field, which triggers a server-side onchange to set registrant_id;
 * paging writes _search_page the same way.
 */
export class CrSearchResultsField extends Component {
    static template = "spp_change_request_v2.CrSearchResultsField";
    static props = {...standardFieldProps};

    setup() {
        this.containerRef = useRef("container");
        this.statusRef = useRef("status");
        this.resolveNextPatch = null;
        onMounted(() => {
            // One delegated listener each: the server re-renders the whole
            // results blob on every search or page change, so per-row handlers
            // would have to be re-attached after each patch.
            this.containerRef.el.addEventListener("click", (ev) => this._onClick(ev));
            this.containerRef.el.addEventListener("keydown", (ev) =>
                this._onKeydown(ev)
            );
            this._announceStatus();
        });
        onPatched(() => {
            this._announceStatus();
            if (this.resolveNextPatch) {
                const resolve = this.resolveNextPatch;
                this.resolveNextPatch = null;
                resolve();
            }
        });
    }

    get htmlContent() {
        return this.props.record.data[this.props.name] || "";
    }

    get rows() {
        return [...this.containerRef.el.querySelectorAll(ROW_SELECTOR)];
    }

    _onClick(ev) {
        const row = ev.target.closest(ROW_SELECTOR);
        if (row) {
            ev.preventDefault();
            ev.stopPropagation();
            this._selectRow(row);
            return;
        }
        const pager = ev.target.closest(PAGER_SELECTOR);
        if (pager && !pager.disabled) {
            ev.preventDefault();
            ev.stopPropagation();
            this._goToPage(pager);
        }
    }

    _onKeydown(ev) {
        // The pager buttons are native buttons: Enter and Space already click them.
        const row = ev.target.closest(ROW_SELECTOR);
        if (!row) {
            return;
        }
        const rows = this.rows;
        const index = rows.indexOf(row);
        let target = null;
        switch (ev.key) {
            case "Enter":
            case " ":
                ev.preventDefault();
                this._selectRow(row);
                return;
            case "ArrowDown":
                target = rows[Math.min(index + 1, rows.length - 1)];
                break;
            case "ArrowUp":
                target = rows[Math.max(index - 1, 0)];
                break;
            case "Home":
                target = rows[0];
                break;
            case "End":
                target = rows[rows.length - 1];
                break;
            default:
                return;
        }
        ev.preventDefault();
        this._focusRow(target, rows);
    }

    /**
     * Roving tabindex: the list is a single Tab stop, and the row that holds
     * focus is the one Tab returns to.
     */
    _focusRow(row, rows) {
        for (const other of rows) {
            other.tabIndex = -1;
        }
        row.tabIndex = 0;
        row.focus();
    }

    async _selectRow(row) {
        const partnerId = parseInt(row.dataset.partnerId, 10);
        if (!partnerId) {
            return;
        }
        // Setting the registrant hides the results block, which unmounts this
        // widget, so focus is handed to the button that brings the search back.
        const formEl = this.containerRef.el.closest(".o_form_view");
        await this.props.record.update({_selected_partner_id: partnerId});
        await this._focusWhenRendered(formEl, [CLEAR_BUTTON_SELECTOR]);
    }

    async _goToPage(button) {
        const page = parseInt(button.dataset.page, 10);
        if (isNaN(page) || page < 0) {
            return;
        }
        const pressed = button.classList.contains("o_cr_page_next")
            ? ".o_cr_page_next"
            : ".o_cr_page_prev";
        const other =
            pressed === ".o_cr_page_next" ? ".o_cr_page_prev" : ".o_cr_page_next";
        const rendered = this._nextPatch();
        await this.props.record.update({_search_page: page});
        await rendered;
        // Keep focus on the button that was pressed so it can be pressed again;
        // on the last page it is disabled, so fall back to the other one, then
        // to the first row.
        await this._focusWhenRendered(this.containerRef.el, [
            pressed,
            other,
            ROW_SELECTOR,
        ]);
    }

    _nextPatch() {
        return new Promise((resolve) => {
            this.resolveNextPatch = resolve;
            setTimeout(resolve, RENDER_WAIT_MS);
        });
    }

    /**
     * Focus the first enabled element matching one of the selectors, polling a
     * few animation frames because the element may only appear once the form
     * has re-rendered with the onchange result.
     */
    async _focusWhenRendered(root, selectors) {
        if (!root) {
            return;
        }
        const deadline = Date.now() + RENDER_WAIT_MS;
        while (Date.now() < deadline) {
            for (const selector of selectors) {
                const target = root.querySelector(selector);
                if (target && !target.disabled) {
                    target.focus();
                    return;
                }
            }
            await new Promise(requestAnimationFrame);
        }
    }

    /**
     * Mirror the range summary ("1-10 of 23") or the empty-result message into
     * a live region that outlives the re-rendered blob, so screen readers hear
     * the outcome of a search or a page change.
     */
    _announceStatus() {
        const status = this.containerRef.el.querySelector(STATUS_SELECTOR);
        const text = status ? status.textContent.trim() : "";
        if (this.statusRef.el && this.statusRef.el.textContent !== text) {
            this.statusRef.el.textContent = text;
        }
    }
}

export const crSearchResultsField = {
    component: CrSearchResultsField,
    displayName: _t("CR Search Results"),
    supportedTypes: ["html"],
};

registry.category("fields").add("cr_search_results", crSearchResultsField);
