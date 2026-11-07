/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The checklist, grouped by category the way the customer report is.
 * The ungraded counter is the gate: OCA's button_confirm refuses while any
 * line is still `todo`, so the technician needs to see what is left.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {InspectionGroup, InspectionLine} from "./inspection_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {severity_color, severity_icon} from "./severity.esm.js";

const RepairInspectionChecklist = defineComponent({
    props: {
        lines: {
            type: /** @type {PropType<InspectionLine[]>} */ (Array),
            default: () => [],
        },
    },
    computed: {
        /** @returns {InspectionGroup[]} */
        groups() {
            /** @type {InspectionGroup[]} */
            const groups = [];
            /** @type {Record<number, InspectionGroup>} */
            const index = {};
            this.lines.forEach((line) => {
                const category = line.category || {id: 0, name: ""};
                if (!(category.id in index)) {
                    index[category.id] = {
                        id: category.id,
                        name: category.name || this.$t("repair.inspection.other"),
                        lines: [],
                    };
                    groups.push(index[category.id]);
                }
                index[category.id].lines.push(line);
            });
            return groups;
        },
        /** @returns {Number} */
        ungraded() {
            return this.lines.filter((line) => !line.severity).length;
        },
    },
    methods: {
        /**
         * @param {InspectionLine} line
         * @returns {String}
         */
        color_for(line) {
            return line.severity ? severity_color(line.severity) : "#e0e0e0";
        },
        /**
         * @param {InspectionLine} line
         * @returns {String}
         */
        icon_for(line) {
            return line.severity ? severity_icon(line.severity) : "mdi-circle-outline";
        },
    },
    template: html`
        <div class="inspection-checklist">
            <v-alert
                dense
                text
                :type="ungraded ? 'warning' : 'success'"
                class="checklist-progress"
            >
                <span v-if="ungraded">
                    {{ $t('repair.inspection.remaining', {count: ungraded}) }}
                </span>
                <span v-else>{{ $t('repair.inspection.all_graded') }}</span>
            </v-alert>

            <v-card
                v-for="group in groups"
                :key="group.id"
                outlined
                class="checklist-group"
            >
                <v-card-title class="checklist-group__title"
                    >{{ group.name }}</v-card-title
                >
                <div
                    class="checklist-item"
                    v-for="line in group.lines"
                    :key="line.id"
                    @click="$emit('select', line)"
                >
                    <div
                        class="checklist-item__marker"
                        :style="{backgroundColor: color_for(line)}"
                    >
                        <v-icon dark>{{ icon_for(line) }}</v-icon>
                    </div>
                    <div class="checklist-item__body">
                        <div class="name">{{ line.name }}</div>
                        <div class="summary" v-if="line.measurement_summary">
                            <v-icon x-small color="error" v-if="line.measurement_alert"
                                >mdi-alert</v-icon
                            >
                            {{ line.measurement_summary }}
                        </div>
                        <div class="note" v-if="line.note">{{ line.note }}</div>
                        <div class="tags" v-if="line.recommended_actions.length">
                            <v-chip
                                x-small
                                outlined
                                class="mr-1"
                                v-for="action in line.recommended_actions"
                                :key="action.id"
                            >
                                {{ action.name }}
                            </v-chip>
                        </div>
                    </div>
                    <div class="checklist-item__side">
                        <v-icon small v-if="line.image_count">mdi-camera</v-icon>
                        <v-icon>mdi-chevron-right</v-icon>
                    </div>
                </div>
            </v-card>
        </div>
    `,
});

export default RepairInspectionChecklist;

Vue.component("repair-inspection-checklist", RepairInspectionChecklist);
