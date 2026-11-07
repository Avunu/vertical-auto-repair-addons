/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * A tiny reactive store for timer state that has to survive navigation
 * across the app's top-level routes - each of which renders its own
 * `<Screen>` (confirmed by reading `main.xml`'s actual root template: just
 * `<router-view/>` in a plain container, not a persistent shell), and
 * therefore its own `<app-bar-actions>`. Component-local `data()` can't
 * hold this - it gets torn down and rebuilt on every route change.
 *
 * `this.$root.current_job_timer = ...` (or `Vue.set(this.$root, ...)`)
 * doesn't work either: confirmed by reading the vendored Vue 2 source
 * (`static/src/lib/vue.js`, `function set(target, key, val)`) that
 * `Vue.set` on a Vue *instance* target (`target._isVue`, true for `$root`)
 * for a key that was never declared in that instance's own `data()` is a
 * silent no-op - it only warns, it never assigns. That was the actual,
 * confirmed root cause of the job timer never showing up at all, not a
 * subtler reactivity-timing issue.
 *
 * `Vue.observable()` makes every key of a plain object reactive up front,
 * with neither restriction - and because this is a plain module-level
 * export, not owned by any component instance, it survives `Screen`/
 * `app-bar-actions` being destroyed and recreated any number of times.
 *
 * The client-side "ticked seconds" counter that bridges the gap between
 * ~60s server polls also has to live here for the same reason, not in
 * `shift_timer.esm.js`/`job_timer_compact.esm.js`'s own component state
 * (the pattern `repair-timer` uses) - those two specifically are mounted *inside*
 * `app-bar-actions`, so they get torn down and rebuilt on every route
 * change too, resetting their local tick count to 0 each time and making
 * the displayed elapsed time visibly jump backward to the last poll's
 * snapshot on every navigation. A single interval started once here,
 * guarded the same way `_shift_polling_started` already guards the REST
 * poll, keeps ticking regardless of which (if any) component is currently
 * mounted to display it.
 */

/* global Vue */

/** @import {TimerState} from "../components/timer_widget_types" */
import {menu_id_for, sf_root} from "./root.esm.js";

/** @typedef {TimerState & {job_name: string}} JobTimer */

/**
 * @typedef {Object} TimerStore
 * @property {JobTimer | null} current_job_timer
 * @property {TimerState} shift_timer
 * @property {Boolean} _shift_polling_started
 *   Guards the poll loop so only the *first* app-bar-actions instance
 *   ever starts it - the interval itself isn't tied to that instance's
 *   lifecycle, so it keeps updating `shift_timer` even after that
 *   instance is destroyed by a route change. Later instances just read
 *   the already-current value reactively - no re-poll flicker, no
 *   reset to blank on every navigation.
 * @property {Number} _shift_ticked_seconds
 * @property {Number} _job_ticked_seconds
 * @property {Boolean} _tick_interval_started
 */

/** @type {TimerStore} */
export const timer_store = Vue.observable({
    current_job_timer: null,
    shift_timer: {running: false, started_at: null, elapsed_hours: 0},
    _shift_polling_started: false,
    _shift_ticked_seconds: 0,
    _job_ticked_seconds: 0,
    _tick_interval_started: false,
});

/** @returns {void} */
function ensure_tick_loop() {
    if (timer_store._tick_interval_started) {
        return;
    }
    timer_store._tick_interval_started = true;
    setInterval(() => {
        if (timer_store.shift_timer.running) {
            timer_store._shift_ticked_seconds += 1;
        }
        if (timer_store.current_job_timer && timer_store.current_job_timer.running) {
            timer_store._job_ticked_seconds += 1;
        }
    }, 1000);
}
ensure_tick_loop();

/**
 * Replaces `timer_store.shift_timer` wholesale (what a fresh poll result
 * always is) - resets the tick counter only when the new snapshot is
 * actually a *different* run (a new `started_at`, or a start/stop
 * transition), not on every routine poll that just re-confirms the same
 * still-running timer.
 *
 * @param {TimerState} next
 * @returns {void}
 */
export function set_shift_timer(next) {
    const prev = timer_store.shift_timer;
    const changed =
        next.started_at !== prev.started_at || next.running !== prev.running;
    timer_store.shift_timer = next;
    if (changed) {
        timer_store._shift_ticked_seconds = 0;
    }
}

/**
 * Same idea as `set_shift_timer`, for the job timer.
 *
 * @param {JobTimer | null} next
 * @returns {void}
 */
export function set_current_job_timer(next) {
    const prev = timer_store.current_job_timer;
    const changed =
        Boolean(next) !== Boolean(prev) ||
        (next &&
            prev &&
            (next.started_at !== prev.started_at || next.running !== prev.running));
    timer_store.current_job_timer = next;
    if (changed) {
        timer_store._job_ticked_seconds = 0;
    }
}

/** @returns {Number} */
export function shift_elapsed_seconds() {
    return (
        Math.round((timer_store.shift_timer.elapsed_hours || 0) * 3600) +
        timer_store._shift_ticked_seconds
    );
}

/** @returns {Number} */
export function job_elapsed_seconds() {
    if (!timer_store.current_job_timer) {
        return 0;
    }
    return (
        Math.round((timer_store.current_job_timer.elapsed_hours || 0) * 3600) +
        timer_store._job_ticked_seconds
    );
}

/**
 * @param {Number} total_seconds
 * @returns {String}
 */
export function format_elapsed(total_seconds) {
    const total = Math.max(total_seconds, 0);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

/**
 * Fetches `shift_timer` (which now also carries `current_job` - see
 * `shopfloor_repair/services/repair_job.py`'s `_shift_timer_data`)
 * and updates both timers from it in one call. Used both by
 * `app_bar_actions.esm.js`'s own ~60s poll (the thing that keeps both timers
 * live regardless of which screen is open) and, once, by
 * `scenario/repair_job.esm.js`'s `timer_start`/`timer_stop` right after they succeed -
 * without that second call site, starting or stopping a job's timer
 * wouldn't show up in the app bar until the next scheduled poll, up to a
 * minute later.
 *
 * @param {Vue} vm
 * @returns {Promise<void>}
 */
export function refresh_shift_timer(vm) {
    const root = sf_root(vm);
    // Every call here needs a profile header; with none selected (just after
    // a login, or a logout that cleared it) the server answers 400 on every
    // poll, and the console fills up with failures that mean nothing. The
    // next poll after a profile is picked picks up where this skips.
    if (!root.has_profile) {
        return Promise.resolve();
    }
    // `shift_timer` inherits `base.shopfloor.process`, which requires both
    // a menu and a profile header on every call (see `menu_id_for`'s own
    // comment for why) - this can be called from widgets that render
    // outside any scenario route, so it always resolves its own menu id
    // rather than assuming one is available from `$route.params`.
    return root
        .getOdoo({
            usage: "repair_job",
            // Runs on a silent ~60s interval (app_bar_actions.esm.js) regardless
            // of which screen is open - without this, each poll trips the
            // app's global `fetchStart`/`fetchEnd` loading indicator
            // (shopfloor_mobile_base's fetch.js/main.esm.js), visible as a
            // once-a-minute flicker on every screen.
            in_background: true,
            headers: {
                "SERVICE-CTX-MENU-ID": String(menu_id_for(vm, "repair_job")),
                "SERVICE-CTX-PROFILE-ID": String(root.profile.id),
            },
        })
        .get("shift_timer")
        .then((/** @type {any} */ result) => {
            const shift_timer = result && result.data && result.data.shift_timer;
            if (shift_timer) {
                set_shift_timer(shift_timer);
                set_current_job_timer(shift_timer.current_job || null);
            }
        });
}
