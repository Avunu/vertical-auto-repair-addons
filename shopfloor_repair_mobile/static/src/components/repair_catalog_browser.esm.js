/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Browse the parts catalog. The search box on the enclosing screen is the
 * global shopfloor searchbar, so the camera button works here too -- scanning
 * a part barcode just fills the search.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {CatalogCategory, CatalogRecord} from "./catalog_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

const RepairCatalogBrowser = defineComponent({
    props: {
        records: {
            type: /** @type {PropType<CatalogRecord[]>} */ (Array),
            default: () => [],
        },
        categories: {
            type: /** @type {PropType<CatalogCategory[]>} */ (Array),
            default: () => [],
        },
        size: {type: Number, default: 0},
        page: {type: Number, default: 1},
        page_size: {type: Number, default: 30},
        category_id: {
            type: /** @type {PropType<number | null>} */ (Number),
            default: null,
        },
    },
    computed: {
        /** @returns {Number} */
        page_count() {
            return Math.max(Math.ceil(this.size / this.page_size), 1);
        },
    },
    template: html`
        <div class="repair-catalog">
            <v-chip-group
                :value="category_id"
                class="catalog-categories"
                show-arrows
                @change="$emit('filter-category', $event)"
            >
                <v-chip filter outlined :value="null"
                    >{{ $t('repair.catalog.all') }}</v-chip
                >
                <v-chip
                    filter
                    outlined
                    v-for="categ in categories"
                    :key="categ.id"
                    :value="categ.id"
                >
                    {{ categ.name }}
                </v-chip>
            </v-chip-group>

            <p class="empty" v-if="!records.length">{{ $t('repair.catalog.empty') }}</p>

            <v-card
                v-for="rec in records"
                :key="rec.id"
                outlined
                class="catalog-row"
                @click="$emit('select', rec)"
            >
                <div class="catalog-row__info">
                    <div class="name">{{ rec.name }}</div>
                    <div class="meta">
                        <span v-if="rec.default_code">{{ rec.default_code }}</span>
                        <span v-if="rec.barcode" class="barcode">
                            <v-icon x-small>mdi-barcode</v-icon> {{ rec.barcode }}
                        </span>
                    </div>
                </div>
                <div class="catalog-row__stock">
                    <span :class="rec.qty_available > 0 ? 'in-stock' : 'out-of-stock'">
                        {{ rec.qty_available }}
                    </span>
                    <small>{{ rec.uom ? rec.uom.name : '' }}</small>
                </div>
            </v-card>

            <div class="catalog-pager" v-if="page_count > 1">
                <v-btn :disabled="page <= 1" @click="$emit('page', page - 1)">
                    <v-icon>mdi-chevron-left</v-icon>
                </v-btn>
                <span>{{ page }} / {{ page_count }}</span>
                <v-btn :disabled="page >= page_count" @click="$emit('page', page + 1)">
                    <v-icon>mdi-chevron-right</v-icon>
                </v-btn>
            </div>
        </div>
    `,
});

export default RepairCatalogBrowser;

Vue.component("repair-catalog-browser", RepairCatalogBrowser);
