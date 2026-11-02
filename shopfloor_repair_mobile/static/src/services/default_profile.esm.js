/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Selects the user's remembered profile by itself.
 *
 * `shopfloor_mobile_base` keeps the active profile only in the browser
 * (`config_registry` -> storage, cleared on logout and after the storage
 * TTL), so every fresh login used to land on "pick your profile" again. The
 * backend (`shopfloor_repair/services/app.py`) now remembers the last
 * profile each user picked and sends it in the sync payload as
 * `default_profile_id`; this module applies it whenever no profile is
 * active. Remembering the pick is done where it is made, in
 * pages/profile.esm.js - not here, because auto-selecting also fires
 * `profile:selected` and must not write back what it just read.
 *
 * Two entry points, because the sync payload reaches the root two ways:
 *  - `app.sync:update`: right after a login or a forced config reload (the
 *    normal "signed in on a fresh device/session" case);
 *  - `app:mounted`: a page load where the payload came out of `$storage`
 *    and no request was made, so no `app.sync:update` fires.
 */
/** @import {ShopfloorRoot} from "../types/shopfloor-mobile-base" */
import event_hub from "/shopfloor_mobile_base/static/src/services/event_hub.esm.js";

/**
 * @param {ShopfloorRoot} root
 * @param {{default_profile_id?: number | null} | null | undefined} config
 * @returns {void}
 */
function apply_default_profile(root, config) {
    if (root.has_profile || !config || !config.default_profile_id) {
        return;
    }
    const profile = root.profiles.find((p) => p.id === config.default_profile_id);
    if (profile) {
        // Same call the Profile page makes; `true` = "don't prefix the event
        // with the current scenario state", which `loadMenu` listens for.
        root.trigger("profile:selected", profile, true);
    }
}

event_hub.$on(
    "app.sync:update",
    (/** @type {{root: ShopfloorRoot, sync_data: {data?: {default_profile_id?: number | null}}}} */ payload) => {
        apply_default_profile(payload.root, payload.sync_data && payload.sync_data.data);
    }
);

event_hub.$on("app:mounted", (/** @type {ShopfloorRoot} */ root) => {
    apply_default_profile(root, root.appconfig);
});
