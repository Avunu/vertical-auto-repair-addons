/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Confirm quantity before adding a catalog part to the job.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {CatalogRecord} from "./catalog_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

const RepairCatalogDetail = defineComponent({
    props: {
        record: {type: /** @type {PropType<CatalogRecord>} */ (Object), required: true},
    },
    data() {
        return {
            quantity: 1,
            consume_now: true,
        };
    },
    computed: {
        // A tracked part needs its serial scanned on the part screen, so
        // "add and mark used" cannot be honoured in one step.
        /** @returns {Boolean} */
        can_consume_now() {
            return this.record.tracking === "none";
        },
    },
    watch: {
        "record.id": "on_record_change",
    },
    methods: {
        /** @returns {void} */
        on_record_change() {
            this.quantity = 1;
            this.consume_now = true;
        },
        /**
         * @param {Number} delta
         * @returns {void}
         */
        step(delta) {
            const next = Number(this.quantity || 0) + delta;
            this.quantity = Math.max(Math.round(next * 1000) / 1000, 0);
        },
    },
    template: html`
        <div class="repair-catalog-detail">
            <item-detail-card :record="record" :options="{key_title: 'name'}" />
            <v-card outlined class="mt-3">
                <v-card-text>
                    <div class="qty-stepper">
                        <v-btn x-large icon @click="step(-1)"
                            ><v-icon large>mdi-minus-circle</v-icon></v-btn
                        >
                        <v-text-field
                            v-model.number="quantity"
                            type="number"
                            step="any"
                            min="0"
                            hide-details
                            class="qty-stepper__field"
                            :label="$t('repair.catalog.quantity')"
                        />
                        <v-btn x-large icon @click="step(1)"
                            ><v-icon large>mdi-plus-circle</v-icon></v-btn
                        >
                    </div>
                    <v-checkbox
                        v-if="can_consume_now"
                        v-model="consume_now"
                        :label="$t('repair.catalog.consume_now')"
                    />
                    <v-alert type="info" dense text class="mt-2">
                        {{ $t('repair.catalog.billing_notice') }}
                    </v-alert>
                </v-card-text>
            </v-card>
            <div class="button-list button-vertical-list full mt-3">
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-action
                            action="complete"
                            @click="$emit('add', {quantity: Number(quantity), consume_now: can_consume_now && consume_now})"
                        >
                            <v-icon left>mdi-plus-box</v-icon>{{
                            $t('repair.catalog.add') }}
                        </btn-action>
                    </v-col>
                </v-row>
            </div>
        </div>
    `,
});

export default RepairCatalogDetail;

Vue.component("repair-catalog-detail", RepairCatalogDetail);
