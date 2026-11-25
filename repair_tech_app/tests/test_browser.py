# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The app in Chrome, end to end: a technician's taps on the built frontend,
through the real facades, checked in the database afterwards.

Each test opens a screen, waits for the app to be up, runs a script that
taps through it like a person would (finding buttons by their visible label
or accessible name), and logs "test successful". Any console error fails
the test. Skipped until the frontend is built (`odoo module build`).
"""

import pathlib
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import file_path

# Prepended to every script: until(), control(), tap(), row(), type(), seen().
HELPERS = pathlib.Path(__file__).with_name("ui_helpers.js").read_text()

READY = "document.documentElement.dataset.appReady !== undefined"


@tagged("post_install", "-at_install")
class TestTechAppInChrome(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.tech = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Chrome Tech",
                    "login": "chrome.tech",
                    "password": "chrome.tech",
                    "email": "chrome.tech@example.com",
                    "tz": "UTC",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref("repair_tech_app.group_shop_technician").id,
                            ],
                        )
                    ],
                }
            )
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Chrome Tech", "user_id": cls.tech.id}
        )
        cls.project = cls.env["project.project"].create(
            {"name": "Chrome Labor", "allow_timesheets": True}
        )
        cls.env.company.repair_timesheet_project_id = cls.project
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Chromeco"})
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": cls.env["fleet.vehicle.model"]
                .create({"name": "Roadster", "brand_id": brand.id})
                .id,
                "license_plate": "CHR-042",
                "odometer_unit": "miles",
            }
        )
        cls.customer = cls.env["res.partner"].create({"name": "Road Runner"})
        cls.part = cls.env["product.product"].create(
            {
                "name": "Chrome Pad Set",
                "type": "consu",
                "is_storable": True,
                "default_code": "CH-PAD",
                "barcode": "RTA-CHROME-PAD",
                "purchase_ok": True,
            }
        )
        cls.labor = cls.env["product.product"].create(
            {"name": "Chrome Brake Job", "type": "service"}
        )
        cls.repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.customer.id,
                "vehicle_id": cls.vehicle.id,
                "technician_id": cls.tech.id,
                "odometer_in": 1234,
                "customer_concern": "<p>Grinds when stopping</p>",
            }
        )
        cls.move = cls.env["stock.move"].create(
            {
                "repair_id": cls.repair.id,
                "repair_line_type": "add",
                "product_id": cls.part.id,
                "product_uom_qty": 2.0,
                "product_uom": cls.part.uom_id.id,
            }
        )
        cls.service = cls.env["repair.service"].create(
            {"repair_id": cls.repair.id, "product_id": cls.labor.id, "accepted": True}
        )
        cls.repair._action_repair_confirm()

    def setUp(self):
        super().setUp()
        try:
            file_path("repair_tech_app/static/dist/.vite/manifest.json")
        except FileNotFoundError:
            self.skipTest("repair_tech_app is not built: run `odoo module build`")

    def run_app(self, path, script, timeout=60):
        self.browser_js(
            f"/repair-tech/app{path}",
            HELPERS
            + "(async () => {"
            + "const {until, control, tap, row, type, seen} = ui;"
            + script
            + "\nconsole.log('test successful');"
            + "})().catch((error) => console.error(error.stack || String(error)));",
            ready=READY,
            login=self.tech.login,
            timeout=timeout,
        )

    def running_lines(self):
        return self.env["account.analytic.line"].search(
            [("employee_id", "=", self.employee.id), ("unit_amount", "=", 0)]
        )

    def test_my_jobs_opens_a_job(self):
        self.run_app(
            "/jobs",
            """
            await until(
                () => seen("Chromeco/Roadster/CHR-042"), "the job on My Jobs");
            await type("Filter jobs", "CHR-042");
            const link = await until(() => [...document.querySelectorAll("a")].find(
                (a) => a.innerText.includes("Chromeco/Roadster")), "the job's row");
            link.click();
            await until(
                () => location.pathname.endsWith("/jobs/JOB"), "the job's page");
            await until(() => seen("Grinds when stopping"), "the concern");
            """.replace("JOB", str(self.repair.id)),
        )

    def test_timer_start_and_stop_from_the_header(self):
        self.run_app(
            f"/jobs/{self.repair.id}",
            """
            await until(() => seen("Chrome Brake Job"), "the service");
            await tap("Start", row("Chrome Brake Job"));
            const header = () => document.querySelector("[data-running-timer]");
            await until(header, "the running timer in the header");
            await until(
                () => control("Stop", row("Chrome Brake Job")), "the service's Stop");
            await tap("Stop timer");
            await until(() => !header(), "the timer gone from the header");
            """,
        )
        self.assertFalse(self.running_lines())
        line = self.env["account.analytic.line"].search(
            [("repair_service_id", "=", self.service.id)]
        )
        self.assertEqual(len(line), 1)
        self.assertEqual(self.employee.attendance_state, "checked_in", "clocked in")

    def test_parts_used_and_undone(self):
        self.run_app(
            f"/jobs/{self.repair.id}/parts",
            """
            await until(() => seen("Chrome Pad Set"), "the part");
            await tap("Used all", row("Chrome Pad Set"));
            await until(
                () => control("Undo", row("Chrome Pad Set")), "Undo after using it");
            await until(() => seen("1 of 1 used"), "the progress");
            """,
        )
        self.assertEqual(self.move.quantity, 2.0)
        self.assertTrue(self.move.picked)

    def test_add_a_note(self):
        self.run_app(
            f"/jobs/{self.repair.id}",
            """
            await type("Add a note", "Rotors scored, need machining");
            await tap("Add note");
            await until(() => seen("[Chrome Tech]"), "the note in the job's notes");
            """,
        )
        self.assertIn("Rotors scored", str(self.repair.internal_notes))

    def test_grade_an_inspection(self):
        item = self.env["fleet.vehicle.inspection.item"].create(
            {"name": "Chrome tires"}
        )
        template = self.env["fleet.vehicle.inspection.template"].create(
            {
                "name": "Chrome check",
                "inspection_template_line_ids": [
                    (0, 0, {"inspection_template_item_id": item.id, "sequence": 1})
                ],
            }
        )
        inspection = (
            self.env["repair.tech.app"]
            .with_user(self.tech)
            .create_inspection(
                repair_id=self.repair.id, template_id=template.id, odometer=1300
            )
        )
        line_id = inspection["lines"][0]["id"]
        inspection_id = inspection["inspection"]["id"]
        self.run_app(
            f"/inspections/{inspection_id}/items/{line_id}",
            """
            await until(() => seen("Chrome tires"), "the item");
            await tap("Good");
            await tap("Save and next");
            await until(
                () => location.pathname.endsWith("/inspections/INSPECTION"),
                "back on the checklist");
            await until(() => control("Complete inspection"), "Complete, all graded");
            await tap("Complete inspection");
            await until(
                () => location.pathname.endsWith("/jobs/JOB/inspections"),
                "the job's inspections");
            """.replace("INSPECTION", str(inspection_id)).replace(
                "JOB", str(self.repair.id)
            ),
        )
        line = self.env["fleet.vehicle.inspection.line"].browse(line_id)
        self.assertEqual(line.severity, "good")
        self.assertEqual(line.inspection_id.state, "confirmed")

    def test_delete_a_timesheet_entry(self):
        start = fields.Datetime.now().replace(microsecond=0) - timedelta(hours=3)
        entry = self.env["account.analytic.line"].create(
            {
                "name": "Chrome work",
                "project_id": self.project.id,
                "employee_id": self.employee.id,
                "repair_order_id": self.repair.id,
                "repair_service_id": self.service.id,
                "date_time": start,
                "unit_amount": 1.0,
            }
        )
        self.run_app(
            "/timesheets",
            """
            const entry = await until(
                () => row("Chromeco/Roadster/CHR-042"), "the entry");
            entry.querySelector("button, a").click();
            await tap("Delete");
            const alert = await until(
                () => document.querySelector("[role=alertdialog]"), "the confirmation");
            await tap("Delete", alert);
            await until(() => !row("Chromeco/Roadster/CHR-042"), "the entry gone");
            """,
        )
        self.assertFalse(entry.exists())
