/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The parts the job expects, with a one-tap "used it all" on each row.
 * Anything that needs a lot number or a partial quantity goes to the detail
 * screen instead.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {RepairPartRecord} from "./parts_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

const RepairPartsList = defineComponent({
    props: {
        parts: {
            type: /** @type {PropType<RepairPartRecord[]>} */ (Array),
            default: () => [],
        },
    },
    methods: {
        /**
         * @param {RepairPartRecord} part
         * @returns {String}
         */
        row_class(part) {
            if (part.picked && part.quantity_done >= part.quantity_demand) {
                return "part-row--done";
            }
            if (part.picked) {
                return "part-row--partial";
            }
            return "";
        },
        /**
         * @param {Number} value
         * @returns {String}
         */
        qty(value) {
            return Number(value).toLocaleString(undefined, {
                maximumFractionDigits: 3,
            });
        },
    },
    template: html`
        <div class="repair-parts-list">
            <p class="empty" v-if="!parts.length">{{ $t('repair.parts.empty') }}</p>
            <v-card
                v-for="part in parts"
                :key="part.id"
                outlined
                class="part-row"
                :class="row_class(part)"
            >
                <div class="part-row__info" @click="$emit('select', part)">
                    <div class="name">{{ part.product.name }}</div>
                    <div class="meta">
                        <span v-if="part.product.default_code"
                            >{{ part.product.default_code }}</span
                        >
                        <span class="qty">
                            {{ qty(part.quantity_done) }} / {{ qty(part.quantity_demand)
                            }} {{ part.uom ? part.uom.name : '' }}
                        </span>
                        <v-chip x-small color="info" dark v-if="part.shopfloor_added">
                            {{ $t('repair.parts.added_here') }}
                        </v-chip>
                        <v-chip x-small outlined v-if="part.tracking !== 'none'">
                            <v-icon x-small left>mdi-barcode</v-icon>
                            {{ part.tracking }}
                        </v-chip>
                    </div>
                </div>
                <div class="part-row__actions">
                    <v-btn icon large v-if="part.picked" @click="$emit('reset', part)">
                        <v-icon>mdi-undo-variant</v-icon>
                    </v-btn>
                    <v-btn
                        large
                        color="success"
                        v-if="!part.picked"
                        @click="$emit('consume-all', part)"
                    >
                        <v-icon left>mdi-check-bold</v-icon>{{
                        $t('repair.parts.use_all') }}
                    </v-btn>
                    <v-btn icon large @click="$emit('select', part)">
                        <v-icon>mdi-chevron-right</v-icon>
                    </v-btn>
                </div>
            </v-card>
        </div>
    `,
});

export default RepairPartsList;

Vue.component("repair-parts-list", RepairPartsList);
