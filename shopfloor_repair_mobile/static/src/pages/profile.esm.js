/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Replaces `shopfloor_mobile_base`'s own Profile page
 * (settings/profile.esm.js) via `page_registry.replace()` - unlike
 * `Vue.component()`, `page_registry.add()` throws on a duplicate key
 * unless `override` is explicitly passed; `replace()` is the documented
 * shorthand for that. Confirmed load order (this module's own assets load
 * well after `shopfloor_mobile_base`'s own `profile.esm.js` registers)
 * makes this reliable.
 *
 * Keeps the original's profile picker (`<manual-select>`) verbatim.
 * Adds Language and Logout - both used to live on the Settings page,
 * which now has nothing left on it worth a drawer entry for (see
 * nav_items_extra.esm.js, which drops that entry) - so they move here,
 * onto the one page a technician actually has a reason to visit from the
 * drawer (tapping their own name/avatar - see user_session_detail.esm.js).
 * Drops `<btn-reset-config>` (the "RELOAD CONFIG AND MENU" button)
 * entirely, per the ask.
 */
/** @import {UserProfile, ShopfloorRoot} from "../types/shopfloor-mobile-base" */
import {page_registry} from "/shopfloor_mobile_base/static/src/services/page_registry.esm.js";
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {sf_root} from "../services/root.esm.js";

translation_registry.add("en-US.repair.profile.language", "Language");
// Overrides shopfloor_mobile_base's own "Select profile" (lowercase "p") -
// same re-registration technique used throughout this module, reliable
// here for the same reason: this page's own script loads after the base
// page it replaces.
translation_registry.add("en-US.screen.settings.profile.title", "Select Profile");

const Profile = defineComponent({
    data() {
        return {
            current_profile_id: /** @type {unknown} */ (
                sf_root(this).has_profile ? sf_root(this).profile.id : null
            ),
        };
    },
    computed: {
        // `$root` in a template resolves through Vue's own (bare) `$root: Vue`
        // type - see services/root.esm.js for why that can't be widened by
        // augmentation. Exposing a typed computed here is what actually gets
        // the template checked against the real shape.
        /** @returns {ShopfloorRoot} */
        root() {
            return sf_root(this);
        },
    },
    methods: {
        /**
         * @param {UserProfile | null} selected
         * @returns {void}
         */
        on_select(selected) {
            if (selected && !_.isEmpty(selected)) {
                sf_root(this).trigger("profile:selected", selected, true);
                this._remember(selected);
                sf_root(this).$router.push("/");
            }
        },
        // Stored on the user (backend), not just in the browser, so the next
        // login - even on another device, or after the browser storage was
        // cleared - starts with this profile already selected; see
        // services/default_profile.esm.js for the other half. Fire and
        // forget: failing to remember must never get in the way of picking.
        // The base REST client resolves with `{error}` on a non-2xx response
        // rather than rejecting, so both outcomes are checked - a missing
        // route (404) used to fail here without a trace.
        /**
         * @param {UserProfile} profile
         * @returns {void}
         */
        _remember(profile) {
            sf_root(this)
                .getOdoo({usage: "app"})
                .post("set_default_profile", {profile_id: profile.id})
                .then((/** @type {any} */ result) => {
                    if (result && result.error) {
                        console.warn("Could not remember the profile choice:", result.error);
                    }
                })
                .catch((/** @type {unknown} */ err) => {
                    console.warn("Could not remember the profile choice:", err);
                });
        },
    },
    template: html`
        <Screen :screen_info="{title: $t('screen.settings.profile.title'), klass: 'settings settings-profile'}">
            <manual-select
                :records="root.profiles"
                :options="{initValue: current_profile_id, showActions: false, required: true}"
                v-on:select="on_select"
                />

            <div class="button-list button-vertical-list full">
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-action color="primary" @click="$router.push({name: 'language'})">
                            <v-icon left>mdi-flag</v-icon>{{ $t('repair.profile.language') }}
                        </btn-action>
                    </v-col>
                </v-row>
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-action color="primary" @click="root.logout()">
                            <v-icon left>mdi-logout</v-icon>{{ $t('app.action.logout') }}
                        </btn-action>
                    </v-col>
                </v-row>
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-back/>
                    </v-col>
                </v-row>
            </div>
        </Screen>
    `,
});

export default Profile;

page_registry.replace("profile", Profile, {
    tag: "settings",
    icon: "mdi-account-cog",
    display_name: (/** @type {Vue} */ instance, /** @type {unknown} */ _rec) => {
        const root = sf_root(instance);
        const profile_name = root.has_profile ? root.profile.name : "?";
        return [instance.$t("screen.settings.profile.name"), profile_name].join(" - ");
    },
    is_enabled: (/** @type {Vue} */ instance, /** @type {unknown} */ _rec) => {
        return sf_root(instance).app_info.profile_required;
    },
});
