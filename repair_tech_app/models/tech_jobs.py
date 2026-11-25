# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import formataddr

from odoo.addons.repair_tech_api.facade import aware, facade, naive_utc
from odoo.addons.repair_tech_api.schemas import Ref

from ..schemas import (
    AppOptions,
    Code,
    JobDetail,
    JobSummary,
    Note,
    Service,
    Shift,
    TechSession,
    Timer,
    TimerStarted,
)
from .repair_tech_app import _ref, _service_name, plaintext

_logger = logging.getLogger(__name__)


# One facade model, split by screen across files on purpose.
class RepairTechApp(models.AbstractModel):
    _inherit = "repair.tech.app"  # pylint: disable=consider-merging-classes-inherited

    # ------------------------------------------------------------------
    # Who, and their day
    # ------------------------------------------------------------------

    @facade
    def session(self) -> TechSession:
        """The signed-in technician, their company and employee, and the
        shop's settings for the app."""
        user = self.env.user
        employee = user.employee_id
        return TechSession(
            uid=user.id,
            name=user.name,
            lang=user.lang or "en_US",
            tz=user.tz or None,
            company=Ref(id=self.env.company.id, name=self.env.company.name),
            employee=Ref(id=employee.id, name=employee.name) if employee else None,
            options=AppOptions(
                allow_finish=self._option("allow_finish", True),
                require_photo_on_fail=self._option("require_photo_on_fail"),
            ),
        )

    @facade
    def shift(self) -> Shift:
        """Clocked in or not, today's clocked hours, and the job timer running
        anywhere. Polled by the app's header."""
        return self._shift()

    @facade
    def clock_toggle(self) -> Shift:
        """Clock in, or out. Clocking out stops a running job timer
        (models/hr_employee.py)."""
        employee = self._employee()
        employee._attendance_action_change()
        return self._shift()

    def _employee(self):
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(
                _("Your user has no employee, so it can't clock in or log time.")
            )
        return employee

    def _shift(self):
        employee = self.env.user.employee_id
        running = self._running_timer(self._running_lines())
        if not employee:
            return Shift(clocked_in=False, since=None, hours_today=0.0, running=running)
        # attendance_state and hr.attendance are HR-officer fields; a
        # technician reads only their own employee's, here.
        employee = employee.sudo()
        clocked_in = employee.attendance_state == "checked_in"
        start, end = self._today_bounds()
        now = self._now()
        attendances = (
            self.env["hr.attendance"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("check_in", "<", end),
                    "|",
                    ("check_out", "=", False),
                    ("check_out", ">", start),
                ]
            )
        )
        seconds = sum(
            (min(a.check_out or now, end) - max(a.check_in, start)).total_seconds()
            for a in attendances
        )
        return Shift(
            clocked_in=clocked_in,
            since=aware(employee.last_check_in) if clocked_in else None,
            hours_today=max(seconds, 0) / 3600,
            running=running,
        )

    def _today_bounds(self):
        """Today in the user's time zone, as the naive UTC Odoo stores."""
        try:
            zone = ZoneInfo(self.env.context.get("tz") or self.env.user.tz or "UTC")
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        today = aware(self._now()).astimezone(zone).date()
        start = datetime.combine(today, time.min, tzinfo=zone)
        end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
        return naive_utc(start), naive_utc(end)

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    @facade
    def jobs(self) -> list[JobSummary]:
        """The technician's jobs: assigned, shared through the appointment
        type, or unassigned. Priority first, then by schedule."""
        running = self._running_lines()
        return [self._job_summary(job, running) for job in self._job_search()]

    @facade
    def find_job(self, code: Code) -> JobSummary | None:
        """A job from a scanned or typed code: its reference, its quote's
        number, the VIN, the plate or the unit number. ``None`` if nothing
        matches."""
        repair = self._job_from_code(code.strip())
        return self._job_summary(repair) if repair else None

    def _job_from_code(self, code):
        """Cheapest and most specific first: the order's own reference is what
        the shop prints, so it wins over a plate a customer might bring twice.
        Newest first within each: a plate or VIN matches every past visit, and
        the technician means the current one."""
        Repair = self.env["repair.order"]
        for domain in (
            [("name", "=ilike", code)],
            [("sale_order_id.name", "=ilike", code)],
            [("vehicle_id.vin_sn", "=ilike", code)],
            [("vehicle_id.license_plate", "=ilike", code)],
            # Last: a unit number is only unique within one customer's fleet.
            [("vehicle_id.unit_number", "=ilike", code)],
        ):
            repair = Repair.search(
                domain + [("company_id", "in", self.env.companies.ids)],
                order="id desc",
                limit=1,
            )
            if repair:
                return repair
        return Repair

    @facade
    def job(self, repair_id: int) -> JobDetail:
        """The job hub: the vehicle, the concern, the services with their
        timers, and what the technician may do next."""
        return self._job_detail(self._get_job(repair_id))

    @facade
    def start_repair(self, repair_id: int) -> JobDetail:
        """Move a confirmed job to Under Repair."""
        repair = self._get_job(repair_id)
        if repair.state == "draft":
            # Core action_repair_start would confirm a draft order on its own,
            # skipping the office's review of what the customer approved. A
            # draft job can be open for diagnosis, but repair work waits for
            # the office to confirm it.
            raise UserError(
                _("%s isn't confirmed yet. Ask the office to confirm it.", repair.name)
            )
        if repair.state == "confirmed":
            repair.action_repair_start()
        return self._job_detail(repair)

    @facade
    def finish(self, repair_id: int) -> JobDetail:
        """Complete the repair (core ``action_repair_end``). The technician's
        timer on the job stops: the work is done."""
        repair = self._get_job(repair_id)
        if not self._option("allow_finish", True):
            raise UserError(_("The office closes jobs in this shop."))
        if repair.state != "under_repair":
            raise UserError(_("Only a job under repair can be finished."))
        running = self._running_lines(repair)
        if running:
            running.button_end_work()
        # repair_service_workflow turns action_repair_end into a "Finalize
        # Repair" wizard for the office; the app can't show it, so skip it.
        repair.with_context(skip_service_finalize_wizard=True).action_repair_end()
        return self._job_detail(repair)

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    @facade
    def timer_start(self, repair_id: int, service_id: int) -> TimerStarted:
        """Start timing a service. A timer running anywhere else stops at the
        same instant, and the first timer of the day clocks the technician in."""
        repair = self._get_job(repair_id)
        service = self._get_service(repair, service_id)
        employee = self._employee()
        if not repair._timesheet_default_project():
            raise UserError(_("No timesheet project is set for repairs (Settings)."))
        if self._running_lines(repair, service):
            return TimerStarted(
                job=self._job_detail(repair), clocked_in=False, stopped=None
            )

        # One technician, one running timer. The old one stops at the very
        # moment the new one starts, so they can't overlap: the *next* whole
        # second. Whole, because Odoo stores no microseconds on the new line;
        # next, so a timer started a moment ago still stops with a duration
        # above zero (zero is what marks a timer as running).
        start = self._now()
        running = self._running_lines()
        stopped = self._running_timer(running)
        if running:
            start += timedelta(seconds=1)
            running.with_context(stop_dt=start).button_end_work()
        clocked_in = self._clock_in(employee)
        self.env["account.analytic.line"].create(
            {
                "name": f"{repair._timesheet_default_description()} — "
                f"{service.display_name}",
                "project_id": repair._timesheet_default_project().id,
                "employee_id": employee.id,
                "user_id": self.env.uid,
                "repair_order_id": repair.id,
                "repair_service_id": service.id,
                "date_time": start,
                # Zero marks the line as running; the time control fills it
                # in on stop.
                "unit_amount": 0.0,
            }
        )
        return TimerStarted(
            job=self._job_detail(repair), clocked_in=clocked_in, stopped=stopped
        )

    @facade
    def timer_stop(self, repair_id: int, service_id: int) -> JobDetail:
        """Stop timing a service. Stopping a timer that isn't running does
        nothing."""
        repair = self._get_job(repair_id)
        service = self._get_service(repair, service_id)
        running = self._running_lines(repair, service)
        if running:
            running.button_end_work()
        return self._job_detail(repair)

    @facade
    def stop_running(self) -> JobDetail | None:
        """Stop whatever timer the technician has running, from anywhere in
        the app. The job it ran on, or ``None`` if nothing was running."""
        running = self._running_lines()
        if not running:
            return None
        repair = running[:1].repair_order_id
        running.button_end_work()
        return self._job_detail(repair) if repair else None

    def _clock_in(self, employee):
        """Working on a job means being at work: clock in if not already.

        Never blocks the timer: a clock-in that fails is logged, not raised.
        The employee's own action, as the Clock In button is: no sudo, only the
        read of the HR-restricted state.
        """
        if employee.sudo().attendance_state == "checked_in":
            return False
        try:
            with self.env.cr.savepoint():
                employee._attendance_action_change()
        except UserError:
            _logger.warning("Could not clock %s in", employee.name, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    @facade
    def add_note(self, repair_id: int, note: Note) -> JobDetail:
        """Add a note to the job's Repair Notes. It is also posted to the
        chatter as a Technician Note, so who hears about it is the order's
        ordinary follower settings."""
        repair = self._get_job(repair_id)
        note = note.strip()
        if not note:
            raise UserError(_("The note is empty."))
        user = self.env.user
        stamp = fields.Datetime.context_timestamp(user, self._now()).strftime(
            "%Y-%m-%d %-I:%M %p"
        )
        body = Markup("<strong>[%s]</strong> %s<br/>%s") % (
            user.display_name,
            stamp,
            escape(note).replace("\n", Markup("<br/>")),
        )
        repair.internal_notes = (repair.internal_notes or Markup("")) + Markup(
            "<p>%s</p>"
        ) % body
        # message_post refuses an author without an email address, which must
        # not stop a technician writing a note: fall back to the company's,
        # then to the server's default sender, under the technician's name.
        default_from = self.env["ir.mail_server"].sudo()._get_default_from_address()
        repair.message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="repair_tech_app.mt_repair_technician_note",
            email_from=user.email_formatted
            or repair.company_id.email_formatted
            or formataddr((user.name, default_from or "noreply@localhost")),
        )
        return self._job_detail(repair)

    # ------------------------------------------------------------------
    # Record -> schema
    # ------------------------------------------------------------------

    def _job_detail(self, repair):
        running = self._running_lines(repair)
        employee = self.env.user.employee_id
        services = []
        for service in repair.repair_service_ids.filtered("accepted"):
            line = running.filtered(
                lambda line, s=service: line.repair_service_id == s
            )[:1]
            mine = service.analytic_line_ids.filtered(
                lambda line: employee and line.employee_id == employee
            )
            services.append(
                Service(
                    id=service.id,
                    name=_service_name(service),
                    estimated_hours=service.estimated_time,
                    actual_hours=service.actual_time,
                    my_hours=sum(mine.mapped("unit_amount")),
                    timer=Timer(
                        running=bool(line),
                        started_at=aware(line.date_time) if line else None,
                    ),
                )
            )
        return JobDetail(
            **self._job_summary_values(repair, running),
            internal_notes=plaintext(repair.internal_notes),
            repair_request=repair.repair_request or "",
            odometer_in=repair.odometer_in or 0.0,
            odometer_unit=repair.vehicle_odometer_unit or "",
            under_warranty=repair.under_warranty,
            sale_order=_ref(repair.sale_order_id),
            services=services,
            inspection_count=len(
                repair.inspection_ids.filtered(lambda i: i.state != "cancel")
            ),
            can_start=repair.state == "confirmed",
            can_finish=repair.state == "under_repair"
            and self._option("allow_finish", True),
            can_edit_parts=repair.state in ("draft", "confirmed", "under_repair"),
        )
