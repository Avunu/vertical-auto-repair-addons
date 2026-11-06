/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The one-tap grading control: six big buttons, no dropdown.
 */

/* global Vue */

/** @import {PropType} from "vue" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {severity_color, severity_icon} from "./severity.esm.js";

/**
 * @typedef {Object} SeverityChoice
 * @property {String} value
 * @property {String} label
 */

const SeveritySelector = defineComponent({
    props: {
        severities: {
            type: /** @type {PropType<SeverityChoice[]>} */ (Array),
            default: () => [],
        },
        value: {type: /** @type {PropType<string | null>} */ (String), default: null},
    },
    methods: {
        /**
         * @param {String} value
         * @returns {String}
         */
        color_for(value) {
            return severity_color(value);
        },
        /**
         * @param {String} value
         * @returns {String}
         */
        icon_for(value) {
            return severity_icon(value);
        },
        /**
         * @param {String} value
         * @returns {Boolean}
         */
        is_selected(value) {
            return this.value === value;
        },
    },
    template: html`
        <div class="severity-selector">
            <v-row dense>
                <v-col cols="12" sm="6" v-for="sev in severities" :key="sev.value">
                    <v-btn
                        block
                        x-large
                        dark
                        class="severity-btn"
                        :class="{'severity-btn--selected': is_selected(sev.value)}"
                        :color="color_for(sev.value)"
                        @click="$emit('select', sev.value)"
                    >
                        <v-icon left>{{ icon_for(sev.value) }}</v-icon>
                        <span class="severity-btn__label">{{ sev.label }}</span>
                        <v-icon right v-if="is_selected(sev.value)"
                            >mdi-check-bold</v-icon
                        >
                    </v-btn>
                </v-col>
            </v-row>
        </div>
    `,
});

export default SeveritySelector;

Vue.component("severity-selector", SeveritySelector);
