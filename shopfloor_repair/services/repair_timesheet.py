# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from collections import defaultdict
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from odoo.addons.base_rest import restapi
from odoo.addons.base_rest.components.service import to_int
from odoo.addons.component.core import Component

from .repair_job import with_savepoint

_logger = logging.getLogger(__name__)


class ShopfloorRepairTimesheet(Component):
    """ "My Timesheets": a technician's own repair-job time entries.

    A flat, searchable, editable list - not a scenario/state machine like
    ``shopfloor.repair.job``, so this is its own service rather than more
    states bolted onto that one.
    """

    _inherit = "base.shopfloor.process"
    _name = "shopfloor.repair.timesheet"
    _usage = "repair_timesheet"
    _description = __doc__

    _timesheet_page_size = 20

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def _timesheet_domain(self, search=None):
        domain = [
            ("employee_id", "=", self.env.user.employee_id.id),
            ("repair_order_id", "!=", False),
        ]
        if search:
            search_domain = expression.OR(
                [
                    [("repair_order_id.name", "ilike", search)],
                    [("name", "ilike", search)],
                ]
            )
            # If the search text also happens to parse as a date (e.g. the
            # user typed "2026-09-10"), also match anything starting that
            # calendar day - `fields.Date.to_date` returns None rather than
            # raising on anything that isn't a plain date, so free-text
            # searches fall through to the name/description match above.
            day = fields.Date.to_date(search)
            if day:
                search_domain = expression.OR(
                    [
                        search_domain,
                        [
                            ("date_time", ">=", f"{day} 00:00:00"),
                            ("date_time", "<=", f"{day} 23:59:59"),
                        ],
                    ]
                )
            domain = expression.AND([domain, search_domain])
        return domain

    def _get_timesheet(self, line_id):
        line = self.env["account.analytic.line"].browse(line_id).exists()
        if line and line.employee_id.id == self.env.user.employee_id.id:
            return line
        return self.env["account.analytic.line"].browse()

    def _get_attendance(self, attendance_id):
        # `hr.attendance` fields are group-restricted the same way
        # `_shift_timer_data()` (repair_job.py) documents - a technician
        # has neither `group_hr_attendance_officer` nor `group_hr_user` -
        # `.sudo()` is needed just to read `employee_id` reliably here, so
        # the actual security boundary is this explicit comparison against
        # the *acting* user's own employee record (derived from
        # `self.env.user`, never from client input), not the read itself.
        attendance = self.env["hr.attendance"].sudo().browse(attendance_id).exists()
        if attendance and attendance.employee_id.id == self.env.user.employee_id.id:
            return attendance
        return self.env["hr.attendance"].browse()

    def _attendance_by_date(self, records):
        """Attendance for the calendar dates this page of timesheets spans.

        Not "today only" like `_shift_timer_data()` - this covers whatever
        historical dates are actually on screen, so each date card can show
        its own real clocked total instead of a sum of job-timer entries.
        """
        employee = self.env.user.employee_id
        dates = records.mapped("date")
        if not employee or not dates:
            return []
        date_from, date_to = min(dates), max(dates)
        attendances = (
            self.env["hr.attendance"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("check_in", ">=", f"{date_from} 00:00:00"),
                    ("check_in", "<=", f"{date_to} 23:59:59"),
                ],
                order="check_in asc",
            )
        )
        by_date = defaultdict(lambda: self.env["hr.attendance"].sudo())
        for attendance in attendances:
            by_date[attendance.check_in.date()] |= attendance
        return [
            self.data.attendance_day(date, recs)
            for date, recs in sorted(by_date.items())
        ]

    def _job_hours_by_date(self, records):
        """Job time for the calendar dates this page of timesheets spans.

        Summed server-side over *every* entry on those dates, not just the
        ones on this page: 20 entries a page means a busy day can straddle
        two pages, and a search can hide some of its entries - the band
        still has to show the whole day. A running timer still carries
        ``unit_amount = 0``, so it counts once it is stopped, matching the
        "—" its own row shows.
        """
        dates = set(records.mapped("date"))
        if not dates:
            return []
        domain = expression.AND(
            [self._timesheet_domain(), [("date", "in", list(dates))]]
        )
        groups = self.env["account.analytic.line"]._read_group(
            domain, ["date:day"], ["unit_amount:sum"]
        )
        return [
            {"date": fields.Date.to_string(date), "hours": hours}
            for date, hours in sorted(groups)
        ]

    def _timesheet_job_choices(self):
        """Jobs this technician could reassign a timesheet to.

        Exactly the jobs on "My Jobs" (``ShopfloorRepairJob._job_search``,
        same menu options): any job they can log time on there, they can
        move time onto here.
        """
        return self.component(usage="repair_job")._job_search()

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def _response_for_timesheets(self, records, size, page, message=None):
        data = {
            "records": self.data.repair_timesheets(records),
            "size": size,
            "page": page,
            "page_size": self._timesheet_page_size,
            "attendance_by_date": self._attendance_by_date(records),
            "job_hours_by_date": self._job_hours_by_date(records),
        }
        return self._response(data={"timesheets": data}, message=message)

    def _job_choices_for(self, line):
        # The line's own job always has to be pickable, even once it has left
        # `confirmed`/`under_repair` - otherwise the dialog has nothing to
        # show as the current selection.
        return self._timesheet_job_choices() | line.repair_order_id

    def _get_job_and_service(self, line, job_id, service_id):
        """Resolve a (job, service) pair a client asked to book time to.

        Returns ``(job, service, error_message)``. The job must be one of the
        jobs the dialog offered, and the service one of that job's accepted
        services - the same rule `_get_service()` applies for the timers.
        """
        job = self._job_choices_for(line).filtered(lambda j: j.id == job_id)
        if not job:
            return None, None, self.msg_store.generic_record_not_found()
        service = self.env["repair.service"]
        if service_id:
            service = job.repair_service_ids.filtered(
                lambda s: s.id == service_id and s.accepted
            )
            if not service:
                return None, None, self.msg_store.timesheet_service_not_on_job()
        return job, service, None

    def _response_for_timesheet_detail(self, line, message=None):
        data = self.data_detail.repair_timesheet_detail(
            line, jobs=self._job_choices_for(line)
        )
        return self._response(data={"timesheet": data}, message=message)

    def _response_for_attendance_day(self, attendance, message=None):
        date = attendance.check_in.date()
        siblings = (
            self.env["hr.attendance"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", attendance.employee_id.id),
                    ("check_in", ">=", f"{date} 00:00:00"),
                    ("check_in", "<=", f"{date} 23:59:59"),
                ]
            )
        )
        return self._response(
            data={"attendance_day": self.data.attendance_day(date, siblings)},
            message=message,
        )

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @restapi.method(
        [(["/timesheets"], "GET")],
        input_param=restapi.CerberusValidator("timesheets"),
        output_param=restapi.CerberusValidator("timesheets"),
    )
    def timesheets(self, search=None, page=1):
        """List this technician's own repair-job timesheets, most recent first."""
        page = max(int(page or 1), 1)
        limit = self._timesheet_page_size
        domain = self._timesheet_domain(search=search)
        AAL = self.env["account.analytic.line"]
        size = AAL.search_count(domain)
        records = AAL.search(
            domain, limit=limit, offset=(page - 1) * limit, order="date_time desc"
        )
        return self._response_for_timesheets(records, size, page)

    @restapi.method(
        [(["/timesheet/<int:line_id>"], "GET")],
        input_param=restapi.CerberusValidator("timesheet"),
        output_param=restapi.CerberusValidator("timesheet"),
    )
    def timesheet(self, line_id):
        """Open one timesheet entry for editing."""
        line = self._get_timesheet(line_id)
        if not line:
            return self._response(message=self.msg_store.generic_record_not_found())
        return self._response_for_timesheet_detail(line)

    @restapi.method(
        [(["/timesheet/<int:line_id>/update"], "POST")],
        input_param=restapi.CerberusValidator("update_timesheet"),
        output_param=restapi.CerberusValidator("update_timesheet"),
    )
    @with_savepoint
    def update_timesheet(
        self, line_id, date_time, date_time_end, job_id=None, service_id=None
    ):
        """Correct a timesheet's job, service, start time and/or end time.

        The no-overlap rule lives as a model constraint on
        ``account.analytic.line`` (see ``models/account_analytic_line.py``)
        so it protects this endpoint *and* the existing timer start/stop
        endpoints the same way - here we only need to translate the
        ``ValidationError`` it raises into a normal shopfloor message
        instead of a 500.

        Writes ``unit_amount`` directly via ``_duration()`` rather than
        writing ``date_time_end`` and trusting its inverse
        (``project_timesheet_time_control``'s ``_inverse_date_time_end``)
        to recompute it - confirmed live that inverse only fires when the
        line's UoM is hours, and silently leaves ``unit_amount`` at its old
        value otherwise, which then reads back as "still running" once the
        cache is gone. `button_end_work()` (the existing timer-stop path)
        already avoids this the same way.

        `date_time`/`date_time_end` arrive as plain JSON strings - parsed
        into real `datetime` objects before use, since `_duration()` does
        `(end - start).total_seconds()`, which on two strings raises a
        `TypeError` that its own `except` silently turns into `0` (a real
        bug caught live: the write "succeeded" but the duration silently
        came back zero).
        """
        line = self._get_timesheet(line_id)
        if not line:
            return self._response(message=self.msg_store.generic_record_not_found())
        start = fields.Datetime.to_datetime(date_time)
        end = fields.Datetime.to_datetime(date_time_end)
        if not start or not end or end <= start:
            return self._response_for_timesheet_detail(
                line, message=self.msg_store.timesheet_end_before_start()
            )
        vals = {
            "date_time": start,
            "unit_amount": line._duration(start, end),
        }
        if job_id is not None:
            job, service, error = self._get_job_and_service(line, job_id, service_id)
            if error:
                return self._response_for_timesheet_detail(line, message=error)
            # The service is always re-set along with the job: a line keeping
            # the *old* RO's service after being moved to another RO would
            # point at a service line that isn't on its own order.
            vals["repair_order_id"] = job.id
            vals["repair_service_id"] = service.id
        error = self._call_or_error(lambda: line.write(vals))
        if error:
            return self._response_for_timesheet_detail(line, message=error)
        return self._response_for_timesheet_detail(
            line, message=self.msg_store.timesheet_updated(line)
        )

    @restapi.method(
        [(["/timesheet/<int:line_id>/delete"], "POST")],
        input_param=restapi.CerberusValidator("delete_timesheet"),
        output_param=restapi.CerberusValidator("delete_timesheet"),
    )
    @with_savepoint
    def delete_timesheet(self, line_id):
        """Remove a timesheet entry the technician added in error.

        `_get_timesheet` already confines this to the caller's own lines -
        same ownership check `update_timesheet` relies on, so there is
        nothing extra to guard here.
        """
        line = self._get_timesheet(line_id)
        if not line:
            return self._response(message=self.msg_store.generic_record_not_found())
        error = self._call_or_error(line.unlink)
        if error:
            return self._response(message=error)
        return self._response(message=self.msg_store.timesheet_deleted())

    @restapi.method(
        [(["/timesheet/<int:line_id>/split"], "POST")],
        input_param=restapi.CerberusValidator("split_timesheet"),
        output_param=restapi.CerberusValidator("split_timesheet"),
    )
    @with_savepoint
    def split_timesheet(self, line_id, job_id, split_start, split_end, service_id=None):
        """Move the slice ``split_start``-``split_end`` of a timesheet to another job.

        The slice may touch either end of the entry or sit in the middle of
        it. The original line shrinks to what is left and copies carry the
        slice (on the chosen job) and, for a middle slice, the tail that
        follows it (on the original job), so together they cover exactly the
        original time. The original is shrunk *first*: the no-overlap
        constraint on ``account.analytic.line`` is checked on every write, and
        creating the slice while the original still spans it would trip it.
        """
        line = self._get_timesheet(line_id)
        if not line:
            return self._response(message=self.msg_store.generic_record_not_found())
        job, service, error = self._get_job_and_service(line, job_id, service_id)
        if error:
            return self._response(message=error)
        start, end = line.date_time, line.date_time_end
        cut_start = fields.Datetime.to_datetime(split_start)
        cut_end = fields.Datetime.to_datetime(split_end)
        if (
            not end
            or not cut_start
            or not cut_end
            or not (start <= cut_start < cut_end <= end)
            or (cut_start == start and cut_end == end)
        ):
            return self._response(message=self.msg_store.timesheet_split_invalid())

        def split():
            if cut_start == start:
                # Slice at the front: what is left starts where it ends.
                keep_start, keep_end, tail = cut_end, end, None
            else:
                keep_start, keep_end = start, cut_start
                tail = (cut_end, end) if cut_end < end else None
            line.write(
                {
                    "date_time": keep_start,
                    "unit_amount": line._duration(keep_start, keep_end),
                }
            )
            line.copy(
                {
                    "date_time": cut_start,
                    "unit_amount": line._duration(cut_start, cut_end),
                    "repair_order_id": job.id,
                    "repair_service_id": service.id,
                }
            )
            if tail:
                # Same job and service as the original: it was never moved.
                line.copy(
                    {
                        "date_time": tail[0],
                        "unit_amount": line._duration(*tail),
                    }
                )

        error = self._call_or_error(split)
        if error:
            return self._response(message=error)
        return self._response(
            message=self.msg_store.timesheet_split(self.data.job_label(job))
        )

    @restapi.method(
        [(["/timesheet/<int:line_id>/add_break"], "POST")],
        input_param=restapi.CerberusValidator("add_break"),
        output_param=restapi.CerberusValidator("add_break"),
    )
    @with_savepoint
    def add_break(self, line_id, break_start, break_end):
        """Cut a break out of the middle of a timesheet.

        The timesheet is split in two around the gap. The clock-in/out period
        that contains the break is split the same way (clock out at the start
        of the break, back in at its end), so the break also comes off the
        day's clocked total - the figure on each date's card - rather than
        only leaving a hole in the job time.

        Three cases, depending on what is clocked over the entry:

        * one period contains the break: both are split (above);
        * nothing is clocked over the entry at all (a day entered by hand, or
          worked without clocking in): only the job time is split, since there
          is no clocked time to take the break from, and the answer says so;
        * the entry is clocked, but no single period holds the break: refused,
          because splitting only the job time would leave the two records
          disagreeing about the same hours (`with_savepoint` rolls back).
        """
        line = self._get_timesheet(line_id)
        if not line:
            return self._response(message=self.msg_store.generic_record_not_found())
        start, end = line.date_time, line.date_time_end
        gap_start = fields.Datetime.to_datetime(break_start)
        gap_end = fields.Datetime.to_datetime(break_end)
        if (
            not end
            or not gap_start
            or not gap_end
            or not (start < gap_start < gap_end < end)
        ):
            return self._response(message=self.msg_store.timesheet_break_outside_line())
        # sudo + explicit employee match, for the same reason as
        # `_get_attendance()`: technicians can't read hr.attendance directly.
        attendance = (
            self.env["hr.attendance"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", line.employee_id.id),
                    ("check_in", "<=", gap_start),
                    "|",
                    ("check_out", "=", False),
                    ("check_out", ">=", gap_end),
                ],
                limit=1,
            )
        )
        if not attendance:
            clocked_over_entry = (
                self.env["hr.attendance"]
                .sudo()
                .search_count(
                    [
                        ("employee_id", "=", line.employee_id.id),
                        ("check_in", "<", end),
                        "|",
                        ("check_out", "=", False),
                        ("check_out", ">", start),
                    ]
                )
            )
            if clocked_over_entry:
                return self._response(
                    message=self.msg_store.timesheet_break_outside_attendance()
                )

        def add():
            line.write({"unit_amount": line._duration(start, gap_start)})
            line.copy(
                {
                    "date_time": gap_end,
                    "unit_amount": line._duration(gap_end, end),
                }
            )
            if not attendance:
                return
            check_out = attendance.check_out
            attendance.write({"check_out": gap_start})
            # `create`, not `copy`: hr.attendance forbids duplicating.
            attendance.create(
                {
                    "employee_id": attendance.employee_id.id,
                    "check_in": gap_end,
                    "check_out": check_out,
                }
            )

        error = self._call_or_error(add)
        if error:
            return self._response(message=error)
        return self._response(
            message=(
                self.msg_store.timesheet_break_added()
                if attendance
                else self.msg_store.timesheet_break_added_unclocked()
            )
        )

    @restapi.method(
        [(["/attendance/<int:attendance_id>/update"], "POST")],
        input_param=restapi.CerberusValidator("update_attendance"),
        output_param=restapi.CerberusValidator("update_attendance"),
    )
    @with_savepoint
    def update_attendance(self, attendance_id, date_time, date_time_end):
        """Correct one clock-in/out pair's start and/or end time.

        Same shape as `update_timesheet` above, but `worked_hours` is a
        stored compute on `check_in`/`check_out` (`hr_attendance`'s own
        `_compute_worked_hours`) - unlike `account.analytic.line`'s
        `unit_amount`, there's no inverse-method footgun here, writing
        both fields is enough for the total to recompute correctly.
        """
        attendance = self._get_attendance(attendance_id)
        if not attendance:
            return self._response(message=self.msg_store.generic_record_not_found())
        start = fields.Datetime.to_datetime(date_time)
        end = fields.Datetime.to_datetime(date_time_end)
        if not start or not end or end <= start:
            return self._response_for_attendance_day(
                attendance, message=self.msg_store.timesheet_end_before_start()
            )
        error = self._call_or_error(
            lambda: attendance.write({"check_in": start, "check_out": end})
        )
        if error:
            return self._response_for_attendance_day(attendance, message=error)
        return self._response_for_attendance_day(
            attendance, message=self.msg_store.attendance_updated()
        )

    # ------------------------------------------------------------------
    # Breaks: the gap between two clock-in/out periods of the same day
    # ------------------------------------------------------------------

    def _break_after(self, attendance_id):
        """The two periods either side of the break that follows one period.

        Returns ``(earlier, later)``; both empty when there is no such break
        (not the technician's own record, a still-open period, or nothing
        clocked in afterwards). `sudo` for the same reason as
        `_get_attendance()`, which also does the ownership check.
        """
        earlier = self._get_attendance(attendance_id)
        none = self.env["hr.attendance"].browse()
        if not earlier or not earlier.check_out:
            return none, none
        later = (
            self.env["hr.attendance"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", earlier.employee_id.id),
                    ("check_in", ">=", earlier.check_out),
                ],
                order="check_in asc",
                limit=1,
            )
        )
        return (earlier, later) if later else (none, none)

    @staticmethod
    def _same_moment(a, b):
        # `date_time_end` is computed as start + hours, so it can differ from
        # the whole-second time it was meant to equal by a few microseconds.
        return abs((a - b).total_seconds()) < 1

    @restapi.method(
        [(["/attendance/<int:attendance_id>/update_break"], "POST")],
        input_param=restapi.CerberusValidator("update_break"),
        output_param=restapi.CerberusValidator("update_break"),
    )
    @with_savepoint
    def update_break(self, attendance_id, break_start, break_end):
        """Move or resize the break that follows one clocked-in period.

        Clocking back in later (or out earlier) is just the end of one period
        and the start of the next, so this moves those two times. Where "Add
        break" had split a job timesheet at the old edges, the two job lines
        that meet the break follow it - otherwise job time would overlap the
        break. Any *other* job time inside the new break is refused rather
        than silently trimmed.
        """
        earlier, later = self._break_after(attendance_id)
        if not earlier:
            return self._response(message=self.msg_store.generic_record_not_found())
        new_start = fields.Datetime.to_datetime(break_start)
        new_end = fields.Datetime.to_datetime(break_end)
        old_start, old_end = earlier.check_out, later.check_in
        if (
            not new_start
            or not new_end
            or not (earlier.check_in < new_start < new_end)
            or (later.check_out and new_end >= later.check_out)
        ):
            return self._response(message=self.msg_store.break_edit_invalid())

        def apply():
            AAL = self.env["account.analytic.line"]
            window = (
                min(old_start, new_start) - timedelta(days=1),
                max(old_end, new_end) + timedelta(days=1),
            )
            lines = AAL.search(
                [
                    ("employee_id", "=", earlier.employee_id.id),
                    ("repair_order_id", "!=", False),
                    ("date_time", ">=", window[0]),
                    ("date_time", "<=", window[1]),
                ]
            )
            for line in lines:
                line_end = line.date_time_end
                if line_end and self._same_moment(line_end, old_start):
                    # The job time that stopped for the break: stop at the new start.
                    if new_start <= line.date_time:
                        raise ValidationError(
                            self.msg_store.break_overlaps_job()["body"]
                        )
                    line.write(
                        {"unit_amount": line._duration(line.date_time, new_start)}
                    )
                elif line_end and self._same_moment(line.date_time, old_end):
                    # The job time that resumed after it: resume at the new end.
                    if new_end >= line_end:
                        raise ValidationError(
                            self.msg_store.break_overlaps_job()["body"]
                        )
                    line.write(
                        {
                            "date_time": new_end,
                            "unit_amount": line._duration(new_end, line_end),
                        }
                    )
                elif (not line_end and line.date_time < new_end) or (
                    line_end and line.date_time < new_end and line_end > new_start
                ):
                    raise ValidationError(self.msg_store.break_overlaps_job()["body"])
            # Move the later period first when the break moves wholly later, so
            # the two periods never overlap each other part-way through.
            if new_start >= old_end:
                later.write({"check_in": new_end})
                earlier.write({"check_out": new_start})
            else:
                earlier.write({"check_out": new_start})
                later.write({"check_in": new_end})

        error = self._call_or_error(apply)
        if error:
            return self._response(message=error)
        return self._response(message=self.msg_store.break_updated())

    @restapi.method(
        [(["/attendance/<int:attendance_id>/delete_break"], "POST")],
        input_param=restapi.CerberusValidator("delete_break"),
        output_param=restapi.CerberusValidator("delete_break"),
    )
    @with_savepoint
    def delete_break(self, attendance_id):
        """Remove a break by joining the two periods around it back into one.

        The time that was the break then counts as clocked in. Job timesheets
        are left as they are - they simply sit next to each other again.
        """
        earlier, later = self._break_after(attendance_id)
        if not earlier:
            return self._response(message=self.msg_store.generic_record_not_found())
        later_out = later.check_out

        def join():
            # The later period goes first: while it exists the earlier one
            # can't be stretched over it (and `later_out` may be "still open").
            later.unlink()
            earlier.write({"check_out": later_out})

        error = self._call_or_error(join)
        if error:
            return self._response(message=error)
        return self._response(message=self.msg_store.break_deleted())

    # ------------------------------------------------------------------
    # Breaks between two parts of one job (a day with nothing clocked)
    # ------------------------------------------------------------------
    #
    # Where nothing is clocked there is no clock-out/in gap to show as a
    # break, so the break *is* the gap between two timesheet entries on the
    # same job and service - which is exactly what "Add break" leaves behind
    # (and what stopping and restarting a timer does). The page recognises
    # those gaps; these two endpoints edit and remove them, addressed by the
    # earlier entry (`line_id`) and the later one (`after_id`).

    def _job_break_parts(self, line_id, after_id):
        """The two entries either side of the break, or two empty recordsets."""
        AAL = self.env["account.analytic.line"]
        before = self._get_timesheet(line_id)
        after = self._get_timesheet(after_id)
        valid = (
            before
            and after
            and before != after
            and before.repair_order_id == after.repair_order_id
            and before.repair_service_id == after.repair_service_id
            and before.date_time_end
            and after.date_time_end
            and not (after.date_time < before.date_time_end - timedelta(seconds=1))
        )
        return (before, after) if valid else (AAL.browse(), AAL.browse())

    @restapi.method(
        [(["/timesheet/<int:line_id>/update_job_break"], "POST")],
        input_param=restapi.CerberusValidator("update_job_break"),
        output_param=restapi.CerberusValidator("update_job_break"),
    )
    @with_savepoint
    def update_job_break(self, line_id, after_id, break_start, break_end):
        """Move or resize the gap between two parts of one job.

        The earlier part is made to end at the new start and the later part to
        begin at the new end. Overlap with any *other* entry is refused by the
        model's own no-overlap rule, which `_call_or_error` turns into a plain
        message.
        """
        before, after = self._job_break_parts(line_id, after_id)
        if not before:
            return self._response(message=self.msg_store.generic_record_not_found())
        new_start = fields.Datetime.to_datetime(break_start)
        new_end = fields.Datetime.to_datetime(break_end)
        old_end = after.date_time
        after_end = after.date_time_end
        if (
            not new_start
            or not new_end
            or not (before.date_time < new_start < new_end < after_end)
        ):
            return self._response(message=self.msg_store.job_break_edit_invalid())

        def apply():
            def move_later_part():
                after.write(
                    {
                        "date_time": new_end,
                        "unit_amount": after._duration(new_end, after_end),
                    }
                )

            def move_earlier_part():
                before.write(
                    {"unit_amount": before._duration(before.date_time, new_start)}
                )

            # A break moved wholly later would make the earlier part run into
            # the later one before it has moved out of the way - so that one
            # goes first. Otherwise growing into the old gap is always safe.
            if new_start >= old_end:
                move_later_part()
                move_earlier_part()
            else:
                move_earlier_part()
                move_later_part()

        error = self._call_or_error(apply)
        if error:
            return self._response(message=error)
        return self._response(message=self.msg_store.break_updated())

    @restapi.method(
        [(["/timesheet/<int:line_id>/delete_job_break"], "POST")],
        input_param=restapi.CerberusValidator("delete_job_break"),
        output_param=restapi.CerberusValidator("delete_job_break"),
    )
    @with_savepoint
    def delete_job_break(self, line_id, after_id):
        """Remove a break by joining the two parts back into one entry."""
        before, after = self._job_break_parts(line_id, after_id)
        if not before:
            return self._response(message=self.msg_store.generic_record_not_found())
        start, end = before.date_time, after.date_time_end

        def join():
            # The later part goes first: while it exists the earlier one can't
            # be stretched over it without tripping the no-overlap rule.
            after.unlink()
            before.write({"unit_amount": before._duration(start, end)})

        error = self._call_or_error(join)
        if error:
            return self._response(message=error)
        return self._response(message=self.msg_store.job_break_deleted())

    def _call_or_error(self, func):
        try:
            func()
        except UserError as err:
            # `ValidationError` (write/create constraints) is itself a
            # `UserError` subclass; catching the parent here also covers
            # `UserError`s like `account.analytic.line.unlink()`'s own
            # `_check_state()` raising on a confirmed timesheet sheet,
            # which previously propagated uncaught into a raw REST error
            # response the frontend didn't know how to surface.
            return {"message_type": "error", "body": str(err)}
        return None


class ShopfloorRepairTimesheetValidator(Component):
    """Input validators for the repair timesheet endpoints."""

    _inherit = "base.shopfloor.validator"
    _name = "shopfloor.repair.timesheet.validator"
    _usage = "repair_timesheet.validator"

    def timesheets(self):
        return {
            "search": {"required": False, "nullable": True, "type": "string"},
            "page": {"coerce": to_int, "required": False, "type": "integer"},
        }

    def timesheet(self):
        return {"line_id": {"coerce": to_int, "required": True, "type": "integer"}}

    def update_timesheet(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "date_time": {"required": True, "type": "string"},
            "date_time_end": {"required": True, "type": "string"},
            "job_id": {
                "coerce": to_int,
                "required": False,
                "nullable": True,
                "type": "integer",
            },
            "service_id": {
                "coerce": to_int,
                "required": False,
                "nullable": True,
                "type": "integer",
            },
        }

    def split_timesheet(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "job_id": {"coerce": to_int, "required": True, "type": "integer"},
            "service_id": {
                "coerce": to_int,
                "required": False,
                "nullable": True,
                "type": "integer",
            },
            "split_start": {"required": True, "type": "string"},
            "split_end": {"required": True, "type": "string"},
        }

    def add_break(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "break_start": {"required": True, "type": "string"},
            "break_end": {"required": True, "type": "string"},
        }

    def delete_timesheet(self):
        return {"line_id": {"coerce": to_int, "required": True, "type": "integer"}}

    def update_break(self):
        return {
            "attendance_id": {"coerce": to_int, "required": True, "type": "integer"},
            "break_start": {"required": True, "type": "string"},
            "break_end": {"required": True, "type": "string"},
        }

    def delete_break(self):
        return {
            "attendance_id": {"coerce": to_int, "required": True, "type": "integer"}
        }

    def update_job_break(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "after_id": {"coerce": to_int, "required": True, "type": "integer"},
            "break_start": {"required": True, "type": "string"},
            "break_end": {"required": True, "type": "string"},
        }

    def delete_job_break(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "after_id": {"coerce": to_int, "required": True, "type": "integer"},
        }

    def update_attendance(self):
        return {
            "attendance_id": {"coerce": to_int, "required": True, "type": "integer"},
            "date_time": {"required": True, "type": "string"},
            "date_time_end": {"required": True, "type": "string"},
        }


class ShopfloorRepairTimesheetValidatorResponse(Component):
    """Response validators for the repair timesheet endpoints."""

    _inherit = "base.shopfloor.validator.response"
    _name = "shopfloor.repair.timesheet.validator.response"
    _usage = "repair_timesheet.validator.response"

    def timesheets(self):
        return self._response_schema(
            {
                "timesheets": self.schemas._schema_dict_of(
                    {
                        "records": self.schemas._schema_list_of(
                            self.schemas.repair_timesheet()
                        ),
                        "size": {"type": "integer", "required": True},
                        "page": {"type": "integer", "required": True},
                        "page_size": {"type": "integer", "required": True},
                        "attendance_by_date": self.schemas._schema_list_of(
                            self.schemas.attendance_day()
                        ),
                        "job_hours_by_date": self.schemas._schema_list_of(
                            {
                                "date": {"type": "string", "required": True},
                                "hours": self.schemas._float(),
                            }
                        ),
                    }
                )
            }
        )

    def timesheet(self):
        return self._response_schema(
            {
                "timesheet": self.schemas._schema_dict_of(
                    self.schemas_detail.repair_timesheet_detail()
                )
            }
        )

    def update_timesheet(self):
        return self.timesheet()

    def delete_timesheet(self):
        return self._response_schema()

    def split_timesheet(self):
        return self._response_schema()

    def update_break(self):
        return self._response_schema()

    def delete_break(self):
        return self._response_schema()

    def update_job_break(self):
        return self._response_schema()

    def delete_job_break(self):
        return self._response_schema()

    def add_break(self):
        return self._response_schema()

    def update_attendance(self):
        return self._response_schema(
            {
                "attendance_day": self.schemas._schema_dict_of(
                    self.schemas.attendance_day()
                )
            }
        )
