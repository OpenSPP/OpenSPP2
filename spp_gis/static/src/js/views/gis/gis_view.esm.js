/** @odoo-module */

import {GisArchParser} from "./gis_arch_parser.esm";
import {GisCompiler} from "./gis_compiler.esm";
import {GisController} from "./gis_controller/gis_controller.esm";
import {GisRenderer} from "./gis_renderer/gis_renderer.esm";
import {RelationalModel} from "@web/model/relational_model/relational_model";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

export const gisView = {
    type: "gis",
    display_name: _t("Map"),
    icon: "fa-map-marker",
    multiRecord: true,
    ArchParser: GisArchParser,
    Controller: GisController,
    Model: RelationalModel,
    Renderer: GisRenderer,
    Compiler: GisCompiler,

    searchMenuTypes: ["filter", "groupBy", "favorite"],

    props: (genericProps, view) => {
        const {ArchParser} = view;
        const {arch, relatedModels, resModel} = genericProps;
        const archInfo = new ArchParser().parse(arch, relatedModels, resModel);

        return {
            ...genericProps,
            Model: view.Model,
            Renderer: view.Renderer,
            archInfo,
        };
    },
};

const viewRegistry = registry.category("views");

// Register the GIS view with Odoo 19's view registry
console.log("[GIS] Registering GIS view with type:", gisView.type);
viewRegistry.add("gis", gisView);
console.log("[GIS] GIS view registered successfully!");
