/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Partial quantities and lot entry for one part.
 */
/** @import {PropType} from "vue" */
/** @import {RepairPartRecord} from "./parts_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

const RepairPartDetail = defineComponent({
    props: {
        record: {type: /** @type {PropType<RepairPartRecord>} */ (Object), required: true},
    },
    data() {
        return {
            quantity: this.record.quantity_done || this.record.quantity_demand,
            lot_name: "",
        };
    },
    computed: {
        /** @returns {boolean} */
        needs_lot() {
            return this.record.tracking !== "none";
        },
    },
    watch: {
        "record.id": "on_record_change",
    },
    methods: {
        /** @returns {void} */
        on_record_change() {
            this.quantity = this.record.quantity_done || this.record.quantity_demand;
            this.lot_name = "";
        },
        /**
         * @param {number} delta
         * @returns {void}
         */
        step(delta) {
            const next = Number(this.quantity || 0) + delta;
            this.quantity = Math.max(Math.round(next * 1000) / 1000, 0);
        },
        /** @returns {void} */
        confirm() {
            this.$emit("confirm", {
                quantity: Number(this.quantity),
                lot_name: this.lot_name || null,
            });
        },
    },
    template: html`
        <div class="repair-part-detail">
            <item-detail-card :record="record.product" :options="{key_title: 'name'}" />
            <v-card outlined class="mt-3">
                <v-card-text>
                    <div class="demand">
                        {{ $t('repair.parts.demand') }}:
                        <strong>{{ record.quantity_demand }} {{ record.uom ? record.uom.name : '' }}</strong>
                    </div>
                    <!--
                        Not input-number-spinner: it parseInt()s its value, and
                        parts are sold in litres and metres as well as in units.
                    -->
                    <div class="qty-stepper">
                        <v-btn x-large icon @click="step(-1)"><v-icon large>mdi-minus-circle</v-icon></v-btn>
                        <v-text-field
                            v-model.number="quantity"
                            type="number"
                            step="any"
                            min="0"
                            hide-details
                            class="qty-stepper__field"
                            :label="$t('repair.parts.used')" />
                        <v-btn x-large icon @click="step(1)"><v-icon large>mdi-plus-circle</v-icon></v-btn>
                    </div>
                    <v-text-field
                        v-if="needs_lot"
                        v-model="lot_name"
                        :label="$t('repair.parts.lot')"
                        prepend-icon="mdi-barcode"
                        clearable />
                    <div class="lots" v-if="record.lots && record.lots.length">
                        <v-chip small class="mr-1" v-for="lot in record.lots" :key="lot.id">
                            {{ lot.name }}
                        </v-chip>
                    </div>
                </v-card-text>
            </v-card>
            <div class="button-list button-vertical-list full mt-3">
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-action action="complete" @click="confirm">
                            <v-icon left>mdi-check-bold</v-icon>{{ $t('repair.parts.record') }}
                        </btn-action>
                    </v-col>
                </v-row>
                <v-row align="center" v-if="record.picked">
                    <v-col class="text-center" cols="12">
                        <btn-action action="warn" @click="$emit('reset')">
                            <v-icon left>mdi-undo-variant</v-icon>{{ $t('repair.parts.reset') }}
                        </btn-action>
                    </v-col>
                </v-row>
            </div>
        </div>
    `,
});

export default RepairPartDetail;

Vue.component("repair-part-detail", RepairPartDetail);
