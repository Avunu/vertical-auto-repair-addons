/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Overrides `shopfloor_mobile_base`'s own `nav-items-extra`
 * (components/screen.esm.js) - a separate, hardcoded, always-visible drawer
 * entry list, independent of `shopfloor.menu`/`<nav-items>`. Vue 2 allows
 * re-registering a global component this way (same technique already used
 * for `app-bar-actions`), which is the only override point available - the
 * base component has no slot for this.
 *
 * Drops the base "Home" entry (it opened a plain, purposeless landing
 * page) and "Settings" (its two pieces of functionality, Language and
 * Logout, moved onto the Profile page - see pages/profile.esm.js - so
 * there's nothing left on the Settings page worth a drawer entry for).
 *
 * Adds its own "Home" row (opens pages/home.esm.js) plus the shared list
 * (My Jobs/My Timesheets/Scan/Clock In-Out) from services/nav_items.esm.js,
 * also used by pages/home.esm.js so the drawer and the Home page always
 * show the same destinations. My Jobs here duplicates what the real
 * `<nav-items>` entry (the `shopfloor.menu`-backed one, rendered
 * separately by `Screen`) would otherwise show - that one is hidden via
 * CSS instead (css/repair_job.css, `.nav-items { display: none; }`), per
 * an explicit ask to keep this styled one instead of the base one.
 */
/** @import {NavItem} from "../services/nav_items.esm.js" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {home_nav_items} from "../services/nav_items.esm.js";

const NavItemsExtra = defineComponent({
    data() {
        return {
            // Was `$options._componentTag` (a Vue-internal, undocumented field
            // some Vue-aware type-checking frontends don't model consistently) -
            // this is just that same tag name, explicit and typed, matching the
            // `Vue.component()` registration below.
            tag_name: "nav-items-extra",
        };
    },
    computed: {
        /** @returns {NavItem[]} */
        items() {
            return home_nav_items(this);
        },
    },
    template: html`
        <div :class="tag_name">
            <v-list-item :to="{name: 'home'}" link active-class="'v-item-active" exact>
                <v-list-item-content>
                    <v-list-item-title><v-icon>mdi-home-outline</v-icon> {{ $t('repair.jobs.home') }}</v-list-item-title>
                </v-list-item-content>
            </v-list-item>
            <v-list-item
                v-for="item in items"
                :key="'nav-item-extra-' + item.id"
                :to="item.to"
                link
                active-class="'v-item-active"
                exact
                >
                <v-list-item-content>
                    <v-list-item-title><v-icon>{{ item.icon }}</v-icon> {{ item.name}}</v-list-item-title>
                </v-list-item-content>
            </v-list-item>
        </div>
    `,
});

export default NavItemsExtra;

Vue.component("nav-items-extra", NavItemsExtra);
