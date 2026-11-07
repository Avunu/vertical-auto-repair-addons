/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Start/stop the work timer.
 *
 * The elapsed time ticks client-side from the `elapsed_hours` the server sent
 * with the screen: the running analytic line carries unit_amount = 0 until it
 * is stopped (that zero is precisely what marks it as running), so there is
 * nothing on the server to poll for.
 */

/* global Vue */

/** @import {PropType} from "vue" */
/** @import {RepairTimerState} from "./timer_widget_types" */
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";

const RepairTimer = defineComponent({
    props: {
        timer: {
            type: /** @type {PropType<RepairTimerState>} */ (Object),
            required: true,
        },
    },
    data() {
        return {
            ticked_seconds: 0,
            interval: /** @type {ReturnType<typeof setInterval> | null} */ (null),
        };
    },
    computed: {
        /** @returns {Number} */
        elapsed_seconds() {
            return Math.round(this.timer.elapsed_hours * 3600) + this.ticked_seconds;
        },
        /** @returns {String} */
        elapsed_display() {
            const total = Math.max(this.elapsed_seconds, 0);
            const h = Math.floor(total / 3600);
            const m = Math.floor((total % 3600) / 60);
            const s = total % 60;
            return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
        },
    },
    watch: {
        // A fresh payload resets the offset; otherwise stopping and starting
        // again would keep counting from the old figure.
        "timer.started_at": "on_timer_change",
        "timer.running": "on_timer_change",
    },
    mounted() {
        this._sync_interval();
    },
    beforeDestroy() {
        this._clear_interval();
    },
    methods: {
        /** @returns {void} */
        on_timer_change() {
            this.ticked_seconds = 0;
            this._sync_interval();
        },
        /** @returns {void} */
        _sync_interval() {
            this._clear_interval();
            if (this.timer.running) {
                this.interval = setInterval(() => {
                    this.ticked_seconds += 1;
                }, 1000);
            }
        },
        /** @returns {void} */
        _clear_interval() {
            if (this.interval) {
                clearInterval(this.interval);
                this.interval = null;
            }
        },
    },
    template: html`
        <v-card
            class="repair-timer"
            outlined
            :class="{'repair-timer--running': timer.running}"
        >
            <v-card-text class="repair-timer__body">
                <div class="repair-timer__readout">
                    <div class="elapsed" v-if="timer.running">
                        {{ elapsed_display }}
                    </div>
                    <div class="elapsed elapsed--idle" v-else>--:--:--</div>
                    <div class="totals">
                        <span
                            >{{ $t('repair.timer.mine') }}: {{ timer.my_hours.toFixed(2)
                            }} h</span
                        >
                        <span class="ml-3"
                            >{{ $t('repair.timer.total') }}: {{
                            timer.total_hours.toFixed(2) }} h</span
                        >
                    </div>
                </div>
                <div class="repair-timer__action">
                    <v-btn
                        x-large
                        block
                        color="error"
                        v-if="timer.running"
                        @click="$emit('stop')"
                    >
                        <v-icon left>mdi-stop-circle</v-icon>{{ $t('repair.timer.stop')
                        }}
                    </v-btn>
                    <v-btn x-large block color="success" v-else @click="$emit('start')">
                        <v-icon left>mdi-play-circle</v-icon>{{ $t('repair.timer.start')
                        }}
                    </v-btn>
                </div>
            </v-card-text>
        </v-card>
    `,
});

export default RepairTimer;

Vue.component("repair-timer", RepairTimer);
