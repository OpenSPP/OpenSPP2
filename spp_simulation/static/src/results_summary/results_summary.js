/** @odoo-module **/

import {Component, useState, onWillStart, onWillUpdateProps} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class SimulationResultsSummary extends Component {
    static template = "spp_simulation.SimulationResultsSummary";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            beneficiaryCount: 0,
            coverageRate: 0,
            totalCost: 0,
            budgetUtilization: 0,
            equityScore: 0,
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
                [
                    "beneficiary_count",
                    "coverage_rate",
                    "total_cost",
                    "budget_utilization",
                    "equity_score",
                    "state",
                ]
            );
            if (data && data.state === "completed") {
                this.state.beneficiaryCount = data.beneficiary_count || 0;
                this.state.coverageRate = data.coverage_rate || 0;
                this.state.totalCost = data.total_cost || 0;
                this.state.budgetUtilization = data.budget_utilization || 0;
                this.state.equityScore = data.equity_score || 0;
            }
        } catch (error) {
            console.error("Failed to load simulation results:", error);
        } finally {
            this.state.loading = false;
        }
    }

    getEquityClass() {
        if (this.state.equityScore >= 80) return "text-success";
        if (this.state.equityScore >= 60) return "text-warning";
        return "text-danger";
    }

    formatNumber(value) {
        return value.toLocaleString();
    }

    formatPercent(value) {
        return value.toFixed(1) + "%";
    }

    formatCurrency(value) {
        return value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

registry.category("fields").add("simulation_results_summary", {
    component: SimulationResultsSummary,
    supportedTypes: ["integer"],
});
