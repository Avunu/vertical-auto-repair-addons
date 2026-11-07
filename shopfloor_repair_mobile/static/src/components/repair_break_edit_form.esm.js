/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Edit an existing break: when it starts and when it ends. A break is the
 * gap between two clocked-in periods, so this is really "clock out at X, back
 * in at Y" - the backend (`update_break`) moves those two times, and the job
 * time that met the break follows them.
 *
 * Unlike the Add break dialog (repair_timesheet_break_form.esm.js), which cuts
 * a break out of one job entry, this one is bounded by what is either side of
 * the break - the clocked periods, or (where nothing is clocked) the two parts
 * of the job: the break has to start after the earlier one began and end
 * before the later one finishes (`record.lower` / `record.upper`). The server
 * checks the same rules and also refuses a break that would cut into other job
 * time; this is only so the technician finds out before tapping Save.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {TimesheetRow} from "../pages/timesheets.esm.js" */
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {
    date_to_server_datetime,
    format_duration,
    local_input_to_date,
    server_datetime_to_date,
    server_datetime_to_local_input,
} from "../services/datetime.esm.js";

translation_registry.add("en-US.repair.timesheets.edit_break_title", "Edit break");
translation_registry.add(
    "en-US.repair.timesheets.edit_break_invalid",
    "The break has to start after you clocked in and end before you clocked out again."
);
translation_registry.add(
    "en-US.repair.timesheets.edit_job_break_invalid",
    "The break has to start after the earlier part of the timesheet begins and end before the later part ends."
);

const RepairBreakEditForm = defineComponent({
    props: {
        record: {type: /** @type {PropType<TimesheetRow>} */ (Object), required: true},
    },
    data() {
        return {
            break_start: server_datetime_to_local_input(this.record.date_time),
            break_end: server_datetime_to_local_input(this.record.date_time_end),
        };
    },
    computed: {
        /** @returns {Date | null} */
        gap_start() {
            return local_input_to_date(this.break_start);
        },
        /** @returns {Date | null} */
        gap_end() {
            return local_input_to_date(this.break_end);
        },
        /** @returns {Boolean} */
        valid() {
            const {gap_start, gap_end} = this;
            if (!gap_start || !gap_end || gap_end.getTime() <= gap_start.getTime()) {
                return false;
            }
            const lower = server_datetime_to_date(this.record.lower);
            const upper = server_datetime_to_date(this.record.upper);
            // `upper` is empty while the later period is still open: no limit.
            return (
                (!lower || gap_start.getTime() > lower.getTime()) &&
                (!upper || gap_end.getTime() < upper.getTime())
            );
        },
        // Updates as either time changes; "—" while the break isn't valid.
        /** @returns {String} */
        total() {
            const {gap_start, gap_end} = this;
            if (!this.valid || !gap_start || !gap_end) {
                return "—";
            }
            return format_duration((gap_end.getTime() - gap_start.getTime()) / 3600000);
        },
    },
    methods: {
        /** @returns {void} */
        save() {
            if (!this.valid || !this.gap_start || !this.gap_end) {
                return;
            }
            this.$emit("save", {
                break_start: date_to_server_datetime(this.gap_start),
                break_end: date_to_server_datetime(this.gap_end),
            });
        },
    },
    template: html`
        <v-card class="repair-break-edit-form">
            <v-card-title>{{ $t('repair.timesheets.edit_break_title') }}</v-card-title>
            <v-card-text>
                <v-text-field
                    type="datetime-local"
                    :label="$t('repair.timesheets.break_start')"
                    v-model="break_start"
                />
                <v-text-field
                    type="datetime-local"
                    :label="$t('repair.timesheets.break_end')"
                    v-model="break_end"
                />
                <div class="repair-timesheet-total">
                    <span>{{ $t('repair.timesheets.total') }}</span>
                    <strong>{{ total }}</strong>
                </div>
                <p v-if="!valid" class="repair-timesheet-preview__invalid">
                    {{ record.source === 'jobs' ?
                    $t('repair.timesheets.edit_job_break_invalid') :
                    $t('repair.timesheets.edit_break_invalid') }}
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

export default RepairBreakEditForm;

Vue.component("repair-break-edit-form", RepairBreakEditForm);
