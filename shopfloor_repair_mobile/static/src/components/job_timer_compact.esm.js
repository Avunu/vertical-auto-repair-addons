/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * "<job name>: HH:MM:SS" - a compact, read-only echo of the interactive
 * `repair-timer` card that still lives in job_detail's `.job-hub` (that one
 * is not removed or moved - see scenario/repair_job.esm.js). This one shows
 * the same running/elapsed state in the app-bar so it stays visible on every
 * screen in the app, not just the repair_job scenario.
 *
 * Fed via `timer_store.current_job_timer` (services/timer_store.esm.js) -
 * published both eagerly by the repair_job scenario while a job with a
 * running timer is open, and independently by app_bar_actions.esm.js's own
 * poll, which is what keeps it correct once the technician has navigated
 * elsewhere. Reads the store directly rather than taking a `timer` prop and
 * ticking locally, for the same reason `shift_timer.esm.js` does: this
 * component lives inside `app-bar-actions`, torn down and rebuilt on every
 * route change, so a tick counter kept in its own component state would
 * reset to 0 (and visibly rewind the display) on every navigation.
 */

/* global Vue */

import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {
    format_elapsed,
    job_elapsed_seconds,
    timer_store,
} from "../services/timer_store.esm.js";

const JobTimerCompact = defineComponent({
    computed: {
        /** @returns {Boolean} */
        running() {
            return Boolean(
                timer_store.current_job_timer && timer_store.current_job_timer.running
            );
        },
        /** @returns {String} */
        job_name() {
            return timer_store.current_job_timer
                ? timer_store.current_job_timer.job_name
                : "";
        },
        /** @returns {String} */
        display() {
            return format_elapsed(job_elapsed_seconds());
        },
    },
    template: html`
        <div class="app-bar-timer job-timer-compact">
            <span class="app-bar-timer__label">{{ job_name }}:</span>
            <span v-if="running">{{ display }}</span>
            <span v-else>--:--:--</span>
        </div>
    `,
});

export default JobTimerCompact;

Vue.component("job-timer-compact", JobTimerCompact);
