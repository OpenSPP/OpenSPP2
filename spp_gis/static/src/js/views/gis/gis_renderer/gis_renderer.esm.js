/** @odoo-module */

import {
    Component,
    onMounted,
    onPatched,
    onWillStart,
    reactive,
    useState,
} from "@odoo/owl";
import {
    addFieldDependencies,
    extractFieldsFromArchInfo,
} from "@web/model/relational_model/utils";
import {loadCSS, loadJS} from "@web/core/assets";
import {LayersPanel} from "../layers_panel/layers_panel.esm";
import {RelationalModel} from "@web/model/relational_model/relational_model";
import {dataLayersStore} from "../../../data_layers_store.esm";
import {parseXML} from "@web/core/utils/xml";
import {rasterLayersStore} from "../../../raster_layers_store.esm";
import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

// GisRenderer component definition.
export class GisRenderer extends Component {
    // Component setup lifecycle hook.
    setup() {
        // Initialize component state.
        this.state = useState({
            isModified: false,
            isFit: false,
        });

        // Initialize properties to store model information.
        this.models = [];
        this.cfg_models = [];
        this.dataLayerModel = {};

        this.sources = [];
        this.layers = [];
        this.geoTypes = ["Polygon", "LineString", "Point"];

        // Create reactive layer stores with change handlers.
        this.rasterLayersStore = reactive(rasterLayersStore, () =>
            this.onRasterLayerChanged()
        );
        this.dataLayersStore = reactive(dataLayersStore, () =>
            this.onDataLayerChanged()
        );

        // Initialize Odoo services.
        this.orm = useService("orm");
        this.view = useService("view");
        this.user = user;
        this.fields = useService("field");
        this.actionService = useService("action");
        this.rpc = rpc;

        this.sourceId = `gisViewSource`;

        // Load additional services required by the RelationalModel.
        this.services = RelationalModel.services.reduce((services, serviceKey) => {
            services[serviceKey] = useService(serviceKey);
            return services;
        }, {});

        this.getMapTilerKey();

        onWillStart(async () => {
            return Promise.all([
                // Load external JavaScript libraries
                loadJS("/spp_gis/static/lib/turf-3.0.11/turf.min.js"),
                loadJS(
                    "/spp_gis/static/lib/maptiler-sdk-js-1.2.0/maptiler-sdk.umd.min.js"
                ),
                loadJS("/spp_gis/static/lib/mapbox-gl-draw-1.2.0/mapbox-gl-draw.js"),
                loadJS(
                    "/spp_gis/static/lib/maptiler-geocoding-control-1.2.0/maptilersdk.umd.js"
                ),
                // Load external CSS libraries
                loadCSS("/spp_gis/static/lib/maptiler-sdk-js-1.2.0/maptiler-sdk.css"),
                loadCSS("/spp_gis/static/lib/mapbox-gl-draw-1.2.0/mapbox-gl-draw.css"),
                loadCSS(
                    "/spp_gis/static/lib/maptiler-geocoding-control-1.2.0/style.css"
                ),
                this.loadDataLayerForm(),
                (this.isGisAdmin = await this.user.hasGroup("spp_gis.group_gis_admin")),
            ]);
        });

        onMounted(() => {
            maptilersdk.config.apiKey = this.mapTilerKey;
            this.setupSourceAndLayer();

            this.renderMap();
        });

        onPatched(() => {
            this.setupFeatureCollection();
            this.map.getSource(this.sourceId).setData(this.featureCollection);
        });
    }

    async getMapTilerKey() {
        try {
            const response = await this.rpc("/get_maptiler_api_key");
            this.mapTilerKey = response.mapTilerKey;
            if (response.mapTilerKey) {
                this.mapTilerKey = response.mapTilerKey;
            } else {
                console.log("Error: Api Key not found.");
            }
        } catch (error) {
            console.error("Error fetching environment variable:", error);
        }
    }

    /**
     * Check if a record matches a domain filter.
     * Supports simple conditions: =, !=, in, not in, <, >, <=, >=
     * @param {Object} values - Record field values
     * @param {String|Array} domain - Domain filter (string or array)
     * @returns {Boolean} True if record matches domain
     */
    _matchesDomain(values, domain) {
        if (!domain) return true;

        let domainArray;
        try {
            domainArray = typeof domain === "string" ? JSON.parse(domain) : domain;
        } catch {
            return true; // Invalid domain, show all records
        }

        if (!Array.isArray(domainArray) || domainArray.length === 0) return true;

        for (const condition of domainArray) {
            if (!Array.isArray(condition) || condition.length !== 3) continue;

            const [field, operator, expected] = condition;
            const actual = values[field];

            let match = false;
            switch (operator) {
                case "=":
                    match = actual === expected;
                    break;
                case "!=":
                    match = actual !== expected;
                    break;
                case "<":
                    match = actual < expected;
                    break;
                case ">":
                    match = actual > expected;
                    break;
                case "<=":
                    match = actual <= expected;
                    break;
                case ">=":
                    match = actual >= expected;
                    break;
                case "in":
                    match = Array.isArray(expected) && expected.includes(actual);
                    break;
                case "not in":
                    match = !Array.isArray(expected) || !expected.includes(actual);
                    break;
                default:
                    match = true;
            }
            if (!match) return false;
        }
        return true;
    }

    /**
     * Load records for a specific model via RPC.
     * @param {String} model - Model name (e.g., "stock.warehouse")
     * @param {String} geoField - Geo field name to fetch
     * @param {Array} extraFields - Additional fields to fetch for choropleth values
     * @param {String} domain - Optional domain filter
     * @returns {Promise<Array>} Records with geo field data
     */
    async _loadModelRecords(model, geoField, extraFields, domain) {
        // Only request geo field and id - display_name is auto-included
        // Extra fields are needed for choropleth values
        const fields = [geoField, "id", ...extraFields];
        let parsedDomain = [];

        // Parse domain if provided
        if (domain) {
            try {
                parsedDomain = typeof domain === "string" ? JSON.parse(domain) : domain;
            } catch {
                parsedDomain = [];
            }
        }

        // Note: We don't filter on geo field in domain because it might be
        // a computed/related field that can't be searched. Filter after fetch.

        try {
            const records = await this.orm.searchRead(model, parsedDomain, fields, {
                limit: 10000,
            });
            // Filter out records without geo data (handles computed/related fields)
            return records.filter((r) => r[geoField]);
        } catch (error) {
            console.warn(
                `Could not load records for model ${model}: ${error.message || error}`
            );
            return [];
        }
    }

    /**
     * Build features from a set of records for a specific layer.
     * @param {Array} records - Records from the model
     * @param {Object} layer - Layer configuration
     * @param {String} geoField - Geo field name
     * @returns {Array} GeoJSON features
     */
    _buildFeaturesFromRecords(records, layer, geoField) {
        const features = [];
        records.forEach((record) => {
            // Apply layer domain filter (for base model records that have _values)
            const values = record._values || record;
            if (!this._matchesDomain(values, layer.domain)) {
                return;
            }

            const jsonGeometry = values[geoField];
            if (jsonGeometry) {
                const properties = {
                    resModel: layer.model || this.props.data._config.resModel,
                    resId: record.id || (record.config && record.config.resId),
                    layerId: layer.id,
                };

                // Add choropleth value if this is a choropleth layer
                if (layer.geo_repr === "choropleth" && layer.choropleth_config) {
                    const fieldName = layer.choropleth_config.field_name;
                    const choroplethValue = values[fieldName];
                    properties.choropleth_value =
                        typeof choroplethValue === "number" ? choroplethValue : 0;
                }

                try {
                    const geometry =
                        typeof jsonGeometry === "string"
                            ? JSON.parse(jsonGeometry)
                            : jsonGeometry;
                    features.push({
                        type: "Feature",
                        geometry,
                        properties,
                    });
                } catch (error) {
                    console.error("Error parsing geometry:", error);
                }
            }
        });
        return features;
    }

    setupFeatureCollection() {
        const records = this.props.data.records;
        const baseModel = this.props.data._config.resModel;
        const features = [];

        this.dataLayersStore.getLayers.forEach((layer) => {
            // Handle report-based layers with pre-built features
            if (layer.source_type === "report" && layer.report_features) {
                // Update layerId in features to match the current layer.id
                // (which may have been modified by layers_panel to use datapoint format)
                layer.report_features.forEach((feature) => {
                    if (feature.properties) {
                        feature.properties.layerId = layer.id;
                    }
                });
                features.push(...layer.report_features);
                this.createDefaultDataLayers(layer);
                return;
            }

            const layerModel = layer.model;
            const geoFieldName = layer.geo_field_id[1];

            // For base model layers, use the already loaded records
            if (!layerModel || layerModel === baseModel) {
                const layerFeatures = this._buildFeaturesFromRecords(
                    records,
                    layer,
                    geoFieldName
                );
                features.push(...layerFeatures);
            }
            // For cross-model layers, records are loaded separately in _loadCrossModelData

            this.createDefaultDataLayers(layer);
        });

        // Merge with cross-model features if available
        if (this._crossModelFeatures) {
            features.push(...this._crossModelFeatures);
        }

        this.featureCollection = {
            type: "FeatureCollection",
            features,
        };
    }

    /**
     * Load data for layers that use models different from the base model.
     * Should be called once after layers are initialized.
     */
    async _loadCrossModelData() {
        const baseModel = this.props.data._config.resModel;
        const layers = this.dataLayersStore.getLayers;
        const crossModelFeatures = [];

        for (const layer of layers) {
            // Skip report-based layers - they use pre-built report_features
            if (layer.source_type === "report" && layer.report_features) {
                continue;
            }

            const layerModel = layer.model;
            const geoFieldName = layer.geo_field_id[1];

            // Skip base model layers - they use props.data.records
            if (!layerModel || layerModel === baseModel) {
                continue;
            }

            // Determine extra fields needed (e.g., choropleth value field)
            const extraFields = [];
            if (layer.geo_repr === "choropleth" && layer.choropleth_config) {
                extraFields.push(layer.choropleth_config.field_name);
            }

            // Load records for this cross-model layer
            const records = await this._loadModelRecords(
                layerModel,
                geoFieldName,
                extraFields,
                layer.domain
            );
            const layerFeatures = this._buildFeaturesFromRecords(
                records,
                layer,
                geoFieldName
            );
            crossModelFeatures.push(...layerFeatures);
        }

        this._crossModelFeatures = crossModelFeatures;
    }

    setupSourceAndLayer() {
        this.rasterLayersStore.getLayers.forEach((layer) => {
            if (layer.raster_type === "d_wms") {
                const rasterLayerSourceId = `wms_${layer.id}`;
                this.createWMSRasterSource(rasterLayerSourceId, layer);
                this.createWMSRasterLayer(rasterLayerSourceId, layer);
            }
            if (layer.raster_type === "image") {
                const sourceId = `image_${layer.id}`;
                this.createImageRasterSource(sourceId, layer);
                this.createImageRasterLayer(sourceId, layer);
            }
            if (layer.raster_type === "osm" && layer.isVisible) {
                this.defaultRaster = layer;
            }
        });

        this.setupFeatureCollection();

        this.createDefaultDataSource(this.featureCollection);
    }

    async renderMap() {
        let defaultCenter = [124.74037191, 7.83479874];
        let defaultZoom = 6;
        const editInfo = await this.orm.call(
            this.props.data._config.resModel,
            "get_edit_info_for_gis",
            []
        );

        if (editInfo.default_center) {
            defaultCenter = JSON.parse(editInfo.default_center);
        }
        if (editInfo.default_zoom) {
            defaultZoom = editInfo.default_zoom;
        }

        if (this.featureCollection.features.length > 0) {
            try {
                const centroid = turf.centroid(this.featureCollection);
                if (centroid && centroid.geometry && centroid.geometry.coordinates) {
                    defaultCenter = centroid.geometry.coordinates;
                }
            } catch (error) {
                console.warn(
                    "Could not compute centroid for feature collection:",
                    error.message
                );
                // Use default center if centroid calculation fails
            }
        }

        let defaultMapStyle = this.getMapStyle();

        if (this.defaultRaster) {
            if (this.defaultRaster.raster_style.includes("-")) {
                const rasterStyleArray = this.defaultRaster.raster_style
                    .toUpperCase()
                    .split("-");
                defaultMapStyle =
                    maptilersdk.MapStyle[rasterStyleArray[0]][rasterStyleArray[1]];
            } else {
                defaultMapStyle =
                    maptilersdk.MapStyle[this.defaultRaster.raster_style.toUpperCase()];
            }
        }

        this.map = new maptilersdk.Map({
            container: "olmap",
            style: defaultMapStyle,
            center: defaultCenter,
            zoom: defaultZoom,
        });

        this.map.on("styledata", () => {
            this.addSourceToMap();
            this.addLayerToMap();
        });

        this.map.on("load", async () => {
            this.addSourceToMap();
            this.addLayerToMap();
            this.renderChoroplethLegends();

            // Load cross-model data (warehouses, dispatches, etc.) and update map
            await this._loadCrossModelData();
            if (this._crossModelFeatures && this._crossModelFeatures.length > 0) {
                this.setupFeatureCollection();
                const source = this.map.getSource(this.sourceId);
                if (source) {
                    source.setData(this.featureCollection);
                }
            }
        });

        this.addMouseInteraction();

        const gc = new maptilersdkMaptilerGeocoder.GeocodingControl({});
        this.map.addControl(gc, "top-left");
    }

    getMapStyle(layer) {
        let mapStyle = maptilersdk.MapStyle.STREETS;

        if (layer) {
            if (layer.raster_style.includes("-")) {
                const rasterStyleArray = layer.raster_style.toUpperCase().split("-");
                mapStyle =
                    maptilersdk.MapStyle[rasterStyleArray[0]][rasterStyleArray[1]];
            } else {
                mapStyle = maptilersdk.MapStyle[layer.raster_style.toUpperCase()];
            }
        }
        return mapStyle;
    }

    addMouseInteraction() {
        let formViewId = null;

        if (this.env.config && this.env.config.views) {
            const viewIds = this.env.config.views;
            const formView = viewIds.find((subList) => subList.includes("form"));
            // Only set formViewId if a form view was actually found
            if (formView) {
                formViewId = [formView];
            }
        }

        this.dataLayersStore.getLayers.forEach((layer) => {
            this.map.on("click", layer.id, (e) => {
                const {resModel, resId} = e.features[0].properties;
                // Only pass formViewId if it's valid, otherwise let controller use default
                this.props.openFormRecord(resModel, resId, formViewId || null);
            });

            // Change the cursor to a pointer when the mouse is over the places layer.
            this.map.on("mouseenter", layer.id, () => {
                this.map.getCanvas().style.cursor = "pointer";
            });
            // Change it back to a pointer when it leaves.
            this.map.on("mouseleave", layer.id, () => {
                this.map.getCanvas().style.cursor = "";
            });
        });
    }

    addSourceToMap() {
        this.sources.forEach((source) => {
            if (!this.map.getSource(source[0])) {
                this.map.addSource(source[0], source[1]);
            }
        });
    }

    createWMSRasterSource(sourceId, layer) {
        const url = `${layer.url}?layers=${layer.wms_layer_name}&tiled=true&service=WMS&request=GetMap&styles=&format=image/png&transparent=true&width=256&height=256&crs=EPSG:3857&srs=EPSG:3857&bbox={bbox-epsg-3857}`;
        this.sources.push([
            sourceId,
            {
                type: "raster",
                tiles: [url],
                tileSize: 256,
            },
        ]);
    }

    createWMSRasterLayer(sourceId, layer) {
        const opacity = Math.min(1, Math.max(0, layer.opacity));

        this.layers.push({
            type: "raster",
            id: sourceId,
            source: sourceId,
            paint: {
                "raster-opacity": opacity,
            },
            layout: {
                visibility: layer.isVisible ? "visible" : "none",
            },
        });
    }

    createImageRasterSource(sourceId, layer) {
        this.sources.push([
            sourceId,
            {
                type: "image",
                url: layer.image_url,
                coordinates: [
                    [layer.x_min, layer.y_max], // Top-left
                    [layer.x_max, layer.y_max], // Top-right
                    [layer.x_max, layer.y_min], // Bottom-right
                    [layer.x_min, layer.y_min], // Bottom-left
                ],
            },
        ]);
    }

    createImageRasterLayer(sourceId, layer) {
        const opacity = Math.min(1, Math.max(0, layer.image_opacity));

        this.layers.push({
            type: "raster",
            id: sourceId,
            source: sourceId,
            paint: {
                "raster-opacity": opacity,
            },
            layout: {
                visibility: layer.isVisible ? "visible" : "none",
            },
        });
    }

    createDefaultDataSource(features) {
        this.sources.push([
            this.sourceId,
            {
                type: "geojson",
                data: features,
            },
        ]);
    }

    /**
     * Build a MapLibre data-driven expression for choropleth coloring.
     * @param {Object} layer - The data layer configuration
     * @returns {Array} MapLibre expression for fill-color
     */
    _buildChoroplethExpression(layer) {
        const config = layer.choropleth_config;
        if (!config) {
            return layer.begin_color || "#3388ff";
        }

        const colors = config.color_ramp || ["#00ff00", "#ff0000"];
        const minValue = config.min_value || 0;
        const maxValue = config.max_value || 100;

        if (config.classification === "linear") {
            // Linear interpolation between colors
            if (colors.length === 2) {
                return [
                    "interpolate",
                    ["linear"],
                    ["coalesce", ["get", "choropleth_value"], 0],
                    minValue,
                    colors[0],
                    maxValue,
                    colors[1],
                ];
            }
            // Multi-stop interpolation (3+ colors)
            const stops = [];
            const step = (maxValue - minValue) / (colors.length - 1);
            colors.forEach((color, index) => {
                stops.push(minValue + step * index);
                stops.push(color);
            });
            return [
                "interpolate",
                ["linear"],
                ["coalesce", ["get", "choropleth_value"], 0],
                ...stops,
            ];
        }

        if (config.classification === "manual" && config.manual_breaks) {
            // Manual classification with user-defined breaks
            const breaks = config.manual_breaks
                .split(",")
                .map((b) => parseFloat(b.trim()))
                .filter((b) => !isNaN(b));

            if (breaks.length === 0) {
                return layer.begin_color || "#3388ff";
            }

            // Build step expression
            const steps = [colors[0]]; // Default color for values below first break
            breaks.forEach((breakValue, index) => {
                steps.push(breakValue);
                steps.push(colors[Math.min(index + 1, colors.length - 1)]);
            });

            return ["step", ["coalesce", ["get", "choropleth_value"], 0], ...steps];
        }

        // Quantile classification - use evenly spaced steps as approximation
        // (True quantile requires server-side calculation of percentiles)
        const classCount = config.class_count || 5;
        const stepSize = (maxValue - minValue) / classCount;
        const steps = [colors[0]];

        for (let i = 1; i <= classCount; i++) {
            const breakValue = minValue + stepSize * i;
            const colorIndex = Math.min(
                Math.floor((i / classCount) * (colors.length - 1)),
                colors.length - 1
            );
            steps.push(breakValue);
            steps.push(colors[colorIndex]);
        }

        return ["step", ["coalesce", ["get", "choropleth_value"], 0], ...steps];
    }

    createDefaultDataLayers(layer) {
        let layer_obj = {};
        const visibility = layer.isVisible ? "visible" : "none";
        const geoType = layer.geo_field_id[4];
        const opacity = Math.min(1, Math.max(0, layer.layer_opacity));

        // Determine fill/stroke color based on layer type
        let fillColor;
        let isChoropleth = false;

        if (layer.source_type === "report" && layer.report_features) {
            // Report layers: use pre-computed report_color from feature properties
            fillColor = ["coalesce", ["get", "report_color"], "#cccccc"];
            isChoropleth = true;
        } else if (layer.geo_repr === "choropleth" && layer.choropleth_config) {
            // Regular choropleth: use computed expression
            fillColor = this._buildChoroplethExpression(layer);
            isChoropleth = true;
        } else {
            // Static color
            fillColor = layer.begin_color || "#3388ff";
        }

        if (geoType === "geo_polygon") {
            layer_obj = {
                id: layer.id,
                type: "fill",
                source: this.sourceId,
                filter: [
                    "all",
                    ["==", "$type", "Polygon"],
                    ["!=", "mode", "static"],
                    ["==", "layerId", layer.id],
                ],
                layout: {
                    visibility: visibility,
                },
                paint: {
                    "fill-color": fillColor,
                    "fill-opacity": opacity,
                },
            };

            // Add outline for choropleth polygons
            if (isChoropleth) {
                this.layers.push({
                    id: `${layer.id}_outline`,
                    type: "line",
                    source: this.sourceId,
                    filter: [
                        "all",
                        ["==", "$type", "Polygon"],
                        ["!=", "mode", "static"],
                        ["==", "layerId", layer.id],
                    ],
                    layout: {
                        visibility: visibility,
                    },
                    paint: {
                        "line-color": "#333333",
                        "line-width": 1,
                        "line-opacity": opacity,
                    },
                });
            }
        }

        if (geoType === "geo_point") {
            layer_obj = {
                id: layer.id,
                type: "circle",
                source: this.sourceId,
                filter: [
                    "all",
                    ["==", "$type", "Point"],
                    ["!=", "mode", "static"],
                    ["==", "layerId", layer.id],
                ],
                layout: {
                    visibility: visibility,
                },
                paint: {
                    "circle-color": fillColor,
                    "circle-opacity": opacity,
                    "circle-radius": isChoropleth ? 8 : 6,
                    "circle-stroke-color": "#333333",
                    "circle-stroke-width": isChoropleth ? 1 : 0,
                },
            };
        }

        if (geoType === "geo_line") {
            layer_obj = {
                id: layer.id,
                type: "line",
                source: this.sourceId,
                filter: [
                    "all",
                    ["==", "$type", "LineString"],
                    ["!=", "mode", "static"],
                    ["==", "layerId", layer.id],
                ],
                layout: {
                    visibility: visibility,
                },
                paint: {
                    "line-color": fillColor,
                    "line-opacity": opacity,
                    "line-width": 4,
                },
            };
        }

        this.layers.push(layer_obj);
    }

    addLayerToMap() {
        this.layers.forEach((layer) => {
            if (!this.map.getLayer(layer.id)) {
                this.map.addLayer(layer);
            }
        });
    }

    async loadDataLayerForm() {
        await this.loadView("spp.gis.data.layer", "form");
    }

    async loadView(model, view) {
        const viewRegistry = registry.category("views");
        const fields = await this.fields.loadFields(model, {
            attributes: [
                "store",
                "searchable",
                "type",
                "string",
                "relation",
                "selection",
                "related",
            ],
        });
        const {relatedModels, views} = await this.view.loadViews({
            resModel: model,
            views: [[false, view]],
        });
        const {ArchParser, Model} = viewRegistry.get(view);

        const xmlDoc = parseXML(views[view].arch);
        const archInfo = new ArchParser().parse(xmlDoc, relatedModels, model);

        if (model === "spp.gis.data.layer") {
            const notAllowedField = Object.keys(fields).filter(
                (field) => fields[field].relation === "ir.ui.view"
            );
            notAllowedField.forEach((field) => {
                delete field[field];
            });
        }

        const {activeFields, arch_fields} = extractFieldsFromArchInfo(archInfo, fields);
        addFieldDependencies(
            activeFields,
            arch_fields,
            this.progressBarAggregateFields(archInfo)
        );

        const modelConfig = {
            model,
            activeFields,
            openGroupsByDefault: true,
            domain: [],
            orderBy: [],
            groupBy: [],
            resModel: model,
            fields,
        };

        const searchParams = {
            config: modelConfig,
            limit: 10000,
            groupsLimit: Number.MAX_SAFE_INTEGER,
            countLimit: archInfo.countLimit || Number.MAX_SAFE_INTEGER,
            orderBy: [],
            resModel: model,
        };

        if (model === "spp.gis.data.layer") {
            this.dataLayerModel = new Model(this.env, searchParams, this.services);
            await this.dataLayerModel.load(searchParams);
        } else {
            const existingModel = this.models.find((e) => e.model.resModel === model);
            if (!existingModel) {
                const toLoadModel = new Model(this.env, searchParams, this.services);
                await toLoadModel.load();
                this.models.push({model: toLoadModel.root, archInfo});
            }
        }
    }

    progressBarAggregateFields(archInfo) {
        const {sumField} = archInfo.progressAttributes || {};
        return sumField ? [sumField] : [];
    }

    async onDataLayerChanged() {
        for (const layer of this.dataLayersStore.getLayers) {
            const visibility = layer.isVisible ? "visible" : "none";
            const geoType = layer.geo_field_id[4];
            const opacity = Math.min(1, Math.max(0, layer.layer_opacity));
            let layerType = "";

            if (geoType === "geo_point") {
                layerType = "circle";
            }
            if (geoType === "geo_line") {
                layerType = "line";
            }
            if (geoType === "geo_polygon") {
                layerType = "fill";
            }

            // Determine color based on layer type
            let fillColor;
            if (layer.source_type === "report" && layer.report_features) {
                // Report layers: use pre-computed report_color
                fillColor = ["coalesce", ["get", "report_color"], "#cccccc"];
            } else if (layer.geo_repr === "choropleth" && layer.choropleth_config) {
                // Regular choropleth: use computed expression
                fillColor = this._buildChoroplethExpression(layer);
            } else {
                // Static color
                fillColor = layer.begin_color || "#3388ff";
            }

            // Skip if layer not yet added to map
            if (!this.map.getLayer(layer.id)) {
                continue;
            }

            this.map.setLayoutProperty(layer.id, "visibility", visibility);
            this.map.setPaintProperty(layer.id, `${layerType}-color`, fillColor);
            this.map.setPaintProperty(layer.id, `${layerType}-opacity`, opacity);

            // Handle choropleth outline layer visibility
            if (geoType === "geo_polygon") {
                const outlineLayerId = `${layer.id}_outline`;
                if (this.map.getLayer(outlineLayerId)) {
                    this.map.setLayoutProperty(
                        outlineLayerId,
                        "visibility",
                        visibility
                    );
                    this.map.setPaintProperty(outlineLayerId, "line-opacity", opacity);
                }
            }
        }

        // Update legends when layer visibility changes
        this.renderChoroplethLegends();
    }

    async onRasterLayerChanged() {
        for (const layer of this.rasterLayersStore.getLayers) {
            if (layer.raster_type === "d_wms") {
                const rasterLayerSourceId = `wms_${layer.id}`;
                const visibility = layer.isVisible ? "visible" : "none";
                const opacity = Math.min(1, Math.max(0, layer.opacity));

                this.map.setLayoutProperty(
                    rasterLayerSourceId,
                    "visibility",
                    visibility
                );
                this.map.setPaintProperty(
                    rasterLayerSourceId,
                    "raster-opacity",
                    opacity
                );
            } else if (layer.raster_type === "image") {
                const sourceId = `image_${layer.id}`;
                const visibility = layer.isVisible ? "visible" : "none";
                const opacity = Math.min(1, Math.max(0, layer.image_opacity));

                const source = this.map.getSource(sourceId);
                if (source) {
                    source.updateImage({
                        url: layer.image_url,
                        coordinates: [
                            [layer.x_min, layer.y_max], // Top-left
                            [layer.x_max, layer.y_max], // Top-right
                            [layer.x_max, layer.y_min], // Bottom-right
                            [layer.x_min, layer.y_min], // Bottom-left
                        ],
                    });
                    this.map.setLayoutProperty(sourceId, "visibility", visibility);
                    this.map.setPaintProperty(sourceId, "raster-opacity", opacity);
                }
            } else if (layer.raster_type === "osm" && layer.isVisible) {
                this.map.setStyle(this.getMapStyle(layer));
            }
        }
    }

    /**
     * Render choropleth legends for visible choropleth layers.
     */
    renderChoroplethLegends() {
        const legendContainer = document.getElementById("map-legend");
        if (!legendContainer) {
            return;
        }

        legendContainer.innerHTML = "";

        for (const layer of this.dataLayersStore.getLayers) {
            // Handle report-based choropleth layers
            if (
                layer.geo_repr === "choropleth" &&
                layer.report_legend &&
                layer.isVisible
            ) {
                this._renderReportLegend(legendContainer, layer);
                continue;
            }

            // Handle model-based choropleth layers with choropleth_config
            if (
                layer.geo_repr !== "choropleth" ||
                !layer.choropleth_config ||
                !layer.isVisible ||
                !layer.choropleth_config.show_legend
            ) {
                continue;
            }

            const config = layer.choropleth_config;
            const legendDiv = document.createElement("div");
            legendDiv.className = "choropleth-legend";

            // Title
            const titleDiv = document.createElement("div");
            titleDiv.className = "choropleth-legend-title";
            titleDiv.textContent =
                config.legend_title || config.field_label || layer.name;
            legendDiv.appendChild(titleDiv);

            const colors = config.color_ramp || ["#00ff00", "#ff0000"];
            const minValue = config.min_value || 0;
            const maxValue = config.max_value || 100;

            if (config.classification === "linear" || colors.length <= 3) {
                // Render gradient legend
                const gradientDiv = document.createElement("div");
                gradientDiv.className = "choropleth-legend-gradient";
                gradientDiv.style.background = `linear-gradient(to right, ${colors.join(", ")})`;
                legendDiv.appendChild(gradientDiv);

                const labelsDiv = document.createElement("div");
                labelsDiv.className = "choropleth-legend-labels";

                const minLabel = document.createElement("span");
                minLabel.textContent = this._formatLegendValue(minValue);
                labelsDiv.appendChild(minLabel);

                const maxLabel = document.createElement("span");
                maxLabel.textContent = this._formatLegendValue(maxValue);
                labelsDiv.appendChild(maxLabel);

                legendDiv.appendChild(labelsDiv);
            } else {
                // Render step legend for manual breaks or quantile
                const stepsDiv = document.createElement("div");
                stepsDiv.className = "choropleth-legend-steps";

                let breaks = [];
                if (config.classification === "manual" && config.manual_breaks) {
                    breaks = config.manual_breaks
                        .split(",")
                        .map((b) => parseFloat(b.trim()))
                        .filter((b) => !isNaN(b));
                } else {
                    // Generate breaks for quantile/equal-interval
                    const classCount = config.class_count || 5;
                    const stepSize = (maxValue - minValue) / classCount;
                    for (let i = 0; i < classCount; i++) {
                        breaks.push(minValue + stepSize * i);
                    }
                }

                // Create step items
                for (let i = 0; i <= breaks.length; i++) {
                    const stepDiv = document.createElement("div");
                    stepDiv.className = "choropleth-legend-step";

                    const colorDiv = document.createElement("div");
                    colorDiv.className = "choropleth-legend-step-color";
                    const colorIndex = Math.min(i, colors.length - 1);
                    colorDiv.style.backgroundColor = colors[colorIndex];
                    stepDiv.appendChild(colorDiv);

                    const labelDiv = document.createElement("div");
                    labelDiv.className = "choropleth-legend-step-label";

                    let rangeText = "";
                    if (i === 0) {
                        rangeText = `< ${this._formatLegendValue(breaks[0] || maxValue)}`;
                    } else if (i === breaks.length) {
                        rangeText = `≥ ${this._formatLegendValue(breaks[i - 1])}`;
                    } else {
                        rangeText = `${this._formatLegendValue(breaks[i - 1])} - ${this._formatLegendValue(breaks[i])}`;
                    }
                    labelDiv.textContent = rangeText;
                    stepDiv.appendChild(labelDiv);

                    stepsDiv.appendChild(stepDiv);
                }

                legendDiv.appendChild(stepsDiv);
            }

            legendContainer.appendChild(legendDiv);
        }
    }

    /**
     * Render legend for report-based choropleth layers.
     * Report layers have pre-defined thresholds with colors and labels.
     * @param {HTMLElement} container - The legend container element
     * @param {Object} layer - The layer data
     */
    _renderReportLegend(container, layer) {
        const legendDiv = document.createElement("div");
        legendDiv.className = "choropleth-legend";

        // Title
        const titleDiv = document.createElement("div");
        titleDiv.className = "choropleth-legend-title";
        titleDiv.textContent = layer.report_legend_title || layer.name;
        legendDiv.appendChild(titleDiv);

        // Steps from report thresholds
        const stepsDiv = document.createElement("div");
        stepsDiv.className = "choropleth-legend-steps";

        for (const item of layer.report_legend) {
            const stepDiv = document.createElement("div");
            stepDiv.className = "choropleth-legend-step";

            const colorDiv = document.createElement("div");
            colorDiv.className = "choropleth-legend-step-color";
            colorDiv.style.backgroundColor = item.color;
            stepDiv.appendChild(colorDiv);

            const labelDiv = document.createElement("div");
            labelDiv.className = "choropleth-legend-step-label";
            labelDiv.textContent = item.label;
            stepDiv.appendChild(labelDiv);

            stepsDiv.appendChild(stepDiv);
        }

        legendDiv.appendChild(stepsDiv);
        container.appendChild(legendDiv);
    }

    /**
     * Format a numeric value for display in the legend.
     * @param {Number} value - The value to format
     * @returns {String} Formatted value
     */
    _formatLegendValue(value) {
        if (typeof value !== "number" || isNaN(value)) {
            return "0";
        }
        if (Math.abs(value) >= 1000000) {
            return (value / 1000000).toFixed(1) + "M";
        }
        if (Math.abs(value) >= 1000) {
            return (value / 1000).toFixed(1) + "K";
        }
        if (Number.isInteger(value)) {
            return value.toString();
        }
        return value.toFixed(1);
    }
}

GisRenderer.template = "spp_gis.GisRenderer";
GisRenderer.props = {
    isSavedOrDiscarded: {type: Boolean},
    archInfo: {type: Object},
    data: {type: Object},
    openFormRecord: {type: Function},
    editable: {type: Boolean, optional: true},
};
GisRenderer.components = {LayersPanel};
