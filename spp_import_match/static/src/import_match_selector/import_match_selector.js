/** @odoo-module */
import {ImportAction} from "@base_import/import_action/import_action";
import {ImportDataSidepanel} from "@base_import/import_data_sidepanel/import_data_sidepanel";
import {BaseImportModel} from "@base_import/import_model";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

patch(ImportAction.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.importMatchRecords = [];
        this.state.selectedImportMatchId = false;
        this.state.overwriteMatch = false;
    },

    async onWillStart() {
        await super.onWillStart(...arguments);
        await this._loadImportMatchRecords();
    },

    async _loadImportMatchRecords() {
        const records = await this.model.orm.searchRead(
            "spp.import.match",
            [["model_name", "=", this.resModel]],
            ["id", "name", "overwrite_match"]
        );
        this.state.importMatchRecords = records;
    },

    async onImportMatchChanged(matchId) {
        this.state.selectedImportMatchId = matchId;
        this.model.importMatchIds = matchId ? [matchId] : [];
        if (matchId) {
            const record = this.state.importMatchRecords.find((r) => r.id === matchId);
            this.state.overwriteMatch = record ? record.overwrite_match : false;
        } else {
            this.state.overwriteMatch = false;
        }
        this.model.overwriteMatch = this.state.overwriteMatch;
    },

    onOverwriteMatchChanged(value) {
        this.state.overwriteMatch = value;
        this.model.overwriteMatch = value;
    },

    async handleImport(isTest) {
        const res = await super.handleImport(...arguments);
        if (!isTest && this.model.importMatchCounts) {
            const counts = this.model.importMatchCounts;
            const parts = [];
            if (counts.created) {
                parts.push(`${counts.created} ${_t("created")}`);
            }
            if (counts.overwritten) {
                parts.push(`${counts.overwritten} ${_t("overwritten")}`);
            }
            if (counts.skipped) {
                parts.push(`${counts.skipped} ${_t("skipped")}`);
            }
            if (parts.length) {
                this.notification.add(parts.join(", "), {
                    type: "success",
                });
            }
            this.model.importMatchCounts = null;
        }
        return res;
    },
});

patch(ImportDataSidepanel, {
    props: {
        ...ImportDataSidepanel.props,
        importMatchRecords: {type: Array, optional: true},
        selectedImportMatchId: {optional: true},
        onImportMatchChanged: {type: Function, optional: true},
        overwriteMatch: {type: Boolean, optional: true},
        onOverwriteMatchChanged: {type: Function, optional: true},
    },
});

patch(ImportDataSidepanel.prototype, {
    onImportMatchChange(ev) {
        const matchId = parseInt(ev.target.value, 10) || false;
        if (this.props.onImportMatchChanged) {
            this.props.onImportMatchChanged(matchId);
        }
    },

    onOverwriteMatchChange(ev) {
        if (this.props.onOverwriteMatchChanged) {
            this.props.onOverwriteMatchChanged(ev.target.checked);
        }
    },
});

patch(BaseImportModel.prototype, {
    async _callImport(dryrun, args) {
        if (this.importMatchIds && this.importMatchIds.length) {
            args[3] = {
                ...args[3],
                import_match_ids: this.importMatchIds,
                overwrite_match: this.overwriteMatch || false,
            };
        }

        try {
            const res = await this.orm.silent.call(
                "base_import.import",
                "execute_import",
                args,
                {
                    dryrun,
                    context: {
                        ...this.context,
                        tracking_disable: this.importOptions.tracking_disable,
                    },
                }
            );
            if (res.async === true) {
                this.displayNotification(_t("Successfully added on Queue"));
                history.go(-1);
            }
            if (res.import_match_counts) {
                if (dryrun) {
                    const counts = res.import_match_counts;
                    const parts = [];
                    if (counts.created) {
                        parts.push(`${counts.created} ${_t("to create")}`);
                    }
                    if (counts.overwritten) {
                        parts.push(`${counts.overwritten} ${_t("to overwrite")}`);
                    }
                    if (counts.skipped) {
                        parts.push(`${counts.skipped} ${_t("to skip")}`);
                    }
                    if (parts.length) {
                        this._addMessage("info", [parts.join(", ")]);
                    }
                } else {
                    this.importMatchCounts = res.import_match_counts;
                }
            }
            return res;
        } catch (error) {
            return {error};
        }
    },

    displayNotification(message) {
        this.env.services.action.doAction({
            type: "ir.actions.client",
            tag: "display_notification",
            params: {
                title: "Queued",
                message: message,
                type: "success",
                sticky: false,
            },
        });
    },
});
