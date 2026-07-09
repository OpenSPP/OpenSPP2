/** @odoo-module */

/**
 * MapLibre/MapTiler GL style for an OpenStreetMap raster fallback, used when no
 * MapTiler API key is configured. Shared by the GIS renderer and the geo-edit
 * map field widget so the fallback stays consistent in one place.
 *
 * @returns {Object} A MapLibre GL style object backed by OSM raster tiles.
 */
export function osmFallbackStyle() {
    return {
        version: 8,
        sources: {
            osm: {
                type: "raster",
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            },
        },
        layers: [
            {
                id: "osm-tiles",
                type: "raster",
                source: "osm",
                minzoom: 0,
                maxzoom: 19,
            },
        ],
    };
}
