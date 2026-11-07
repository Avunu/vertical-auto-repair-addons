/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The inspections already on this job, plus the "start a new one" form.
 * The odometer lives here rather than on a state of its own: OCA's odometer
 * inverse raises on a blank value, so the reading has to be collected before
 * the record is created, and one screen is one fewer tap.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {InspectionRecord, InspectionTemplate} from "./inspection_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {severity_color} from "./severity.esm.js";

const RepairInspectionList = defineComponent({
    props: {
        records: {
            type: /** @type {PropType<InspectionRecord[]>} */ (Array),
            default: () => [],
        },
        templates: {
            type: /** @type {PropType<InspectionTemplate[]>} */ (Array),
            default: () => [],
        },
        default_odometer: {type: Number, default: 0},
        odometer_unit: {type: String, default: ""},
    },
    data() {
        return {
            template_id: /** @type {unknown} */ (null),
            odometer: /** @type {number | null} */ (this.default_odometer || null),
        };
    },
    computed: {
        /** @returns {Boolean} */
        can_start() {
            return Boolean(this.template_id) && Number(this.odometer) > 0;
        },
        /** @returns {String} */
        unit_label() {
            return this.odometer_unit === "kilometers" ? "km" : "mi";
        },
    },
    watch: {
        default_odometer: "on_default_odometer_change",
    },
    methods: {
        /**
         * @param {Number} value
         * @returns {void}
         */
        on_default_odometer_change(value) {
            if (!this.odometer) {
                this.odometer = value || null;
            }
        },
        /**
         * @param {String} value
         * @returns {String}
         */
        color_for(value) {
            return severity_color(value);
        },
    },
    template: html`
        <div class="inspection-list">
            <v-card
                v-for="rec in records"
                :key="rec.id"
                outlined
                class="inspection-row"
                @click="$emit('open', rec)"
            >
                <div class="inspection-row__info">
                    <div class="name">{{ rec.name }}</div>
                    <div class="meta">
                        <v-chip
                            x-small
                            :color="rec.state === 'confirmed' ? 'success' : 'info'"
                            dark
                        >
                            {{ rec.state_label }}
                        </v-chip>
                        <span class="ml-2"
                            >{{ rec.graded_count }} / {{ rec.line_count }}</span
                        >
                    </div>
                    <div class="counts">
                        <v-chip
                            x-small
                            dark
                            class="mr-1"
                            v-if="rec.counts.today"
                            :color="color_for('today')"
                            >{{ rec.counts.today }}</v-chip
                        >
                        <v-chip
                            x-small
                            dark
                            class="mr-1"
                            v-if="rec.counts.attention"
                            :color="color_for('attention')"
                            >{{ rec.counts.attention }}</v-chip
                        >
                        <v-chip
                            x-small
                            dark
                            class="mr-1"
                            v-if="rec.counts.future"
                            :color="color_for('future')"
                            >{{ rec.counts.future }}</v-chip
                        >
                        <v-chip
                            x-small
                            dark
                            class="mr-1"
                            v-if="rec.counts.good"
                            :color="color_for('good')"
                            >{{ rec.counts.good }}</v-chip
                        >
                    </div>
                </div>
                <v-icon>mdi-chevron-right</v-icon>
            </v-card>

            <v-card outlined class="inspection-new mt-3">
                <v-card-title>{{ $t('repair.inspection.new') }}</v-card-title>
                <v-card-text>
                    <v-select
                        v-model="template_id"
                        :items="templates"
                        item-text="name"
                        item-value="id"
                        :label="$t('repair.inspection.template')"
                    />
                    <v-text-field
                        v-model.number="odometer"
                        type="number"
                        step="any"
                        min="1"
                        :suffix="unit_label"
                        :label="$t('repair.inspection.odometer')"
                        :hint="$t('repair.inspection.odometer_hint')"
                        persistent-hint
                    />
                </v-card-text>
                <v-card-actions>
                    <v-btn
                        block
                        x-large
                        color="primary"
                        :disabled="!can_start"
                        @click="$emit('start', {template_id: template_id, odometer: Number(odometer)})"
                    >
                        <v-icon left>mdi-clipboard-plus-outline</v-icon>
                        {{ $t('repair.inspection.start') }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </div>
    `,
});

export default RepairInspectionList;

Vue.component("repair-inspection-list", RepairInspectionList);
