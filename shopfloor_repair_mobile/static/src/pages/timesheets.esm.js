/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * "My Timesheets" - a flat, searchable, editable list of the technician's
 * own repair-job time entries, grouped into date sections (most recent
 * first). Registered as a standalone `page_registry` page (the pattern
 * `pages/profile.esm.js` already establishes), not a `process_registry`
 * scenario - there is no multi-step flow here, just list -> edit -> save.
 *
 * Each entry row carries four actions: Edit (job/service/times), Add break
 * (cut a gap out of the entry and the clocked day), Split (move the first or
 * last minutes to another job) and Delete. They all open one shared
 * `v-dialog` driven by `dialog` ({mode, record}); the forms themselves live
 * in `components/repair_timesheet_*_form.esm.js` and know nothing about REST -
 * this page does every `POST`.
 *
 * Each date's total is real clocked attendance (`hr.attendance`, the same
 * source the app-bar's "Shift" timer reads), not a sum of that day's job
 * timers - those are tracked separately and can disagree with actual
 * clocked time (breaks, gaps). Editing it means correcting the underlying
 * clock-in/out pair(s) via `repair_attendance_edit_form.esm.js`, not the
 * total itself.
 *
 * Tagged `"app_page"`, deliberately NOT `"settings"` - `settings/
 * settings.esm.js` filters its own page list via `page_registry.
 * by_tag("settings")`, so reusing that tag would make this page show up
 * inside Settings too.
 */
/** @import {OdooClient} from "../types/shopfloor-mobile-base" */
/** @import {AttendanceDay} from "../components/attendance_types" */
import {page_registry} from "/shopfloor_mobile_base/static/src/services/page_registry.esm.js";
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {menu_id_for, sf_root} from "../services/root.esm.js";
import {
    duration_hours,
    format_duration,
    format_time_of_day,
} from "../services/datetime.esm.js";

/**
 * @typedef {Object} TimesheetListEntry
 * @property {unknown} id
 * @property {String} [date]
 * @property {String} [date_time]
 * @property {String} [date_time_end]
 * @property {{id?: unknown, name: string}} job
 * @property {String} [job_ref] the repair order number ("WH/RO/00011")
 * @property {{id?: unknown, name: string}} [service]
 */

/**
 * One line of a day's table: a job entry, or a break between two clocked
 * periods. `date_time`/`date_time_end` are server strings for both kinds, so
 * they sort and format the same way.
 *
 * @typedef {Object} TimesheetRow
 * @property {String} key
 * @property {"entry" | "break"} kind
 * @property {String} date_time
 * @property {string | null} date_time_end
 * @property {TimesheetListEntry} [rec] present on `entry` rows only
 * @property {"attendance" | "jobs"} [source] `break` rows: where the break was read from -
 *     the gap between two clocked periods, or the gap between two parts of one job
 * @property {Number} [attendance_id] `attendance` breaks: the clocked period the break follows
 * @property {Number} [before_id] `jobs` breaks: the timesheet entry before the gap
 * @property {Number} [after_id] `jobs` breaks: the timesheet entry after it
 * @property {String} [lower] `break` rows: when the earlier period/part began - the break must start after it
 * @property {string | null} [upper] `break` rows: when the later one ends (null while an attendance period is open) - the break must end before it
 */

/**
 * @typedef {Object} TimesheetGroup
 * @property {String} key
 * @property {String} title
 * @property {TimesheetListEntry[]} records
 * @property {AttendanceDay | null} attendance
 * @property {Number} job_hours sum of the day's job entries - all of them,
 *     not just this page's (the server totals it)
 * @property {TimesheetRow[]} rows entries and breaks, latest first
 */

/**
 * @typedef {Object} ErrorMessage
 * @property {String} body
 * @property {String} message_type
 */

/**
 * @typedef {Object} TimesheetDialog
 * @property {"edit" | "split" | "break" | "delete" | "edit_break" | "delete_break"} mode
 * @property {any} record `edit`/`split`: the detail record (it carries the
 *     `jobs` to choose from); `break`/`delete`: the list entry itself;
 *     `edit_break`/`delete_break`: the break row.
 */

const MyTimesheets = defineComponent({
    data() {
        return {
            records: /** @type {TimesheetListEntry[]} */ ([]),
            attendance: /** @type {AttendanceDay[]} */ ([]),
            job_hours: /** @type {{date: string, hours: number}[]} */ ([]),
            size: 0,
            page: 1,
            page_size: 20,
            search: /** @type {string | null} */ (null),
            dialog: /** @type {TimesheetDialog | null} */ (null),
            attendance_detail: /** @type {AttendanceDay | null} */ (null),
            loading: false,
            error_message: /** @type {ErrorMessage | null} */ (null),
        };
    },
    computed: {
        /** @returns {{title: string, user_message: ErrorMessage | null}} */
        screen_info() {
            return {
                title: this.$t("repair.timesheets.title"),
                user_message: this.error_message,
            };
        },
        /** @returns {OdooClient} */
        odoo() {
            const root = sf_root(this);
            // `repair_timesheet` inherits `base.shopfloor.process` too, so it
            // also 400s without a menu header - but unlike `repair_job` it has
            // no `shopfloor.menu` entry of its own (this page isn't reachable
            // from the drawer's own menu list). The header validation
            // (shopfloor_base/services/service.py `_work_ctx_get_menu_id`)
            // only needs *some* existing menu record id, not one matching this
            // usage, so "repair_job" - the app's one real menu - is used here
            // too. See services/root.esm.js's `menu_id_for` for the general
            // case.
            return root.getOdoo({
                usage: "repair_timesheet",
                headers: {
                    "SERVICE-CTX-MENU-ID": String(menu_id_for(this, "repair_job")),
                    "SERVICE-CTX-PROFILE-ID": String(root.profile.id),
                },
            });
        },
        // `records` already arrive ordered `date_time desc` from the server,
        // so grouping in encounter order keeps both the sections and the
        // entries within each section most-recent-first with no extra
        // sorting needed here.
        /** @returns {TimesheetGroup[]} */
        grouped() {
            /** @type {TimesheetGroup[]} */
            const groups = [];
            /** @type {Record<string, TimesheetGroup>} */
            const by_date = {};
            _.each(this.records, (/** @type {TimesheetListEntry} */ rec) => {
                const key = rec.date || (rec.date_time || "").slice(0, 10);
                if (!by_date[key]) {
                    by_date[key] = {
                        key: key,
                        title: this._format_date(key),
                        records: [],
                        attendance: this.attendance.find((a) => a.date === key) || null,
                        job_hours: (
                            this.job_hours.find((j) => j.date === key) || {hours: 0}
                        ).hours,
                        rows: [],
                    };
                    groups.push(by_date[key]);
                }
                by_date[key].records.push(rec);
            });
            _.each(groups, (/** @type {TimesheetGroup} */ group) => {
                group.rows = this._rows_for(group);
            });
            return groups;
        },
    },
    mounted() {
        this.fetch(1);
    },
    methods: {
        // A break is the time between one clocked-in period and the next on
        // the same day (what "Add break" creates - it clocks the technician out
        // and back in - but also a real lunch punch-out). It has no timesheet
        // entry of its own, so it is read off the day's attendance and mixed
        // in with the job entries, latest first like the rest of the list.
        /**
         * @param {TimesheetGroup} group
         * @returns {TimesheetRow[]}
         */
        _rows_for(group) {
            /** @type {TimesheetRow[]} */
            const rows = group.records.map((rec) => ({
                key: "entry-" + rec.id,
                kind: /** @type {"entry"} */ ("entry"),
                date_time: rec.date_time || "",
                date_time_end: rec.date_time_end || null,
                rec: rec,
            }));
            const periods = group.attendance
                ? group.attendance.records
                      .slice()
                      .sort((a, b) => (a.check_in < b.check_in ? -1 : 1))
                : [];
            for (let i = 0; i < periods.length - 1; i++) {
                const left_at = periods[i].check_out;
                const back_at = periods[i + 1].check_in;
                // Under a minute is a punch correction, not a break.
                if (left_at && duration_hours(left_at, back_at) >= 1 / 60) {
                    rows.push({
                        key: "break-" + periods[i].id,
                        kind: "break",
                        source: "attendance",
                        date_time: left_at,
                        date_time_end: back_at,
                        attendance_id: periods[i].id,
                        lower: periods[i].check_in,
                        upper: periods[i + 1].check_out,
                    });
                }
            }
            rows.push(...this._job_breaks(group, rows));
            // "YYYY-MM-DD HH:MM:SS" strings sort chronologically as plain text.
            rows.sort((a, b) => (a.date_time < b.date_time ? 1 : -1));
            return rows;
        },
        // Where nothing is clocked there is no clock-out/in gap to show, so the
        // break is the gap between two entries on the *same job and service* -
        // exactly what "Add break" leaves behind (and what stopping a timer and
        // starting it again does). It only counts as a break when nothing else
        // was worked in the gap: job A, then job B, then job A again is not a
        // break on A. And a gap already shown as a clock-out/in break isn't
        // shown twice.
        /**
         * @param {TimesheetGroup} group
         * @param {TimesheetRow[]} shown rows built so far (entries and clocked breaks)
         * @returns {TimesheetRow[]}
         */
        _job_breaks(group, shown) {
            /** @type {TimesheetRow[]} */
            const breaks = [];
            const finished = group.records.filter(
                (rec) => rec.date_time && rec.date_time_end
            );
            /** @type {Record<string, TimesheetListEntry[]>} */
            const by_part = {};
            _.each(finished, (/** @type {TimesheetListEntry} */ rec) => {
                const key = `${rec.job && rec.job.id}|${rec.service ? rec.service.id : ""}`;
                (by_part[key] = by_part[key] || []).push(rec);
            });
            _.each(by_part, (/** @type {TimesheetListEntry[]} */ parts) => {
                parts.sort((a, b) =>
                    (a.date_time || "") < (b.date_time || "") ? -1 : 1
                );
                for (let i = 0; i < parts.length - 1; i++) {
                    const before = parts[i];
                    const after = parts[i + 1];
                    const gap_start = /** @type {String} */ (before.date_time_end);
                    const gap_end = /** @type {String} */ (after.date_time);
                    // Under a minute is rounding, not a break.
                    if (duration_hours(gap_start, gap_end) < 1 / 60) {
                        continue;
                    }
                    const worked_in_gap = finished.some(
                        (rec) =>
                            rec !== before &&
                            rec !== after &&
                            /** @type {String} */ (rec.date_time) < gap_end &&
                            /** @type {String} */ (rec.date_time_end) > gap_start
                    );
                    const already_shown = shown.some(
                        (row) =>
                            row.kind === "break" &&
                            row.date_time < gap_end &&
                            /** @type {String} */ (row.date_time_end) > gap_start
                    );
                    if (worked_in_gap || already_shown) {
                        continue;
                    }
                    breaks.push({
                        key: "break-jobs-" + before.id,
                        kind: "break",
                        source: "jobs",
                        date_time: gap_start,
                        date_time_end: gap_end,
                        before_id: /** @type {Number} */ (before.id),
                        after_id: /** @type {Number} */ (after.id),
                        lower: before.date_time,
                        upper: after.date_time_end,
                    });
                }
            });
            return breaks;
        },
        /**
         * @param {String} iso_date
         * @returns {String}
         */
        _format_date(iso_date) {
            try {
                return new Date(iso_date + "T00:00:00").toLocaleDateString(undefined, {
                    weekday: "short",
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                });
            } catch {
                return iso_date;
            }
        },
        /**
         * @param {Number} hours
         * @returns {String}
         */
        format_duration(hours) {
            return format_duration(hours);
        },
        /**
         * @param {string | undefined} value
         * @returns {String}
         */
        time_of_day(value) {
            return format_time_of_day(value);
        },
        // Second line under the vehicle: order number first (two open orders
        // on one vehicle share a description), then the service the time is
        // booked to.
        /**
         * @param {TimesheetListEntry} rec
         * @returns {String}
         */
        job_detail(rec) {
            const service = rec.service
                ? rec.service.name
                : this.$t("repair.timesheets.no_service");
            return [rec.job_ref, service].filter((part) => part).join(" · ");
        },
        // A running entry has no end yet, so no meaningful total.
        /**
         * @param {{date_time?: string | null, date_time_end?: string | null}} rec
         * @returns {String}
         */
        entry_total(rec) {
            return rec.date_time_end
                ? format_duration(
                      duration_hours(rec.date_time || undefined, rec.date_time_end)
                  )
                : "—";
        },
        /**
         * @param {Number} [page]
         * @returns {Promise<void>}
         */
        fetch(page) {
            /** @type {Record<string, unknown>} */
            const params = {page: page || this.page};
            if (this.search) {
                params.search = this.search;
            }
            this.loading = true;
            return this.odoo
                .get("timesheets", params)
                .then((/** @type {any} */ result) => {
                    const data = (result.data || {}).timesheets || {};
                    this.records = data.records || [];
                    this.attendance = data.attendance_by_date || [];
                    this.job_hours = data.job_hours_by_date || [];
                    this.size = data.size || 0;
                    this.page = data.page || 1;
                    this.page_size = data.page_size || this.page_size;
                })
                .finally(() => {
                    this.loading = false;
                });
        },
        /**
         * @param {{text?: string}} found
         * @returns {void}
         */
        on_search(found) {
            this.search = found.text || null;
            this.fetch(1);
        },
        // Edit and Split need the job choices (and each job's services),
        // which only the detail endpoint returns, so they fetch the full
        // record first; the other actions are fully described by the row.
        /**
         * @param {"edit" | "split" | "break" | "delete" | "edit_break" | "delete_break"} mode
         * @param {TimesheetListEntry | TimesheetRow} rec
         * @returns {void}
         */
        open_action(mode, rec) {
            this.error_message = null;
            if (mode !== "edit" && mode !== "split") {
                this.dialog = {mode: mode, record: rec};
                return;
            }
            this.odoo
                .get(["timesheet", /** @type {TimesheetListEntry} */ (rec).id])
                .then((/** @type {any} */ result) => {
                    const detail = (result.data || {}).timesheet || null;
                    this.dialog = detail ? {mode: mode, record: detail} : null;
                })
                .catch(() => this._request_failed());
        },
        /** @returns {void} */
        close_dialog() {
            this.dialog = null;
            this.error_message = null;
        },
        // The base REST client calls `response.json()` on every non-2xx answer
        // and throws if the body is an HTML page (Odoo's own 404 for a URL it
        // doesn't know, a 401 login redirect, a proxy error). That reaches us
        // as a *rejected* promise rather than the `{error}` result handled
        // below, and without this the technician saw the dialog dim and come
        // back with nothing changed and no explanation.
        /** @returns {void} */
        _request_failed() {
            this.error_message = {
                body: this.$t("repair.timesheets.request_failed"),
                message_type: "error",
            };
        },
        // `OdooClient._call` (shopfloor_mobile_base's odoo.esm.js) resolves -
        // never rejects - on a non-2xx HTTP response, returning `{error: ...}`
        // instead of `{message: ...}`. Checking only `result.message` let a
        // raw backend error (e.g. an `unlink()` raising `UserError`) fall
        // through as if it were a success, closing the dialog and refetching
        // a list that still had the un-deleted/un-changed row in it. Shaped
        // like `mixins.esm.js`'s own `display_app_error` (status/name/
        // description) since that's this codebase's existing convention for
        // a raw REST error, not the `{message_type, ...}` shape the backend's
        // own `msg_store` responses use.
        /**
         * @param {{status?: unknown, name?: unknown, description?: string}} error
         * @returns {ErrorMessage}
         */
        _error_message_from_raw(error) {
            const parts = [error.status, error.name].filter((part) => part);
            if (error.description) {
                parts.push(error.description);
            }
            return {
                body: parts.join(" ") || this.$t("repair.timesheets.unknown_error"),
                message_type: "error",
            };
        },
        // One endpoint per dialog mode; every one of them is a POST, and every
        // one answers in the same `{error | message}` shape, so a single
        // `submit_dialog` handles them all.
        /**
         * @param {TimesheetDialog} dialog
         * @returns {unknown[]}
         */
        _endpoint_for(dialog) {
            // A break isn't a timesheet entry: it is addressed through the
            // clocked period it follows.
            if (dialog.mode === "edit_break" || dialog.mode === "delete_break") {
                const edit = dialog.mode === "edit_break";
                if (dialog.record.source === "jobs") {
                    return [
                        "timesheet",
                        dialog.record.before_id,
                        edit ? "update_job_break" : "delete_job_break",
                    ];
                }
                return [
                    "attendance",
                    dialog.record.attendance_id,
                    edit ? "update_break" : "delete_break",
                ];
            }
            const action = {
                edit: "update",
                split: "split",
                break: "add_break",
                delete: "delete",
            }[dialog.mode];
            return ["timesheet", dialog.record.id, action];
        },
        /**
         * @param {Record<string, unknown>} [payload]
         * @returns {void}
         */
        submit_dialog(payload) {
            const dialog = /** @type {TimesheetDialog} */ (this.dialog);
            // A job-gap break is addressed by the entry before it; the entry
            // after it travels in the body.
            const body = _.extend(
                {},
                payload,
                dialog.record.source === "jobs"
                    ? {after_id: dialog.record.after_id}
                    : {}
            );
            this.odoo
                .post(this._endpoint_for(dialog), body)
                .then((/** @type {any} */ result) => {
                    if (result.error) {
                        this.error_message = this._error_message_from_raw(result.error);
                        return;
                    }
                    const message = result.message;
                    if (message && message.message_type === "error") {
                        // Keep the dialog open (with its current edits) so the
                        // technician can adjust - an overlapping time, a break
                        // outside the clocked period - and retry, rather than
                        // losing the input on a rejection.
                        const detail = (result.data || {}).timesheet;
                        if (detail && dialog.mode === "edit") {
                            this.dialog = {mode: dialog.mode, record: detail};
                        }
                        this.error_message = message;
                        return;
                    }
                    // A plain "done" needs no banner - the list refreshing is the
                    // confirmation. Anything else (e.g. "No clock-in is recorded
                    // for that time, so the day's total didn't change") explains
                    // something the technician couldn't otherwise see, so it
                    // stays at the top of the page after the dialog closes.
                    this.error_message =
                        message && message.message_type !== "success" ? message : null;
                    this.dialog = null;
                    this.fetch(this.page);
                })
                .catch(() => this._request_failed());
        },
        /**
         * @param {TimesheetGroup} group
         * @returns {Boolean}
         */
        is_attendance_editable(group) {
            return Boolean(group.attendance && group.attendance.records.length);
        },
        /**
         * @param {TimesheetGroup} group
         * @returns {void}
         */
        open_attendance(group) {
            if (!this.is_attendance_editable(group)) {
                return;
            }
            this.attendance_detail = group.attendance;
        },
        /** @returns {void} */
        close_attendance() {
            this.attendance_detail = null;
        },
        /**
         * @param {AttendanceDay} updated
         * @returns {void}
         */
        on_attendance_saved(updated) {
            const idx = this.attendance.findIndex((a) => a.date === updated.date);
            if (idx >= 0) {
                this.attendance.splice(idx, 1, updated);
            } else {
                this.attendance.push(updated);
            }
            this.attendance_detail = updated;
        },
    },
    template: html`
        <Screen :screen_info="screen_info">
            <searchbar
                :autofocus="false"
                v-on:found="on_search"
                :input_placeholder="$t('repair.timesheets.search_placeholder')"
            />
            <p class="empty" v-if="!loading && !records.length">
                {{ $t('repair.timesheets.empty') }}
            </p>
            <!-- One table for the whole page, like a spreadsheet: a single header
                 row, then for each day a band (date + clocked total) followed
                 by one row per entry. The band is tappable to correct that
                 day's clock-in/out. Rows carry only what a technician needs to
                 find an entry - plate, order number, service, times, length. -->
            <v-card v-if="grouped.length" outlined class="timesheet-table">
                <div class="timesheet-row timesheet-row--head">
                    <span>{{ $t('repair.timesheets.job') }}</span>
                    <span>{{ $t('repair.timesheets.start') }}</span>
                    <span>{{ $t('repair.timesheets.end') }}</span>
                    <span class="timesheet-row__num"
                        >{{ $t('repair.timesheets.duration') }}</span
                    >
                    <span></span>
                </div>
                <template v-for="group in grouped">
                    <div
                        :key="'day-' + group.key"
                        class="timesheet-day"
                        :class="{'timesheet-day--editable': is_attendance_editable(group)}"
                        @click="open_attendance(group)"
                    >
                        <span class="timesheet-day__date">{{ group.title }}</span>
                        <span class="timesheet-day__totals">
                            <span class="timesheet-day__total">
                                {{ $t('repair.timesheets.shift_time') }}
                                <strong
                                    >{{ format_duration(group.attendance ?
                                    group.attendance.hours : 0) }}</strong
                                >
                            </span>
                            <span class="timesheet-day__total">
                                {{ $t('repair.timesheets.job_time') }}
                                <strong>{{ format_duration(group.job_hours) }}</strong>
                            </span>
                        </span>
                    </div>
                    <div
                        v-for="row in group.rows"
                        :key="row.key"
                        class="timesheet-row"
                        :class="{'timesheet-row--break': row.kind === 'break'}"
                    >
                        <template v-if="row.kind === 'break'">
                            <div class="timesheet-row__job">
                                <span class="timesheet-row__plate"
                                    >{{ $t('repair.timesheets.break') }}</span
                                >
                            </div>
                            <span>{{ time_of_day(row.date_time) }}</span>
                            <span>{{ time_of_day(row.date_time_end) }}</span>
                            <span class="timesheet-row__num timesheet-row__duration"
                                >{{ entry_total(row) }}</span
                            >
                            <span class="timesheet-row__actions">
                                <v-menu left offset-y>
                                    <template v-slot:activator="{on, attrs}">
                                        <v-btn
                                            icon
                                            v-bind="attrs"
                                            v-on="on"
                                            :title="$t('repair.timesheets.actions')"
                                        >
                                            <v-icon>mdi-dots-vertical</v-icon>
                                        </v-btn>
                                    </template>
                                    <v-list>
                                        <v-list-item
                                            @click="open_action('edit_break', row)"
                                        >
                                            <v-list-item-icon
                                                ><v-icon
                                                    >mdi-pencil</v-icon
                                                ></v-list-item-icon
                                            >
                                            <v-list-item-title
                                                >{{ $t('repair.timesheets.action.edit')
                                                }}</v-list-item-title
                                            >
                                        </v-list-item>
                                        <v-list-item
                                            class="error--text"
                                            @click="open_action('delete_break', row)"
                                        >
                                            <v-list-item-icon
                                                ><v-icon color="error"
                                                    >mdi-delete</v-icon
                                                ></v-list-item-icon
                                            >
                                            <v-list-item-title
                                                >{{
                                                $t('repair.timesheets.action.delete')
                                                }}</v-list-item-title
                                            >
                                        </v-list-item>
                                    </v-list>
                                </v-menu>
                            </span>
                        </template>
                        <template v-else>
                            <div class="timesheet-row__job">
                                <span class="timesheet-row__plate"
                                    >{{ row.rec.job.name }}</span
                                >
                                <span class="timesheet-row__sub"
                                    >{{ job_detail(row.rec) }}</span
                                >
                            </div>
                            <span>{{ time_of_day(row.rec.date_time) }}</span>
                            <span>
                                <v-chip
                                    v-if="!row.rec.date_time_end"
                                    small
                                    label
                                    color="success"
                                >
                                    {{ $t('repair.timesheets.running') }}
                                </v-chip>
                                <template v-else
                                    >{{ time_of_day(row.rec.date_time_end) }}</template
                                >
                            </span>
                            <span class="timesheet-row__num timesheet-row__duration"
                                >{{ entry_total(row.rec) }}</span
                            >
                            <span class="timesheet-row__actions">
                                <v-menu left offset-y>
                                    <template v-slot:activator="{on, attrs}">
                                        <v-btn
                                            icon
                                            v-bind="attrs"
                                            v-on="on"
                                            :title="$t('repair.timesheets.actions')"
                                        >
                                            <v-icon>mdi-dots-vertical</v-icon>
                                        </v-btn>
                                    </template>
                                    <v-list>
                                        <v-list-item
                                            @click="open_action('edit', row.rec)"
                                        >
                                            <v-list-item-icon
                                                ><v-icon
                                                    >mdi-pencil</v-icon
                                                ></v-list-item-icon
                                            >
                                            <v-list-item-title
                                                >{{ $t('repair.timesheets.action.edit')
                                                }}</v-list-item-title
                                            >
                                        </v-list-item>
                                        <v-list-item
                                            :disabled="!row.rec.date_time_end"
                                            @click="open_action('break', row.rec)"
                                        >
                                            <v-list-item-icon
                                                ><v-icon
                                                    >mdi-coffee</v-icon
                                                ></v-list-item-icon
                                            >
                                            <v-list-item-title
                                                >{{ $t('repair.timesheets.action.break')
                                                }}</v-list-item-title
                                            >
                                        </v-list-item>
                                        <v-list-item
                                            :disabled="!row.rec.date_time_end"
                                            @click="open_action('split', row.rec)"
                                        >
                                            <v-list-item-icon
                                                ><v-icon
                                                    >mdi-call-split</v-icon
                                                ></v-list-item-icon
                                            >
                                            <v-list-item-title
                                                >{{ $t('repair.timesheets.action.split')
                                                }}</v-list-item-title
                                            >
                                        </v-list-item>
                                        <v-list-item
                                            class="error--text"
                                            @click="open_action('delete', row.rec)"
                                        >
                                            <v-list-item-icon
                                                ><v-icon color="error"
                                                    >mdi-delete</v-icon
                                                ></v-list-item-icon
                                            >
                                            <v-list-item-title
                                                >{{
                                                $t('repair.timesheets.action.delete')
                                                }}</v-list-item-title
                                            >
                                        </v-list-item>
                                    </v-list>
                                </v-menu>
                            </span>
                        </template>
                    </div>
                </template>
            </v-card>
            <div
                class="button-list button-vertical-list full"
                v-if="page * page_size < size || page > 1"
            >
                <v-row align="center">
                    <v-col cols="6">
                        <v-btn block :disabled="page <= 1" @click="fetch(page - 1)">
                            {{ $t('repair.timesheets.prev_page') }}
                        </v-btn>
                    </v-col>
                    <v-col cols="6">
                        <v-btn
                            block
                            :disabled="page * page_size >= size"
                            @click="fetch(page + 1)"
                        >
                            {{ $t('repair.timesheets.next_page') }}
                        </v-btn>
                    </v-col>
                </v-row>
            </div>
            <v-dialog
                :value="Boolean(dialog)"
                max-width="480"
                scrollable
                @input="close_dialog"
            >
                <div v-if="dialog" class="timesheet-dialog">
                    <!-- The page's own error banner sits behind the dimmed screen,
                         so a rejected save would look like nothing happened. -->
                    <v-alert v-if="error_message" type="error" tile dense class="mb-0">
                        {{ error_message.body }}
                    </v-alert>
                    <repair-timesheet-edit-form
                        v-if="dialog && dialog.mode === 'edit'"
                        :record="dialog.record"
                        :key="make_component_key(['timesheet', 'edit', dialog.record.id])"
                        v-on:save="submit_dialog"
                        v-on:close="close_dialog"
                    />
                    <repair-timesheet-split-form
                        v-else-if="dialog && dialog.mode === 'split'"
                        :record="dialog.record"
                        :key="make_component_key(['timesheet', 'split', dialog.record.id])"
                        v-on:save="submit_dialog"
                        v-on:close="close_dialog"
                    />
                    <repair-timesheet-break-form
                        v-else-if="dialog && dialog.mode === 'break'"
                        :record="dialog.record"
                        :key="make_component_key(['timesheet', 'break', dialog.record.id])"
                        v-on:save="submit_dialog"
                        v-on:close="close_dialog"
                    />
                    <repair-break-edit-form
                        v-else-if="dialog && dialog.mode === 'edit_break'"
                        :record="dialog.record"
                        :key="make_component_key(['break', 'edit', dialog.record.key])"
                        v-on:save="submit_dialog"
                        v-on:close="close_dialog"
                    />
                    <v-card v-else-if="dialog && dialog.mode === 'delete_break'">
                        <v-card-title
                            >{{ $t('repair.timesheets.delete_break_title')
                            }}</v-card-title
                        >
                        <v-card-text>
                            <p>
                                {{ dialog.record.source === 'jobs' ?
                                $t('repair.timesheets.confirm_delete_job_break') :
                                $t('repair.timesheets.confirm_delete_break') }}
                            </p>
                            <strong>
                                {{ time_of_day(dialog.record.date_time) }} – {{
                                time_of_day(dialog.record.date_time_end) }} ({{
                                entry_total(dialog.record) }})
                            </strong>
                        </v-card-text>
                        <v-card-actions>
                            <v-spacer />
                            <v-btn text @click="close_dialog"
                                >{{ $t('btn.cancel.title') }}</v-btn
                            >
                            <v-btn color="error" @click="submit_dialog()"
                                >{{ $t('btn.delete.title') }}</v-btn
                            >
                        </v-card-actions>
                    </v-card>
                    <v-card v-else-if="dialog && dialog.mode === 'delete'">
                        <v-card-title
                            >{{ $t('repair.timesheets.delete_title') }}</v-card-title
                        >
                        <v-card-text>
                            <p>{{ $t('repair.timesheets.confirm_delete') }}</p>
                            <strong>
                                {{ dialog.record.job.name }}: {{
                                time_of_day(dialog.record.date_time) }} – {{
                                dialog.record.date_time_end ?
                                time_of_day(dialog.record.date_time_end) :
                                $t('repair.timesheets.running') }} ({{
                                entry_total(dialog.record) }})
                            </strong>
                        </v-card-text>
                        <v-card-actions>
                            <v-spacer />
                            <v-btn text @click="close_dialog"
                                >{{ $t('btn.cancel.title') }}</v-btn
                            >
                            <v-btn color="error" @click="submit_dialog()"
                                >{{ $t('btn.delete.title') }}</v-btn
                            >
                        </v-card-actions>
                    </v-card>
                </div>
            </v-dialog>
            <v-dialog
                :value="Boolean(attendance_detail)"
                max-width="480"
                @input="close_attendance"
            >
                <repair-attendance-edit-form
                    v-if="attendance_detail"
                    :day="attendance_detail"
                    :key="make_component_key(['attendance', attendance_detail.date])"
                    v-on:saved="on_attendance_saved"
                    v-on:close="close_attendance"
                />
            </v-dialog>
            <div class="button-list button-vertical-list full">
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-back />
                    </v-col>
                </v-row>
            </div>
        </Screen>
    `,
});

export default MyTimesheets;

page_registry.add(
    "timesheets",
    MyTimesheets,
    {},
    {
        tag: "app_page",
    }
);

/** @type {Record<string, string>} */
const T = {
    "repair.timesheets.title": "My Timesheets",
    "repair.timesheets.search_placeholder": "Search job or date",
    "repair.timesheets.empty": "No timesheets found.",
    "repair.timesheets.start": "Start",
    "repair.timesheets.end": "End",
    "repair.timesheets.total": "Total",
    "repair.timesheets.running": "Running",
    "repair.timesheets.no_service": "Unassigned",
    "repair.timesheets.unknown_error": "Something went wrong. Please try again.",
    "repair.timesheets.prev_page": "Previous",
    "repair.timesheets.next_page": "Next",
    "repair.timesheets.break": "Break",
    "repair.timesheets.request_failed":
        "That didn't work - the server didn't recognise the request. Please try again, and tell an administrator if it keeps happening.",
    "repair.timesheets.duration": "Duration",
    "repair.timesheets.shift_time": "Shift Time",
    "repair.timesheets.job_time": "Job Time",
    "repair.timesheets.actions": "Actions",
    "repair.timesheets.action.edit": "Edit",
    "repair.timesheets.action.break": "Add break",
    "repair.timesheets.action.split": "Split",
    "repair.timesheets.action.delete": "Delete",
    "repair.timesheets.delete_title": "Delete timesheet",
    "repair.timesheets.confirm_delete": "Delete this timesheet entry?",
    "repair.timesheets.delete_break_title": "Delete break",
    "repair.timesheets.confirm_delete_break":
        "Remove this break? The time will count as clocked in.",
    "repair.timesheets.confirm_delete_job_break":
        "Remove this break? The two parts of the timesheet will be joined into one, so this time counts as work.",
    "btn.delete.title": "Delete",
};
_.each(T, (/** @type {String} */ value, /** @type {String} */ key) => {
    translation_registry.add("en-US." + key, value);
});
