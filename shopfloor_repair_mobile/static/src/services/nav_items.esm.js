/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The app's own list of "always reachable" destinations - My Jobs, My
 * Timesheets, Scan, Clock In/Out - shared between the drawer
 * (`nav_items_extra.esm.js`) and the full-page Home screen (`pages/home.esm.js`,
 * what the app-bar's own "Home" button opens) so both stay in sync from
 * one definition instead of two copies drifting apart.
 */
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {timer_store} from "./timer_store.esm.js";
import {menu_id_for} from "./root.esm.js";

translation_registry.add("en-US.repair.timesheets.title", "My Timesheets");
translation_registry.add("en-US.repair.clock.clock_in", "Clock In");
translation_registry.add("en-US.repair.clock.clock_out", "Clock Out");

/**
 * @typedef {Object} NavItem
 * @property {String} id
 * @property {String} name
 * @property {String} icon
 * @property {{name: string, params?: Record<string, unknown>}} to
 */

/**
 * @param {Vue} vm
 * @returns {NavItem[]}
 */
export function home_nav_items(vm) {
    const shift_timer = timer_store.shift_timer;
    return [
        {
            id: "my-jobs",
            name: vm.$t("repair.jobs.my_jobs"),
            icon: "mdi-format-list-checks",
            to: {
                name: "repair_job",
                // Mirrors the real `<nav-items>` entry's own `:to` binding
                // (shopfloor_mobile_base's screen.esm.js) exactly, since
                // this row navigates to the same place that one does.
                params: {menu_id: menu_id_for(vm, "repair_job"), state: "init"},
            },
        },
        {
            id: "my-timesheets",
            name: vm.$t("repair.timesheets.title"),
            icon: "mdi-clock-outline",
            to: {name: "timesheets"},
        },
        {
            id: "scan-anything",
            name: vm.$t("screen.scan_anything.title", {what: ""}),
            icon: "mdi-magnify",
            to: {name: "scan_anything"},
        },
        {
            id: "clock",
            name: shift_timer.running
                ? vm.$t("repair.clock.clock_out")
                : vm.$t("repair.clock.clock_in"),
            icon: shift_timer.running
                ? "mdi-clock-remove-outline"
                : "mdi-clock-check-outline",
            to: {name: "clock"},
        },
    ];
}
