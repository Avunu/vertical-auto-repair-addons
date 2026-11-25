# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

from odoo.addons.repair_tech_api.facade import aware, facade, naive_utc
from odoo.addons.repair_tech_api.schemas import Ref

from ..schemas import (
    Attendance,
    AttendanceDay,
    DayHours,
    JobChoice,
    Notice,
    Page,
    TimesheetDetail,
    TimesheetEntry,
    TimesheetPage,
)
from .repair_tech_app import _job_label, _service_name

PAGE_SIZE = 20
Search = Annotated[str, Field(max_length=200)]


# One facade model, split by screen across files on purpose.
class RepairTechApp(models.AbstractModel):
    """My Timesheets: a technician's own repair-job time, and the clock-ins
    around it.

    Every facade here is confined to the caller's own employee: entries by
    ``_get_entry`` and attendances by ``_get_attendance``, which compare
    against ``env.user``'s employee, never against anything the client sent.
    Attendances are read with ``sudo`` because a technician isn't an HR
    officer; that comparison is the boundary.

    Overlaps are refused by the model's own constraint
    (models/account_analytic_line.py), so they hold here and for the timers
    alike.
    """

    _inherit = "repair.tech.app"  # pylint: disable=consider-merging-classes-inherited

    # ------------------------------------------------------------------
    # The list
    # ------------------------------------------------------------------

    @facade
    def timesheets(self, search: Search | None = None, page: Page = 1) -> TimesheetPage:
        """The technician's repair-job time, newest first, 20 a page; with the
        clocked time and the job time of each day on the page. ``search``
        matches the job's reference or the description, or a day
        (``YYYY-MM-DD``)."""
        domain = self._entry_domain((search or "").strip())
        AAL = self.env["account.analytic.line"]
        entries = AAL.search(
            domain,
            limit=PAGE_SIZE,
            offset=(page - 1) * PAGE_SIZE,
            order="date_time desc, id desc",
        )
        dates = sorted(set(entries.mapped("date")))
        return TimesheetPage(
            records=[self._entry(entry) for entry in entries],
            total=AAL.search_count(domain),
            page=page,
            page_size=PAGE_SIZE,
            attendance=self._attendance_days(dates),
            job_hours=self._job_hours(dates),
        )

    def _entry_domain(self, search=""):
        domain = [
            ("employee_id", "=", self.env.user.employee_id.id or False),
            ("repair_order_id", "!=", False),
        ]
        if search:
            matches = [
                [("repair_order_id.name", "ilike", search)],
                [("name", "ilike", search)],
            ]
            # Text that is also a day, "2026-09-10", finds that day too.
            day = _parse_day(search)
            if day:
                matches.append([("date", "=", day)])
            domain = expression.AND([domain, expression.OR(matches)])
        return domain

    def _attendance_days(self, dates):
        """The clocked time on each of these days, every period listed."""
        employee = self.env.user.employee_id
        if not employee or not dates:
            return []
        start, _end = self._day_bounds(dates[0])
        _start, end = self._day_bounds(dates[-1])
        attendances = (
            self.env["hr.attendance"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("check_in", ">=", start),
                    ("check_in", "<", end),
                ],
                order="check_in asc",
            )
        )
        by_day = defaultdict(lambda: self.env["hr.attendance"].sudo())
        for attendance in attendances:
            by_day[self._local_date(attendance.check_in)] |= attendance
        return [self._attendance_day(day, recs) for day, recs in sorted(by_day.items())]

    def _job_hours(self, dates):
        """Job time on each of these days, over every entry that day, not only
        the page's: a busy day can straddle two pages, and a search can hide
        some of it. A running timer counts once it stops."""
        if not dates:
            return []
        groups = self.env["account.analytic.line"]._read_group(
            expression.AND([self._entry_domain(), [("date", "in", dates)]]),
            ["date:day"],
            ["unit_amount:sum"],
        )
        return [
            DayHours(date=fields.Date.to_string(day), hours=hours)
            for day, hours in sorted(groups)
        ]

    # ------------------------------------------------------------------
    # One entry
    # ------------------------------------------------------------------

    @facade
    def timesheet(self, line_id: int) -> TimesheetDetail:
        """One entry, with the jobs it can be moved to."""
        return self._entry_detail(self._get_entry(line_id))

    @facade
    def update_timesheet(
        self,
        line_id: int,
        start: AwareDatetime,
        end: AwareDatetime,
        job_id: int | None = None,
        service_id: int | None = None,
    ) -> TimesheetDetail:
        """Correct an entry's times, and with ``job_id`` its job and service.

        The duration is written as such rather than through ``date_time_end``,
        whose inverse only works when the line's unit is hours and otherwise
        leaves the old duration - read back later as "still running".
        """
        line = self._get_entry(line_id)
        start, end = self._interval(start, end)
        vals = {"date_time": start, "unit_amount": line._duration(start, end)}
        if job_id is not None:
            job, service = self._job_and_service(line, job_id, service_id)
            # The service always moves with the job: the old job's service
            # isn't a line of the new one.
            vals["repair_order_id"] = job.id
            vals["repair_service_id"] = service.id
        line.write(vals)
        return self._entry_detail(line)

    @facade
    def delete_timesheet(self, line_id: int) -> Notice:
        """Remove an entry made by mistake."""
        self._get_entry(line_id).unlink()
        return Notice(message=_("Entry deleted."))

    @facade
    def split_timesheet(
        self,
        line_id: int,
        job_id: int,
        start: AwareDatetime,
        end: AwareDatetime,
        service_id: int | None = None,
    ) -> Notice:
        """Move the slice ``start``-``end`` of an entry to another job.

        The slice may touch either end of the entry or sit inside it. The entry
        shrinks to what is left, and copies carry the slice (on the chosen job)
        and, for a slice inside, the tail after it (on the entry's job), so
        together they cover exactly the original time. The entry shrinks
        *first*: the no-overlap constraint is checked on every write.
        """
        line = self._get_entry(line_id)
        job, service = self._job_and_service(line, job_id, service_id)
        cut_start, cut_end = self._interval(start, end)
        line_start, line_end = line.date_time, line.date_time_end
        if (
            not line_end
            or not (line_start <= cut_start < cut_end <= line_end)
            or (cut_start == line_start and cut_end == line_end)
        ):
            raise UserError(
                _(
                    "Pick a part of the entry's time to move: inside it, and not "
                    "all of it (to move all of it, change its job)."
                )
            )
        if cut_start == line_start:
            keep, tail = (cut_end, line_end), None
        else:
            keep = (line_start, cut_start)
            tail = (cut_end, line_end) if cut_end < line_end else None
        line.write({"date_time": keep[0], "unit_amount": line._duration(*keep)})
        line.copy(
            {
                "date_time": cut_start,
                "unit_amount": line._duration(cut_start, cut_end),
                "repair_order_id": job.id,
                "repair_service_id": service.id,
            }
        )
        if tail:
            line.copy({"date_time": tail[0], "unit_amount": line._duration(*tail)})
        return Notice(message=_("Time moved to %s.", _job_label(job)))

    @facade
    def add_break(
        self, line_id: int, start: AwareDatetime, end: AwareDatetime
    ) -> Notice:
        """Cut a break out of the middle of an entry.

        The entry is split around the gap, and so is the clocked period that
        holds the break (clocked out at its start, back in at its end), so the
        break comes off the day's clocked total too. When nothing is clocked
        over the entry (a day entered by hand), only the job time splits. When
        the entry is clocked but no single period holds the break, it is
        refused: splitting the job time alone would leave the two disagreeing
        about the same hours.
        """
        line = self._get_entry(line_id)
        gap_start, gap_end = self._interval(start, end)
        line_start, line_end = line.date_time, line.date_time_end
        if not line_end or not (line_start < gap_start < gap_end < line_end):
            raise UserError(_("A break has to fall inside the entry's time."))
        Attendance = self.env["hr.attendance"].sudo()
        employee = line.employee_id
        attendance = Attendance.search(
            [
                ("employee_id", "=", employee.id),
                ("check_in", "<=", gap_start),
                "|",
                ("check_out", "=", False),
                ("check_out", ">=", gap_end),
            ],
            limit=1,
        )
        if not attendance and Attendance.search_count(
            [
                ("employee_id", "=", employee.id),
                ("check_in", "<", line_end),
                "|",
                ("check_out", "=", False),
                ("check_out", ">", line_start),
            ]
        ):
            raise UserError(
                _(
                    "The break crosses a clock-out. Fix the clock-in times first, "
                    "or put the break inside one clocked period."
                )
            )
        line.write({"unit_amount": line._duration(line_start, gap_start)})
        line.copy(
            {"date_time": gap_end, "unit_amount": line._duration(gap_end, line_end)}
        )
        if not attendance:
            return Notice(
                message=_(
                    "Break added. Nothing was clocked then, so only job time changed."
                )
            )
        check_out = attendance.check_out
        attendance.write({"check_out": gap_start})
        # create, not copy: hr.attendance refuses to be duplicated.
        Attendance.create(
            {"employee_id": employee.id, "check_in": gap_end, "check_out": check_out}
        )
        return Notice(message=_("Break added, and clocked out for it."))

    # ------------------------------------------------------------------
    # Clocked periods, and the breaks between them
    # ------------------------------------------------------------------

    @facade
    def update_attendance(
        self, attendance_id: int, start: AwareDatetime, end: AwareDatetime
    ) -> AttendanceDay:
        """Correct one clocked period's start and end. Worked hours follow:
        hr.attendance computes them from the two times."""
        attendance = self._get_attendance(attendance_id)
        start, end = self._interval(start, end)
        attendance.write({"check_in": start, "check_out": end})
        day = self._local_date(attendance.check_in)
        return self._attendance_days([day])[0]

    @facade
    def update_break(
        self, attendance_id: int, start: AwareDatetime, end: AwareDatetime
    ) -> Notice:
        """Move or resize the break after a clocked period: the end of that
        period and the start of the next. The two job entries that met the
        break's old edges ("Add break" split them there) follow it; any other
        job time inside the new break is refused, not trimmed."""
        earlier, later = self._break_after(attendance_id)
        new_start, new_end = self._interval(start, end)
        old_start, old_end = earlier.check_out, later.check_in
        if not (earlier.check_in < new_start) or (
            later.check_out and new_end >= later.check_out
        ):
            raise UserError(
                _("The break has to stay between the two clocked periods' ends.")
            )
        AAL = self.env["account.analytic.line"]
        lines = AAL.search(
            [
                ("employee_id", "=", earlier.employee_id.id),
                ("repair_order_id", "!=", False),
                ("date_time", ">=", min(old_start, new_start) - timedelta(days=1)),
                ("date_time", "<=", max(old_end, new_end) + timedelta(days=1)),
            ]
        )
        overlap = _("The new break overlaps job time. Move that time first.")
        # Every change is worked out before anything is written, so a refusal
        # leaves the day exactly as it was.
        writes = []
        for line in lines:
            line_end = line.date_time_end
            if line_end and _same_moment(line_end, old_start):
                # The job time that stopped for the break stops at the new start.
                if new_start <= line.date_time:
                    raise UserError(overlap)
                grows = new_start > old_start
                writes.append(
                    (
                        grows,
                        line,
                        {"unit_amount": line._duration(line.date_time, new_start)},
                    )
                )
            elif line_end and _same_moment(line.date_time, old_end):
                # The job time that resumed after it resumes at the new end.
                if new_end >= line_end:
                    raise UserError(overlap)
                grows = new_end < old_end
                writes.append(
                    (
                        grows,
                        line,
                        {
                            "date_time": new_end,
                            "unit_amount": line._duration(new_end, line_end),
                        },
                    )
                )
            elif line.date_time < new_end and (not line_end or line_end > new_start):
                raise UserError(overlap)
        # The entry that shrinks goes first, making room for the one that
        # grows: the no-overlap constraint checks every write.
        for _grows, line, vals in sorted(writes, key=lambda write: write[0]):
            line.write(vals)
        # Move the later period first when the break moves wholly later, so the
        # two never overlap part way through.
        if new_start >= old_end:
            later.write({"check_in": new_end})
            earlier.write({"check_out": new_start})
        else:
            earlier.write({"check_out": new_start})
            later.write({"check_in": new_end})
        return Notice(message=_("Break updated."))

    @facade
    def delete_break(self, attendance_id: int) -> Notice:
        """Remove the break after a clocked period by joining it to the next.
        The break's time counts as clocked; job entries stay as they are."""
        earlier, later = self._break_after(attendance_id)
        check_out = later.check_out
        # The later period goes first: while it exists the earlier one can't
        # stretch over it.
        later.unlink()
        earlier.write({"check_out": check_out})
        return Notice(message=_("Break removed."))

    def _break_after(self, attendance_id):
        earlier = self._get_attendance(attendance_id)
        later = earlier.browse()
        if earlier.check_out:
            later = earlier.search(
                [
                    ("employee_id", "=", earlier.employee_id.id),
                    ("check_in", ">=", earlier.check_out),
                ],
                order="check_in asc",
                limit=1,
            )
        if not later:
            raise UserError(_("There is no break after that period."))
        return earlier, later

    # ------------------------------------------------------------------
    # Breaks between two parts of one job (a day with nothing clocked)
    # ------------------------------------------------------------------
    #
    # With nothing clocked there is no clock-out to show as a break, so the
    # break *is* the gap between two entries on the same job and service: what
    # "Add break" leaves behind, and what stopping and restarting a timer does.
    # The app recognises those gaps; these edit and remove them, addressed by
    # the entry before (line_id) and the one after (after_id).

    @facade
    def update_job_break(
        self, line_id: int, after_id: int, start: AwareDatetime, end: AwareDatetime
    ) -> Notice:
        """Move or resize the gap between two parts of one job."""
        before, after = self._job_break(line_id, after_id)
        new_start, new_end = self._interval(start, end)
        after_end, old_end = after.date_time_end, after.date_time
        if not (before.date_time < new_start and new_end < after_end):
            raise UserError(_("The break has to stay between the two entries' ends."))

        def move_later():
            after.write(
                {
                    "date_time": new_end,
                    "unit_amount": after._duration(new_end, after_end),
                }
            )

        def move_earlier():
            before.write({"unit_amount": before._duration(before.date_time, new_start)})

        # Moved wholly later, the earlier part would run into the later one
        # before it got out of the way: that one goes first.
        for step in (
            (move_later, move_earlier)
            if new_start >= old_end
            else (
                move_earlier,
                move_later,
            )
        ):
            step()
        return Notice(message=_("Break updated."))

    @facade
    def delete_job_break(self, line_id: int, after_id: int) -> Notice:
        """Join two parts of one job back into one entry."""
        before, after = self._job_break(line_id, after_id)
        start, end = before.date_time, after.date_time_end
        after.unlink()
        before.write({"unit_amount": before._duration(start, end)})
        return Notice(message=_("Break removed."))

    def _job_break(self, line_id, after_id):
        before, after = self._get_entry(line_id), self._get_entry(after_id)
        valid = (
            before != after
            and before.repair_order_id == after.repair_order_id
            and before.repair_service_id == after.repair_service_id
            and before.date_time_end
            and after.date_time_end
            and after.date_time >= before.date_time_end - timedelta(seconds=1)
        )
        if not valid:
            raise UserError(_("Those two entries don't have a break between them."))
        return before, after

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def _get_entry(self, line_id):
        line = self.env["account.analytic.line"].browse(line_id).exists()
        employee = self.env.user.employee_id
        if not line or not employee or line.employee_id != employee:
            raise UserError(_("That entry isn't one of yours."))
        if not line.repair_order_id:
            raise UserError(_("That entry isn't time on a job."))
        return line

    def _get_attendance(self, attendance_id):
        attendance = self.env["hr.attendance"].sudo().browse(attendance_id).exists()
        employee = self.env.user.employee_id
        if not attendance or not employee or attendance.employee_id != employee:
            raise UserError(_("That clock-in isn't one of yours."))
        return attendance

    def _job_choices(self, line):
        """The jobs time can move to: those on My Jobs, and the entry's own
        (which may have left that list) so it stays the current choice."""
        return self._job_search() | line.repair_order_id

    def _job_and_service(self, line, job_id, service_id):
        job = self._job_choices(line).filtered(lambda job: job.id == job_id)
        if not job:
            raise UserError(_("That job isn't one you can book time to."))
        service = self.env["repair.service"]
        if service_id:
            service = job.repair_service_ids.filtered(
                lambda s: s.id == service_id and s.accepted
            )
            if not service:
                raise UserError(_("That service isn't an accepted service on the job."))
        return job, service

    def _interval(self, start, end):
        start, end = naive_utc(start), naive_utc(end)
        if end <= start:
            raise UserError(_("The end has to come after the start."))
        return start, end

    # ------------------------------------------------------------------
    # Days, in the technician's time zone
    # ------------------------------------------------------------------

    def _zone(self):
        try:
            return ZoneInfo(self.env.context.get("tz") or self.env.user.tz or "UTC")
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _local_date(self, value):
        return aware(value).astimezone(self._zone()).date()

    def _day_bounds(self, day):
        zone = self._zone()
        start = datetime.combine(day, time.min, tzinfo=zone)
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
        return naive_utc(start), naive_utc(end)

    # ------------------------------------------------------------------
    # Record -> schema
    # ------------------------------------------------------------------

    def _entry(self, line):
        repair = line.repair_order_id
        service = line.repair_service_id
        return TimesheetEntry(
            id=line.id,
            description=line.name or "",
            date=fields.Date.to_string(line.date),
            start=aware(line.date_time),
            end=aware(line.date_time_end) if line.unit_amount else None,
            hours=line.unit_amount,
            job=Ref(id=repair.id, name=_job_label(repair)) if repair else None,
            job_ref=repair.name or "",
            service=Ref(id=service.id, name=_service_name(service))
            if service
            else None,
        )

    def _entry_detail(self, line):
        return TimesheetDetail(
            entry=self._entry(line),
            jobs=[
                JobChoice(
                    id=job.id,
                    name=_job_label(job),
                    ref=job.name,
                    customer=job.partner_id.name or "",
                    services=[
                        Ref(id=service.id, name=_service_name(service))
                        for service in job.repair_service_ids.filtered("accepted")
                    ],
                )
                for job in self._job_choices(line)
            ],
        )

    def _attendance_day(self, day, attendances):
        return AttendanceDay(
            date=fields.Date.to_string(day),
            hours=sum(attendances.mapped("worked_hours")),
            records=[
                Attendance(
                    id=rec.id,
                    check_in=aware(rec.check_in),
                    check_out=aware(rec.check_out),
                )
                for rec in attendances
            ],
        )


def _parse_day(text):
    try:
        return fields.Date.to_date(text)
    except ValueError:
        return None


def _same_moment(a, b):
    # date_time_end is start + hours, so it can miss the whole second it was
    # meant to be by a few microseconds.
    return abs((a - b).total_seconds()) < 1
