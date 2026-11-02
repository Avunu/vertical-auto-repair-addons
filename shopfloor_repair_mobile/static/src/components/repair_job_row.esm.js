/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * One row of the job list. Kept separate from repair-job-card so the list
 * stays scannable: vehicle, then what the customer said, then the clock.
 */
/** @import {PropType} from "vue" */
/** @import {RepairJobRecord} from "./repair_job_types" */
/** @import {JobTimer} from "../services/timer_store.esm.js" */
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {job_label, job_meta, job_status_label} from "../services/job_label.esm.js";
import {timer_store, job_elapsed_seconds, format_elapsed} from "../services/timer_store.esm.js";

translation_registry.add("en-US.repair.jobs.preferred_technician", "Preferred Technician");

const RepairJobRow = defineComponent({
    props: {
        record: {type: /** @type {PropType<RepairJobRecord>} */ (Object), required: true},
    },
    computed: {
        /** @returns {string} */
        label() {
            return job_label(this.record);
        },
        /** @returns {string} */
        meta() {
            return job_meta(this.record);
        },
        /** @returns {string} */
        status_label() {
            return job_status_label(this.record);
        },
        /** @returns {string} */
        scheduled() {
            if (!this.record.schedule_date) {
                return "";
            }
            return this.utils.display.format_date_display(this.record.schedule_date);
        },
        // The same store the app bar's job timer reads, so the two can never
        // disagree about what is running.
        /** @returns {JobTimer | null} */
        running_timer() {
            const timer = timer_store.current_job_timer;
            return timer && timer.running && timer.repair_id === this.record.id ? timer : null;
        },
        /** @returns {string} */
        running_display() {
            return format_elapsed(job_elapsed_seconds());
        },
    },
    template: html`
        <div class="repair-job-row" @click="$emit('select', record)">
            <div class="repair-job-row__main">
                <div class="job-label">{{ label }}</div>
                <div class="meta">{{ meta }}</div>
                <div class="meta" v-if="record.technician">
                    {{ $t('repair.jobs.preferred_technician') }}: {{ record.technician.name }}
                </div>
                <div class="concern" v-if="record.customer_concern">
                    {{ record.customer_concern }}
                </div>
                <div class="repair-job-row__running" v-if="running_timer">
                    <v-icon small color="success">mdi-timer-outline</v-icon>
                    <span class="service">{{ running_timer.service_name }}</span>
                    <span class="elapsed">{{ running_display }}</span>
                    <v-btn small color="error" @click.stop="$emit('stop-timer', running_timer)">
                        <v-icon left small>mdi-stop-circle</v-icon>{{ $t('repair.timer.stop') }}
                    </v-btn>
                </div>
            </div>
            <div class="repair-job-row__side">
                <v-chip
                    :color="record.state === 'under_repair' ? 'success' : 'info'"
                    dark small>
                    {{ status_label }}
                </v-chip>
                <div class="when" v-if="scheduled">{{ scheduled }}</div>
                <div class="hours">{{ record.total_hours.toFixed(1) }} h</div>
            </div>
        </div>
    `,
});

export default RepairJobRow;

Vue.component("repair-job-row", RepairJobRow);
