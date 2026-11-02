/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Move part of a timesheet to another job (and service): choose the job, then
 * the start and end of the part to move - the same two fields as everywhere
 * else on this page, with the total worked out underneath. The part can touch
 * either end of the entry or sit in the middle. The backend
 * (`split_timesheet`) shrinks this entry, creates a new one for the moved part
 * and, for a part in the middle, another for the time after it, so they still
 * add up to exactly the original time.
 *
 * `record` is the full detail record (it carries the `jobs` the picker needs,
 * which the plain list entries don't) - the page fetches it before opening
 * this dialog, the same way it does for the Edit dialog.
 */
/** @import {PropType} from "vue" */
/** @import {TimesheetRecord, JobPickerValue} from "./timesheet_types" */
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {
    server_datetime_to_date,
    local_input_to_date,
    date_to_local_input,
    date_to_server_datetime,
    format_clock,
    format_duration,
} from "../services/datetime.esm.js";

translation_registry.add("en-US.repair.timesheets.split_title", "Split timesheet");
translation_registry.add("en-US.repair.timesheets.split_hint", "Move this part of the timesheet to the job above");
translation_registry.add("en-US.repair.timesheets.split_invalid", "Choose a part inside the timesheet, but not all of it.");

/**
 * A `datetime-local` field only holds whole minutes, while an entry's own
 * start/end usually carry seconds (timers stamp to the second). When the field
 * still shows the entry's own start or end, use the exact value - otherwise a
 * part that visibly runs "to the end" would stop a few seconds short and leave
 * a sliver of time behind.
 *
 * @param {string} input
 * @param {Date | null} entry_edge
 * @returns {Date | null}
 */
function resolve_edge(input, entry_edge) {
    if (entry_edge && input === date_to_local_input(entry_edge)) {
        return entry_edge;
    }
    return local_input_to_date(input);
}

const RepairTimesheetSplitForm = defineComponent({
    props: {
        record: {type: /** @type {PropType<TimesheetRecord>} */ (Object), required: true},
    },
    data() {
        const current = this.record.job ? this.record.job.id : null;
        // Splitting is mostly about moving time to a *different* job, so
        // start there; fall back to the current job (a different service
        // on it is a legitimate split too) when it's the only one.
        const other = this.record.jobs.find((job) => job.id !== current);
        const start = server_datetime_to_date(this.record.date_time);
        const end = server_datetime_to_date(this.record.date_time_end);
        // Open on the second half of the entry - a valid choice to adjust.
        const middle = start && end ? new Date((start.getTime() + end.getTime()) / 2) : null;
        return {
            pick: /** @type {JobPickerValue} */ ({
                job_id: other ? other.id : /** @type {number | null} */ (current),
                service_id: null,
            }),
            split_start: middle ? date_to_local_input(middle) : "",
            split_end: end ? date_to_local_input(end) : "",
        };
    },
    computed: {
        /** @returns {Date | null} */
        entry_start() {
            return server_datetime_to_date(this.record.date_time);
        },
        /** @returns {Date | null} */
        entry_end() {
            return server_datetime_to_date(this.record.date_time_end);
        },
        /** @returns {Date | null} */
        part_start() {
            return resolve_edge(this.split_start, this.entry_start);
        },
        /** @returns {Date | null} */
        part_end() {
            return resolve_edge(this.split_end, this.entry_end);
        },
        /** @returns {boolean} */
        valid() {
            const {entry_start, entry_end, part_start, part_end} = this;
            if (!this.pick.job_id || !entry_start || !entry_end || !part_start || !part_end) {
                return false;
            }
            const inside =
                part_start.getTime() >= entry_start.getTime() &&
                part_end.getTime() <= entry_end.getTime() &&
                part_end.getTime() > part_start.getTime();
            const everything =
                part_start.getTime() === entry_start.getTime() && part_end.getTime() === entry_end.getTime();
            return inside && !everything;
        },
        // Updates as either time changes; "—" while the choice isn't valid.
        /** @returns {string} */
        total() {
            const {part_start, part_end} = this;
            if (!this.valid || !part_start || !part_end) {
                return "—";
            }
            return format_duration((part_end.getTime() - part_start.getTime()) / 3600000);
        },
        // What the part has to fit inside, e.g. "10:50 AM – 5:11 PM".
        /** @returns {string} */
        entry_range() {
            const {entry_start, entry_end} = this;
            return entry_start && entry_end ? `${format_clock(entry_start)} – ${format_clock(entry_end)}` : "";
        },
    },
    methods: {
        /** @returns {void} */
        save() {
            if (!this.valid || !this.part_start || !this.part_end) {
                return;
            }
            this.$emit("save", {
                job_id: this.pick.job_id,
                service_id: this.pick.service_id,
                split_start: date_to_server_datetime(this.part_start),
                split_end: date_to_server_datetime(this.part_end),
            });
        },
    },
    template: html`
        <v-card class="repair-timesheet-split-form">
            <v-card-title>{{ $t('repair.timesheets.split_title') }}</v-card-title>
            <v-card-text>
                <repair-job-picker :jobs="record.jobs" v-model="pick" />
                <div class="repair-timesheet-hint">
                    {{ $t('repair.timesheets.split_hint') }}
                    ({{ $t('repair.timesheets.entry_range') }}: <strong>{{ entry_range }}</strong>)
                </div>
                <v-text-field
                    type="datetime-local"
                    :label="$t('repair.timesheets.start')"
                    v-model="split_start"
                    />
                <v-text-field
                    type="datetime-local"
                    :label="$t('repair.timesheets.end')"
                    v-model="split_end"
                    />
                <div class="repair-timesheet-total">
                    <span>{{ $t('repair.timesheets.total') }}</span>
                    <strong>{{ total }}</strong>
                </div>
                <p v-if="!valid" class="repair-timesheet-preview__invalid">
                    {{ $t('repair.timesheets.split_invalid') }}
                </p>
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

export default RepairTimesheetSplitForm;

Vue.component("repair-timesheet-split-form", RepairTimesheetSplitForm);
