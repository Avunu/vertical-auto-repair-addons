/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Correct one day's clock-in/out. Modeled directly on
 * repair_timesheet_edit_form.esm.js's local-state/save pattern, but a day
 * can have more than one clock-in/out pair (a lunch break, a correction -
 * confirmed by reading hr_attendance's own model: nothing prevents it), so
 * this renders one independent start/end row + Save per pair rather than a
 * single combined form - editing is always a real start/end correction on
 * a specific pair, never a guess at which segment an aggregate total came
 * from.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {AttendanceDay} from "./attendance_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {menu_id_for, sf_root} from "../services/root.esm.js";
import {
    local_input_to_server_datetime,
    server_datetime_to_local_input,
} from "../services/datetime.esm.js";

/**
 * @typedef {Object} EditableRow
 * @property {Number} id
 * @property {String} date_time
 * @property {String} date_time_end
 * @property {Boolean} saving
 */

// "2026-01-01 09:00:00" (server, UTC) <-> "2026-01-01T09:00" (local
// wall-clock, the format an <input type="datetime-local"> both requires
// and produces) - same real UTC<->local conversion
// repair_timesheet_edit_form.esm.js uses (see services/datetime.esm.js),
// kept identical on purpose so a time edited here and the same time edited
// there always agree.
/**
 * @param {string | null} value
 * @returns {String}
 */
function to_local_input(value) {
    return server_datetime_to_local_input(value);
}

/**
 * @param {String} value
 * @returns {string | null}
 */
function from_local_input(value) {
    return local_input_to_server_datetime(value);
}

const RepairAttendanceEditForm = defineComponent({
    props: {
        day: {type: /** @type {PropType<AttendanceDay>} */ (Object), required: true},
    },
    data() {
        return {
            rows: /** @type {EditableRow[]} */ (
                this.day.records.map((r) => ({
                    id: r.id,
                    date_time: to_local_input(r.check_in),
                    date_time_end: to_local_input(r.check_out),
                    saving: false,
                }))
            ),
            error_message: /** @type {string | null} */ (null),
        };
    },
    computed: {
        // Same weekday/month/day format `pages/timesheets.esm.js`'s own
        // `_format_date` uses for the card titles, so the dialog's title
        // reads as "which day is this" the same way the card it was opened
        // from already does - "Edit clock-in/out" said nothing about that.
        /** @returns {String} */
        title() {
            try {
                return new Date(this.day.date + "T00:00:00").toLocaleDateString(
                    undefined,
                    {
                        weekday: "short",
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                    }
                );
            } catch {
                return this.day.date;
            }
        },
    },
    methods: {
        /**
         * @param {EditableRow} row
         * @returns {Boolean}
         */
        row_valid(row) {
            return Boolean(
                row.date_time && row.date_time_end && row.date_time_end > row.date_time
            );
        },
        /**
         * @param {EditableRow} row
         * @returns {void}
         */
        save_row(row) {
            if (!this.row_valid(row)) {
                return;
            }
            row.saving = true;
            this.error_message = null;
            const root = sf_root(this);
            root.getOdoo({
                usage: "repair_timesheet",
                headers: {
                    "SERVICE-CTX-MENU-ID": String(menu_id_for(this, "repair_job")),
                    "SERVICE-CTX-PROFILE-ID": String(root.profile.id),
                },
            })
                .post(["attendance", row.id, "update"], {
                    date_time: from_local_input(row.date_time),
                    date_time_end: from_local_input(row.date_time_end),
                })
                .then((/** @type {any} */ result) => {
                    const day = result && result.data && result.data.attendance_day;
                    const message = result && result.message;
                    if (message && message.message_type === "error") {
                        this.error_message = message.body;
                        return;
                    }
                    if (day) {
                        this.$emit("saved", day);
                    }
                })
                .finally(() => {
                    row.saving = false;
                });
        },
    },
    template: html`
        <v-card class="repair-attendance-edit-form">
            <v-card-title>{{ title }}</v-card-title>
            <v-card-text>
                <v-alert v-if="error_message" type="error" dense>
                    {{ error_message }}
                </v-alert>
                <div v-for="row in rows" :key="row.id" class="attendance-row mb-4">
                    <v-text-field
                        type="datetime-local"
                        :label="$t('repair.timesheets.start')"
                        v-model="row.date_time"
                    />
                    <v-text-field
                        type="datetime-local"
                        :label="$t('repair.timesheets.end')"
                        v-model="row.date_time_end"
                    />
                    <v-btn
                        color="success"
                        block
                        :disabled="!row_valid(row)"
                        :loading="row.saving"
                        @click="save_row(row)"
                    >
                        {{ $t('btn.save.title') }}
                    </v-btn>
                </div>
            </v-card-text>
            <v-card-actions>
                <v-btn text @click="$emit('close')">{{ $t('btn.cancel.title') }}</v-btn>
            </v-card-actions>
        </v-card>
    `,
});

export default RepairAttendanceEditForm;

Vue.component("repair-attendance-edit-form", RepairAttendanceEditForm);
