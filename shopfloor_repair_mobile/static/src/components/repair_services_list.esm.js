/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The accepted services on a job, one start/stop timer per row. Reuses the
 * existing `<repair-timer>` card unmodified (one instance per row, isolated
 * by Vue's own `v-for` `:key`) rather than forking a new timer widget -
 * there is nothing row-specific about how a timer ticks, only which service
 * the start/stop click should act on, and that is carried by emitting the
 * whole row record rather than by adding an id prop to `repair_timer.esm.js`
 * itself.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {RepairTimerState} from "./timer_widget_types" */
/** @import {RepairServiceRecord} from "./repair_service_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

/**
 * `<repair-timer>` expects a full `RepairTimerState` -- `my_hours` is this
 * technician's own time on the service (`my_time`), `total_hours` everyone's
 * (`actual_time`): several technicians can work the same service.
 *
 * @param {RepairServiceRecord} record
 * @returns {RepairTimerState}
 */
function service_timer_state(record) {
    return {
        running: record.timer.running,
        started_at: record.timer.started_at,
        elapsed_hours: record.timer.elapsed_hours,
        my_hours: record.my_time,
        total_hours: record.actual_time,
    };
}

const RepairServicesList = defineComponent({
    props: {
        records: {
            type: /** @type {PropType<RepairServiceRecord[]>} */ (Array),
            default: () => [],
        },
    },
    methods: {
        /**
         * @param {RepairServiceRecord} rec
         * @returns {String}
         */
        service_name(rec) {
            return (rec.product && rec.product.name) || rec.name;
        },
        /**
         * @param {RepairServiceRecord} rec
         * @returns {RepairTimerState}
         */
        timer_state(rec) {
            return service_timer_state(rec);
        },
    },
    template: html`
        <div class="repair-services-list">
            <p class="empty" v-if="!records.length">
                {{ $t('repair.services.empty') }}
            </p>
            <v-card v-for="rec in records" :key="rec.id" outlined class="service-row">
                <v-card-text>
                    <div class="service-row__name">{{ service_name(rec) }}</div>
                    <div class="service-row__meta">
                        {{ $t('repair.services.estimated') }}: {{
                        rec.estimated_time.toFixed(2) }} h
                    </div>
                    <repair-timer
                        :timer="timer_state(rec)"
                        v-on:start="$emit('timer-start', rec)"
                        v-on:stop="$emit('timer-stop', rec)"
                    />
                </v-card-text>
            </v-card>
        </div>
    `,
});

export default RepairServicesList;

Vue.component("repair-services-list", RepairServicesList);
