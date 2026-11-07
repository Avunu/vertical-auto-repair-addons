/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Edit a timesheet's job, service, start time and end time.
 *
 * Modeled on repair_inspection_line_form.esm.js's established local
 * pattern: local state seeded from the record, a watcher on `record.id` to
 * reset local state whenever a different record is opened, and a `save`
 * event carrying just the edited payload up to the page, which does the
 * actual `POST` - this component knows nothing about the REST call itself.
 *
 * Start/end use plain `<v-text-field type="datetime-local">` rather than a
 * new picker component: the base framework's own `date_picker.esm.js` only
 * handles a date, not time-of-day, and native `datetime-local` inputs work
 * fine on iPad Safari, this app's actual target device.
 *
 * Deleting is no longer done from here - each row on the timesheets page
 * has its own Delete action (with its own confirm dialog).
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {TimesheetRecord, JobPickerValue} from "./timesheet_types" */
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {
    format_duration,
    local_input_duration_hours,
    local_input_to_server_datetime,
    server_datetime_to_local_input,
} from "../services/datetime.esm.js";

translation_registry.add("en-US.repair.timesheets.edit_title", "Edit timesheet");
translation_registry.add("en-US.repair.timesheets.start", "Start time");
translation_registry.add("en-US.repair.timesheets.end", "End time");
translation_registry.add("en-US.btn.save.title", "Save");

/**
 * @param {TimesheetRecord} record
 * @returns {JobPickerValue}
 */
function pick_from_record(record) {
    return {
        job_id: /** @type {number | null} */ (record.job ? record.job.id : null),
        service_id: /** @type {number | null} */ (
            record.service ? record.service.id : null
        ),
    };
}

const RepairTimesheetEditForm = defineComponent({
    props: {
        record: {
            type: /** @type {PropType<TimesheetRecord>} */ (Object),
            required: true,
        },
    },
    data() {
        return {
            pick: /** @type {JobPickerValue} */ (pick_from_record(this.record)),
            date_time: server_datetime_to_local_input(this.record.date_time),
            date_time_end: server_datetime_to_local_input(this.record.date_time_end),
        };
    },
    computed: {
        /** @returns {Boolean} */
        valid() {
            return Boolean(
                this.pick.job_id &&
                    this.date_time &&
                    this.date_time_end &&
                    this.date_time_end > this.date_time
            );
        },
        // Recomputed on every keystroke/pick in either field, so the
        // technician sees what the entry will add up to before saving.
        /** @returns {String} */
        total() {
            if (
                !this.date_time ||
                !this.date_time_end ||
                this.date_time_end <= this.date_time
            ) {
                return "—";
            }
            return format_duration(
                local_input_duration_hours(this.date_time, this.date_time_end)
            );
        },
    },
    watch: {
        "record.id": "on_record_change",
    },
    methods: {
        /** @returns {void} */
        on_record_change() {
            this.pick = pick_from_record(this.record);
            this.date_time = this._to_local_input(this.record.date_time);
            this.date_time_end = this._to_local_input(this.record.date_time_end);
        },
        // "2026-01-01 09:00:00" (server, UTC) <-> "2026-01-01T09:00" (local
        // wall-clock, the format an <input type="datetime-local"> both
        // requires and produces) - see services/datetime.esm.js for why this
        // needs a real UTC<->local conversion rather than a plain string
        // splice.
        /**
         * @param {string | null} value
         * @returns {String}
         */
        _to_local_input(value) {
            return server_datetime_to_local_input(value);
        },
        /**
         * @param {String} value
         * @returns {string | null}
         */
        _from_local_input(value) {
            return local_input_to_server_datetime(value);
        },
        /** @returns {void} */
        save() {
            if (!this.valid) {
                return;
            }
            this.$emit("save", {
                job_id: this.pick.job_id,
                service_id: this.pick.service_id,
                date_time: this._from_local_input(this.date_time),
                date_time_end: this._from_local_input(this.date_time_end),
            });
        },
    },
    template: html`
        <v-card class="repair-timesheet-edit-form">
            <v-card-title>{{ $t('repair.timesheets.edit_title') }}</v-card-title>
            <v-card-text>
                <repair-job-picker :jobs="record.jobs" v-model="pick" />
                <v-text-field
                    type="datetime-local"
                    :label="$t('repair.timesheets.start')"
                    v-model="date_time"
                />
                <v-text-field
                    type="datetime-local"
                    :label="$t('repair.timesheets.end')"
                    v-model="date_time_end"
                />
                <div class="repair-timesheet-total">
                    <span>{{ $t('repair.timesheets.total') }}</span>
                    <strong>{{ total }}</strong>
                </div>
            </v-card-text>
            <v-card-actions>
                <v-spacer />
                <v-btn text @click="$emit('close')">{{ $t('btn.cancel.title') }}</v-btn>
                <v-btn color="success" :disabled="!valid" @click="save">
                    {{ $t('btn.save.title') }}
                </v-btn>
            </v-card-actions>
        </v-card>
    `,
});

export default RepairTimesheetEditForm;

Vue.component("repair-timesheet-edit-form", RepairTimesheetEditForm);
