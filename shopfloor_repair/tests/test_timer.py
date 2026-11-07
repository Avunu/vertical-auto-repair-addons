# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.tests.common import tagged

from .common import RepairJobCase


@tagged("post_install", "-at_install")
class TestTimer(RepairJobCase):
    """Timer behaviour that is not specific to refusing a second timer.

    The one-timer-at-a-time rule lives in ``test_service_timer``.
    """

    @classmethod
    def setUpClassBaseData(cls):
        res = super().setUpClassBaseData()
        cls.service = (
            cls.env["repair.service"]
            .sudo()
            .create(
                {
                    "repair_id": cls.repair.id,
                    "product_id": cls.part.id,
                    "accepted": True,
                }
            )
        )
        return res

    def _running_lines(self, repair):
        return self.env["account.analytic.line"].search(
            [("repair_order_id", "=", repair.id), ("unit_amount", "=", 0)]
        )

    def _start(self):
        return self._dispatch(
            "service_timer_start",
            repair_id=self.repair.id,
            service_id=self.service.id,
        )

    def _stop(self):
        return self._dispatch(
            "service_timer_stop",
            repair_id=self.repair.id,
            service_id=self.service.id,
        )

    def test_timer_start_creates_a_running_line(self):
        response = self._start()
        self.assert_no_error(response)
        line = self._running_lines(self.repair)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.project_id, self.labor_project)
        self.assertEqual(line.employee_id, self.employee)
        self.assertEqual(line.repair_service_id, self.service)
        self.assertTrue(line.date_time)

    def test_timer_stop_banks_the_duration(self):
        with freeze_time("2026-08-06 09:00:00"):
            self._start()
        with freeze_time("2026-08-06 10:30:00"):
            response = self._stop()
        self.assert_no_error(response)
        line = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", self.repair.id)]
        )
        self.assertAlmostEqual(line.unit_amount, 1.5, places=2)
        self.assertFalse(self._running_lines(self.repair))

    def test_timer_stop_without_a_timer_warns(self):
        response = self._stop()
        self.assertEqual(response["message"]["message_type"], "warning")

    def test_elapsed_hours_reported_while_running(self):
        start = fields.Datetime.now() - timedelta(hours=2)
        self._start()
        self._running_lines(self.repair).sudo().date_time = start
        timer = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]["timer"]
        self.assertTrue(timer["running"])
        self.assertAlmostEqual(timer["elapsed_hours"], 2.0, places=1)
        # Still zero on the line itself: that is what marks it as running.
        self.assertEqual(timer["total_hours"], 0.0)

    def test_timer_needs_an_employee(self):
        self.employee.sudo().user_id = False
        response = self._start()
        self.assert_error(response)
        self.assertFalse(self._running_lines(self.repair))

    def test_timer_needs_a_project(self):
        self.company.sudo().repair_timesheet_project_id = False
        response = self._start()
        self.assert_error(response)
        self.assertIn("project", response["message"]["body"].lower())

    def test_finish_stops_a_running_timer(self):
        self._dispatch("start_repair", repair_id=self.repair.id)
        self._start()
        self._dispatch("finish", repair_id=self.repair.id)
        self.assertEqual(self.repair.state, "done")
        self.assertFalse(self._running_lines(self.repair))
