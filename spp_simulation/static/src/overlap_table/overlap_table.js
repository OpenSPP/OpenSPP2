/** @odoo-module **/

import {Component, useState, onWillStart, onWillUpdateProps} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class SimulationOverlapTable extends Component {
    static template = "spp_simulation.SimulationOverlapTable";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            overlaps: [],
        });

        onWillStart(() => {
            this.updateFromProps();
        });

        onWillUpdateProps((nextProps) => {
            this.updateFromProps(nextProps);
        });
    }

    updateFromProps(props = this.props) {
        const value = props.record?.data?.[props.name];
        if (value && typeof value === "object") {
            // Convert object to array for easier iteration
            this.state.overlaps = Object.values(value);
        } else {
            this.state.overlaps = [];
        }
    }

    formatPercent(value) {
        if (value === null || value === undefined) return "-";
        return (value * 100).toFixed(1) + "%";
    }

    formatNumber(value) {
        if (value === null || value === undefined) return "-";
        return value.toLocaleString();
    }
}

registry.category("fields").add("simulation_overlap_table", {
    component: SimulationOverlapTable,
    supportedTypes: ["json"],
});
