# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TechCase, at, utc


@tagged("post_install", "-at_install")
class TestTimesheets(TechCase):
    def entries(self, repair):
        return self.env["account.analytic.line"].search(
            [("repair_order_id", "=", repair.id)], order="date_time"
        )

    def spans(self, lines):
        return [(line.date_time, line.date_time_end) for line in lines]

    # -- the list -------------------------------------------------------

    def test_list(self):
        self.line(self.repair, at(9), at(10), self.brakes)
        self.line(self.repair, at(13), at(14, 30), self.diagnostics)
        clocked = self.attendance(at(8), at(17))
        page = self.app.timesheets()
        self.assertEqual(page["total"], 2)
        first, second = page["records"]
        self.assertEqual(first["start"], "2026-01-05T13:00:00Z", "newest first")
        self.assertEqual(first["service"]["name"], "Diagnostics")
        self.assertEqual(second["hours"], 1.0)
        self.assertEqual(second["job"]["name"], "Acme/Hauler/SHOP-001")
        self.assertEqual(second["job_ref"], self.repair.name)
        self.assertEqual(page["job_hours"], [{"date": "2026-01-05", "hours": 2.5}])
        (day,) = page["attendance"]
        # Odoo's worked hours (which take the calendar's lunch off).
        self.assertEqual(
            (day["date"], day["hours"]), ("2026-01-05", clocked.worked_hours)
        )
        self.assertEqual(day["records"][0]["check_in"], "2026-01-05T08:00:00Z")

    def test_only_my_entries(self):
        other = self._make_technician("Other Tech", "other.tech")
        theirs = self.line(self.repair, at(9), at(10), employee=other.employee_id)
        self.assertNotIn(theirs.id, self.ids(self.app.timesheets()["records"]))
        with self.assertRaisesRegex(UserError, "isn't one of yours"):
            self.app.timesheet(line_id=theirs.id)
        with self.assertRaisesRegex(UserError, "isn't one of yours"):
            self.app.delete_timesheet(line_id=theirs.id)

    def test_search(self):
        mine = self.line(self.repair, at(9), at(10))
        other = self._make_repair()
        self.line(other, at(11), at(12))
        self.assertEqual(
            self.ids(self.app.timesheets(search=self.repair.name)["records"]), [mine.id]
        )
        self.assertEqual(self.app.timesheets(search="2026-01-05")["total"], 2)
        self.assertEqual(self.app.timesheets(search="2026-01-06")["total"], 0)

    def test_paged(self):
        for hour in range(22):
            self.line(self.repair, at(hour), at(hour, 30))
        first, second = self.app.timesheets(), self.app.timesheets(page=2)
        self.assertEqual((len(first["records"]), len(second["records"])), (20, 2))
        # The day's job time covers every entry, not just the page's.
        self.assertEqual(second["job_hours"], [{"date": "2026-01-05", "hours": 11.0}])

    def test_running_entry_has_no_end(self):
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        entry = self.app.timesheets()["records"][0]
        self.assertIsNone(entry["end"])

    # -- one entry ------------------------------------------------------

    def test_detail_offers_my_jobs(self):
        line = self.line(self.repair, at(9), at(10))
        other = self._make_repair()
        detail = self.app.timesheet(line_id=line.id)
        jobs = {job["id"]: job for job in detail["jobs"]}
        self.assertIn(other.id, jobs)
        self.assertEqual(
            [s["name"] for s in jobs[self.repair.id]["services"]],
            ["Brake Job", "Diagnostics"],
        )

    def test_update_times(self):
        line = self.line(self.repair, at(9), at(10))
        detail = self.app.update_timesheet(
            line_id=line.id, start=utc(at(8, 30)), end=utc(at(10, 15))
        )
        self.assertEqual(detail["entry"]["hours"], 1.75)
        self.assertEqual(self.spans(line), [(at(8, 30), at(10, 15))])

    def test_times_need_an_offset(self):
        """A time without its zone could be read either way: refused."""
        line = self.line(self.repair, at(9), at(10))
        with self.assertRaises(ValidationError):
            self.app.update_timesheet(line_id=line.id, start=at(9), end=at(10))

    def test_end_before_start(self):
        line = self.line(self.repair, at(9), at(10))
        with self.assertRaisesRegex(UserError, "after the start"):
            self.app.update_timesheet(
                line_id=line.id, start=utc(at(10)), end=utc(at(9))
            )

    def test_overlap_is_refused(self):
        self.line(self.repair, at(9), at(10))
        line = self.line(self.repair, at(11), at(12))
        with self.assertRaisesRegex(ValidationError, "overlaps"):
            self.app.update_timesheet(
                line_id=line.id, start=utc(at(9, 30)), end=utc(at(12))
            )

    def test_move_to_another_job_takes_its_service(self):
        other = self._make_repair()
        service = other.repair_service_ids[:1]
        line = self.line(self.repair, at(9), at(10), self.brakes)
        self.app.update_timesheet(
            line_id=line.id,
            start=utc(at(9)),
            end=utc(at(10)),
            job_id=other.id,
            service_id=service.id,
        )
        self.assertEqual(
            (line.repair_order_id, line.repair_service_id), (other, service)
        )
        # Without a service the old job's service doesn't come along.
        self.app.update_timesheet(
            line_id=line.id, start=utc(at(9)), end=utc(at(10)), job_id=self.repair.id
        )
        self.assertFalse(line.repair_service_id)

    def test_move_needs_the_jobs_own_service(self):
        other = self._make_repair()
        line = self.line(self.repair, at(9), at(10))
        with self.assertRaisesRegex(UserError, "accepted service on the job"):
            self.app.update_timesheet(
                line_id=line.id,
                start=utc(at(9)),
                end=utc(at(10)),
                job_id=other.id,
                service_id=self.brakes.id,
            )

    def test_move_to_a_job_i_cant_book_to(self):
        theirs = self._make_repair(
            technician=self._make_technician("Other Tech", "other.tech")
        )
        line = self.line(self.repair, at(9), at(10))
        with self.assertRaisesRegex(UserError, "can book time to"):
            self.app.update_timesheet(
                line_id=line.id, start=utc(at(9)), end=utc(at(10)), job_id=theirs.id
            )

    def test_delete(self):
        line = self.line(self.repair, at(9), at(10))
        self.assertEqual(
            self.app.delete_timesheet(line_id=line.id)["message"], "Entry deleted."
        )
        self.assertFalse(line.exists())

    # -- split ------------------------------------------------------------

    def split(self, line, other, start, end):
        return self.app.split_timesheet(
            line_id=line.id, job_id=other.id, start=utc(start), end=utc(end)
        )

    def test_split_the_end(self):
        other = self._make_repair()
        line = self.line(self.repair, at(9), at(10))
        self.split(line, other, at(9, 40), at(10))
        self.assertEqual(self.spans(self.entries(other)), [(at(9, 40), at(10))])
        self.assertEqual(self.spans(line), [(at(9), at(9, 40))])

    def test_split_the_start(self):
        other = self._make_repair()
        line = self.line(self.repair, at(9), at(10))
        self.split(line, other, at(9), at(9, 15))
        self.assertEqual(self.spans(self.entries(other)), [(at(9), at(9, 15))])
        self.assertEqual(self.spans(line), [(at(9, 15), at(10))])

    def test_split_the_middle(self):
        other = self._make_repair()
        line = self.line(self.repair, at(9), at(10))
        notice = self.split(line, other, at(9, 20), at(9, 40))
        self.assertIn("Acme/Hauler/SHOP-001", notice["message"])
        self.assertEqual(self.spans(self.entries(other)), [(at(9, 20), at(9, 40))])
        self.assertEqual(
            self.spans(self.entries(self.repair)),
            [(at(9), at(9, 20)), (at(9, 40), at(10))],
        )

    def test_split_outside_or_all_of_it(self):
        other = self._make_repair()
        line = self.line(self.repair, at(9), at(10))
        for start, end in ((at(8), at(9, 30)), (at(9), at(10))):
            with self.assertRaisesRegex(UserError, "Pick a part"):
                self.split(line, other, start, end)
        self.assertEqual(self.spans(line), [(at(9), at(10))])

    # -- breaks against the clock -----------------------------------------

    def test_add_break_splits_the_entry_and_the_clock(self):
        line = self.line(self.repair, at(9), at(12))
        attendance = self.attendance(at(8), at(17))
        notice = self.app.add_break(
            line_id=line.id, start=utc(at(10)), end=utc(at(10, 30))
        )
        self.assertIn("clocked out", notice["message"])
        self.assertEqual(
            self.spans(self.entries(self.repair)),
            [(at(9), at(10)), (at(10, 30), at(12))],
        )
        periods = self.env["hr.attendance"].search(
            [("employee_id", "=", self.employee.id)], order="check_in"
        )
        self.assertEqual(
            [(a.check_in, a.check_out) for a in periods],
            [(at(8), at(10)), (at(10, 30), at(17))],
        )
        self.assertEqual(attendance.check_out, at(10))

    def test_add_break_on_an_unclocked_day(self):
        line = self.line(self.repair, at(9), at(12))
        notice = self.app.add_break(
            line_id=line.id, start=utc(at(10)), end=utc(at(10, 30))
        )
        self.assertIn("only job time", notice["message"])
        self.assertEqual(len(self.entries(self.repair)), 2)

    def test_add_break_outside_the_entry(self):
        line = self.line(self.repair, at(9), at(12))
        with self.assertRaisesRegex(UserError, "inside the entry"):
            self.app.add_break(line_id=line.id, start=utc(at(8)), end=utc(at(9, 30)))

    def test_add_break_across_a_clock_out(self):
        line = self.line(self.repair, at(9), at(12))
        self.attendance(at(8), at(10, 15))
        self.attendance(at(10, 20), at(17))
        with self.assertRaisesRegex(UserError, "crosses a clock-out"):
            self.app.add_break(line_id=line.id, start=utc(at(10)), end=utc(at(10, 30)))
        self.assertEqual(self.spans(line), [(at(9), at(12))])

    def lunch_day(self):
        """8-10 and 10:30-17 clocked, job time either side of the gap."""
        return (
            self.attendance(at(8), at(10)),
            self.attendance(at(10, 30), at(17)),
            self.line(self.repair, at(9), at(10)),
            self.line(self.repair, at(10, 30), at(12)),
        )

    def test_move_a_break(self):
        morning, afternoon, before, after = self.lunch_day()
        self.app.update_break(
            attendance_id=morning.id, start=utc(at(10, 10)), end=utc(at(10, 45))
        )
        self.assertEqual(
            (morning.check_out, afternoon.check_in), (at(10, 10), at(10, 45))
        )
        self.assertEqual(self.spans(before), [(at(9), at(10, 10))])
        self.assertEqual(self.spans(after), [(at(10, 45), at(12))])

    def test_move_a_break_wholly_later(self):
        morning, afternoon, before, after = self.lunch_day()
        after.write({"date_time": at(11, 30), "unit_amount": 0.5})
        before.unlink()
        self.app.update_break(
            attendance_id=morning.id, start=utc(at(11)), end=utc(at(11, 30))
        )
        self.assertEqual((morning.check_out, afternoon.check_in), (at(11), at(11, 30)))

    def test_move_a_break_into_job_time(self):
        morning, _afternoon, before, _after = self.lunch_day()
        with self.assertRaisesRegex(UserError, "overlaps job time"):
            self.app.update_break(
                attendance_id=morning.id, start=utc(at(8, 30)), end=utc(at(10, 30))
            )
        self.assertEqual(morning.check_out, at(10))
        self.assertEqual(before.date_time_end, at(10))

    def test_move_a_break_past_clock_out(self):
        morning, afternoon, _before, _after = self.lunch_day()
        with self.assertRaisesRegex(UserError, "between the two"):
            self.app.update_break(
                attendance_id=morning.id, start=utc(at(10)), end=utc(at(17, 30))
            )
        self.assertEqual(afternoon.check_in, at(10, 30))

    def test_remove_a_break(self):
        morning, afternoon, _before, _after = self.lunch_day()
        self.app.delete_break(attendance_id=morning.id)
        self.assertEqual((morning.check_in, morning.check_out), (at(8), at(17)))
        self.assertFalse(afternoon.exists())

    def test_remove_a_break_before_an_open_period(self):
        morning = self.attendance(at(8), at(10))
        self.attendance(at(10, 30), False)
        self.app.delete_break(attendance_id=morning.id)
        self.assertFalse(morning.check_out)

    def test_no_break_after_the_last_period(self):
        only = self.attendance(at(8), at(17))
        with self.assertRaisesRegex(UserError, "no break after"):
            self.app.delete_break(attendance_id=only.id)

    def test_correct_a_clock_in(self):
        attendance = self.attendance(at(8), at(17))
        day = self.app.update_attendance(
            attendance_id=attendance.id, start=utc(at(7, 30)), end=utc(at(16))
        )
        self.assertEqual(
            (attendance.check_in, attendance.check_out), (at(7, 30), at(16))
        )
        self.assertEqual(
            (day["date"], day["hours"]), ("2026-01-05", attendance.worked_hours)
        )

    def test_someone_elses_clock_in(self):
        other = self._make_technician("Other Tech", "other.tech")
        theirs = self.env["hr.attendance"].create(
            {"employee_id": other.employee_id.id, "check_in": at(8), "check_out": at(9)}
        )
        with self.assertRaisesRegex(UserError, "isn't one of yours"):
            self.app.update_attendance(
                attendance_id=theirs.id, start=utc(at(8)), end=utc(at(10))
            )

    # -- breaks between two parts of one job ------------------------------

    def two_parts(self):
        """9-10 and 10:30-12 on one service: a 30 minute break between."""
        return (
            self.line(self.repair, at(9), at(10), self.brakes),
            self.line(self.repair, at(10, 30), at(12), self.brakes),
        )

    def test_move_a_job_break(self):
        first, second = self.two_parts()
        self.app.update_job_break(
            line_id=first.id,
            after_id=second.id,
            start=utc(at(10, 10)),
            end=utc(at(10, 45)),
        )
        self.assertEqual(self.spans(first), [(at(9), at(10, 10))])
        self.assertEqual(self.spans(second), [(at(10, 45), at(12))])

    def test_move_a_job_break_wholly_later(self):
        first, second = self.two_parts()
        self.app.update_job_break(
            line_id=first.id, after_id=second.id, start=utc(at(11)), end=utc(at(11, 30))
        )
        self.assertEqual(self.spans(first), [(at(9), at(11))])
        self.assertEqual(self.spans(second), [(at(11, 30), at(12))])

    def test_job_break_outside_the_parts(self):
        first, second = self.two_parts()
        with self.assertRaisesRegex(UserError, "between the two entries"):
            self.app.update_job_break(
                line_id=first.id, after_id=second.id, start=utc(at(8)), end=utc(at(10))
            )

    def test_job_break_needs_two_parts_of_one_service(self):
        first = self.line(self.repair, at(9), at(10), self.brakes)
        second = self.line(self.repair, at(10, 30), at(12), self.diagnostics)
        with self.assertRaisesRegex(UserError, "don't have a break"):
            self.app.delete_job_break(line_id=first.id, after_id=second.id)

    def test_remove_a_job_break(self):
        first, second = self.two_parts()
        self.app.delete_job_break(line_id=first.id, after_id=second.id)
        self.assertFalse(second.exists())
        self.assertEqual(self.spans(first), [(at(9), at(12))])
