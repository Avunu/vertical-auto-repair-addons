/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Overrides `shopfloor_mobile_base`'s own `app-bar-actions`
 * (components/screen.esm.js) - Vue 2 allows re-registering a global
 * component this way, the same technique already used for `nav-items-extra`
 * in this module. `app-bar-actions` is mounted inside `Screen`'s actual
 * `v-app-bar` (the bar holding the hamburger icon, title and info icon) on
 * every authenticated screen - this is deliberately NOT a `Screen` override,
 * which would touch a much bigger, pinned-upstream surface for the same
 * result.
 *
 * Keeps the base magnifier/scan button and adds the shift timer and
 * (when there is one) the compact job timer, centered in the bar (see
 * `.app-bar-timers` in css/repair_job.css) - both shown on every screen,
 * not gated by route: the shift timer is a standing "am I clocked in"
 * indicator regardless of what the technician is doing, and the job timer
 * already gates itself on `job_timer` being non-null (a job actually being
 * open), which is the condition that actually matters, not which screen
 * renders it. `shift_timer.esm.js`/`job_timer_compact.esm.js` read
 * `timer_store` directly now rather than taking a `timer` prop from here -
 * see their own comments for why (component-local tick state doesn't
 * survive this component's own teardown/rebuild on every route change).
 *
 * Both timers are backed by `timer_store` (services/timer_store.esm.js), a
 * `Vue.observable()` that lives outside this component's own lifecycle -
 * `app-bar-actions` itself gets destroyed and recreated on every route
 * change (`Screen` isn't a persistent shell - every top-level page renders
 * its own).
 */
/** @import {JobTimer} from "../services/timer_store.esm.js" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {timer_store, refresh_shift_timer} from "../services/timer_store.esm.js";

const AppBarActions = defineComponent({
    data() {
        return {
            // Was `$options._componentTag` (a Vue-internal, undocumented field
            // some Vue-aware type-checking frontends don't model consistently) -
            // this is just that same tag name, explicit and typed, matching the
            // `Vue.component()` registration below.
            tag_name: "app-bar-actions",
        };
    },
    computed: {
        // `$route` in a template hits the same IDE-typing gap as `$root`
        // (user_session_detail.esm.js/pages/profile.esm.js) and
        // `$options._componentTag` (this file's own `tag_name` above) -
        // exposing a typed computed instead of `this.$route.name` inline is
        // what actually gets the template checked.
        /** @returns {boolean} */
        is_scan_anything() {
            return this.$route.name === "scan_anything";
        },
        /** @returns {JobTimer | null} */
        job_timer() {
            return timer_store.current_job_timer;
        },
    },
    mounted() {
        this._start_shift_polling();
    },
    methods: {
        /** @returns {void} */
        _start_shift_polling() {
            // Guarded so only the *first* app-bar-actions instance ever
            // starts the interval - it isn't tied to this instance's own
            // lifecycle (deliberately not cleared in beforeDestroy), so it
            // keeps `timer_store` current in the background for as long as
            // the technician stays logged in, regardless of which page
            // destroys/recreates this component.
            if (timer_store._shift_polling_started) {
                return;
            }
            timer_store._shift_polling_started = true;
            const poll = () => {
                refresh_shift_timer(this).catch(() => {
                    // A missed poll isn't worth surfacing to the technician;
                    // the display just keeps ticking from its last value
                    // until the next successful poll.
                });
            };
            poll();
            // Attendance state rarely changes mid-shift; a slow poll is
            // plenty and keeps this consistent with the per-job timer's
            // own client-tick-from-a-server-timestamp approach (no `bus`
            // push).
            setInterval(poll, 60000);
        },
    },
    template: html`
        <div :class="tag_name">
            <div class="app-bar-timers">
                <job-timer-compact v-if="job_timer" />
                <shift-timer />
            </div>
            <v-btn icon @click="$router.push({'name': 'scan_anything'})" :disabled="is_scan_anything">
                <v-icon>mdi-magnify</v-icon>
            </v-btn>
        </div>
    `,
});

export default AppBarActions;

Vue.component("app-bar-actions", AppBarActions);
