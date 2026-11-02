/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Clock in/out for the technician's shift. Reads and writes the same
 * `timer_store.shift_timer` (services/timer_store.esm.js) that the app-bar's
 * compact shift timer and the drawer's Clock In/Out label already share -
 * no separate polling loop here, this screen just gives that shared state
 * a dedicated place to view and act on it, matching what
 * `app_bar_actions.esm.js` already keeps current in the background.
 *
 * The client-side tick display duplicates the same small pattern already
 * used in `repair_timer.esm.js` rather than introducing a shared mixin for
 * one more consumer - matches this codebase's established convention of
 * deliberate duplication over a shared mixin for this exact logic.
 */
/** @import {TimerState} from "../components/timer_widget_types" */
import {page_registry} from "/shopfloor_mobile_base/static/src/services/page_registry.esm.js";
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {defineComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {timer_store, set_shift_timer, set_current_job_timer} from "../services/timer_store.esm.js";
import {sf_root, menu_id_for} from "../services/root.esm.js";

translation_registry.add("en-US.repair.clock.title", "Clock");
translation_registry.add("en-US.repair.clock.clocked_in", "Clocked in");
translation_registry.add("en-US.repair.clock.clocked_out", "Not clocked in");

const Clock = defineComponent({
    data() {
        return {
            ticked_seconds: 0,
            interval: /** @type {ReturnType<typeof setInterval> | null} */ (null),
            busy: false,
        };
    },
    computed: {
        /** @returns {{title: string}} */
        screen_info() {
            return {title: this.$t("repair.clock.title")};
        },
        /** @returns {TimerState} */
        timer() {
            return timer_store.shift_timer;
        },
        /** @returns {number} */
        elapsed_seconds() {
            return Math.round((this.timer.elapsed_hours || 0) * 3600) + this.ticked_seconds;
        },
        /** @returns {string} */
        elapsed_display() {
            const total = Math.max(this.elapsed_seconds, 0);
            const h = Math.floor(total / 3600);
            const m = Math.floor((total % 3600) / 60);
            const s = total % 60;
            return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
        },
    },
    watch: {
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
        /** @returns {void} */
        toggle() {
            this.busy = true;
            const root = sf_root(this);
            // `clock_toggle` inherits `base.shopfloor.process`, which requires
            // both a menu and a profile header on every call - see
            // services/root.esm.js's `menu_id_for` for why this page (outside
            // any scenario route) has to resolve its own menu id.
            root.getOdoo({
                usage: "repair_job",
                headers: {
                    "SERVICE-CTX-MENU-ID": String(menu_id_for(this, "repair_job")),
                    "SERVICE-CTX-PROFILE-ID": String(root.profile.id),
                },
            })
                .post("clock_toggle", {})
                .then((/** @type {any} */ result) => {
                    const data = (result && result.data) || {};
                    // Clocking out also stops any running job timer server-
                    // side, and this same response already says so in
                    // `current_job` - applying it here clears the app bar's
                    // job timer now instead of on the next ~60s poll.
                    if (data.shift_timer) {
                        set_shift_timer(data.shift_timer);
                        set_current_job_timer(data.shift_timer.current_job || null);
                    }
                    // No natural `screen_info`/notification slot for a
                    // Cerberus-validated error here (e.g. no employee linked
                    // to this user), so it's surfaced plainly rather than
                    // silently doing nothing - same choice already made by
                    // the drawer's own toggle before this screen existed.
                    const message = result && result.message;
                    if (message && message.message_type === "error") {
                        window.alert(message.body);
                    }
                })
                .finally(() => {
                    this.busy = false;
                });
        },
    },
    template: html`
        <Screen :screen_info="screen_info">
            <v-card outlined class="clock-status" :class="{'clock-status--running': timer.running}">
                <v-card-text class="clock-status__body">
                    <div class="elapsed" v-if="timer.running">{{ elapsed_display }}</div>
                    <div class="elapsed elapsed--idle" v-else>--:--:--</div>
                    <div class="clock-status__label">
                        {{ timer.running ? $t('repair.clock.clocked_in') : $t('repair.clock.clocked_out') }}
                    </div>
                </v-card-text>
            </v-card>
            <div class="button-list button-vertical-list full mt-3">
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-action :action="timer.running ? 'warn' : 'complete'" :loading="busy" @click="toggle">
                            <v-icon left>{{ timer.running ? 'mdi-clock-remove-outline' : 'mdi-clock-check-outline' }}</v-icon>
                            {{ timer.running ? $t('repair.clock.clock_out') : $t('repair.clock.clock_in') }}
                        </btn-action>
                    </v-col>
                </v-row>
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-back />
                    </v-col>
                </v-row>
            </div>
        </Screen>
    `,
});

page_registry.add("clock", Clock, {}, {tag: "app_page"});

export default Clock;
