/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Gets a signed-out browser back to the login screen instead of leaving it
 * stuck on a half-working app.
 *
 * `shopfloor_mobile_base` keeps the sign-in (`apikey`), the sync payload and
 * the selected profile in browser storage, each entry expiring 24 hours after
 * it was written (see `_make_app_info` in models/shopfloor_app.py). The
 * `authenticated` flag, though, is rewritten - and so re-extended - on every
 * page load that finds a stored config. So a day after logging in, the key
 * can be gone while the flag still says "signed in": every request then goes
 * out with an empty `API-KEY` header and gets a 401 whose body is an HTML
 * page, which the base REST client fails to parse as JSON and never turns
 * into a logout. The result is a Home page with no user, no profile and a
 * console full of "Unexpected token '<'".
 *
 * This checks for exactly that state once, when the app mounts, and signs out
 * the normal way (`root.logout()` clears the stored app data and routes to
 * the login page). It deliberately does not try to detect a key that is
 * present but rejected by the server - that needs the REST client itself to
 * handle a 401, which is the base module's business.
 *
 * Order relative to the OAuth login's own `app:mounted` listener doesn't
 * matter: if it runs first it sets the key and this sees one; if this runs
 * first the logout only clears stale state, and the OAuth listener then sets
 * the key and logs in as usual.
 */
/** @import {ShopfloorRoot} from "../types/shopfloor-mobile-base" */
import event_hub from "/shopfloor_mobile_base/static/src/services/event_hub.esm.js";

const KEY_AUTH_TYPES = ["api_key", "oauth"];

event_hub.$on("app:mounted", (/** @type {ShopfloorRoot} */ root) => {
    if (
        KEY_AUTH_TYPES.includes(String(root.app_info.auth_type)) &&
        root.is_authenticated() &&
        !root.apikey
    ) {
        root.logout();
    }
});
