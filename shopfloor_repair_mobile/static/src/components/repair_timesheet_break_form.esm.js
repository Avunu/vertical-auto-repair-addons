/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Cut a break out of the middle of a timesheet: pick when it starts and when
 * it ends, like any other time on this page. The backend (`add_break`) splits
 * the timesheet in two around the gap and clocks the technician out and back
 * in over it, so the break comes off the day's clocked total as well.
 *
 * Same shape as repair_timesheet_edit_form.esm.js: local state seeded from
 * the record, a `save` event with the payload for the page to `POST`. Save
 * stays disabled until the whole break sits strictly inside the timesheet
 * (the same rule the server enforces - this is only so the technician finds
 * out before tapping Save, not instead of the server check).
 */
/** @import {PropType} from "vue" */
/** @import {TimesheetListEntry} from "../pages/timesheets.esm.js" */
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

translation_registry.add("en-US.repair.timesheets.break_title", "Add break");
translation_registry.add("en-US.repair.timesheets.break_start", "Break starts");
translation_registry.add("en-US.repair.timesheets.break_end", "Break ends");
translation_registry.add("en-US.repair.timesheets.break_invalid", "The break has to fall inside the timesheet.");
translation_registry.add("en-US.repair.timesheets.entry_range", "Timesheet");

const DEFAULT_BREAK_MINUTES = 15;

const RepairTimesheetBreakForm = defineComponent({
    props: {
        record: {type: /** @type {PropType<TimesheetListEntry>} */ (Object), required: true},
    },
    data() {
        const start = server_datetime_to_date(this.record.date_time);
        const end = server_datetime_to_date(this.record.date_time_end);
        // Open on a break in the middle of the entry: it is always inside it,
        // so the dialog starts valid and the technician only has to nudge the
        // times. Capped to half of what is left so a short entry still fits.
        let break_start = "";
        let break_end = "";
        if (start && end) {
            const middle = (start.getTime() + end.getTime()) / 2;
            const length = Math.min(DEFAULT_BREAK_MINUTES * 60000, (end.getTime() - middle) / 2);
            break_start = date_to_local_input(new Date(middle));
            break_end = date_to_local_input(new Date(middle + length));
        }
        return {break_start: break_start, break_end: break_end};
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
        gap_start() {
            return local_input_to_date(this.break_start);
        },
        /** @returns {Date | null} */
        gap_end() {
            return local_input_to_date(this.break_end);
        },
        /** @returns {boolean} */
        valid() {
            const {entry_start, entry_end, gap_start, gap_end} = this;
            return Boolean(
                entry_start &&
                    entry_end &&
                    gap_start &&
                    gap_end &&
                    gap_start.getTime() > entry_start.getTime() &&
                    gap_end.getTime() > gap_start.getTime() &&
                    gap_end.getTime() < entry_end.getTime()
            );
        },
        // Updates as either time changes; "—" while the break isn't valid.
        /** @returns {string} */
        total() {
            const {gap_start, gap_end} = this;
            if (!this.valid || !gap_start || !gap_end) {
                return "—";
            }
            return format_duration((gap_end.getTime() - gap_start.getTime()) / 3600000);
        },
        // "10:50 AM – 5:11 PM": what the break has to fit inside.
        /** @returns {string} */
        entry_range() {
            const {entry_start, entry_end} = this;
            return entry_start && entry_end ? `${format_clock(entry_start)} – ${format_clock(entry_end)}` : "";
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
        <v-card class="repair-timesheet-break-form">
            <v-card-title>{{ $t('repair.timesheets.break_title') }}</v-card-title>
            <v-card-text>
                <div class="repair-timesheet-hint">
                    {{ $t('repair.timesheets.entry_range') }}: <strong>{{ entry_range }}</strong>
                </div>
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
                    {{ $t('repair.timesheets.break_invalid') }}
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

export default RepairTimesheetBreakForm;

Vue.component("repair-timesheet-break-form", RepairTimesheetBreakForm);
