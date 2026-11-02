/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The one module `templates/assets.xml` loads; the browser fetches the rest
 * through these imports. Every import below is for its registration side
 * effect (`Vue.component(...)`, `page_registry.add`, `process_registry.add`),
 * in this exact order: components and pages first, the scenario last, since
 * its template references every component above by tag name and expects
 * them already registered on Vue. ES module imports are evaluated in the
 * order they are written, so this order is the registration order.
 */
import "./components/severity.esm.js";
import "./components/severity_chip.esm.js";
import "./components/severity_selector.esm.js";
import "./components/job_timer_compact.esm.js";
import "./components/shift_timer.esm.js";
import "./components/repair_job_card.esm.js";
import "./components/repair_job_row.esm.js";
import "./components/repair_timer.esm.js";
import "./components/repair_services_list.esm.js";
import "./components/repair_parts_list.esm.js";
import "./components/repair_part_detail.esm.js";
import "./components/repair_catalog_browser.esm.js";
import "./components/repair_catalog_detail.esm.js";
import "./components/repair_measurement_grid.esm.js";
import "./components/repair_photo_capture.esm.js";
import "./components/repair_inspection_checklist.esm.js";
import "./components/repair_inspection_list.esm.js";
import "./components/repair_inspection_line_form.esm.js";
import "./components/repair_job_picker.esm.js";
import "./components/repair_timesheet_edit_form.esm.js";
import "./components/repair_timesheet_break_form.esm.js";
import "./components/repair_timesheet_split_form.esm.js";
import "./components/repair_break_edit_form.esm.js";
import "./components/repair_attendance_edit_form.esm.js";
import "./components/app_bar_actions.esm.js";
import "./components/nav_items_extra.esm.js";
import "./components/user_session_detail.esm.js";
import "./services/session_guard.esm.js";
import "./services/default_profile.esm.js";
import "./pages/timesheets.esm.js";
import "./pages/clock.esm.js";
import "./pages/home.esm.js";
import "./pages/profile.esm.js";
import "./scenario/repair_job.esm.js";
