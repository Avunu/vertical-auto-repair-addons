/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Measured values for one checklist item.
 *
 * A value of 0 means "not measured" (that is the server's convention too), so
 * the field starts blank rather than at zero and is only sent on blur -- one
 * round trip per reading, not one per keystroke.
 */
/** @import {PropType} from "vue" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

/**
 * @typedef {Object} Measurement
 * @property {unknown} id
 * @property {string} name
 * @property {number} value
 * @property {string} [position]
 * @property {string} [position_label]
 * @property {number} [spec_min]
 * @property {number} [spec_max]
 * @property {string} [uom_label]
 * @property {boolean} [out_of_spec]
 */

const RepairMeasurementGrid = defineComponent({
    props: {
        measurements: {type: /** @type {PropType<Measurement[]>} */ (Array), default: () => []},
    },
    data() {
        return {
            local: /** @type {Record<string, string | number>} */ ({}),
        };
    },
    watch: {
        measurements: {
            /** @param {Measurement[] | undefined} values */
            handler(values) {
                this.on_measurements_change(values);
            },
            immediate: true,
        },
    },
    methods: {
        /**
         * @param {Measurement[] | undefined} values
         * @returns {void}
         */
        on_measurements_change(values) {
            /** @type {Record<string, string | number>} */
            const local = {};
            (values || []).forEach((m) => {
                local[/** @type {string} */ (m.id)] = m.value ? m.value : "";
            });
            this.local = local;
        },
        /**
         * @param {Measurement} measurement
         * @returns {string}
         */
        label(measurement) {
            const bits = [measurement.name];
            if (measurement.position && measurement.position !== "none") {
                bits.push(measurement.position_label || "");
            }
            return bits.join(" — ");
        },
        /**
         * @param {Measurement} measurement
         * @returns {string}
         */
        spec_hint(measurement) {
            /** @type {string[]} */
            const bits = [];
            if (measurement.spec_min) {
                bits.push("min " + measurement.spec_min);
            }
            if (measurement.spec_max) {
                bits.push("max " + measurement.spec_max);
            }
            return bits.join(" · ");
        },
        /**
         * @param {Measurement} measurement
         * @returns {void}
         */
        commit(measurement) {
            const raw = this.local[/** @type {string} */ (measurement.id)];
            const value = raw === "" || raw === null ? 0 : Number(raw);
            if (Number.isNaN(value) || value === measurement.value) {
                return;
            }
            this.$emit("change", {id: measurement.id, value: value});
        },
    },
    template: html`
        <div class="measurement-grid" v-if="measurements.length">
            <separator-title>{{ $t('repair.inspection.measurements') }}</separator-title>
            <div class="measurement-row" v-for="m in measurements" :key="m.id"
                 :class="{'measurement-row--alert': m.out_of_spec}">
                <div class="measurement-row__label">
                    <div class="name">{{ label(m) }}</div>
                    <div class="spec" v-if="spec_hint(m)">{{ spec_hint(m) }} {{ m.uom_label }}</div>
                </div>
                <div class="measurement-row__input">
                    <v-text-field
                        v-model="local[m.id]"
                        type="number"
                        step="any"
                        hide-details
                        :suffix="m.uom_label"
                        :placeholder="$t('repair.inspection.not_measured')"
                        @blur="commit(m)"
                        @keyup.enter="commit(m)" />
                    <v-icon color="error" v-if="m.out_of_spec">mdi-alert-circle</v-icon>
                </div>
            </div>
        </div>
    `,
});

export default RepairMeasurementGrid;

Vue.component("repair-measurement-grid", RepairMeasurementGrid);
