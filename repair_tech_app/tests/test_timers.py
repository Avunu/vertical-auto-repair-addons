# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TechCase


@tagged("post_install", "-at_install")
class TestTimers(TechCase):
    def running(self):
        return self.env["account.analytic.line"].search(
            [("employee_id", "=", self.employee.id), ("unit_amount", "=", 0)]
        )

    def timers(self, job):
        return {service["id"]: service["timer"] for service in job["services"]}

    def test_start_creates_a_running_entry(self):
        result = self.app.timer_start(
            repair_id=self.repair.id, service_id=self.brakes.id
        )
        timer = self.timers(result["job"])[self.brakes.id]
        self.assertTrue(timer["running"])
        self.assertTrue(timer["started_at"].endswith("Z"))
        self.assertTrue(result["job"]["timer_running"])
        line = self.running()
        self.assertEqual(line.repair_service_id, self.brakes)
        self.assertEqual(line.project_id, self.labor_project)

    def test_stop_banks_the_time(self):
        start = fields.Datetime.now() - timedelta(minutes=90)
        with patch.object(type(self.app), "_now", lambda self: start):
            self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        job = self.app.timer_stop(repair_id=self.repair.id, service_id=self.brakes.id)
        self.assertFalse(self.timers(job)[self.brakes.id]["running"])
        brakes = next(s for s in job["services"] if s["id"] == self.brakes.id)
        self.assertAlmostEqual(brakes["my_hours"], 1.5, places=1)
        self.assertAlmostEqual(brakes["actual_hours"], 1.5, places=1)

    def test_stop_without_a_timer_does_nothing(self):
        job = self.app.timer_stop(repair_id=self.repair.id, service_id=self.brakes.id)
        self.assertFalse(job["timer_running"])

    def test_one_timer_per_person(self):
        """Starting a second timer stops the first at the very same instant:
        no overlap, no gap."""
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        first = self.running()
        other = self._make_repair()
        result = self.app.timer_start(
            repair_id=other.id, service_id=other.repair_service_ids[:1].id
        )
        self.assertEqual(result["stopped"]["repair_id"], self.repair.id)
        self.assertEqual(result["stopped"]["service_id"], self.brakes.id)
        second = self.running()
        self.assertEqual(len(second), 1)
        self.assertEqual(second.repair_order_id, other)
        self.assertTrue(first.unit_amount > 0, "stopped with a duration above zero")
        self.assertEqual(first.date_time_end.replace(microsecond=0), second.date_time)

    def test_starting_with_nothing_else_running_stops_nothing(self):
        result = self.app.timer_start(
            repair_id=self.repair.id, service_id=self.brakes.id
        )
        self.assertIsNone(result["stopped"])

    def test_starting_the_same_service_twice(self):
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        result = self.app.timer_start(
            repair_id=self.repair.id, service_id=self.brakes.id
        )
        self.assertIsNone(result["stopped"])
        self.assertEqual(len(self.running()), 1)

    def test_switching_right_after_starting(self):
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        self.app.timer_start(repair_id=self.repair.id, service_id=self.diagnostics.id)
        self.assertEqual(self.running().repair_service_id, self.diagnostics)

    def test_first_timer_of_the_day_clocks_in(self):
        result = self.app.timer_start(
            repair_id=self.repair.id, service_id=self.brakes.id
        )
        self.assertTrue(result["clocked_in"])
        self.assertEqual(self.employee.attendance_state, "checked_in")
        result = self.app.timer_start(
            repair_id=self.repair.id, service_id=self.diagnostics.id
        )
        self.assertFalse(result["clocked_in"], "not twice")

    def test_stop_running_from_anywhere(self):
        self.assertIsNone(self.app.stop_running())
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        job = self.app.stop_running()
        self.assertEqual(job["id"], self.repair.id)
        self.assertFalse(self.running())

    def test_only_accepted_services(self):
        self.brakes.accepted = False
        with self.assertRaisesRegex(UserError, "accepted service"):
            self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)

    def test_service_of_another_job(self):
        other = self._make_repair()
        with self.assertRaisesRegex(UserError, "accepted service"):
            self.app.timer_start(
                repair_id=self.repair.id, service_id=other.repair_service_ids[:1].id
            )

    def test_needs_an_employee(self):
        self.employee.user_id = False
        with self.assertRaisesRegex(UserError, "no employee"):
            self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)

    def test_needs_a_project(self):
        self.company.repair_timesheet_project_id = False
        with self.assertRaisesRegex(UserError, "timesheet project"):
            self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)

    def test_mine_is_only_my_time(self):
        """Everyone's time is everyone's, whoever's request recomputes it: a
        technician's record rules hide the others' entries."""
        other = self._make_technician("Other Tech", "other.tech")
        start = fields.Datetime.now() - timedelta(hours=5)
        self.line(self.repair, start, start + timedelta(hours=2), self.brakes)
        self.line(
            self.repair,
            start,
            start + timedelta(hours=1),
            self.brakes,
            employee=other.employee_id,
        )
        brakes = next(
            s
            for s in self.app.job(repair_id=self.repair.id)["services"]
            if s["id"] == self.brakes.id
        )
        self.assertAlmostEqual(brakes["my_hours"], 2.0)
        self.assertAlmostEqual(brakes["actual_hours"], 3.0)
