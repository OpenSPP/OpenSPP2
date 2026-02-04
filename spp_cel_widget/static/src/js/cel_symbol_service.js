/** @odoo-module **/

/**
 * CEL Symbol Service
 *
 * Frontend service for fetching and caching CEL symbols.
 */

import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";

/**
 * Symbol cache to avoid repeated RPC calls
 */
const symbolCache = new Map();

/**
 * CEL Symbol Service
 */
export const celSymbolService = {
    dependencies: [],

    start() {
        return {
            /**
             * Get symbols for a profile
             * @param {String} profile - Profile name
             * @param {Boolean} forceRefresh - Skip cache
             * @returns {Promise<Object>} Symbol data
             */
            async getSymbols(profile, forceRefresh = false) {
                const cacheKey = profile;

                if (!forceRefresh && symbolCache.has(cacheKey)) {
                    return symbolCache.get(cacheKey);
                }

                try {
                    const result = await rpc(`/spp_cel/symbols/${profile}`, {});
                    symbolCache.set(cacheKey, result);
                    return result;
                } catch (error) {
                    console.error("[CelSymbolService] Failed to fetch symbols:", error);
                    return null;
                }
            },

            /**
             * Validate a CEL expression
             * @param {String} expression - CEL expression
             * @param {String} profile - Profile name
             * @param {Object} options - Optional parameters
             * @param {String} options.expression_type - Type of expression (filter, formula, scoring, etc.)
             * @param {String} options.output_type - Expected output type (boolean, number, money, string)
             * @returns {Promise<Object>} Validation result
             */
            async validate(expression, profile, options = {}) {
                try {
                    const params = {
                        expression,
                        profile,
                    };
                    // Add optional expression_type and output_type if provided
                    if (options.expression_type) {
                        params.expression_type = options.expression_type;
                    }
                    if (options.output_type) {
                        params.output_type = options.output_type;
                    }
                    const result = await rpc("/spp_cel/validate", params);
                    return result;
                } catch (error) {
                    console.error("[CelSymbolService] Validation error:", error);
                    return {
                        valid: false,
                        errors: [
                            {
                                message: error.message || "Validation failed",
                                line: 1,
                                col_start: 0,
                                col_end: expression.length,
                            },
                        ],
                    };
                }
            },

            /**
             * Get available profiles
             * @returns {Promise<Array>} List of profiles
             */
            async getProfiles() {
                try {
                    const result = await rpc("/spp_cel/profiles", {});
                    return result;
                } catch (error) {
                    console.error(
                        "[CelSymbolService] Failed to fetch profiles:",
                        error
                    );
                    return [];
                }
            },

            /**
             * Clear symbol cache
             * @param {String} profile - Optional specific profile to clear
             */
            clearCache(profile = null) {
                if (profile) {
                    symbolCache.delete(profile);
                } else {
                    symbolCache.clear();
                }
            },
        };
    },
};

registry.category("services").add("cel_symbols", celSymbolService);
