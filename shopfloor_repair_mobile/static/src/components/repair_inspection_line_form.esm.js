/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Grade one checklist item: severity, what was found, what to do about it,
 * a note, the measurements and a photo.
 *
 * Conditions, actions and the note are held locally and sent together with
 * the severity, because the severity tap is the moment the technician
 * declares they are done with this item.
 */
/** @import {PropType} from "vue" */
/** @import {SeverityValue} from "./severity.esm.js" */
/** @import {InspectionLine, InspectionLineChoices} from "./inspection_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {PROBLEM_SEVERITIES} from "./severity.esm.js";

const RepairInspectionLineForm = defineComponent({
    props: {
        record: {type: /** @type {PropType<InspectionLine>} */ (Object), required: true},
        choices: {type: /** @type {PropType<InspectionLineChoices>} */ (Object), required: true},
        require_photo_on_fail: {type: Boolean, default: false},
    },
    data() {
        return {
            severity: /** @type {SeverityValue | null | undefined} */ (this.record.severity),
            condition_ids: /** @type {unknown[]} */ ((this.record.conditions || []).map((c) => c.id)),
            action_ids: /** @type {unknown[]} */ ((this.record.recommended_actions || []).map((a) => a.id)),
            note: this.record.note || "",
        };
    },
    computed: {
        /** @returns {boolean} */
        photo_blocked() {
            return (
                this.require_photo_on_fail &&
                !this.record.image_count &&
                Boolean(this.severity) &&
                PROBLEM_SEVERITIES.indexOf(/** @type {SeverityValue} */ (this.severity)) !== -1
            );
        },
    },
    watch: {
        "record.id": "on_record_change",
    },
    methods: {
        /** @returns {void} */
        on_record_change() {
            this.severity = this.record.severity;
            this.condition_ids = (this.record.conditions || []).map((c) => c.id);
            this.action_ids = (this.record.recommended_actions || []).map((a) => a.id);
            this.note = this.record.note || "";
        },
        /**
         * @param {SeverityValue} value
         * @returns {void}
         */
        on_severity(value) {
            this.severity = value;
            this.$emit("grade", {
                severity: value,
                condition_ids: this.condition_ids,
                action_ids: this.action_ids,
                note: this.note,
            });
        },
    },
    template: html`
        <div class="inspection-line-form">
            <v-card outlined class="line-header">
                <v-card-title>{{ record.name }}</v-card-title>
                <v-card-subtitle v-if="record.instruction">{{ record.instruction }}</v-card-subtitle>
            </v-card>

            <repair-measurement-grid
                :measurements="record.measurements"
                v-on:change="$emit('measure', $event)" />

            <div class="line-choices" v-if="choices.conditions.length">
                <separator-title>{{ $t('repair.inspection.conditions') }}</separator-title>
                <v-chip-group v-model="condition_ids" multiple column>
                    <v-chip filter outlined v-for="c in choices.conditions" :key="c.id" :value="c.id">
                        {{ c.name }}
                    </v-chip>
                </v-chip-group>
            </div>

            <div class="line-choices" v-if="choices.actions.length">
                <separator-title>{{ $t('repair.inspection.actions') }}</separator-title>
                <v-chip-group v-model="action_ids" multiple column>
                    <v-chip filter outlined v-for="a in choices.actions" :key="a.id" :value="a.id">
                        {{ a.name }}
                    </v-chip>
                </v-chip-group>
            </div>

            <v-textarea
                v-model="note"
                rows="2"
                auto-grow
                :label="$t('repair.inspection.note')"
                class="mt-2" />

            <repair-photo-capture
                :count="record.image_count"
                v-on:capture="$emit('photo', $event)" />

            <v-alert type="warning" dense text v-if="photo_blocked" class="mt-2">
                {{ $t('repair.inspection.photo_required') }}
            </v-alert>

            <separator-title>{{ $t('repair.inspection.grade') }}</separator-title>
            <severity-selector
                :severities="choices.severities"
                :value="severity"
                v-on:select="on_severity" />
        </div>
    `,
});

export default RepairInspectionLineForm;

Vue.component("repair-inspection-line-form", RepairInspectionLineForm);
