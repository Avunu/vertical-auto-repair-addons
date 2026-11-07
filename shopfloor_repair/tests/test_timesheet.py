# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime

from odoo.tests.common import tagged

from .common import RepairJobCase

DAY = datetime(2026, 1, 5)


def at(hour, minute=0):
    return DAY.replace(hour=hour, minute=minute)


@tagged("post_install", "-at_install")
class TestTimesheetActions(RepairJobCase):
    def _service(self, usage):
        with self.work_on_services(profile=self.profile, menu=self.menu) as work:
            service = work.component(usage=usage)
            self.env["shopfloor.app"]._prepare_non_decorated_endpoints(service)
            return service

    def _call(self, usage, method, **params):
        return self._service(usage).dispatch(method, params=params)

    def _line(self, repair, start, end, service=None):
        return (
            self.env["account.analytic.line"]
            .sudo()
            .create(
                {
                    "name": "Work",
                    "project_id": self.labor_project.id,
                    "employee_id": self.employee.id,
                    "repair_order_id": repair.id,
                    "repair_service_id": service.id if service else False,
                    "date": start.date(),
                    "date_time": start,
                    "unit_amount": (end - start).total_seconds() / 3600,
                }
            )
        )

    def _attendance(self, check_in, check_out):
        return (
            self.env["hr.attendance"]
            .sudo()
            .create(
                {
                    "employee_id": self.employee.id,
                    "check_in": check_in,
                    "check_out": check_out,
                }
            )
        )

    def _service_line(self, repair):
        return (
            self.env["repair.service"]
            .sudo()
            .create(
                {
                    "repair_id": repair.id,
                    "product_id": self.part.id,
                    "accepted": True,
                }
            )
        )

    # -- split ------------------------------------------------------------

    def test_split_from_the_end_moves_the_last_minutes(self):
        other = self._make_repair()
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "split_timesheet",
            line_id=line.id,
            job_id=other.id,
            split_start="2026-01-05 09:40:00",
            split_end="2026-01-05 10:00:00",
        )
        self.assert_no_error(response)
        moved = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", other.id)]
        )
        self.assertEqual(len(moved), 1)
        self.assertEqual((moved.date_time, moved.date_time_end), (at(9, 40), at(10)))
        self.assertEqual((line.date_time, line.date_time_end), (at(9), at(9, 40)))

    def test_split_from_the_start_moves_the_first_minutes(self):
        other = self._make_repair()
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "split_timesheet",
            line_id=line.id,
            job_id=other.id,
            split_start="2026-01-05 09:00:00",
            split_end="2026-01-05 09:15:00",
        )
        self.assert_no_error(response)
        moved = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", other.id)]
        )
        self.assertEqual((moved.date_time, moved.date_time_end), (at(9), at(9, 15)))
        self.assertEqual((line.date_time, line.date_time_end), (at(9, 15), at(10)))

    def test_split_from_the_middle_leaves_a_head_and_a_tail(self):
        other = self._make_repair()
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "split_timesheet",
            line_id=line.id,
            job_id=other.id,
            split_start="2026-01-05 09:20:00",
            split_end="2026-01-05 09:40:00",
        )
        self.assert_no_error(response)
        moved = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", other.id)]
        )
        self.assertEqual((moved.date_time, moved.date_time_end), (at(9, 20), at(9, 40)))
        lines = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", self.repair.id)], order="date_time"
        )
        self.assertEqual(
            [(la.date_time, la.date_time_end) for la in lines],
            [(at(9), at(9, 20)), (at(9, 40), at(10))],
        )

    def test_split_outside_the_line_is_refused(self):
        other = self._make_repair()
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "split_timesheet",
            line_id=line.id,
            job_id=other.id,
            split_start="2026-01-05 09:30:00",
            split_end="2026-01-05 10:30:00",
        )
        self.assert_error(response)
        self.assertEqual(line.date_time_end, at(10))

    def test_split_of_the_whole_line_is_refused(self):
        other = self._make_repair()
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "split_timesheet",
            line_id=line.id,
            job_id=other.id,
            split_start="2026-01-05 09:00:00",
            split_end="2026-01-05 10:00:00",
        )
        self.assert_error(response)
        self.assertEqual(line.date_time_end, at(10))

    def test_split_rejects_a_service_from_another_job(self):
        other = self._make_repair()
        foreign = self._service_line(self.repair)
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "split_timesheet",
            line_id=line.id,
            job_id=other.id,
            service_id=foreign.id,
            split_start="2026-01-05 09:50:00",
            split_end="2026-01-05 10:00:00",
        )
        self.assert_error(response)

    # -- update (job + service) ---------------------------------------------

    def test_moving_a_line_to_another_job_replaces_the_service(self):
        other = self._make_repair()
        old_service = self._service_line(self.repair)
        line = self._line(self.repair, at(9), at(10), service=old_service)
        response = self._call(
            "repair_timesheet",
            "update_timesheet",
            line_id=line.id,
            date_time="2026-01-05 09:00:00",
            date_time_end="2026-01-05 10:00:00",
            job_id=other.id,
        )
        self.assert_no_error(response)
        self.assertEqual(line.repair_order_id, other)
        self.assertFalse(line.repair_service_id)

    def test_moving_a_line_to_a_job_shared_through_its_appointment_type(self):
        other = (
            self.env["res.users"]
            .sudo()
            .create({"name": "Other Tech", "login": "other.tech"})
        )
        theirs = self._make_repair(technician=other)
        resource = (
            self.env["resource.resource"]
            .sudo()
            .search([("user_id", "=", self.technician.id)])
        )
        combination = (
            self.env["resource.booking.combination"]
            .sudo()
            .create({"resource_ids": [(6, 0, resource.ids)]})
        )
        booking_type = (
            self.env["resource.booking.type"]
            .sudo()
            .create(
                {
                    "name": "Alignment",
                    "combination_rel_ids": [(0, 0, {"combination_id": combination.id})],
                }
            )
        )
        self.env["resource.booking"].sudo().create(
            {
                "repair_id": theirs.id,
                "type_id": booking_type.id,
                "partner_ids": [(6, 0, self.customer.ids)],
            }
        )
        # The office books in its own request, which ends with a flush.
        self.env.flush_all()
        line = self._line(self.repair, at(9), at(10))
        response = self._call(
            "repair_timesheet",
            "update_timesheet",
            line_id=line.id,
            date_time="2026-01-05 09:00:00",
            date_time_end="2026-01-05 10:00:00",
            job_id=theirs.id,
        )
        self.assert_no_error(response)
        self.assertEqual(line.repair_order_id, theirs)

    # -- break --------------------------------------------------------------

    def test_add_break_splits_the_line_and_the_attendance(self):
        line = self._line(self.repair, at(9), at(12))
        attendance = self._attendance(at(8), at(17))
        response = self._call(
            "repair_timesheet",
            "add_break",
            line_id=line.id,
            break_start="2026-01-05 10:00:00",
            break_end="2026-01-05 10:30:00",
        )
        self.assert_no_error(response)
        lines = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", self.repair.id)], order="date_time"
        )
        self.assertEqual(
            [(la.date_time, la.date_time_end) for la in lines],
            [(at(9), at(10)), (at(10, 30), at(12))],
        )
        attendances = (
            self.env["hr.attendance"]
            .sudo()
            .search([("employee_id", "=", self.employee.id)], order="check_in")
        )
        self.assertEqual(
            [(a.check_in, a.check_out) for a in attendances],
            [(at(8), at(10)), (at(10, 30), at(17))],
        )
        self.assertIn(attendance, attendances)

    def test_add_break_on_an_unclocked_day_splits_only_the_job_time(self):
        line = self._line(self.repair, at(9), at(12))
        self.assertFalse(
            self.env["hr.attendance"]
            .sudo()
            .search([("employee_id", "=", self.employee.id)])
        )
        response = self._call(
            "repair_timesheet",
            "add_break",
            line_id=line.id,
            break_start="2026-01-05 10:00:00",
            break_end="2026-01-05 10:30:00",
        )
        self.assert_no_error(response)
        lines = self.env["account.analytic.line"].search(
            [("repair_order_id", "=", self.repair.id)], order="date_time"
        )
        self.assertEqual(
            [(la.date_time, la.date_time_end) for la in lines],
            [(at(9), at(10)), (at(10, 30), at(12))],
        )
        # Nothing was clocked, and nothing is invented to take the break from.
        self.assertFalse(
            self.env["hr.attendance"]
            .sudo()
            .search([("employee_id", "=", self.employee.id)])
        )
        # ...and the answer says why the day's total didn't move.
        self.assertEqual(response["message"]["message_type"], "info")
        self.assertIn("No clock-in is recorded", response["message"]["body"])

    def test_add_break_outside_the_line_is_refused(self):
        line = self._line(self.repair, at(9), at(10))
        self._attendance(at(8), at(17))
        response = self._call(
            "repair_timesheet",
            "add_break",
            line_id=line.id,
            break_start="2026-01-05 09:45:00",
            break_end="2026-01-05 10:15:00",
        )
        self.assert_error(response)

    def test_add_break_without_a_covering_attendance_changes_nothing(self):
        line = self._line(self.repair, at(9), at(12))
        self._attendance(at(8), at(10))  # ends mid-break
        response = self._call(
            "repair_timesheet",
            "add_break",
            line_id=line.id,
            break_start="2026-01-05 09:45:00",
            break_end="2026-01-05 10:15:00",
        )
        self.assert_error(response)
        self.assertEqual((line.date_time, line.date_time_end), (at(9), at(12)))

    # -- editing / deleting a break -----------------------------------------

    def _lunch_day(self):
        """8-10 and 10:30-17 clocked, with job time either side of the gap."""
        morning = self._attendance(at(8), at(10))
        afternoon = self._attendance(at(10, 30), at(17))
        before = self._line(self.repair, at(9), at(10))
        after = self._line(self.repair, at(10, 30), at(12))
        return morning, afternoon, before, after

    def test_update_break_moves_the_clock_times_and_the_job_edges(self):
        morning, afternoon, before, after = self._lunch_day()
        response = self._call(
            "repair_timesheet",
            "update_break",
            attendance_id=morning.id,
            break_start="2026-01-05 10:10:00",
            break_end="2026-01-05 10:45:00",
        )
        self.assert_no_error(response)
        self.assertEqual(morning.check_out, at(10, 10))
        self.assertEqual(afternoon.check_in, at(10, 45))
        # The job time that met the break follows it.
        self.assertEqual((before.date_time, before.date_time_end), (at(9), at(10, 10)))
        self.assertEqual((after.date_time, after.date_time_end), (at(10, 45), at(12)))

    def test_update_break_moved_wholly_later_does_not_collide(self):
        morning, afternoon, _before, _after = self._lunch_day()
        response = self._call(
            "repair_timesheet",
            "update_break",
            attendance_id=morning.id,
            break_start="2026-01-05 11:00:00",
            break_end="2026-01-05 11:30:00",
        )
        self.assert_no_error(response)
        self.assertEqual(morning.check_out, at(11))
        self.assertEqual(afternoon.check_in, at(11, 30))

    def test_update_break_into_job_time_is_refused_and_changes_nothing(self):
        morning, afternoon, before, _after = self._lunch_day()
        response = self._call(
            "repair_timesheet",
            "update_break",
            attendance_id=morning.id,
            # Before the job time that ends the morning.
            break_start="2026-01-05 08:30:00",
            break_end="2026-01-05 10:30:00",
        )
        self.assert_error(response)
        self.assertEqual(morning.check_out, at(10))
        self.assertEqual(before.date_time_end, at(10))

    def test_update_break_outside_the_clocked_periods_is_refused(self):
        morning, afternoon, _before, _after = self._lunch_day()
        response = self._call(
            "repair_timesheet",
            "update_break",
            attendance_id=morning.id,
            break_start="2026-01-05 10:00:00",
            break_end="2026-01-05 17:30:00",  # past clock-out
        )
        self.assert_error(response)
        self.assertEqual(afternoon.check_in, at(10, 30))

    def test_delete_break_joins_the_two_periods(self):
        morning, afternoon, _before, _after = self._lunch_day()
        response = self._call(
            "repair_timesheet", "delete_break", attendance_id=morning.id
        )
        self.assert_no_error(response)
        self.assertEqual((morning.check_in, morning.check_out), (at(8), at(17)))
        self.assertFalse(afternoon.exists())

    def test_delete_break_before_a_period_still_open_leaves_it_open(self):
        morning = self._attendance(at(8), at(10))
        afternoon = self._attendance(at(10, 30), False)
        response = self._call(
            "repair_timesheet", "delete_break", attendance_id=morning.id
        )
        self.assert_no_error(response)
        self.assertEqual(morning.check_in, at(8))
        self.assertFalse(morning.check_out)
        self.assertFalse(afternoon.exists())

    def test_there_is_no_break_after_the_last_period(self):
        only = self._attendance(at(8), at(17))
        response = self._call("repair_timesheet", "delete_break", attendance_id=only.id)
        self.assert_error(response)
        self.assertEqual(only.check_out, at(17))

    # -- breaks between two parts of one job (nothing clocked) ---------------

    def _two_parts(self):
        """9-10 and 10:30-12 on one job: a 30 minute break between them."""
        service = self._service_line(self.repair)
        first = self._line(self.repair, at(9), at(10), service=service)
        second = self._line(self.repair, at(10, 30), at(12), service=service)
        return first, second

    def test_update_job_break_moves_the_edges_of_both_parts(self):
        first, second = self._two_parts()
        response = self._call(
            "repair_timesheet",
            "update_job_break",
            line_id=first.id,
            after_id=second.id,
            break_start="2026-01-05 10:10:00",
            break_end="2026-01-05 10:45:00",
        )
        self.assert_no_error(response)
        self.assertEqual((first.date_time, first.date_time_end), (at(9), at(10, 10)))
        self.assertEqual((second.date_time, second.date_time_end), (at(10, 45), at(12)))

    def test_update_job_break_moved_wholly_later_does_not_collide(self):
        first, second = self._two_parts()
        response = self._call(
            "repair_timesheet",
            "update_job_break",
            line_id=first.id,
            after_id=second.id,
            break_start="2026-01-05 11:00:00",
            break_end="2026-01-05 11:30:00",
        )
        self.assert_no_error(response)
        self.assertEqual(first.date_time_end, at(11))
        self.assertEqual(second.date_time, at(11, 30))

    def test_update_job_break_outside_the_two_parts_is_refused(self):
        first, second = self._two_parts()
        response = self._call(
            "repair_timesheet",
            "update_job_break",
            line_id=first.id,
            after_id=second.id,
            break_start="2026-01-05 10:00:00",
            break_end="2026-01-05 12:30:00",  # past the end of the later part
        )
        self.assert_error(response)
        self.assertEqual(second.date_time, at(10, 30))

    def test_job_break_needs_two_parts_of_the_same_job(self):
        other = self._make_repair()
        first = self._line(self.repair, at(9), at(10))
        second = self._line(other, at(10, 30), at(12))
        response = self._call(
            "repair_timesheet",
            "delete_job_break",
            line_id=first.id,
            after_id=second.id,
        )
        self.assert_error(response)
        self.assertTrue(second.exists())

    def test_delete_job_break_joins_the_parts(self):
        first, second = self._two_parts()
        response = self._call(
            "repair_timesheet",
            "delete_job_break",
            line_id=first.id,
            after_id=second.id,
        )
        self.assert_no_error(response)
        self.assertEqual((first.date_time, first.date_time_end), (at(9), at(12)))
        self.assertFalse(second.exists())

    # -- default profile ----------------------------------------------------

    def test_default_profile_is_remembered_and_returned_on_sync(self):
        self.assertFalse(self._call("app", "user_config")["data"]["default_profile_id"])
        response = self._call("app", "set_default_profile", profile_id=self.profile.id)
        self.assert_no_error(response)
        self.assertEqual(self.technician.shopfloor_default_profile_id, self.profile)
        self.assertEqual(
            self._call("app", "user_config")["data"]["default_profile_id"],
            self.profile.id,
        )

    def test_default_profile_must_be_one_the_app_offers(self):
        response = self._call("app", "set_default_profile", profile_id=999999)
        self.assert_error(response)
        self.assertFalse(self.technician.shopfloor_default_profile_id)

    # -- day totals ---------------------------------------------------------

    def test_job_hours_sum_every_job_entry_of_the_day(self):
        other = self._make_repair()
        self._line(self.repair, at(9), at(10))
        self._line(other, at(11), at(11, 30))
        # A running timer: no hours booked yet, so not counted.
        self._line(self.repair, at(13), at(13))
        response = self._call("repair_timesheet", "timesheets")
        self.assert_no_error(response)
        self.assertEqual(
            response["data"]["timesheets"]["job_hours_by_date"],
            [{"date": "2026-01-05", "hours": 1.5}],
        )
