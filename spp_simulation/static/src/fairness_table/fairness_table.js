/** @odoo-module **/

import {Component, useState, onWillStart, onWillUpdateProps} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class SimulationFairnessTable extends Component {
    static template = "spp_simulation.SimulationFairnessTable";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            attributes: [],
            equityScore: 0,
            hasDisparity: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.record?.resId !== this.props.record?.resId) {
                await this.loadData(nextProps.record?.resId);
            }
        });
    }

    get resId() {
        return this.props.record?.resId;
    }

    async loadData(recordId = null) {
        const resId = recordId || this.resId;
        if (!resId) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        try {
            const [data] = await this.orm.read(
                "spp.simulation.run",
                [resId],
                ["fairness_json", "equity_score", "has_disparity"]
            );
            if (data && data.fairness_json) {
                const fairness = data.fairness_json;
                this.state.equityScore = data.equity_score || 0;
                this.state.hasDisparity = data.has_disparity || false;
                this.state.attributes = Object.entries(fairness.attributes || {}).map(
                    ([key, attr]) => ({
                        name: key,
                        groups: attr.groups || [],
                        worstRatio: attr.worst_ratio || 0,
                        hasDisparity: attr.has_disparity || false,
                    })
                );
            }
        } catch (error) {
            console.error("Failed to load fairness data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    getStatusIcon(status) {
        if (status === "proportional" || status === "fair") return "\u2713";
        if (status === "low_coverage" || status === "warning") return "\u26A0";
        return "\u2717";
    }

    getStatusClass(status) {
        if (status === "proportional" || status === "fair") return "text-success";
        if (status === "low_coverage" || status === "warning") return "text-warning";
        return "text-danger";
    }

    getStatusLabel(status) {
        if (status === "proportional" || status === "fair") return "Proportional";
        if (status === "low_coverage" || status === "warning") return "Low coverage";
        if (status === "under_represented" || status === "disparity")
            return "Under-represented";
        return status;
    }

    formatRatio(value) {
        return (value || 0).toFixed(2);
    }

    formatPercent(value) {
        return (value || 0).toFixed(1) + "%";
    }

    getScoreBadgeClass() {
        if (this.state.equityScore >= 80) return "bg-success";
        if (this.state.equityScore >= 60) return "bg-warning";
        return "bg-danger";
    }
}

registry.category("fields").add("simulation_fairness_table", {
    component: SimulationFairnessTable,
    supportedTypes: ["json"],
});
