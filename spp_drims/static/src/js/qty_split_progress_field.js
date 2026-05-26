/** @odoo-module **/
import {useEffect} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {FloatField, floatField} from "@web/views/fields/float/float_field";
import {formatFloat} from "@web/views/fields/formatters";

/**
 * Float widget for the inspection wizard's Qty column.
 *
 * On split **parent rows** (any other line points to this row via
 * ``parent_line_id``) it renders ``X / Y``, where ``X`` is the running
 * sum of child quantities (green when equal to the expected total ``Y``,
 * red otherwise). Children are read live from the wizard's One2many so
 * the display reacts to in-memory edits without relying on Python
 * onchange propagation (which is unreliable in Odoo 19's editable-list
 * cross-record updates).
 *
 * On split **child rows** the field behaves like a standard editable
 * float; a ``useEffect`` mirrors the running sum onto the parent record
 * via ``record.update`` so the parent's ``X / Y`` display updates
 * reactively whenever any child's quantity changes.
 *
 * On plain rows it falls back to the stock ``FloatField`` behaviour.
 */
export class QtySplitProgressField extends FloatField {
    static template = "spp_drims.QtySplitProgressField";

    setup() {
        super.setup();
        useEffect(
            () => {
                this._syncParentQuantity();
            },
            () => [this.props.record.data.quantity]
        );
    }

    _wizardLines() {
        const record = this.props.record;
        const candidates = [record._parentRecord, record.model && record.model.root];
        for (const wizard of candidates) {
            const lineList = wizard && wizard.data && wizard.data.line_ids;
            if (
                lineList &&
                Array.isArray(lineList.records) &&
                lineList.records.length > 0
            ) {
                return lineList.records;
            }
        }
        return [];
    }

    _extractM2oId(value) {
        // Many2one values in Odoo 19 OWL come as { id, ... } objects (often
        // wrapped in a Proxy). Older code paths use a [id, name] tuple.
        // Handle both shapes plus the bare-id case.
        if (value === null || value === undefined) {
            return null;
        }
        if (typeof value === "number" || typeof value === "string") {
            return value;
        }
        if (Array.isArray(value)) {
            return value[0];
        }
        if (typeof value === "object" && "id" in value) {
            return value.id;
        }
        return null;
    }

    _parentId() {
        const parentRef = this.props.record.data.parent_line_id;
        if (!parentRef) {
            return null;
        }
        return this._extractM2oId(parentRef);
    }

    _myChildren() {
        const myId = this.props.record.resId;
        if (!myId) {
            return [];
        }
        return this._wizardLines().filter((line) => {
            const parentRef = line.data.parent_line_id;
            if (!parentRef) {
                return false;
            }
            const parentId = this._extractM2oId(parentRef);
            return parentId === myId;
        });
    }

    async _syncParentQuantity() {
        // Runs after every change to this row's quantity. If the row is a
        // split child, recompute the parent's running sum and push it onto
        // the parent record so the parent's "X / Y" display refreshes.
        const parentId = this._parentId();
        if (!parentId) {
            return;
        }
        const lines = this._wizardLines();
        const parentRecord = lines.find(
            (line) => line.resId === parentId || String(line.resId) === String(parentId)
        );
        if (!parentRecord) {
            return;
        }
        const siblings = lines.filter((line) => {
            const parentRef = line.data.parent_line_id;
            if (!parentRef) {
                return false;
            }
            const pid = this._extractM2oId(parentRef);
            return pid === parentId;
        });
        const sum = siblings.reduce((acc, line) => acc + (line.data.quantity || 0), 0);
        const currentParentQty = parentRecord.data.quantity || 0;
        const expected = parentRecord.data.quantity_expected || 0;
        const nextFullySplit = sum >= expected - 0.001;
        const currentFullySplit = Boolean(parentRecord.data.is_fully_split);
        const qtyChanged = Math.abs(sum - currentParentQty) >= 0.001;
        const fullyChanged = currentFullySplit !== nextFullySplit;
        if (!qtyChanged && !fullyChanged) {
            return;
        }
        const updates = {};
        if (qtyChanged) {
            updates.quantity = sum;
        }
        if (fullyChanged) {
            updates.is_fully_split = nextFullySplit;
        }
        await parentRecord.update(updates);
    }

    get hasSplits() {
        return Boolean(this.props.record.data.has_splits);
    }

    get splitTotal() {
        const children = this._myChildren();
        if (children.length === 0) {
            // Fallback to the stored parent.quantity on initial render
            // before sibling reactivity has kicked in.
            return this.props.record.data.quantity || 0;
        }
        return children.reduce((sum, line) => sum + (line.data.quantity || 0), 0);
    }

    get splitTotalFormatted() {
        return formatFloat(this.splitTotal, {
            digits: [16, 2],
            trailingZeros: true,
        });
    }

    get splitTotalClass() {
        const expected = this.props.record.data.quantity_expected || 0;
        const matches = Math.abs(this.splitTotal - expected) < 0.001;
        return matches ? "text-success fw-bold" : "text-danger fw-bold";
    }

    get expectedFormatted() {
        return formatFloat(this.props.record.data.quantity_expected || 0, {
            digits: [16, 2],
            trailingZeros: true,
        });
    }
}

export const qtySplitProgressField = {
    ...floatField,
    component: QtySplitProgressField,
};

registry.category("fields").add("qty_split_progress", qtySplitProgressField);
