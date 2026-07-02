/** @odoo-module **/

import {Component, onMounted, onPatched, onWillStart} from "@odoo/owl";

import {loadCSS, loadJS} from "@web/core/assets";
import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

export class FieldGisEditMap extends Component {
    setup() {
        // Generate a unique id for the map element
        this.id = `map_${Date.now()}`;
        this.orm = useService("orm");
        this.rpc = rpc;

        this.sourceId = `${this.geoType}Source`;

        // Load required libraries
        onWillStart(async () => {
            return Promise.all([
                loadJS("/spp_gis/static/lib/turf-3.0.11/turf.min.js"),
                loadJS(
                    "/spp_gis/static/lib/maptiler-sdk-js-1.2.0/maptiler-sdk.umd.min.js"
                ),
                loadJS("/spp_gis/static/lib/mapbox-gl-draw-1.2.0/mapbox-gl-draw.js"),
                loadCSS("/spp_gis/static/lib/maptiler-sdk-js-1.2.0/maptiler-sdk.css"),
                loadCSS("/spp_gis/static/lib/mapbox-gl-draw-1.2.0/mapbox-gl-draw.css"),
                this.getMapTilerKey(),
            ]);
        });

        onMounted(async () => {
            maptilersdk.config.apiKey = this.mapTilerKey;
            const editInfo = await this.orm.call(
                this.props.record.resModel,
                "get_edit_info_for_gis_column",
                [this.props.name]
            );
            const {default_zoom, srid} = editInfo;

            const default_center = JSON.parse(editInfo.default_center);

            Object.assign(this, {
                defaultZoom: default_zoom,
                srid,
                defaultCenter: default_center,
            });

            this.renderMap();
            this.onLoadMap();
            this.addDrawInteraction();
        });

        onPatched(() => {
            this.defaultZoom = this.map.getZoom();
            this.renderMap();
            this.onLoadMap();
            this.addDrawInteraction();
        });
    }

    async getMapTilerKey() {
        try {
            const response = await this.rpc("/get_maptiler_api_key");
            if (response.mapTilerKey) {
                this.mapTilerKey = response.mapTilerKey;
                this.webBaseUrl = response.webBaseUrl;
            } else {
                console.log("Error: Api Key not found.");
            }
        } catch (error) {
            console.error("Error fetching environment variable:", error);
        }
    }

    onLoadMap() {
        if (this.props.record.data[this.props.name]) {
            this.map.on("load", async () => {
                this.addSourceAndLayer(
                    this.sourceId,
                    this.props.record.data[this.props.name]
                );
            });
        }
    }

    renderMap() {
        if (this.props.record.data[this.props.name]) {
            const obj = JSON.parse(this.props.record.data[this.props.name]);
            const centroid = turf.centroid(obj);
            this.defaultCenter = centroid.geometry.coordinates;
        } else {
            // If this field is empty, try to center on a sibling geo field's data
            // (e.g., polygon map centers on coordinates point if set)
            const siblingCenter = this._findSiblingGeoCenter();
            if (siblingCenter) {
                this.defaultCenter = siblingCenter;
            }
        }

        if (!this.defaultZoom) {
            this.defaultZoom = 10;
        }

        this.map = new maptilersdk.Map({
            container: this.id,
            style: maptilersdk.MapStyle.STREETS,
            center: this.defaultCenter,
            zoom: this.defaultZoom,
        });
    }

    /**
     * Look for other geo fields on the same record that have data,
     * and return their centroid coordinates. This allows e.g. the polygon
     * map to auto-center on the coordinates point when the polygon is empty.
     */
    _findSiblingGeoCenter() {
        const geoFieldTypes = ["geo_point", "geo_polygon", "geo_line"];
        const record = this.props.record;
        for (const fieldName of Object.keys(record.fields)) {
            if (fieldName === this.props.name) {
                continue;
            }
            const fieldDef = record.fields[fieldName];
            if (geoFieldTypes.includes(fieldDef.type) && record.data[fieldName]) {
                try {
                    const obj = JSON.parse(record.data[fieldName]);
                    const centroid = turf.centroid(obj);
                    return centroid.geometry.coordinates;
                } catch {
                    // Skip invalid geo data
                }
            }
        }
        return null;
    }

    addSourceAndLayer(sourceId, jsonString) {
        if (!this.map.getSource(sourceId)) {
            this.addSource(sourceId, jsonString);
            this.addLayer(sourceId);
        }
    }

    addSource(sourceId, jsonString) {
        const obj = JSON.parse(jsonString);
        const centroid = turf.centroid(obj);

        this.map.addSource(sourceId, {
            type: "geojson",
            data: obj,
        });
        this.map.setCenter(centroid.geometry.coordinates);

        this.source = this.map.getSource(sourceId);
    }

    addLayer(sourceId) {
        // Polygon
        this.map.addLayer({
            id: `${sourceId}-polygon-layerid`,
            type: "fill",
            source: sourceId,
            filter: ["all", ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
            layout: {},
            paint: {
                "fill-color": "#98b",
                "fill-opacity": 0.8,
            },
        });

        // Point
        this.map.addLayer({
            id: `${sourceId}-point-layerid`,
            type: "circle",
            source: sourceId,
            filter: ["all", ["==", "$type", "Point"], ["!=", "mode", "static"]],
            layout: {},
            paint: {
                "circle-color": "#FF680A",
            },
        });

        // Linestring
        this.map.addLayer({
            id: `${sourceId}-linestring-layerid`,
            type: "line",
            source: sourceId,
            filter: ["all", ["==", "$type", "LineString"], ["!=", "mode", "static"]],
            layout: {},
            paint: {
                "line-color": "#e11",
                "line-width": 4,
            },
        });
    }

    removeSourceAndLayer(source) {
        this.map.removeLayer(source);
        this.map.removeSource(source);
    }

    onUIChange() {
        this.removeSourceAndLayer(this.sourceId);
        this.onLoadMap();
        this.addDrawInteraction();
    }

    addDrawInteraction() {
        const self = this;

        function updateArea(e) {
            console.log(e);
            var data = self.draw.getAll();
            self.props.record.update({
                [self.props.name]: JSON.stringify(data.features[0].geometry),
            });
        }

        this.draw = new MapboxDraw({
            displayControlsDefault: false,
            controls: {
                [this.drawControl]: !this.props.record.data[this.props.name],
                trash: Boolean(this.props.record.data[this.props.name]),
            },
            styles: this.addDrawInteractionStyle(),
            defaultMode: "custom_mode",
            modes: Object.assign(
                {
                    custom_mode: this.addDrawCustomModes(),
                },
                MapboxDraw.modes
            ),
        });
        this.map.addControl(this.draw);

        const drawControls = document.querySelectorAll(
            ".mapboxgl-ctrl-group.mapboxgl-ctrl"
        );
        drawControls.forEach((elem) => {
            elem.classList.add("maplibregl-ctrl", "maplibregl-ctrl-group");
        });

        this.map.on("draw.create", updateArea);
        this.map.on("draw.update", updateArea);

        const url = `/spp_gis/static/src/images/laos_farm.png`;

        this.map.on("click", `${this.sourceId}-polygon-layerid`, (e) => {
            new maptilersdk.Popup()
                .setLngLat(e.lngLat)
                .setHTML(
                    `<img src="${url}" height="200" width="300" alt="Placeholder Image">`
                )
                .addTo(this.map);
        });
    }

    addDrawInteractionStyle() {
        return [
            // Polygon fill
            {
                id: "gl-draw-polygon-fill",
                type: "fill",
                filter: ["all", ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
                paint: {
                    "fill-color": "#D20C0C",
                    "fill-outline-color": "#D20C0C",
                    "fill-opacity": 0.3,
                },
            },
            // Polygon mid points
            {
                id: "gl-draw-polygon-midpoint",
                type: "circle",
                filter: ["all", ["==", "$type", "Point"], ["==", "meta", "midpoint"]],
                paint: {
                    "circle-radius": 3,
                    "circle-color": "#fbb03b",
                },
            },
            // Polygon outline stroke
            // This doesn't style the first edge of the polygon, which uses the line stroke styling instead
            {
                id: "gl-draw-polygon-stroke-active",
                type: "line",
                filter: ["all", ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
                layout: {
                    "line-cap": "round",
                    "line-join": "round",
                },
                paint: {
                    "line-color": "#D20C0C",
                    "line-dasharray": [0.2, 2],
                    "line-width": 2,
                },
            },
            {
                id: "highlight-active-points",
                type: "circle",
                filter: [
                    "all",
                    ["==", "$type", "Point"],
                    ["==", "meta", "feature"],
                    ["==", "active", "true"],
                ],
                paint: {
                    "circle-radius": 7,
                    "circle-color": "#000000",
                },
            },
            {
                id: "points-are-blue",
                type: "circle",
                filter: [
                    "all",
                    ["==", "$type", "Point"],
                    ["==", "meta", "feature"],
                    ["==", "active", "false"],
                ],
                paint: {
                    "circle-radius": 5,
                    "circle-color": "#000088",
                },
            },
            {
                id: "gl-draw-line",
                type: "line",
                filter: [
                    "all",
                    ["==", "$type", "LineString"],
                    ["!=", "mode", "static"],
                ],
                layout: {
                    "line-cap": "round",
                    "line-join": "round",
                },
                paint: {
                    "line-color": "#D20C0C",
                    "line-dasharray": [0.2, 2],
                    "line-width": 2,
                },
            },
            // INACTIVE (static, already drawn)
            // line stroke
            {
                id: "gl-draw-line-static",
                type: "line",
                filter: [
                    "all",
                    ["==", "$type", "LineString"],
                    ["==", "mode", "static"],
                ],
                layout: {
                    "line-cap": "round",
                    "line-join": "round",
                },
                paint: {
                    "line-color": "#000",
                    "line-width": 3,
                },
            },
        ];
    }

    addDrawCustomModes() {
        const customMode = {};
        const self = this;
        customMode.onTrash = function (state) {
            console.log(state);
            self.props.record.update({[self.props.name]: null});
        };

        return customMode;
    }
}

FieldGisEditMap.template = "spp_gis.FieldGisEditMap";
FieldGisEditMap.props = {
    ...standardFieldProps,
    opacity: {type: Number, optional: true},
    color: {type: String, optional: true},
};

FieldGisEditMap.extractProps = (attrs) => {
    return {
        opacity: attrs.options.opacity,
        color: attrs.options.color,
    };
};

export class FieldGisEditMapPolygon extends FieldGisEditMap {
    setup() {
        this.geoType = "Polygon";
        this.drawControl = "polygon";
        super.setup();
    }
}

export class FieldGisEditMapPoint extends FieldGisEditMap {
    setup() {
        this.geoType = "Point";
        this.drawControl = "point";
        super.setup();
    }
}

export class FieldGisEditMapLine extends FieldGisEditMap {
    setup() {
        this.geoType = "LineString";
        this.drawControl = "line_string";
        super.setup();
    }
}
export const fieldGisEditMapPolygon = {
    component: FieldGisEditMapPolygon,
};

export const fieldGisEditMapPoint = {
    component: FieldGisEditMapPoint,
};

export const fieldGisEditMapLine = {
    component: FieldGisEditMapLine,
};

registry.category("fields").add("geo_polygon", fieldGisEditMapPolygon);
registry.category("fields").add("geo_point", fieldGisEditMapPoint);
registry.category("fields").add("geo_line", fieldGisEditMapLine);
