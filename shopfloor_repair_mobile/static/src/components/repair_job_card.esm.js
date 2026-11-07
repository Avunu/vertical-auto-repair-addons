/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The vehicle-and-customer header that identifies the job on every screen.
 * The vehicle description is the biggest thing on it: that is what the
 * technician matches against the car in front of them.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {RepairJobRecord} from "./repair_job_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {job_label, job_meta, job_status_label} from "../services/job_label.esm.js";

const RepairJobCard = defineComponent({
    props: {
        record: {
            type: /** @type {PropType<RepairJobRecord>} */ (Object),
            required: true,
        },
        compact: {type: Boolean, default: false},
    },
    computed: {
        /** @returns {String} */
        label() {
            return job_label(this.record);
        },
        /** @returns {String} */
        meta() {
            return job_meta(this.record);
        },
        /** @returns {String} */
        status_label() {
            return job_status_label(this.record);
        },
        /** @returns {String} */
        state_color() {
            return this.record.state === "under_repair" ? "success" : "info";
        },
    },
    template: html`
        <v-card class="repair-job-card" outlined>
            <v-card-title class="repair-job-card__title">
                <span class="job-label">{{ label }}</span>
                <v-spacer />
                <v-chip :color="state_color" dark small>{{ status_label }}</v-chip>
            </v-card-title>
            <v-card-subtitle class="repair-job-card__subtitle">
                <div class="job-ref">{{ meta }}</div>
            </v-card-subtitle>
            <v-card-text v-if="!compact">
                <div class="concern" v-if="record.customer_concern">
                    <span class="label">{{ $t('repair.concern') }}</span>
                    <p>{{ record.customer_concern }}</p>
                </div>
                <div class="counters">
                    <v-chip small outlined class="mr-2">
                        <v-icon left small>mdi-package-variant-closed</v-icon>
                        {{ record.parts_done }} / {{ record.parts_total }}
                    </v-chip>
                    <v-chip small outlined class="mr-2" v-if="record.inspection_total">
                        <v-icon left small>mdi-clipboard-check-outline</v-icon>
                        {{ record.inspection_graded }} / {{ record.inspection_total }}
                    </v-chip>
                    <v-chip small outlined>
                        <v-icon left small>mdi-timer-outline</v-icon>
                        {{ record.total_hours.toFixed(2) }} h
                    </v-chip>
                </div>
            </v-card-text>
        </v-card>
    `,
});

export default RepairJobCard;

Vue.component("repair-job-card", RepairJobCard);
