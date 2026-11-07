/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * "Shift: HH:MM:SS" - elapsed time since today's hr_attendance clock-in.
 *
 * Read-only on purpose: hr_attendance (a kiosk, a backend check-in, another
 * device), not this app, is what starts and stops it - there is nothing to
 * click here, unlike the interactive per-job `repair-timer`.
 *
 * Reads `timer_store` (services/timer_store.esm.js) directly rather than
 * taking a `timer` prop and ticking locally - this component lives inside
 * `app-bar-actions`, which is destroyed and recreated on every route
 * change, so any tick counter kept in its own component state would reset
 * to 0 on every navigation, visibly rewinding the display to the last
 * poll's snapshot each time. `timer_store` owns the persistent tick counter
 * instead (see its own comment for why), so this component only ever needs
 * to read and format it - remounting has no effect on the value shown.
 */

/* global Vue */

import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {
    format_elapsed,
    shift_elapsed_seconds,
    timer_store,
} from "../services/timer_store.esm.js";

translation_registry.add("en-US.repair.timer.shift", "Shift");

const ShiftTimer = defineComponent({
    computed: {
        /** @returns {Boolean} */
        running() {
            return timer_store.shift_timer.running;
        },
        /** @returns {String} */
        display() {
            return format_elapsed(shift_elapsed_seconds());
        },
    },
    template: html`
        <div class="app-bar-timer shift-timer">
            <span class="app-bar-timer__label">{{ $t('repair.timer.shift') }}:</span>
            <span v-if="running">{{ display }}</span>
            <span v-else>--:--:--</span>
        </div>
    `,
});

export default ShiftTimer;

Vue.component("shift-timer", ShiftTimer);
