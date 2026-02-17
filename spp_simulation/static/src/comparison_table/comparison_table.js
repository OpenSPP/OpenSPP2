/** @odoo-module **/

import {Component, useState, onWillStart, onWillUpdateProps} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class SimulationComparisonTable extends Component {
    static template = "spp_simulation.SimulationComparisonTable";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            runs: [],
            metrics: [
                {key: "beneficiary_count", label: "Beneficiaries", format: "number"},
                {key: "total_cost", label: "Total Cost", format: "currency"},
                {key: "coverage_rate", label: "Coverage Rate", format: "percent"},
                {key: "equity_score", label: "Equity Score", format: "score"},
                {key: "gini_coefficient", label: "Benefit Equality (Gini)", format: "decimal"},
                {key: "leakage_rate", label: "Leakage", format: "percent"},
                {key: "undercoverage_rate", label: "Missed Population", format: "percent"},
                {key: "targeting_accuracy", label: "Targeting Accuracy", format: "percent"},
                {key: "budget_utilization", label: "Budget Utilization", format: "percent"},
            ],
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
        if (value && value.runs) {
            this.state.runs = value.runs;
        } else {
            this.state.runs = [];
        }
    }

    formatValue(value, format) {
        if (value === null || value === undefined) return "-";
        switch (format) {
            case "number":
                return value.toLocaleString();
            case "currency":
                return value.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                });
            case "percent":
                return value.toFixed(1) + "%";
            case "score":
                return Math.round(value) + "/100";
            case "decimal":
                return value.toFixed(2);
            default:
                return String(value);
        }
    }

    formatDate(isoString) {
        if (!isoString) return "";
        try {
            const date = new Date(isoString);
            return date.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return isoString;
        }
    }

    isBestValue(metricKey, runIndex) {
        const values = this.state.runs.map((r) => r[metricKey] || 0);
        const value = values[runIndex];
        // For these metrics, lower is better
        const lowerIsBetter = ["gini_coefficient", "leakage_rate", "undercoverage_rate", "total_cost"];
        if (lowerIsBetter.includes(metricKey)) {
            return value === Math.min(...values);
        }
        return value === Math.max(...values);
    }
}

registry.category("fields").add("simulation_comparison_table", {
    component: SimulationComparisonTable,
    supportedTypes: ["json"],
});
