/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Pick which job - and which of that job's services - some time belongs to.
 * Used by the Edit and Split timesheet dialogs.
 *
 * Replaces `<manual-select>` there: that component always draws a checkbox
 * on every row and labels each entry with its `name` alone, which for two
 * open repair orders on the same vehicle is the same vehicle twice. This one
 * selects on a tap anywhere in the row (a `v-list-item-group`), shows the
 * customer and RO reference under the vehicle, and follows the job list with
 * the chosen job's services.
 *
 * Controlled component: it owns no state, the parent holds
 * `{job_id, service_id}` and receives the next value through `input`
 * (so `v-model` works). Picking a different job resets the service to
 * "Unassigned", because the old service belongs to the old job.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {TimesheetJobChoice, JobPickerValue} from "./timesheet_types" */
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

translation_registry.add("en-US.repair.timesheets.job", "Job");
translation_registry.add("en-US.repair.timesheets.service", "Service");
// `repair.timesheets.no_service` ("Unassigned") is registered by
// pages/timesheets.esm.js, which also needs it for its own service groups.

// `v-list-item-group` can't tell "the item whose value is null" from "nothing
// selected", so "Unassigned" is given a real value of its own.
const NO_SERVICE = 0;

const RepairJobPicker = defineComponent({
    props: {
        jobs: {
            type: /** @type {PropType<TimesheetJobChoice[]>} */ (Array),
            required: true,
        },
        value: {type: /** @type {PropType<JobPickerValue>} */ (Object), required: true},
    },
    computed: {
        /** @returns {TimesheetJobChoice | undefined} */
        selected_job() {
            return this.jobs.find((job) => job.id === this.value.job_id);
        },
        /** @returns {Number} */
        selected_service() {
            return this.value.service_id || NO_SERVICE;
        },
    },
    methods: {
        /**
         * @param {TimesheetJobChoice} job
         * @returns {String}
         */
        job_subtitle(job) {
            return [job.customer, job.ref]
                .filter((part) => part && part !== job.name)
                .join(" · ");
        },
        /**
         * @param {number | undefined} job_id
         * @returns {void}
         */
        select_job(job_id) {
            // The group also fires when the parent pushes the value back
            // down; only a real change is a pick.
            if (job_id === undefined || job_id === this.value.job_id) {
                return;
            }
            this.$emit("input", {job_id: job_id, service_id: null});
        },
        /**
         * @param {number | undefined} service_id
         * @returns {void}
         */
        select_service(service_id) {
            if (service_id === undefined) {
                return;
            }
            this.$emit("input", {
                job_id: this.value.job_id,
                service_id: service_id || null,
            });
        },
    },
    template: html`
        <div class="repair-job-picker">
            <div class="repair-job-picker__label">
                {{ $t('repair.timesheets.job') }}
            </div>
            <v-list dense outlined class="repair-job-picker__list">
                <v-list-item-group
                    :value="value.job_id"
                    mandatory
                    active-class="repair-job-picker__item--active"
                    @change="select_job"
                >
                    <v-list-item v-for="job in jobs" :key="job.id" :value="job.id">
                        <v-list-item-content>
                            <v-list-item-title>{{ job.name }}</v-list-item-title>
                            <v-list-item-subtitle
                                >{{ job_subtitle(job) }}</v-list-item-subtitle
                            >
                        </v-list-item-content>
                    </v-list-item>
                </v-list-item-group>
            </v-list>
            <template v-if="selected_job">
                <div class="repair-job-picker__label">
                    {{ $t('repair.timesheets.service') }}
                </div>
                <v-list dense outlined class="repair-job-picker__list">
                    <v-list-item-group
                        :value="selected_service"
                        mandatory
                        active-class="repair-job-picker__item--active"
                        @change="select_service"
                    >
                        <v-list-item :value="0">
                            <v-list-item-title
                                >{{ $t('repair.timesheets.no_service')
                                }}</v-list-item-title
                            >
                        </v-list-item>
                        <v-list-item
                            v-for="service in selected_job.services"
                            :key="service.id"
                            :value="service.id"
                        >
                            <v-list-item-title>{{ service.name }}</v-list-item-title>
                        </v-list-item>
                    </v-list-item-group>
                </v-list>
            </template>
        </div>
    `,
});

export default RepairJobPicker;

Vue.component("repair-job-picker", RepairJobPicker);
