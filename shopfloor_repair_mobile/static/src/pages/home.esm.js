/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * A full-page version of the drawer's own extra nav list (My Jobs, My
 * Timesheets, Scan, Clock In/Out - services/nav_items.esm.js), reached via
 * the repair-job scenario's bottom "Home" button (see
 * scenario/repair_job.esm.js, renamed from "My Jobs" - that button used to
 * go straight to the job list; now it opens this page instead, matching the
 * drawer's own set of destinations rather than jumping to just one of
 * them).
 */
/** @import {NavItem} from "../services/nav_items.esm.js" */
import {page_registry} from "/shopfloor_mobile_base/static/src/services/page_registry.esm.js";
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {home_nav_items} from "../services/nav_items.esm.js";

translation_registry.add("en-US.repair.jobs.home", "Home");

const Home = defineComponent({
    computed: {
        /** @returns {{title: string}} */
        screen_info() {
            return {title: this.$t("repair.jobs.home")};
        },
        /** @returns {NavItem[]} */
        items() {
            return home_nav_items(this);
        },
    },
    template: html`
        <Screen :screen_info="screen_info">
            <v-list>
                <v-list-item
                    v-for="item in items"
                    :key="'home-item-' + item.id"
                    :to="item.to"
                    link
                >
                    <v-list-item-content>
                        <v-list-item-title
                            ><v-icon left>{{ item.icon }}</v-icon> {{ item.name
                            }}</v-list-item-title
                        >
                    </v-list-item-content>
                </v-list-item>
            </v-list>
        </Screen>
    `,
});

page_registry.add("home", Home, {}, {tag: "app_page"});

export default Home;
