/** @odoo-module **/

import {router} from "@web/core/browser/router";
import {patch} from "@web/core/utils/patch";

/**
 * Patch the router to use /openspp/ instead of /odoo/ for branding.
 *
 * This changes URLs from:
 *   /odoo/programs/123 -> /openspp/programs/123
 *   /odoo/individuals  -> /openspp/individuals
 *
 * The server-side controller handles both /odoo and /openspp routes,
 * so existing bookmarks and links continue to work.
 */

// The URL prefix used by the webclient router
const OPENSPP_PREFIX = "/openspp";
const ODOO_PREFIX = "/odoo";

// Patch the router's functions to handle /openspp prefix
patch(router, {
    stateToUrl(state) {
        // Call original to get the URL with /odoo prefix
        let url = super.stateToUrl(state);
        // Replace /odoo with /openspp at the start of the path
        if (url && url.startsWith(ODOO_PREFIX)) {
            url = OPENSPP_PREFIX + url.slice(ODOO_PREFIX.length);
        }
        return url;
    },

    urlToState(url) {
        // Convert /openspp URLs to /odoo before parsing so the router recognizes them
        // Note: url is a URL object, not a string - access pathname property
        if (url && url.pathname && url.pathname.startsWith(OPENSPP_PREFIX)) {
            url = new URL(url); // Clone to avoid mutating original
            url.pathname = ODOO_PREFIX + url.pathname.slice(OPENSPP_PREFIX.length);
        }
        return super.urlToState(url);
    },
});

// Re-initialize router state after patch is applied
// This is needed because startRouter() runs before our patch, so the initial
// state was parsed without /openspp -> /odoo conversion
const currentUrl = new URL(window.location);
if (currentUrl.pathname.startsWith(OPENSPP_PREFIX)) {
    const correctState = router.urlToState(currentUrl);
    if (correctState.action && correctState.action !== router.current?.action) {
        router.replaceState(correctState, {replace: true, sync: true});
    }
}
