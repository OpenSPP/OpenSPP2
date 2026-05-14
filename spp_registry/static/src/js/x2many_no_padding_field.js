/** @odoo-module **/

import {ListRenderer} from "@web/views/list/list_renderer";
import {X2ManyField, x2ManyField} from "@web/views/fields/x2many/x2many_field";
import {registry} from "@web/core/registry";

/**
 * Drop-in replacement for the standard x2many list widget that suppresses
 * the trailing empty placeholder rows. See OP#943.
 *
 * Odoo 19's ListRenderer hardcodes a 4-row minimum (list_renderer.js
 * `getEmptyRowIds`), padding inline One2many tables with empty rows in
 * readonly view. Those empty rows look like unfinished data entry. This
 * widget overrides `getEmptyRowIds` to always return an empty list, so
 * only populated rows render.
 *
 * Usage:
 *   <field name="phone_number_ids" widget="x2many_no_padding">
 *       <list editable="bottom">
 *           ...
 *       </list>
 *   </field>
 *
 * "Add a line" still works in edit mode — only the visual padding rows
 * are removed.
 */
export class NoPaddingListRenderer extends ListRenderer {
    get getEmptyRowIds() {
        return [];
    }
}

export class X2ManyNoPaddingField extends X2ManyField {}
X2ManyNoPaddingField.components = {
    ...X2ManyField.components,
    ListRenderer: NoPaddingListRenderer,
};

export const x2ManyNoPaddingField = {
    ...x2ManyField,
    component: X2ManyNoPaddingField,
};

registry.category("fields").add("x2many_no_padding", x2ManyNoPaddingField);
