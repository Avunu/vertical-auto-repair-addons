/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

/* global Vue */

/** @import {PropType} from "vue" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {severity_color, severity_icon} from "./severity.esm.js";

const SeverityChip = defineComponent({
    props: {
        value: {type: /** @type {PropType<string | null>} */ (String), default: null},
        label: {type: String, default: ""},
        small: {type: Boolean, default: false},
    },
    computed: {
        /** @returns {String} */
        color() {
            return severity_color(this.value);
        },
        /** @returns {String} */
        icon() {
            return severity_icon(this.value);
        },
    },
    template: html`
        <v-chip :color="color" dark :small="small" class="severity-chip">
            <v-icon left :small="small">{{ icon }}</v-icon>
            <span v-if="label">{{ label }}</span>
        </v-chip>
    `,
});

export default SeverityChip;

Vue.component("severity-chip", SeverityChip);
