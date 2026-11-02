/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * One scenario for the whole job.
 *
 * `job_detail` is the hub: the technician picks a job once and comes back
 * here between the timer, the parts and the inspection. Splitting these into
 * separate menu items would mean re-selecting the job every time.
 *
 * Every screen renders the global <searchbar>, which the
 * shopfloor_mobile_camera_scan module has already extended with a camera
 * button -- so scanning works everywhere with no code here.
 *
 * `states` is built in `created()`, against the fully-initialized
 * instance: every state's `enter`/`on_scan` closure calls mixin-provided
 * members like `this.wait_call`/`this.odoo` (a computed property, which
 * `data()` - run before Vue's `initComputed` - could not yet resolve).
 */
/** @import {OdooClient} from "../types/shopfloor-mobile-base" */
/** @import {RepairServiceRecord} from "../components/repair_service_types" */
/**
 * @import {
 *     JobHubRecord,
 *     ClientOptions,
 *     ScannedBarcode,
 *     PartDetailData,
 *     CatalogDetailData,
 *     InspectionLinesData,
 *     InspectionLineDetailData,
 *     ServicesData,
 * } from "./repair_job_scenario_types"
 */
/** @import {JobTimer} from "../services/timer_store.esm.js" */
import {process_registry} from "/shopfloor_mobile_base/static/src/services/process_registry.esm.js";
import {translation_registry} from "/shopfloor_mobile_base/static/src/services/translation_registry.esm.js";
import {extendComponent} from "../services/define_component.esm.js";
import {html} from "../services/html.esm.js";
import {refresh_shift_timer} from "../services/timer_store.esm.js";
import {sf_root} from "../services/root.esm.js";
import {ScenarioBaseMixinClass} from "./scenario_base_mixin.esm.js";

/**
 * @typedef {Object} StateSpec
 * @property {Record<string, unknown>} [display_info]
 * @property {() => void} [enter]
 * @property {() => void} [exit]
 * @property {(scanned: ScannedBarcode) => void} [on_scan]
 */

/**
 * @typedef {Object} JobDetailDataLike
 * @property {ClientOptions} [options]
 */

// Only the scenario's *first* mount in a page load can be the one a browser
// reload produced: the navigation entry keeps reporting "reload" for the
// whole life of the document, so without this flag every later re-creation
// of this component (Home and back into My Jobs, say) would refetch too.
let first_mount_done = false;

/** @returns {boolean} */
function is_browser_reload() {
    const [nav] = /** @type {PerformanceNavigationTiming[]} */ (
        performance.getEntriesByType("navigation")
    );
    return Boolean(nav) && nav.type === "reload";
}

const RepairJob = extendComponent(ScenarioBaseMixinClass, {
    data() {
        return {
            usage: "repair_job",
            initial_state_key: "job_list",
            confirm_finish: false,
            // Kept out of the server payload on purpose: which category chip
            // is lit is pure client state, and echoing it back would make the
            // filter fight the scan-driven searches.
            catalog_category_id: /** @type {number | null} */ (null),
            catalog_search: /** @type {string | null} */ (null),
            // Client state: the 20s services poll must never clear what the
            // technician is in the middle of typing.
            note_draft: "",
            _services_poll_interval: /** @type {ReturnType<typeof setInterval> | null} */ (null),
            _job_list_poll_interval: /** @type {ReturnType<typeof setInterval> | null} */ (null),
        };
    },

    created() {
        /** @type {Record<string, StateSpec>} */
        const states = {
            init: {
                enter: () => {
                    this.wait_call(this.odoo.get("jobs"));
                },
            },
            job_list: {
                display_info: {
                    title: this.$t("repair.jobs.my_jobs"),
                    scan_placeholder: this.$t("repair.jobs.scan_placeholder"),
                },
                // New and newly-assigned jobs are created on the desktop while
                // a technician is sitting here, so the list refetches silently
                // on entry (which is also the only thing that refreshes it on
                // a browser reload, which otherwise redisplays `$storage`) and
                // keeps polling for as long as the screen stays open - same
                // approach as `services` below.
                enter: () => {
                    this._fetch_job_list(true);
                    this._start_job_list_polling();
                },
                exit: () => {
                    this._stop_job_list_polling();
                },
                on_scan: (scanned) => {
                    this.wait_call(this.odoo.get(["scan", scanned.text]));
                },
            },
            job_detail: {
                display_info: {
                    title: this.$t("repair.jobs.job"),
                    scan_placeholder: this.$t("repair.jobs.scan_placeholder"),
                },
                on_scan: (scanned) => {
                    this.wait_call(this.odoo.get(["scan", scanned.text]));
                },
            },
            services: {
                display_info: {
                    title: this.$t("repair.jobs.services"),
                    scan_placeholder: this.$t("repair.jobs.scan_placeholder"),
                },
                // A service's Accepted checkbox (and estimated time) can be
                // changed from the desktop Services tab at any moment while
                // a technician is sitting on this screen - `enter` refetches
                // whenever the screen is (re)entered, including on a plain
                // browser reload (which otherwise just redisplays whatever
                // was last persisted to `$storage`, per `state_get_data`),
                // and the poll started here keeps it current for as long as
                // the technician stays on the screen without navigating
                // away at all.
                enter: () => {
                    // Silent: whatever navigated here (a job-row click, the
                    // "Services" button) already shows its own loading
                    // state via `wait_call`'s own fetch; this is purely a
                    // freshness top-up (and the only thing that runs at all
                    // on a plain browser reload, which re-hydrates from
                    // `$storage` with no network call otherwise) and
                    // shouldn't cause a second visible flicker right after.
                    this._fetch_services(true);
                    this._start_services_polling();
                },
                exit: () => {
                    this._stop_services_polling();
                },
                on_scan: (scanned) => {
                    this.wait_call(this.odoo.get(["scan", scanned.text]));
                },
            },
            parts: {
                display_info: {
                    title: this.$t("repair.jobs.parts"),
                    scan_placeholder: this.$t("repair.parts.scan_placeholder"),
                },
                on_scan: (scanned) => {
                    this.wait_call(
                        this.odoo.post(["job", this.job_id, "scan_part"], {
                            barcode: scanned.text,
                        })
                    );
                },
            },
            part_detail: {
                display_info: {
                    title: this.$t("repair.parts.detail"),
                    scan_placeholder: this.$t("repair.parts.scan_lot"),
                },
                // A scan here is the lot/serial for the part on screen.
                on_scan: (scanned) => {
                    const record = /** @type {PartDetailData} */ (this.state.data).record;
                    this.wait_call(
                        this.odoo.post(["part", record.id, "set_quantity"], {
                            quantity: record.quantity_demand,
                            lot_name: scanned.text,
                        })
                    );
                },
            },
            catalog_search: {
                display_info: {
                    title: this.$t("repair.jobs.catalog"),
                    scan_placeholder: this.$t("repair.catalog.scan_placeholder"),
                },
                on_scan: (scanned) => {
                    this.catalog_search = scanned.text;
                    this.go_catalog(1);
                },
            },
            catalog_detail: {
                display_info: {title: this.$t("repair.catalog.detail")},
            },
            inspection_list: {
                display_info: {title: this.$t("repair.jobs.inspections")},
            },
            inspection_lines: {
                display_info: {title: this.$t("repair.inspection.checklist")},
            },
            inspection_line_detail: {
                display_info: {title: this.$t("repair.inspection.item")},
            },
        };
        this.states = states;
    },

    // A browser reload lands back on whatever state the URL names, and
    // shopfloor_mobile_base's `beforeMount` (scenario/mixins.esm.js) just
    // re-hydrates that state from `$storage` - no network call unless the
    // state has its own `enter`. So a technician who reloads to see a new
    // job would get the same stale list back. Treat the reload as "fetch
    // this screen again from the server" instead.
    mounted() {
        if (first_mount_done) {
            return;
        }
        first_mount_done = true;
        if (is_browser_reload()) {
            this._refetch_current_state();
        }
    },

    beforeDestroy() {
        this._stop_services_polling();
        this._stop_job_list_polling();
    },

    computed: {
        /**
         * The job the technician is standing on, wherever they are.
         * Every state carries it under `record` or `job`, so navigation never
         * has to thread an id through the router.
         *
         * @returns {Partial<JobHubRecord>}
         */
        job() {
            const data = /** @type {Record<string, any>} */ (this.state.data || {});
            if (this.state_is("job_detail") || this.state_is("parts")) {
                return data.record || {};
            }
            return data.job || {};
        },
        /** @returns {unknown} */
        job_id() {
            return this.job.id;
        },
        /** @returns {ClientOptions} */
        client_options() {
            const stored = /** @type {JobDetailDataLike} */ (this.state_get_data("job_detail") || {});
            return (
                stored.options || {
                    allow_repair_end: false,
                    require_photo_on_fail: false,
                }
            );
        },
        /** @returns {unknown} */
        inspection_id() {
            const data = /** @type {Record<string, any>} */ (this.state.data || {});
            if (this.state_is("inspection_lines")) {
                return data.record.id;
            }
            if (this.state_is("inspection_line_detail")) {
                return data.inspection.id;
            }
            return null;
        },
        /** @returns {string} */
        back_label() {
            if (this.state_in(["job_detail", "services", "part_detail", "catalog_detail", "inspection_line_detail"])) {
                return this.$t("repair.nav.back");
            }
            return this.$t("repair.nav.back_to_job");
        },
    },

    methods: {
        /** @returns {string} */
        screen_title() {
            const job = this.job;
            if (_.isEmpty(job)) {
                return this.$t("repair.jobs.my_jobs");
            }
            return job.vehicle_description
                ? job.vehicle_description + " · " + job.name
                : job.name || "";
        },

        /** @returns {{record: Partial<JobHubRecord>, identifier: string} | null} */
        current_doc() {
            const job = this.job;
            if (_.isEmpty(job)) {
                return null;
            }
            return {record: job, identifier: job.name || ""};
        },

        // -- navigation ---------------------------------------------------

        /** @returns {void} */
        go_job_list() {
            this.wait_call(this.odoo.get("jobs"));
        },

        /** @returns {void} */
        go_home() {
            this.$router.push({name: "home"});
        },

        /** @returns {void | Promise<unknown>} */
        go_back_in_flow() {
            if (this.state_is("part_detail")) {
                return this.go_parts();
            }
            if (this.state_is("catalog_detail")) {
                return this.go_catalog();
            }
            if (this.state_is("inspection_line_detail")) {
                return this.wait_call(this.odoo.get(["inspection", this.inspection_id]));
            }
            if (this.state_is("inspection_lines")) {
                return this.go_inspections();
            }
            if (this.state_is("job_detail")) {
                return this.go_job_list();
            }
            // Services is now the screen "My Jobs" opens directly into, so its
            // own Back returns there too, same as the hub's - not to the hub
            // below, which is one tap further in from here (see
            // `go_job_hub`), not where a services-screen Back came from.
            if (this.state_is("services")) {
                return this.go_job_list();
            }
            return this.open_job(/** @type {JobHubRecord} */ (this.job));
        },

        // Used by the fallback above (Parts/Catalog/Inspections list "Back"
        // returns to the hub, where the buttons to reach them live) - kept
        // pointed at the job hub itself, NOT at services, precisely so that
        // fallback still lands where those screens were actually opened from.
        /**
         * @param {{id: unknown}} record
         * @returns {void}
         */
        open_job(record) {
            this.wait_call(this.odoo.get(["job", record.id]));
        },

        // "My Jobs" opens straight into a job's services now - that's the
        // primary thing a technician does with a job (diagnostics timers,
        // whether it's still draft with just an accepted diagnostics line, or
        // already confirmed). The job hub (Start Repair/Parts/Catalog/
        // Inspections/Finish) is one tap away via "Job Details" below.
        /**
         * @param {{id: unknown}} record
         * @returns {void}
         */
        open_job_services(record) {
            this.wait_call(this.odoo.get(["job", record.id, "services"]));
        },

        /** @returns {void} */
        go_services() {
            this.wait_call(this.odoo.get(["job", this.job_id, "services"]));
        },

        /** @returns {void} */
        go_job_hub() {
            this.wait_call(this.odoo.get(["job", this.job_id]));
        },

        // Re-asks the server for the screen currently shown, through the same
        // call that normally opens it. `wait_call` answering with the state
        // already on screen only reloads its data (`on_call_success`), so this
        // never re-runs the state's `enter`. `part_detail`/`catalog_detail`
        // are filled client-side from their parent list and have no endpoint
        // of their own, so they reload that list instead.
        /** @returns {void} */
        _refetch_current_state() {
            const data = /** @type {Record<string, any>} */ (this.state.data || {});
            const state_key = this.current_state_key;
            // `services` and `job_list` already refetch in their own `enter`
            // (which a reload runs too); `init` fetches the list itself.
            if (["services", "job_list", "init"].includes(state_key)) {
                return;
            }
            if (!this.job_id) {
                this.go_job_list();
                return;
            }
            switch (state_key) {
                case "job_detail":
                    this.go_job_hub();
                    break;
                case "parts":
                case "part_detail":
                    this.go_parts();
                    break;
                case "catalog_search":
                    this.go_catalog(data.page);
                    break;
                case "catalog_detail":
                    this.go_catalog(1);
                    break;
                case "inspection_list":
                    this.go_inspections();
                    break;
                case "inspection_lines":
                    this.open_inspection(data.record);
                    break;
                case "inspection_line_detail":
                    this.open_inspection_line(data.record);
                    break;
            }
        },

        // Refetches the accepted-services list for whichever job is current and
        // replaces `services`' stored data with it - `state_reset_data` before
        // `state_set_data` because the latter deep-merges by default (lodash
        // `_.merge`), which for an array only overwrites matching indices and
        // never drops the tail, so a service that got un-accepted (removed
        // server-side) would otherwise linger in the list forever. Deliberately
        // not routed through `wait_call`/`state_to`: this can fire from a
        // silent poll as often as every 20s, and going through the normal
        // navigation path would re-trigger this same state's `enter` (and, via
        // the global fetch events, flicker the loading indicator) every time.
        /**
         * @param {boolean} [silent]
         * @returns {void}
         */
        _fetch_services(silent = false) {
            const job_id = this.job_id;
            if (!job_id) {
                return;
            }
            const client = silent ? this._silent_repair_job_client() : this.odoo;
            client
                .get(["job", job_id, "services"])
                .then((/** @type {{data?: {services?: ServicesData}}} */ result) => {
                    // Every endpoint wraps its payload one level deeper than it
                    // looks: `_response(next_state="services", data=...)`
                    // (shopfloor_base/services/service.py) puts it under a key
                    // named after the state itself - `result.data.services`,
                    // not `result.data` - so a state can return to different
                    // states with different shapes. Missing this produced
                    // `{job: undefined, records: undefined}`, silently wiping
                    // out the real list on every poll.
                    const data = result && result.data && result.data.services;
                    if (!data) {
                        return;
                    }
                    this.state_reset_data("services");
                    this.state_set_data({job: data.job, records: data.records, notes: data.notes}, "services");
                })
                .catch(() => {});
        },

        // Same client `refresh_shift_timer` (services/timer_store.esm.js)
        // builds for its own silent poll - `in_background: true` skips the
        // global `fetchStart`/`fetchEnd` loading indicator, which would
        // otherwise flicker on every screen once every poll interval.
        /** @returns {OdooClient} */
        _silent_repair_job_client() {
            const root = sf_root(this);
            return root.getOdoo({
                usage: "repair_job",
                in_background: true,
                headers: {
                    "SERVICE-CTX-MENU-ID": String(this.menu_item_id),
                    "SERVICE-CTX-PROFILE-ID": String(root.profile.id),
                },
            });
        },

        // Same idea as `_fetch_services`, for "My Jobs": the response for
        // `/jobs` is `{data: {job_list: {records}}}`, replaced wholesale (see
        // `_fetch_services` for why `state_reset_data` comes first), and kept
        // off `wait_call` so a silent poll neither flickers the loading
        // indicator nor re-runs this state's `enter`.
        /**
         * @param {boolean} [silent]
         * @returns {void}
         */
        _fetch_job_list(silent = false) {
            const client = silent ? this._silent_repair_job_client() : this.odoo;
            client
                .get("jobs")
                .then((/** @type {{data?: {job_list?: {records?: unknown[]}}}} */ result) => {
                    const data = result && result.data && result.data.job_list;
                    // Leaving the screen while the request was in flight must
                    // not write a list into a state nobody is looking at.
                    if (!data || !this.state_is("job_list")) {
                        return;
                    }
                    this.state_reset_data("job_list");
                    this.state_set_data({records: data.records}, "job_list");
                })
                .catch(() => {});
        },

        /** @returns {void} */
        _start_job_list_polling() {
            this._stop_job_list_polling();
            this._job_list_poll_interval = setInterval(() => {
                // A backgrounded tab has nobody to show the list to.
                if (this.state_is("job_list") && !document.hidden) {
                    this._fetch_job_list(true);
                }
            }, 30000);
        },

        /** @returns {void} */
        _stop_job_list_polling() {
            if (this._job_list_poll_interval) {
                clearInterval(this._job_list_poll_interval);
                this._job_list_poll_interval = null;
            }
        },

        /** @returns {void} */
        _start_services_polling() {
            this._stop_services_polling();
            this._services_poll_interval = setInterval(() => {
                if (this.state_is("services")) {
                    this._fetch_services(true);
                }
            }, 20000);
        },

        /** @returns {void} */
        _stop_services_polling() {
            if (this._services_poll_interval) {
                clearInterval(this._services_poll_interval);
                this._services_poll_interval = null;
            }
        },

        /** @returns {void} */
        go_parts() {
            this.wait_call(this.odoo.get(["job", this.job_id, "parts"]));
        },

        /** @returns {void} */
        go_inspections() {
            this.wait_call(this.odoo.get(["job", this.job_id, "inspections"]));
        },

        // -- job actions --------------------------------------------------

        /** @returns {void} */
        start_repair() {
            this.wait_call(this.odoo.post(["job", this.job_id, "start_repair"], {}));
        },

        /** @returns {void} */
        ask_finish() {
            this.confirm_finish = true;
        },

        /** @returns {void} */
        finish() {
            this.confirm_finish = false;
            this.wait_call(this.odoo.post(["job", this.job_id, "finish"], {}));
        },

        // -- notes -----------------------------------------------------------

        /** @returns {void} */
        save_note() {
            const note = this.note_draft.trim();
            if (!note) {
                return;
            }
            this.wait_call(this.odoo.post(["job", this.job_id, "add_note"], {note})).then(() => {
                this.note_draft = "";
            });
        },

        // -- services --------------------------------------------------------

        /**
         * @param {RepairServiceRecord} service
         * @returns {void}
         */
        service_timer_start(service) {
            this.wait_call(
                this.odoo.post(["job", this.job_id, "service", service.id, "timer_start"], {})
            ).then(() => this._refresh_shift_timer_now());
        },

        /**
         * @param {RepairServiceRecord} service
         * @returns {void}
         */
        service_timer_stop(service) {
            this.wait_call(
                this.odoo.post(["job", this.job_id, "service", service.id, "timer_stop"], {})
            ).then(() => this._refresh_shift_timer_now());
        },

        // Stop button on a "My Jobs" card. Not `wait_call`: `timer_stop`
        // answers with the services screen, and the technician should stay
        // on the list.
        /**
         * @param {JobTimer} timer
         * @returns {void}
         */
        job_list_timer_stop(timer) {
            this.odoo
                .post(["job", timer.repair_id, "service", timer.service_id, "timer_stop"], {})
                .then(() => {
                    this._refresh_shift_timer_now();
                    this._fetch_job_list(true);
                })
                .catch(() => {});
        },

        // Without this, starting or stopping a service's timer here wouldn't
        // show up in the app bar's compact job timer until
        // app_bar_actions.esm.js's own ~60s poll happened to catch up -
        // nothing else publishes it eagerly now that the job-level timer (and
        // its own eager publish via `on_job_change`) is gone.
        /** @returns {void} */
        _refresh_shift_timer_now() {
            refresh_shift_timer(this).catch(() => {});
        },

        // -- parts ---------------------------------------------------------

        /**
         * @param {{id: unknown}} part
         * @returns {void}
         */
        open_part(part) {
            // The parts screen already holds everything the detail screen
            // needs, so switch locally instead of asking the server again.
            this.state_set_data({record: part, job: this.job}, "part_detail");
            this.state_to("part_detail");
        },

        /**
         * @param {{quantity: number, lot_name: string | null}} payload
         * @returns {void}
         */
        set_quantity(payload) {
            const record = /** @type {PartDetailData} */ (this.state.data).record;
            this.wait_call(
                this.odoo.post(["part", record.id, "set_quantity"], {
                    quantity: payload.quantity,
                    lot_name: payload.lot_name,
                })
            );
        },

        /**
         * @param {{id: unknown}} part
         * @returns {void}
         */
        consume_all(part) {
            this.wait_call(this.odoo.post(["part", part.id, "consume_all"], {}));
        },

        /**
         * @param {{id: unknown}} part
         * @returns {void}
         */
        reset_part(part) {
            this.wait_call(this.odoo.post(["part", part.id, "reset"], {}));
        },

        // -- catalog --------------------------------------------------------

        /**
         * @param {number} [page]
         * @returns {void}
         */
        go_catalog(page) {
            /** @type {Record<string, unknown>} */
            const params = {page: page || 1};
            if (this.catalog_search) {
                params.search = this.catalog_search;
            }
            if (this.catalog_category_id) {
                params.category_id = this.catalog_category_id;
            }
            this.wait_call(this.odoo.get(["job", this.job_id, "catalog"], params));
        },

        /**
         * @param {number} page
         * @returns {void}
         */
        go_catalog_page(page) {
            this.go_catalog(page);
        },

        /**
         * @param {number | null} category_id
         * @returns {void}
         */
        filter_catalog_category(category_id) {
            this.catalog_category_id = category_id || null;
            this.go_catalog(1);
        },

        /**
         * @param {{id: unknown}} product
         * @returns {void}
         */
        open_catalog_product(product) {
            this.state_set_data({record: product, job: this.job}, "catalog_detail");
            this.state_to("catalog_detail");
        },

        /**
         * @param {{quantity: number, consume_now: boolean}} payload
         * @returns {void}
         */
        add_part(payload) {
            const product = /** @type {CatalogDetailData} */ (this.state.data).record;
            this.wait_call(
                this.odoo.post(["job", this.job_id, "add_part"], {
                    product_id: product.id,
                    quantity: payload.quantity,
                    consume_now: payload.consume_now,
                })
            );
        },

        // -- inspections ------------------------------------------------------

        /**
         * @param {{template_id: unknown, odometer: number}} payload
         * @returns {void}
         */
        create_inspection(payload) {
            this.wait_call(this.odoo.post(["job", this.job_id, "inspection_create"], payload));
        },

        /**
         * @param {{id: unknown}} inspection
         * @returns {void}
         */
        open_inspection(inspection) {
            this.wait_call(this.odoo.get(["inspection", inspection.id]));
        },

        /**
         * @param {{id: unknown}} line
         * @returns {void}
         */
        open_inspection_line(line) {
            this.wait_call(this.odoo.get(["inspection_line", line.id]));
        },

        /**
         * @param {Record<string, unknown>} payload
         * @returns {void}
         */
        grade_line(payload) {
            const line = /** @type {InspectionLinesData} */ (this.state.data).record;
            this.wait_call(this.odoo.post(["inspection_line", line.id, "grade"], payload));
        },

        /**
         * @param {{id: unknown, value: number}} payload
         * @returns {void}
         */
        set_measurement(payload) {
            this.wait_call(
                this.odoo.post(["measurement", payload.id, "set_value"], {
                    value: payload.value,
                })
            );
        },

        /**
         * @param {Record<string, unknown>} payload
         * @returns {void}
         */
        add_photo(payload) {
            const line = /** @type {InspectionLineDetailData} */ (this.state.data).record;
            this.wait_call(this.odoo.post(["inspection_line", line.id, "photo"], payload));
        },

        /** @returns {void} */
        confirm_inspection() {
            this.wait_call(this.odoo.post(["inspection", this.inspection_id, "confirm"], {}));
        },
    },

    template: html`
        <Screen :screen_info="screen_info">
            <searchbar
                v-if="state.on_scan"
                v-on:found="on_scan"
                :input_placeholder="search_input_placeholder"
                />

            <!-- ============ job list ============ -->
            <div v-if="state_is('job_list')">
                <p class="empty" v-if="!state.data.records.length">
                    {{ $t('repair.jobs.empty') }}
                </p>
                <repair-job-row
                    v-for="rec in state.data.records"
                    :key="make_state_component_key(['job', rec.id])"
                    :record="rec"
                    v-on:select="open_job_services"
                    v-on:stop-timer="job_list_timer_stop"
                    />
            </div>

            <!-- ============ job hub ============ -->
            <div v-if="state_is('job_detail')" class="job-hub">
                <v-row>
                    <v-col cols="12" md="6">
                        <repair-job-card :record="job" />
                        <!-- Read-only rollup: time tracking now happens per
                             service (see the Services screen below), so this no
                             longer starts/stops anything itself. -->
                        <v-card outlined class="repair-timer-summary">
                            <v-card-text>
                                {{ $t('repair.timer.total') }}: {{ job.timer.total_hours.toFixed(2) }} h
                            </v-card-text>
                        </v-card>
                    </v-col>
                    <v-col cols="12" md="6">
                        <div class="button-list button-vertical-list full">
                            <!-- Not shown while draft: the job can be open here
                                 for diagnostics (an accepted service is enough
                                 to show up on My Jobs), but actual repair work
                                 waits on the office confirming the repair. -->
                            <v-row align="center" v-if="job.state === 'confirmed'">
                                <v-col class="text-center" cols="12">
                                    <btn-action action="complete" @click="start_repair">
                                        <v-icon left>mdi-wrench</v-icon>{{ $t('repair.jobs.start_repair') }}
                                    </btn-action>
                                </v-col>
                            </v-row>
                            <v-row align="center">
                                <v-col class="text-center" cols="12">
                                    <btn-action @click="go_services">
                                        <v-icon left>mdi-timer-outline</v-icon>
                                        {{ $t('repair.jobs.services') }}
                                    </btn-action>
                                </v-col>
                            </v-row>
                            <v-row align="center">
                                <v-col class="text-center" cols="12">
                                    <btn-action @click="go_parts">
                                        <v-icon left>mdi-package-variant-closed</v-icon>
                                        {{ $t('repair.jobs.parts') }}
                                        ({{ job.parts_done }}/{{ job.parts_total }})
                                    </btn-action>
                                </v-col>
                            </v-row>
                            <v-row align="center">
                                <v-col class="text-center" cols="12">
                                    <btn-action @click="go_catalog()">
                                        <v-icon left>mdi-magnify</v-icon>{{ $t('repair.jobs.catalog') }}
                                    </btn-action>
                                </v-col>
                            </v-row>
                            <v-row align="center">
                                <v-col class="text-center" cols="12">
                                    <btn-action @click="go_inspections">
                                        <v-icon left>mdi-clipboard-check-outline</v-icon>
                                        {{ $t('repair.jobs.inspections') }}
                                        <span v-if="job.inspection_total">
                                            ({{ job.inspection_graded }}/{{ job.inspection_total }})
                                        </span>
                                    </btn-action>
                                </v-col>
                            </v-row>
                            <v-row align="center"
                                   v-if="client_options.allow_repair_end && job.state === 'under_repair'">
                                <v-col class="text-center" cols="12">
                                    <btn-action action="warn" @click="ask_finish">
                                        <v-icon left>mdi-flag-checkered</v-icon>{{ $t('repair.jobs.finish') }}
                                    </btn-action>
                                </v-col>
                            </v-row>
                        </div>
                    </v-col>
                </v-row>
                <v-dialog v-model="confirm_finish" max-width="480">
                    <v-card>
                        <v-card-title>{{ $t('repair.jobs.finish') }}</v-card-title>
                        <v-card-text>{{ $t('repair.jobs.finish_confirm') }}</v-card-text>
                        <v-card-actions>
                            <v-btn text @click="confirm_finish = false">{{ $t('btn.cancel.title') }}</v-btn>
                            <v-spacer />
                            <v-btn color="warning" @click="finish">{{ $t('repair.jobs.finish') }}</v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>
            </div>

            <!-- ============ services ============ -->
            <div v-if="state_is('services')">
                <repair-job-card :record="state.data.job" :compact="true" />
                <repair-services-list
                    :records="state.data.records"
                    v-on:timer-start="service_timer_start"
                    v-on:timer-stop="service_timer_stop"
                    />
                <v-card outlined class="repair-notes">
                    <v-card-text>
                        <div class="repair-notes-existing" v-if="state.data.notes">{{ state.data.notes }}</div>
                        <v-textarea
                            v-model="note_draft"
                            :label="$t('repair.notes.placeholder')"
                            outlined
                            auto-grow
                            rows="2"
                            hide-details
                            />
                        <btn-action :disabled="!note_draft.trim()" @click="save_note">
                            <v-icon left>mdi-note-plus-outline</v-icon>{{ $t('repair.notes.add') }}
                        </btn-action>
                    </v-card-text>
                </v-card>
                <div class="button-list button-vertical-list full">
                    <v-row align="center">
                        <v-col class="text-center" cols="12">
                            <btn-action @click="go_job_hub">
                                <v-icon left>mdi-briefcase-outline</v-icon>
                                {{ $t('repair.jobs.job_details') }}
                            </btn-action>
                        </v-col>
                    </v-row>
                </div>
            </div>

            <!-- ============ parts ============ -->
            <div v-if="state_is('parts')">
                <repair-job-card :record="state.data.record" :compact="true" />
                <repair-parts-list
                    :parts="state.data.parts"
                    v-on:select="open_part"
                    v-on:consume-all="consume_all"
                    v-on:reset="reset_part"
                    />
                <div class="button-list button-vertical-list full">
                    <v-row align="center">
                        <v-col class="text-center" cols="12">
                            <btn-action @click="go_catalog()">
                                <v-icon left>mdi-plus-box</v-icon>{{ $t('repair.jobs.catalog') }}
                            </btn-action>
                        </v-col>
                    </v-row>
                </div>
            </div>

            <div v-if="state_is('part_detail')">
                <repair-part-detail
                    :record="state.data.record"
                    :key="make_state_component_key(['part', state.data.record.id])"
                    v-on:confirm="set_quantity"
                    v-on:reset="reset_part(state.data.record)"
                    />
            </div>

            <!-- ============ catalog ============ -->
            <div v-if="state_is('catalog_search')">
                <repair-catalog-browser
                    :records="state.data.records"
                    :categories="state.data.categories"
                    :size="state.data.size"
                    :page="state.data.page"
                    :page_size="state.data.page_size"
                    :category_id="catalog_category_id"
                    v-on:select="open_catalog_product"
                    v-on:filter-category="filter_catalog_category"
                    v-on:page="go_catalog_page"
                    />
            </div>

            <div v-if="state_is('catalog_detail')">
                <repair-catalog-detail
                    :record="state.data.record"
                    :key="make_state_component_key(['product', state.data.record.id])"
                    v-on:add="add_part"
                    />
            </div>

            <!-- ============ inspections ============ -->
            <div v-if="state_is('inspection_list')">
                <repair-job-card :record="state.data.job" :compact="true" />
                <repair-inspection-list
                    :records="state.data.records"
                    :templates="state.data.templates"
                    :default_odometer="state.data.default_odometer"
                    :odometer_unit="state.data.odometer_unit"
                    v-on:open="open_inspection"
                    v-on:start="create_inspection"
                    />
            </div>

            <div v-if="state_is('inspection_lines')">
                <repair-inspection-checklist
                    :lines="state.data.lines"
                    v-on:select="open_inspection_line"
                    />
                <div class="button-list button-vertical-list full">
                    <v-row align="center" v-if="state.data.record.state === 'draft'">
                        <v-col class="text-center" cols="12">
                            <btn-action action="complete"
                                        :disabled="state.data.record.graded_count < state.data.record.line_count"
                                        @click="confirm_inspection">
                                <v-icon left>mdi-check-decagram</v-icon>
                                {{ $t('repair.inspection.complete') }}
                            </btn-action>
                        </v-col>
                    </v-row>
                </div>
            </div>

            <div v-if="state_is('inspection_line_detail')">
                <repair-inspection-line-form
                    :record="state.data.record"
                    :choices="state.data.choices"
                    :require_photo_on_fail="client_options.require_photo_on_fail"
                    :key="make_state_component_key(['line', state.data.record.id])"
                    v-on:grade="grade_line"
                    v-on:measure="set_measurement"
                    v-on:photo="add_photo"
                    />
            </div>

            <!-- ============ navigation ============ -->
            <div class="button-list button-vertical-list full">
                <!-- On the job list itself "back" would duplicate Home below,
                     with nowhere else to go anyway - every other state,
                     job_detail included, shows both Back and Home together. -->
                <v-row align="center" v-if="!state_is('job_list')">
                    <v-col class="text-center" cols="12">
                        <btn-action action="back" :router_back="false" @click="go_back_in_flow">
                            <v-icon left>mdi-keyboard-backspace</v-icon>{{ back_label }}
                        </btn-action>
                    </v-col>
                </v-row>
                <v-row align="center">
                    <v-col class="text-center" cols="12">
                        <btn-action action="cancel" @click="go_home">
                            <v-icon left>mdi-home-outline</v-icon>{{ $t('repair.jobs.home') }}
                        </btn-action>
                    </v-col>
                </v-row>
            </div>
        </Screen>
    `,
});

process_registry.add("repair_job", RepairJob);

/** @type {Record<string, string>} */
const T = {
    "repair.jobs.my_jobs": "My Jobs",
    "repair.jobs.job": "Job",
    "repair.jobs.empty": "No jobs assigned to you right now.",
    "repair.jobs.scan_placeholder": "Scan work order, plate or VIN",
    "repair.jobs.start_repair": "Start repair",
    "repair.jobs.services": "Services",
    "repair.jobs.job_details": "Job Details",
    "repair.services.empty": "No accepted services on this job yet.",
    "repair.services.estimated": "Estimated",
    "repair.notes.placeholder": "Add a note for the office",
    "repair.notes.add": "Add note",
    "repair.jobs.parts": "Parts",
    "repair.jobs.catalog": "Add part from catalog",
    "repair.jobs.inspections": "Inspections",
    "repair.jobs.finish": "Finish repair",
    "repair.jobs.finish_confirm":
        "This completes the repair and consumes the parts you recorded. It cannot be undone from here.",
    "repair.concern": "Customer concern",
    "repair.nav.back": "Back",
    "repair.nav.back_to_job": "Back to job",
    "repair.timer.start": "Start work",
    "repair.timer.stop": "Stop work",
    "repair.timer.mine": "Mine",
    "repair.timer.total": "Total",
    "repair.parts.empty": "No parts on this job yet.",
    "repair.parts.use_all": "Used all",
    "repair.parts.added_here": "Added here",
    "repair.parts.detail": "Part",
    "repair.parts.demand": "Planned",
    "repair.parts.used": "Used",
    "repair.parts.lot": "Lot / serial number",
    "repair.parts.record": "Record usage",
    "repair.parts.reset": "Not used after all",
    "repair.parts.scan_placeholder": "Scan a part",
    "repair.parts.scan_lot": "Scan lot / serial",
    "repair.catalog.all": "All",
    "repair.catalog.empty": "Nothing matches that search.",
    "repair.catalog.detail": "Add part",
    "repair.catalog.quantity": "Quantity",
    "repair.catalog.consume_now": "Mark as used straight away",
    "repair.catalog.add": "Add to job",
    "repair.catalog.scan_placeholder": "Scan or search a part",
    "repair.catalog.billing_notice":
        "This goes on the customer's quote for the service advisor to review.",
    "repair.inspection.new": "New inspection",
    "repair.inspection.template": "Checklist",
    "repair.inspection.odometer": "Odometer",
    "repair.inspection.odometer_hint": "Required — the reading is written to the vehicle history.",
    "repair.inspection.start": "Start inspection",
    "repair.inspection.checklist": "Inspection",
    "repair.inspection.item": "Checklist item",
    "repair.inspection.grade": "Grade",
    "repair.inspection.conditions": "What did you find?",
    "repair.inspection.actions": "Recommended",
    "repair.inspection.note": "Note for the customer",
    "repair.inspection.measurements": "Measurements",
    "repair.inspection.not_measured": "not measured",
    "repair.inspection.add_photo": "Take photo",
    "repair.inspection.photo_required": "A photo is required before grading this as a problem.",
    "repair.inspection.complete": "Complete inspection",
    "repair.inspection.remaining": "{count} item(s) still to grade",
    "repair.inspection.all_graded": "Everything graded — ready to complete.",
    "repair.inspection.other": "Other",
};
_.each(T, (/** @type {string} */ value, /** @type {string} */ key) => {
    translation_registry.add("en-US." + key, value);
});

export default RepairJob;
