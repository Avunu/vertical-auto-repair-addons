# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from freezegun import freeze_time

from odoo.tests.common import tagged

from .common import RepairJobCase


@tagged("post_install", "-at_install")
class TestServiceTimer(RepairJobCase):
    def _service_line(self, repair, product=None):
        return (
            self.env["repair.service"]
            .sudo()
            .create(
                {
                    "repair_id": repair.id,
                    "product_id": (product or self.part).id,
                    "accepted": True,
                }
            )
        )

    def _start(self, repair, service):
        return self._dispatch(
            "service_timer_start", repair_id=repair.id, service_id=service.id
        )

    def _running(self):
        return self.env["account.analytic.line"].search(
            [("repair_order_id", "!=", False), ("unit_amount", "=", 0)]
        )

    def test_mine_counts_only_my_time_on_a_shared_service(self):
        service = self._service_line(self.repair)
        other = self.env["res.users"].sudo().create(
            {"name": "Other Tech", "login": "other.tech"}
        )
        other_employee = self.env["hr.employee"].sudo().create(
            {"name": other.name, "user_id": other.id, "company_id": self.company.id}
        )
        for employee, hours in ((self.employee, 1.0), (other_employee, 2.0)):
            self.env["account.analytic.line"].sudo().create(
                {
                    "name": "Work",
                    "project_id": self.labor_project.id,
                    "employee_id": employee.id,
                    "user_id": employee.user_id.id,
                    "repair_order_id": self.repair.id,
                    "repair_service_id": service.id,
                    "unit_amount": hours,
                }
            )
        records = self.state_data(
            self._dispatch("services", repair_id=self.repair.id)
        )["records"]
        row = next(rec for rec in records if rec["id"] == service.id)
        self.assertEqual(row["my_time"], 1.0)
        self.assertEqual(row["actual_time"], 3.0)

    def test_starting_another_timer_stops_the_running_one(self):
        other = self._make_repair()
        first = self._service_line(self.repair, self.part)
        second = self._service_line(other, self.other_part)
        # Mid-second on purpose: a stop time with microseconds used to overlap
        # a new start without them, and the start was refused.
        with freeze_time("2026-01-05 09:00:00") as clock:
            self.assert_no_error(self._start(self.repair, first))
            clock.move_to("2026-01-05 09:10:00.700000")
            response = self._start(other, second)

        self.assert_no_error(response)
        self.assertEqual(self._running().repair_service_id, second)
        stopped = self.env["account.analytic.line"].search(
            [("repair_service_id", "=", first.id)]
        )
        # The old timer ends exactly where the new one starts.
        self.assertEqual(stopped.date_time_end, self._running().date_time)
        # And the technician is told which timer was stopped - service,
        # vehicle and order number - and which one started.
        body = response["message"]["body"]
        self.assertIn("Timer stopped on", body)
        self.assertIn(self.part.name, body)
        self.assertIn("Acme/Hauler/SHOP-001", body)
        self.assertIn(self.repair.name, body)
        self.assertIn(f"Timer started on {second.display_name}", body)

    def test_starting_with_no_other_timer_mentions_no_stop(self):
        service = self._service_line(self.repair)
        response = self._start(self.repair, service)
        self.assertNotIn("stopped", response["message"]["body"])

    def test_switching_straight_after_starting_still_stops_the_first(self):
        other = self._make_repair()
        first = self._service_line(self.repair, self.part)
        second = self._service_line(other, self.other_part)
        # Both taps in the same second: the first timer must still end up
        # stopped (a duration above zero), not left running.
        with freeze_time("2026-01-05 09:00:00"):
            self.assert_no_error(self._start(self.repair, first))
            self.assert_no_error(self._start(other, second))

        self.assertEqual(self._running().repair_service_id, second)

    def test_start_works_once_the_other_timer_is_stopped(self):
        other = self._make_repair()
        first = self._service_line(self.repair, self.part)
        second = self._service_line(other, self.other_part)
        # Frozen time, so the stop and the next start are minutes apart like
        # they are for a person - not within the same second, where the stop
        # time's sub-second part would overlap the next start.
        with freeze_time("2026-01-05 09:00:00") as clock:
            self.assert_no_error(self._start(self.repair, first))
            clock.tick(timedelta(minutes=10))
            self.assert_no_error(
                self._dispatch(
                    "service_timer_stop",
                    repair_id=self.repair.id,
                    service_id=first.id,
                )
            )
            clock.tick(timedelta(minutes=1))
            response = self._start(other, second)

        self.assert_no_error(response)
        self.assertEqual(self._running().repair_service_id, second)

    def test_starting_the_same_service_twice_is_still_informative(self):
        first = self._service_line(self.repair)
        self._start(self.repair, first)
        response = self._start(self.repair, first)
        self.assertEqual(response["message"]["message_type"], "info")

    # -- the day clock starts with the first timer --------------------------

    def _attendances(self):
        return self.env["hr.attendance"].sudo().search(
            [("employee_id", "=", self.employee.id)]
        )

    def test_first_timer_of_the_day_clocks_you_in_and_says_so(self):
        self.assertFalse(self._attendances())
        service = self._service_line(self.repair)

        response = self._start(self.repair, service)

        self.assert_no_error(response)
        attendances = self._attendances()
        self.assertEqual(len(attendances), 1)
        self.assertFalse(attendances.check_out)  # clocked in, still open
        message = response["message"]
        self.assertEqual(message["message_type"], "info")
        self.assertIn("clocked in for the day", message["body"])
        self.assertIn("clock out", message["body"])

    def test_timer_does_not_clock_in_twice(self):
        self.employee.sudo()._attendance_action_change()  # already clocked in
        self.assertEqual(len(self._attendances()), 1)
        service = self._service_line(self.repair)

        response = self._start(self.repair, service)

        self.assert_no_error(response)
        self.assertEqual(len(self._attendances()), 1)
        self.assertEqual(response["message"]["message_type"], "success")
        self.assertNotIn("clocked in", response["message"]["body"])

