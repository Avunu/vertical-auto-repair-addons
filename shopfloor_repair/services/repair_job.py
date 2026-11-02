# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import binascii
import logging
from datetime import timedelta
from functools import wraps

from markupsafe import Markup, escape

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from odoo.addons.base_rest import restapi
from odoo.addons.base_rest.components.service import to_bool, to_int
from odoo.addons.component.core import Component
from odoo.addons.shop_inspection.models.fleet_vehicle_inspection_line import (
    SEVERITY_SELECTION,
)

_logger = logging.getLogger(__name__)

# Grades that mean "the customer has a problem here". Used to decide whether
# a photo is required when the `require_photo_on_fail` option is on.
PROBLEM_SEVERITIES = ("today", "attention", "fail_state")

# States in which the technician may still change parts.
EDITABLE_REPAIR_STATES = ("draft", "confirmed", "under_repair")


def with_savepoint(method):
    """Roll back whatever the endpoint did when it answers with an error.

    Odoo methods such as ``action_repair_end`` write as they go and only then
    raise, so without this an error response would leave half the work
    committed. Modelled on shopfloor_single_product_transfer.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        savepoint = self._actions_for("savepoint").new()
        response = method(self, *args, **kwargs)
        if response.get("message", {}).get("message_type") == "error":
            savepoint.rollback()
        savepoint.release()
        return response

    return wrapper


class ShopfloorRepairJob(Component):
    """Technician-facing repair shop floor.

    One scenario covering the whole job: pick a job off your list (or scan the
    work order, a plate or a VIN), run the work timer, record which parts you
    actually used, add parts from the catalog, and fill in the digital vehicle
    inspection.

    States: ``job_list``, ``job_detail``, ``parts``, ``part_detail``,
    ``catalog_search``, ``catalog_detail``, ``inspection_list``,
    ``inspection_odometer``, ``inspection_lines``, ``inspection_line_detail``.
    """

    _inherit = "base.shopfloor.process"
    _name = "shopfloor.repair.job"
    _usage = "repair_job"
    _description = __doc__

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def _response_for_job_list(self, message=None, popup=None):
        records = self._job_search()
        return self._response(
            next_state="job_list",
            data={"records": self.data.repair_jobs(records)},
            message=message,
            popup=popup,
        )

    def _response_for_job_detail(self, repair, message=None, popup=None):
        data = {
            "record": self.data_detail.repair_job_detail(
                repair, running_line=self._running_timer_lines(repair)
            ),
            "options": self._client_options(),
        }
        return self._response(
            next_state="job_detail", data=data, message=message, popup=popup
        )

    def _response_for_services(self, repair, message=None, popup=None):
        data = {
            "job": self.data.repair_job(repair),
            "records": self.data.repair_services(
                self._job_services(repair),
                running_line=self._running_timer_lines(repair),
            ),
            "notes": self.data._plaintext(repair.internal_notes),
        }
        return self._response(
            next_state="services", data=data, message=message, popup=popup
        )

    def _response_for_parts(self, repair, message=None, popup=None):
        data = {
            "record": self.data.repair_job(repair),
            "parts": self.data.repair_parts(self._job_parts(repair)),
        }
        return self._response(
            next_state="parts", data=data, message=message, popup=popup
        )

    def _response_for_part_detail(self, move, message=None, popup=None):
        data = {
            "record": self.data.repair_part(move),
            "job": self.data.repair_job(move.repair_id),
        }
        return self._response(
            next_state="part_detail", data=data, message=message, popup=popup
        )

    def _response_for_catalog_search(
        self, repair, products, size, page, message=None
    ):
        data = {
            "job": self.data.repair_job(repair),
            "records": self.data.catalog_products(products),
            "size": size,
            "page": page,
            "page_size": self._catalog_page_size,
            "categories": [
                {"id": categ.id, "name": categ.display_name}
                for categ in self._catalog_categories()
            ],
        }
        return self._response(next_state="catalog_search", data=data, message=message)

    def _response_for_catalog_detail(self, repair, product, message=None):
        data = {
            "job": self.data.repair_job(repair),
            "record": self.data.catalog_product(product),
        }
        return self._response(next_state="catalog_detail", data=data, message=message)

    def _response_for_inspection_list(self, repair, message=None):
        data = {
            "job": self.data.repair_job(repair),
            "records": self.data.inspections(self._job_inspections(repair)),
            "templates": [
                {"id": tmpl.id, "name": tmpl.display_name}
                for tmpl in self._inspection_templates()
            ],
            "default_odometer": repair.odometer_in
            or repair.vehicle_id.odometer
            or 0.0,
            "odometer_unit": repair.vehicle_odometer_unit or "",
        }
        return self._response(
            next_state="inspection_list", data=data, message=message
        )

    def _response_for_inspection_lines(self, inspection, message=None):
        lines = inspection.inspection_line_ids.sorted(
            lambda line: (
                line.category_id.sequence,
                line.category_id.id,
                line.sequence,
                line.id,
            )
        )
        data = {
            "record": self.data.inspection(inspection),
            "job": self.data.repair_job(inspection.repair_id),
            "lines": self.data.inspection_lines(lines),
        }
        return self._response(
            next_state="inspection_lines", data=data, message=message
        )

    def _response_for_inspection_line_detail(self, line, message=None):
        data = {
            "record": self.data.inspection_line(line),
            "inspection": self.data.inspection(line.inspection_id),
            "job": self.data.repair_job(line.inspection_id.repair_id),
            "choices": self._inspection_choices(line),
        }
        return self._response(
            next_state="inspection_line_detail", data=data, message=message
        )

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    @property
    def _catalog_page_size(self):
        return int(self.options.get("catalog_page_size") or 30)

    def _client_options(self):
        """Feature flags the app needs in order to hide buttons it must not show."""
        return {
            "allow_repair_end": bool(self.options.get("allow_repair_end", True)),
            "require_photo_on_fail": bool(
                self.options.get("require_photo_on_fail", False)
            ),
        }

    # ------------------------------------------------------------------
    # Job lookup
    # ------------------------------------------------------------------

    def _job_search_domain(self):
        """Jobs the technician should see on "My Jobs".

        Confirmed/under-repair jobs show up regardless of their services'
        acceptance -- unchanged, so existing jobs already in progress are
        never hidden by the newer `accepted` field defaulting to False.

        A *draft* job also shows up, but only once it has at least one
        accepted service. That is deliberate: the office can accept just a
        "Diagnostics" line and send the job to a technician before
        confirming the repair at all, so the technician can diagnose the
        vehicle and report back what else is needed before the customer
        approves a final scope and the office clicks "Confirm Repair".
        Without an accepted service a draft job has nothing for the
        technician to do yet, so it stays off the list.

        Besides their own jobs, a technician sees every job whose appointment
        type they are bookable for, even one assigned to someone else: the
        type is the pool of people who can do that work, and any of them
        may pick it up and log time on it.
        """
        uid = self.env.user.id
        assignment = expression.OR(
            [[("technician_id", "=", uid)], [("booking_type_user_ids", "in", uid)]]
        )
        if self.options.get("include_responsible"):
            assignment = expression.OR([assignment, [("user_id", "=", uid)]])
        if self.options.get("show_unassigned", True):
            assignment = expression.OR([assignment, [("technician_id", "=", False)]])
        state_domain = expression.OR(
            [
                [("state", "in", ("confirmed", "under_repair"))],
                [
                    ("state", "=", "draft"),
                    ("repair_service_ids.accepted", "=", True),
                ],
            ]
        )
        return expression.AND(
            [
                state_domain,
                [("company_id", "in", self.env.companies.ids)],
                assignment,
            ]
        )

    def _job_search(self):
        return self.env["repair.order"].search(
            self._job_search_domain(), order="priority desc, schedule_date asc, id asc"
        )

    def _get_repair(self, repair_id):
        """Fetch one job.

        Deliberately not filtered by the list domain: right after ``finish``
        the job is ``done`` and would drop out of it, but the app still has to
        render the screen it is standing on.
        """
        return self.env["repair.order"].browse(repair_id).exists()

    def _job_parts(self, repair):
        return self.data._repair_job_parts(repair)

    def _get_part(self, move_id):
        move = self.env["stock.move"].browse(move_id).exists()
        if move and move.repair_id and move.repair_line_type == "add":
            return move
        return self.env["stock.move"].browse()

    def _job_services(self, repair):
        """Services the shop floor app tracks time against.

        Only accepted ones: an unaccepted service is not yet something the
        customer has agreed to pay for, so it has no business showing up as
        a timer the technician can start.
        """
        return repair.repair_service_ids.filtered("accepted")

    def _get_service(self, repair, service_id):
        service = self.env["repair.service"].browse(service_id).exists()
        if service and service.repair_id == repair and service.accepted:
            return service
        return self.env["repair.service"].browse()

    # ------------------------------------------------------------------
    # Endpoints -- jobs
    # ------------------------------------------------------------------

    @restapi.method([(["/jobs"], "GET")],
        input_param=restapi.CerberusValidator("jobs"),
        output_param=restapi.CerberusValidator("jobs"),
    )
    def jobs(self):
        """List the repair orders assigned to the technician."""
        return self._response_for_job_list()

    @restapi.method([(["/scan/<string:identifier>"], "GET")],
        input_param=restapi.CerberusValidator("scan"),
        output_param=restapi.CerberusValidator("scan"),
    )
    def scan(self, identifier):
        """Open a job from a work order number, quote number, plate or VIN."""
        repair = self._actions_for("search").repair_from_scan(identifier)
        if not repair:
            return self._response_for_job_list(message=self.msg_store.job_not_found())
        return self._response_for_job_detail(repair)

    @restapi.method([(["/job/<int:repair_id>"], "GET")],
        input_param=restapi.CerberusValidator("job"),
        output_param=restapi.CerberusValidator("job"),
    )
    def job(self, repair_id):
        """Open a job by id."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        return self._response_for_job_detail(repair)

    @restapi.method([(["/job/<int:repair_id>/start_repair"], "POST")],
        input_param=restapi.CerberusValidator("start_repair"),
        output_param=restapi.CerberusValidator("start_repair"),
    )
    @with_savepoint
    def start_repair(self, repair_id):
        """Move the job to Under Repair."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if repair.state == "under_repair":
            return self._response_for_job_detail(
                repair, message=self.msg_store.repair_already_started(repair)
            )
        if repair.state == "draft":
            # Core `action_repair_start` auto-confirms a draft order with no
            # gate of its own - letting that through here would let a
            # technician silently confirm (and start) a job the office has
            # only accepted a diagnostics line on, skipping the Confirm
            # Repair wizard's review entirely. A draft job can still be
            # open (see `_job_search_domain`) so the technician can diagnose
            # it and log time against accepted services; only the actual
            # repair work waits on the office's explicit confirmation.
            return self._response_for_job_detail(
                repair, message=self.msg_store.repair_not_confirmed(repair)
            )
        message = self._call_or_error(repair.action_repair_start)
        return self._response_for_job_detail(
            repair, message=message or self.msg_store.repair_started(repair)
        )

    @restapi.method([(["/job/<int:repair_id>/finish"], "POST")],
        input_param=restapi.CerberusValidator("finish"),
        output_param=restapi.CerberusValidator("finish"),
    )
    @with_savepoint
    def finish(self, repair_id):
        """Complete the repair (core ``action_repair_end``)."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if not self.options.get("allow_repair_end", True):
            return self._response_for_job_detail(
                repair, message=self.msg_store.repair_end_not_allowed()
            )
        if repair.state != "under_repair":
            return self._response_for_job_detail(
                repair, message=self.msg_store.repair_must_be_under_repair()
            )
        # Leaving a timer running would bank hours against a closed job, and
        # the technician has clearly stopped working on it.
        self._stop_running_timers(self._running_timer_lines(repair))
        # repair_service_workflow turns `action_repair_end` into a "Finalize
        # Repair" wizard action for the office; the shop floor has no way to
        # show it, and discarding that return value reported the job as
        # finished while it stayed under repair.
        message = self._call_or_error(
            repair.with_context(skip_service_finalize_wizard=True).action_repair_end
        )
        return self._response_for_job_detail(
            repair, message=message or self.msg_store.repair_finished(repair)
        )

    # ------------------------------------------------------------------
    # Endpoints -- timer
    # ------------------------------------------------------------------

    def _running_timer_lines(self, repair=None, service=None):
        """Analytic lines with a timer running for the current user.

        ``_running_domain`` is user-global by design (start time set, no
        duration yet), so without the repair filter this returns the timer on
        *any* job -- which is exactly what the "another timer is running"
        check needs.
        """
        AAL = self.env["account.analytic.line"]
        domain = AAL._running_domain()
        if repair is not None:
            domain = expression.AND([domain, [("repair_order_id", "=", repair.id)]])
        if service is not None:
            domain = expression.AND(
                [domain, [("repair_service_id", "=", service.id)]]
            )
        return AAL.search(domain)

    def _stop_running_timers(self, lines):
        if lines:
            lines.button_end_work()
        return lines

    def _check_timer_prerequisites(self, repair):
        """Fail loudly and usefully instead of letting hr_timesheet swallow it."""
        if not self.env.user.employee_id:
            return self.msg_store.timer_no_employee()
        if not repair._timesheet_default_project():
            return self.msg_store.timer_no_project()
        return None

    def _clock_in_if_needed(self):
        """Start the day clock with the first job timer. Returns whether it did.

        Working on a job means being at work, so a technician who forgot to
        clock in shouldn't end up with job time and no clocked day. Does what
        the Clock In screen does (`clock_toggle`): the employee's own
        `_attendance_action_change`, no `sudo`. Only ever clocks *in* - the end
        of the day can't be known here, which is why the response tells them to
        clock out.

        `attendance_state` is group-restricted, hence the `sudo()` read, as in
        `_shift_timer_data()`. A failure to clock in must never stop the timer
        from starting, so it is contained in a savepoint and logged instead.
        """
        employee = self.env.user.employee_id
        if employee.sudo().attendance_state == "checked_in":
            return False
        try:
            with self.env.cr.savepoint():
                employee._attendance_action_change()
        except UserError:
            _logger.warning(
                "Could not clock %s in when starting a job timer",
                employee.name,
                exc_info=True,
            )
            return False
        return True

    def _prepare_timer_vals(self, repair, service, start):
        return {
            "name": f"{repair._timesheet_default_description()} — {service.display_name}",
            "project_id": repair._timesheet_default_project().id,
            "employee_id": self.env.user.employee_id.id,
            "user_id": self.env.user.id,
            "repair_order_id": repair.id,
            "repair_service_id": service.id,
            "date_time": start,
            # A zero duration is what marks the line as still running; the OCA
            # time control fills it in on stop.
            "unit_amount": 0.0,
        }

    @restapi.method(
        [(["/job/<int:repair_id>/service/<int:service_id>/timer_start"], "POST")],
        input_param=restapi.CerberusValidator("service_timer_start"),
        output_param=restapi.CerberusValidator("service_timer_start"),
    )
    @with_savepoint
    def service_timer_start(self, repair_id, service_id):
        """Start the work timer on one service, stopping any other running one."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        service = self._get_service(repair, service_id)
        if not service:
            return self._response_for_services(
                repair, message=self.msg_store.generic_record_not_found()
            )
        error = self._check_timer_prerequisites(repair)
        if error:
            return self._response_for_services(repair, message=error)
        if self._running_timer_lines(repair=repair, service=service):
            return self._response_for_services(
                repair, message=self.msg_store.service_timer_already_running(service)
            )
        # One technician, one running timer: switching to this service ends
        # whatever they were timing before, on this job or any other. The old
        # timer stops at the very moment the new one starts, so the two can't
        # overlap. That moment is the *next* whole second: whole, because
        # Odoo stores no microseconds on the new line; next, so a timer started
        # a moment ago still stops with a duration above zero (zero is what
        # marks a timer as running).
        start = fields.Datetime.now()
        running = self._running_timer_lines()
        if running:
            start += timedelta(seconds=1)
            self._stop_running_timers(running.with_context(stop_dt=start))
        clocked_in = self._clock_in_if_needed()
        self.env["account.analytic.line"].create(
            self._prepare_timer_vals(repair, service, start)
        )
        repair.invalidate_recordset(["timesheet_ids", "timesheet_total_hours"])
        service.invalidate_recordset(["actual_time"])
        return self._response_for_services(
            repair,
            message=self.msg_store.service_timer_started(
                service, clocked_in=clocked_in, stopped=running[:1]
            ),
        )

    @restapi.method(
        [(["/job/<int:repair_id>/service/<int:service_id>/timer_stop"], "POST")],
        input_param=restapi.CerberusValidator("service_timer_stop"),
        output_param=restapi.CerberusValidator("service_timer_stop"),
    )
    @with_savepoint
    def service_timer_stop(self, repair_id, service_id):
        """Stop the work timer on one service."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        service = self._get_service(repair, service_id)
        if not service:
            return self._response_for_services(
                repair, message=self.msg_store.generic_record_not_found()
            )
        running = self._running_timer_lines(repair=repair, service=service)
        if not running:
            return self._response_for_services(
                repair, message=self.msg_store.service_timer_not_running(service)
            )
        self._stop_running_timers(running)
        repair.invalidate_recordset(["timesheet_ids", "timesheet_total_hours"])
        service.invalidate_recordset(["actual_time"])
        return self._response_for_services(
            repair, message=self.msg_store.service_timer_stopped(service)
        )

    # ------------------------------------------------------------------
    # Endpoints -- shift timer
    # ------------------------------------------------------------------

    def _shift_timer_data(self):
        """Elapsed time since today's hr_attendance clock-in, if any.

        `attendance_state`/`last_check_in` live on `hr.employee`, group-
        restricted to `hr_attendance.group_hr_attendance_officer,hr.
        group_hr_user` - a technician using this app is very unlikely to be
        in either, so this reads them with `sudo()`, the same way
        `repair_timesheet_time_control` already reads `vehicle.sudo().
        display_name` elsewhere in this stack. Deliberately the same shape
        as `data.timer()` (`running`/`started_at`/`elapsed_hours`) so the
        frontend can reuse the same client-side ticking logic.

        Also includes `current_job` (the same shape `data.service_timer()`
        returns for whichever service has a running work timer, if any) so
        the app-bar's compact job timer can poll for this independently of
        the repair_job scenario being mounted - the services screen still
        publishes it eagerly right after starting/stopping a timer there (no
        need to wait a poll cycle), but this is what keeps it live and
        correct once the technician has navigated away to My Timesheets, the
        Clock screen, or anywhere else.
        """
        employee = self.env.user.employee_id
        if not employee:
            return {
                "running": False,
                "started_at": None,
                "elapsed_hours": 0.0,
                "current_job": None,
            }
        employee = employee.sudo()
        running = employee.attendance_state == "checked_in"
        started_at = employee.last_check_in if running else None
        elapsed = 0.0
        if started_at:
            elapsed = self.env["account.analytic.line"]._duration(
                started_at, fields.Datetime.now()
            )
        job_line = self._running_timer_lines()[:1]
        current_job = None
        if job_line and job_line.repair_service_id:
            current_job = self.data.service_timer(
                job_line.repair_service_id, job_line
            )
        return {
            "running": running,
            "started_at": (
                fields.Datetime.to_string(started_at) if started_at else None
            ),
            "elapsed_hours": elapsed,
            "current_job": current_job,
        }

    @restapi.method([(["/shift_timer"], "GET")],
        input_param=restapi.CerberusValidator("shift_timer"),
        output_param=restapi.CerberusValidator("shift_timer"),
    )
    def shift_timer(self):
        """Polled by the app's header to show a running "Day:" timer."""
        return self._response(data={"shift_timer": self._shift_timer_data()})

    @restapi.method([(["/clock_toggle"], "POST")],
        input_param=restapi.CerberusValidator("clock_toggle"),
        output_param=restapi.CerberusValidator("clock_toggle"),
    )
    def clock_toggle(self):
        """Clock in/out of hr_attendance from inside the app.

        Always self-service - acts on ``self.env.user.employee_id``, the
        same person making this call under their own API key. No
        ``sudo()``: this *is* the employee's own action, unlike the
        cascade-stop-timer side effect in
        ``hr.employee._stop_repair_timers_on_clock_out`` (models/
        hr_employee.py), which runs regardless of who or what triggered
        the underlying clock-out.
        """
        employee = self.env.user.employee_id
        if not employee:
            return self._response(
                data={"shift_timer": self._shift_timer_data()},
                message=self.msg_store.timer_no_employee(),
            )
        employee._attendance_action_change()
        return self._response(data={"shift_timer": self._shift_timer_data()})

    # ------------------------------------------------------------------
    # Endpoints -- services
    # ------------------------------------------------------------------

    @restapi.method([(["/job/<int:repair_id>/services"], "GET")],
        input_param=restapi.CerberusValidator("services"),
        output_param=restapi.CerberusValidator("services"),
    )
    def services(self, repair_id):
        """List this job's accepted services, each with its own timer."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        return self._response_for_services(repair)

    @restapi.method([(["/job/<int:repair_id>/add_note"], "POST")],
        input_param=restapi.CerberusValidator("add_note"),
        output_param=restapi.CerberusValidator("add_note"),
    )
    @with_savepoint
    def add_note(self, repair_id, note):
        """Append a technician's note to the order's Repair Notes.

        The note is also posted to the chatter under the "Technician Note"
        subtype, so who gets told is ordinary Odoo follower configuration
        (Followers -> Edit Subscription) rather than anything app-specific.
        """
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        note = (note or "").strip()
        if not note:
            return self._response_for_services(
                repair, message=self.msg_store.note_empty()
            )
        error = self._call_or_error(lambda: self._add_note(repair, note))
        if error:
            return self._response_for_services(repair, message=error)
        return self._response_for_services(
            repair, message=self.msg_store.note_added()
        )

    def _add_note(self, repair, note):
        user = self.env.user
        stamp = fields.Datetime.context_timestamp(
            user, fields.Datetime.now()
        ).strftime("%Y-%m-%d %-I:%M %p")
        body = Markup("<strong>[%s]</strong> %s<br/>%s") % (
            user.display_name,
            stamp,
            escape(note).replace("\n", Markup("<br/>")),
        )
        repair.internal_notes = (repair.internal_notes or Markup("")) + Markup(
            "<p>%s</p>"
        ) % body
        # Explicit email_from: message_post refuses to run for an author with
        # no email address, which must not stop a technician writing a note
        # (same reason `_notify_part_added` uses `_message_log`).
        repair.message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="shopfloor_repair.mt_repair_technician_note",
            email_from=user.email_formatted or repair.company_id.email_formatted,
        )

    # ------------------------------------------------------------------
    # Endpoints -- parts
    # ------------------------------------------------------------------

    @restapi.method([(["/job/<int:repair_id>/parts"], "GET")],
        input_param=restapi.CerberusValidator("parts"),
        output_param=restapi.CerberusValidator("parts"),
    )
    def parts(self, repair_id):
        """List the parts the job expects, with what has been used so far."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        return self._response_for_parts(repair)

    @restapi.method([(["/job/<int:repair_id>/scan_part"], "POST")],
        input_param=restapi.CerberusValidator("scan_part"),
        output_param=restapi.CerberusValidator("scan_part"),
    )
    def scan_part(self, repair_id, barcode):
        """Scan a part barcode and jump to it.

        A code that matches a part already on the job opens that part; a code
        that only matches a catalogue product offers to add it.
        """
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        search = self._actions_for("search")
        product = search.product_from_scan(barcode)
        if not product:
            lot = search.lot_from_scan(barcode)
            product = lot.product_id
        if not product:
            return self._response_for_parts(
                repair, message=self.msg_store.part_not_found()
            )
        move = self._job_parts(repair).filtered(
            lambda m: m.product_id == product
        )[:1]
        if move:
            return self._response_for_part_detail(move)
        return self._response_for_catalog_detail(
            repair, product, message=self.msg_store.part_not_on_job(product)
        )

    @restapi.method([(["/part/<int:move_id>/set_quantity"], "POST")],
        input_param=restapi.CerberusValidator("set_quantity"),
        output_param=restapi.CerberusValidator("set_quantity"),
    )
    @with_savepoint
    def set_quantity(self, move_id, quantity, lot_id=None, lot_name=None):
        """Record how much of a part was actually used.

        Writes ``stock.move.quantity`` only. Touching ``product_uom_qty``
        would make core rewrite the customer's approved sale order line.

        ``lot_name`` is what a scanner produces; ``lot_id`` is what a picker
        produces. Accept both.
        """
        move = self._get_part(move_id)
        if not move:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if move.repair_id.state not in EDITABLE_REPAIR_STATES:
            return self._response_for_parts(
                move.repair_id, message=self.msg_store.part_job_closed(move.repair_id)
            )
        if quantity < 0:
            return self._response_for_part_detail(
                move, message=self.msg_store.part_negative_quantity()
            )
        lot = None
        if lot_id:
            lot = self.env["stock.lot"].browse(lot_id).exists()
        elif lot_name:
            lot = self._actions_for("search").lot_from_scan(
                lot_name, product=move.product_id
            )
            if not lot:
                return self._response_for_part_detail(
                    move, message=self.msg_store.lot_not_found(lot_name)
                )
        message = self._set_move_quantity(move, quantity, lot=lot)
        if message:
            return self._response_for_part_detail(move, message=message)
        return self._response_for_parts(
            move.repair_id, message=self.msg_store.part_quantity_updated(move)
        )

    @restapi.method([(["/part/<int:move_id>/consume_all"], "POST")],
        input_param=restapi.CerberusValidator("consume_all"),
        output_param=restapi.CerberusValidator("consume_all"),
    )
    @with_savepoint
    def consume_all(self, move_id):
        """Mark the whole demanded quantity as used."""
        move = self._get_part(move_id)
        if not move:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if move.repair_id.state not in EDITABLE_REPAIR_STATES:
            return self._response_for_parts(
                move.repair_id, message=self.msg_store.part_job_closed(move.repair_id)
            )
        if move.product_id.tracking != "none":
            # Serials cannot be guessed; send the technician to the detail
            # screen to scan them.
            return self._response_for_part_detail(
                move, message=self.msg_store.lot_required(move.product_id)
            )
        message = self._set_move_quantity(move, move.product_uom_qty)
        if message:
            return self._response_for_part_detail(move, message=message)
        return self._response_for_parts(
            move.repair_id, message=self.msg_store.part_quantity_updated(move)
        )

    @restapi.method([(["/part/<int:move_id>/reset"], "POST")],
        input_param=restapi.CerberusValidator("reset_part"),
        output_param=restapi.CerberusValidator("reset_part"),
    )
    @with_savepoint
    def reset_part(self, move_id):
        """Undo a consumption: back to nothing used."""
        move = self._get_part(move_id)
        if not move:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if move.repair_id.state not in EDITABLE_REPAIR_STATES:
            return self._response_for_parts(
                move.repair_id, message=self.msg_store.part_job_closed(move.repair_id)
            )
        message = self._set_move_quantity(move, 0.0)
        if message:
            return self._response_for_part_detail(move, message=message)
        return self._response_for_parts(
            move.repair_id, message=self.msg_store.part_reset(move)
        )

    def _set_move_quantity(self, move, quantity, lot=None):
        """Write the done quantity (and lot when the product is tracked).

        Returns an error message dict, or None on success.
        """
        if lot is not None and not lot:
            return self.msg_store.generic_record_not_found()
        tracking = move.product_id.tracking
        if tracking != "none" and quantity and not lot:
            return self.msg_store.lot_required(move.product_id)

        def _write():
            if tracking == "serial" and lot:
                # Each serial is one unit; the core inverse spreads them over
                # move lines for us.
                move.lot_ids = [Command.link(lot.id)]
            else:
                move.quantity = quantity
                if lot:
                    lines = move.move_line_ids.filtered(lambda ml: not ml.lot_id)
                    (lines or move.move_line_ids).write({"lot_id": lot.id})
            move.picked = bool(move.quantity)

        return self._call_or_error(_write)

    # ------------------------------------------------------------------
    # Endpoints -- catalog
    # ------------------------------------------------------------------

    def _catalog_domain(self, search=None, category_id=None):
        domain = [
            # Odoo 18: goods are type 'consu'; 'is_storable' only tells them
            # apart from non-stocked consumables, which the shop also fits.
            ("type", "=", "consu"),
            ("purchase_ok", "=", True),
        ]
        if category_id:
            domain.append(("categ_id", "child_of", category_id))
        if search:
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        "|",
                        ("name", "ilike", search),
                        ("default_code", "ilike", search),
                        ("barcode", "=", search),
                    ],
                ]
            )
        return domain

    def _catalog_categories(self):
        return self.env["product.category"].search([], limit=200)

    @restapi.method([(["/catalog/categories"], "GET")],
        input_param=restapi.CerberusValidator("catalog_categories"),
        output_param=restapi.CerberusValidator("catalog_categories"),
    )
    def catalog_categories(self):
        """Product categories, for the catalog filter chips."""
        return self._response(
            data={
                "categories": [
                    {"id": categ.id, "name": categ.display_name}
                    for categ in self._catalog_categories()
                ]
            }
        )

    @restapi.method([(["/job/<int:repair_id>/catalog"], "GET")],
        input_param=restapi.CerberusValidator("catalog"),
        output_param=restapi.CerberusValidator("catalog"),
    )
    def catalog(self, repair_id, search=None, category_id=None, page=1):
        """Browse the parts catalog for this job."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        page = max(int(page or 1), 1)
        limit = self._catalog_page_size
        domain = self._catalog_domain(search=search, category_id=category_id)
        Product = self.env["product.product"]
        size = Product.search_count(domain)
        products = Product.search(
            domain, limit=limit, offset=(page - 1) * limit, order="default_code, name"
        )
        return self._response_for_catalog_search(repair, products, size, page)

    @restapi.method([(["/job/<int:repair_id>/add_part"], "POST")],
        input_param=restapi.CerberusValidator("add_part"),
        output_param=restapi.CerberusValidator("add_part"),
    )
    @with_savepoint
    def add_part(self, repair_id, product_id, quantity=1.0, consume_now=False):
        """Add a part from the catalog to the job.

        The move syncs to its own sale order line exactly as core does -- we
        do *not* suppress that. Instead the move is stamped with
        ``shopfloor_added_uid`` and a note is posted to the repair order, so
        the service advisor can see what the technician added on top of the
        estimate the customer approved and decide what to bill.
        """
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if repair.state not in EDITABLE_REPAIR_STATES:
            return self._response_for_parts(
                repair, message=self.msg_store.part_job_closed(repair)
            )
        product = self.env["product.product"].browse(product_id).exists()
        if not product:
            return self._response_for_parts(
                repair, message=self.msg_store.part_not_found()
            )
        if quantity <= 0:
            return self._response_for_catalog_detail(
                repair, product, message=self.msg_store.part_negative_quantity()
            )
        # Create inside the error wrapper so a company/route misconfiguration
        # answers with a message instead of a 500.
        created = []

        def _create():
            created.append(
                self.env["stock.move"].create(
                    self._prepare_added_part_vals(repair, product, quantity)
                )
            )

        error = self._call_or_error(_create)
        if error:
            return self._response_for_catalog_detail(repair, product, message=error)
        move = created[0]
        self._notify_part_added(repair, move)
        if consume_now and product.tracking == "none":
            self._set_move_quantity(move, quantity)
        return self._response_for_parts(
            repair, message=self.msg_store.part_added(move)
        )

    def _prepare_added_part_vals(self, repair, product, quantity):
        return {
            "repair_id": repair.id,
            "repair_line_type": "add",
            "product_id": product.id,
            "product_uom_qty": quantity,
            "product_uom": product.uom_id.id,
            "company_id": repair.company_id.id,
            "shopfloor_added_uid": self.env.user.id,
        }

    def _notify_part_added(self, repair, move):
        """Tell the service advisor, in the one place they already read.

        ``_message_log`` rather than ``message_post``: the latter resolves an
        author email address and raises "please configure the sender's email
        address" when it cannot, so a technician whose user record has no
        email would be unable to add a part at all. This is an internal log
        note -- nothing is being emailed -- so the email machinery has no
        business gating it.
        """
        body = self.env._(
            "%(user)s added %(qty)s x %(product)s from the shop floor app.",
            user=self.env.user.display_name,
            qty=f"{move.product_uom_qty:g}",
            product=move.product_id.display_name,
        )
        if repair.sale_order_id:
            body += " " + self.env._(
                "It was added to quotation %(order)s -- review it before invoicing.",
                order=repair.sale_order_id.name,
            )
        repair._message_log(body=body)

    # ------------------------------------------------------------------
    # Endpoints -- inspections
    # ------------------------------------------------------------------

    def _job_inspections(self, repair):
        return repair.inspection_ids.filtered(lambda insp: insp.state != "cancel")

    def _inspection_templates(self):
        return self.env["fleet.vehicle.inspection.template"].search([])

    def _get_inspection(self, inspection_id):
        return (
            self.env["fleet.vehicle.inspection"].browse(inspection_id).exists()
        )

    def _get_inspection_line(self, line_id):
        return (
            self.env["fleet.vehicle.inspection.line"].browse(line_id).exists()
        )

    def _inspection_choices(self, line):
        """Everything the grading form needs to render without a second call.

        Conditions and actions are the item's typical ones first, then the
        rest of the catalogue -- a technician grading brake pads wants "worn"
        at the top, not alphabetically among sixty options.
        """
        item = line.inspection_item_id
        conditions = item.condition_ids | self.env["shop.inspection.condition"].search(
            []
        )
        actions = item.recommended_action_ids | self.env[
            "shop.inspection.action"
        ].search([])
        return {
            "severities": [
                {"value": value, "label": label} for value, label in SEVERITY_SELECTION
            ],
            "conditions": [{"id": rec.id, "name": rec.name} for rec in conditions],
            "actions": [{"id": rec.id, "name": rec.name} for rec in actions],
        }

    @restapi.method([(["/job/<int:repair_id>/inspections"], "GET")],
        input_param=restapi.CerberusValidator("inspections"),
        output_param=restapi.CerberusValidator("inspections"),
    )
    def inspections(self, repair_id):
        """List this job's inspections and the templates available."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        return self._response_for_inspection_list(repair)

    @restapi.method(
        [(["/job/<int:repair_id>/inspection_create"], "POST")],
        input_param=restapi.CerberusValidator("inspection_create"),
        output_param=restapi.CerberusValidator("inspection_create"),
    )
    @with_savepoint
    def inspection_create(self, repair_id, template_id, odometer):
        """Start an inspection from a checklist template."""
        repair = self._get_repair(repair_id)
        if not repair:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if not repair.vehicle_id:
            return self._response_for_job_detail(
                repair, message=self.msg_store.inspection_no_vehicle(repair)
            )
        if not odometer:
            # fleet_vehicle_inspection's odometer inverse raises on a falsy
            # value, so catch it here where we can say something useful.
            return self._response_for_inspection_list(
                repair, message=self.msg_store.inspection_odometer_required()
            )
        template = (
            self.env["fleet.vehicle.inspection.template"]
            .browse(template_id)
            .exists()
        )
        if not template:
            return self._response_for_inspection_list(
                repair, message=self.msg_store.generic_record_not_found()
            )
        created = []

        def _create():
            created.append(self._create_inspection(repair, template, odometer))

        error = self._call_or_error(_create)
        if error:
            return self._response_for_inspection_list(repair, message=error)
        inspection = created[0]
        return self._response_for_inspection_lines(
            inspection, message=self.msg_store.inspection_created(inspection)
        )

    def _create_inspection(self, repair, template, odometer):
        vehicle = repair.vehicle_id
        inspection = self.env["fleet.vehicle.inspection"].create(
            {
                "name": template.name or "New",
                "repair_id": repair.id,
                "vehicle_id": vehicle.id,
                "direction": "in",
                "odometer_unit": vehicle.odometer_unit or "miles",
                "odometer": odometer,
                "inspection_template_id": template.id,
                "technician_id": self.env.user.id,
                "service_advisor_id": repair.service_advisor_id.id,
            }
        )
        inspection.write({"inspection_line_ids": self._template_line_commands(template)})
        return inspection

    def _template_line_commands(self, template):
        """Replicate the template onchange, which is all OCA provides.

        ``_compute_line_data_for_template_change`` also returns ``state``,
        which on the line is a stored related to the inspection -- harmless in
        an onchange, pointless in a real write. Drop it and let the related
        compute do its job. Measurement rows are prefilled by
        ``shop_inspection``'s create override.
        """
        Inspection = self.env["fleet.vehicle.inspection"]
        commands = [Command.clear()]
        for tmpl_line in template.inspection_template_line_ids.sorted("sequence"):
            vals = Inspection._compute_line_data_for_template_change(tmpl_line)
            vals.pop("state", None)
            commands.append(Command.create(vals))
        return commands

    @restapi.method([(["/inspection/<int:inspection_id>"], "GET")],
        input_param=restapi.CerberusValidator("inspection"),
        output_param=restapi.CerberusValidator("inspection"),
    )
    def inspection(self, inspection_id):
        """Open an inspection checklist."""
        inspection = self._get_inspection(inspection_id)
        if not inspection:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        return self._response_for_inspection_lines(inspection)

    @restapi.method(
        [(["/inspection_line/<int:line_id>"], "GET")],
        input_param=restapi.CerberusValidator("inspection_line"),
        output_param=restapi.CerberusValidator("inspection_line"),
    )
    def inspection_line(self, line_id):
        """Open one checklist item for grading."""
        line = self._get_inspection_line(line_id)
        if not line:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        return self._response_for_inspection_line_detail(line)

    @restapi.method(
        [(["/inspection_line/<int:line_id>/grade"], "POST")],
        input_param=restapi.CerberusValidator("grade"),
        output_param=restapi.CerberusValidator("grade"),
    )
    @with_savepoint
    def grade(
        self,
        line_id,
        severity,
        condition_ids=None,
        action_ids=None,
        note=None,
    ):
        """Grade one checklist item.

        Writing ``severity`` is enough: ``shop_inspection`` maps it onto the
        OCA pass/fail ``result`` so the confirm gate keeps working.
        """
        line = self._get_inspection_line(line_id)
        if not line:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if line.inspection_id.state != "draft":
            return self._response_for_inspection_lines(
                line.inspection_id,
                message=self.msg_store.inspection_locked(line.inspection_id),
            )
        if (
            self.options.get("require_photo_on_fail")
            and severity in PROBLEM_SEVERITIES
            and not line.inspection_line_image_ids
        ):
            return self._response_for_inspection_line_detail(
                line, message=self.msg_store.inspection_photo_required(line)
            )
        vals = {"severity": severity}
        if condition_ids is not None:
            vals["condition_ids"] = [Command.set(condition_ids)]
        if action_ids is not None:
            vals["recommended_action_ids"] = [Command.set(action_ids)]
        if note is not None:
            vals["result_description"] = note
        error = self._call_or_error(lambda: line.write(vals))
        if error:
            return self._response_for_inspection_line_detail(line, message=error)
        return self._response_for_inspection_lines(line.inspection_id)

    @restapi.method(
        [(["/measurement/<int:measurement_id>/set_value"], "POST")],
        input_param=restapi.CerberusValidator("set_measurement"),
        output_param=restapi.CerberusValidator("set_measurement"),
    )
    @with_savepoint
    def set_measurement(self, measurement_id, value):
        """Record a measured value (0 means 'not measured')."""
        measurement = (
            self.env["shop.inspection.measurement"].browse(measurement_id).exists()
        )
        if not measurement:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        line = measurement.line_id
        if line.inspection_id.state != "draft":
            return self._response_for_inspection_lines(
                line.inspection_id,
                message=self.msg_store.inspection_locked(line.inspection_id),
            )
        error = self._call_or_error(lambda: measurement.write({"value": value}))
        if error:
            return self._response_for_inspection_line_detail(line, message=error)
        return self._response_for_inspection_line_detail(line)

    @restapi.method(
        [(["/inspection_line/<int:line_id>/photo"], "POST")],
        input_param=restapi.CerberusValidator("add_photo"),
        output_param=restapi.CerberusValidator("add_photo"),
    )
    @with_savepoint
    def add_photo(self, line_id, image_b64, filename=None):
        """Attach a photo taken with the tablet camera."""
        line = self._get_inspection_line(line_id)
        if not line:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        if line.inspection_id.state != "draft":
            return self._response_for_inspection_lines(
                line.inspection_id,
                message=self.msg_store.inspection_locked(line.inspection_id),
            )
        image = self._clean_image_payload(image_b64)
        if not image:
            return self._response_for_inspection_line_detail(
                line, message=self.msg_store.generic_record_not_found()
            )
        error = self._call_or_error(
            lambda: self.env["fleet.vehicle.inspection.line.image"].create(
                {
                    "name": filename or line.inspection_item_id.name,
                    "image_1920": image,
                    "inspection_line_id": line.id,
                }
            )
        )
        if error:
            return self._response_for_inspection_line_detail(line, message=error)
        return self._response_for_inspection_line_detail(
            line, message=self.msg_store.photo_added(line)
        )

    def _clean_image_payload(self, image_b64):
        """Accept both a bare base64 string and a browser data: URL."""
        if not image_b64:
            return None
        payload = image_b64
        if payload.startswith("data:"):
            _header, _sep, payload = payload.partition(",")
            if not payload:
                return None
        try:
            base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            _logger.warning("Rejected a photo upload that was not valid base64")
            return None
        return payload

    @restapi.method(
        [(["/inspection/<int:inspection_id>/confirm"], "POST")],
        input_param=restapi.CerberusValidator("confirm_inspection"),
        output_param=restapi.CerberusValidator("confirm_inspection"),
    )
    @with_savepoint
    def confirm_inspection(self, inspection_id):
        """Complete the inspection (core OCA ``button_confirm``)."""
        inspection = self._get_inspection(inspection_id)
        if not inspection:
            return self._response_for_job_list(
                message=self.msg_store.generic_record_not_found()
            )
        ungraded = inspection.inspection_line_ids.filtered(
            lambda line: not line.severity
        )
        if ungraded:
            # button_confirm would raise on the same condition; saying how
            # many are left is more use than its wall of text.
            return self._response_for_inspection_lines(
                inspection,
                message=self.msg_store.inspection_not_graded(len(ungraded)),
            )
        message = self._call_or_error(inspection.button_confirm)
        if message:
            return self._response_for_inspection_lines(inspection, message=message)
        return self._response_for_inspection_list(
            inspection.repair_id,
            message=self.msg_store.inspection_confirmed(inspection),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call_or_error(self, func):
        """Run an ORM action, turning a business error into a shopfloor message.

        Without this the technician gets base_rest's raw traceback dialog.
        ``with_savepoint`` rolls back whatever the raising method already
        wrote.
        """
        try:
            func()
        except (UserError, ValidationError) as err:
            return {"message_type": "error", "body": str(err)}
        return None


class ShopfloorRepairJobValidator(Component):
    """Input validators for the repair job endpoints."""

    _inherit = "base.shopfloor.validator"
    _name = "shopfloor.repair.job.validator"
    _usage = "repair_job.validator"

    def jobs(self):
        return {}

    def scan(self):
        return {"identifier": {"required": True, "type": "string"}}

    def job(self):
        return {"repair_id": {"coerce": to_int, "required": True, "type": "integer"}}

    def start_repair(self):
        return self.job()

    def finish(self):
        return self.job()

    def services(self):
        return self.job()

    def add_note(self):
        return {
            "repair_id": {"coerce": to_int, "required": True, "type": "integer"},
            "note": {"required": True, "type": "string"},
        }

    def _service_schema(self):
        schema = self.job()
        schema["service_id"] = {
            "coerce": to_int,
            "required": True,
            "type": "integer",
        }
        return schema

    def service_timer_start(self):
        return self._service_schema()

    def service_timer_stop(self):
        return self._service_schema()

    def parts(self):
        return self.job()

    def scan_part(self):
        schema = self.job()
        schema["barcode"] = {"required": True, "type": "string"}
        return schema

    def set_quantity(self):
        return {
            "move_id": {"coerce": to_int, "required": True, "type": "integer"},
            "quantity": {"coerce": float, "required": True, "type": "float"},
            "lot_id": {
                "coerce": to_int,
                "required": False,
                "nullable": True,
                "type": "integer",
            },
            "lot_name": {"required": False, "nullable": True, "type": "string"},
        }

    def consume_all(self):
        return {"move_id": {"coerce": to_int, "required": True, "type": "integer"}}

    def reset_part(self):
        return self.consume_all()

    def shift_timer(self):
        return {}

    def clock_toggle(self):
        return {}

    def catalog_categories(self):
        return {}

    def catalog(self):
        return {
            "repair_id": {"coerce": to_int, "required": True, "type": "integer"},
            "search": {"required": False, "nullable": True, "type": "string"},
            "category_id": {
                "coerce": to_int,
                "required": False,
                "nullable": True,
                "type": "integer",
            },
            "page": {"coerce": to_int, "required": False, "type": "integer"},
        }

    def add_part(self):
        return {
            "repair_id": {"coerce": to_int, "required": True, "type": "integer"},
            "product_id": {"coerce": to_int, "required": True, "type": "integer"},
            "quantity": {"coerce": float, "required": False, "type": "float"},
            "consume_now": {"coerce": to_bool, "required": False, "type": "boolean"},
        }

    def inspections(self):
        return self.job()

    def inspection_create(self):
        return {
            "repair_id": {"coerce": to_int, "required": True, "type": "integer"},
            "template_id": {"coerce": to_int, "required": True, "type": "integer"},
            "odometer": {"coerce": float, "required": True, "type": "float"},
        }

    def inspection(self):
        return {
            "inspection_id": {"coerce": to_int, "required": True, "type": "integer"}
        }

    def inspection_line(self):
        return {"line_id": {"coerce": to_int, "required": True, "type": "integer"}}

    def grade(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "severity": {
                "required": True,
                "type": "string",
                "allowed": [value for value, _label in SEVERITY_SELECTION],
            },
            "condition_ids": {
                "required": False,
                "nullable": True,
                "type": "list",
                "schema": {"coerce": to_int, "type": "integer"},
            },
            "action_ids": {
                "required": False,
                "nullable": True,
                "type": "list",
                "schema": {"coerce": to_int, "type": "integer"},
            },
            "note": {"required": False, "nullable": True, "type": "string"},
        }

    def set_measurement(self):
        return {
            "measurement_id": {"coerce": to_int, "required": True, "type": "integer"},
            "value": {"coerce": float, "required": True, "type": "float"},
        }

    def add_photo(self):
        return {
            "line_id": {"coerce": to_int, "required": True, "type": "integer"},
            "image_b64": {"required": True, "type": "string"},
            "filename": {"required": False, "nullable": True, "type": "string"},
        }

    def confirm_inspection(self):
        return self.inspection()


class ShopfloorRepairJobValidatorResponse(Component):
    """Response validators for the repair job endpoints."""

    _inherit = "base.shopfloor.validator.response"
    _name = "shopfloor.repair.job.validator.response"
    _usage = "repair_job.validator.response"

    _start_state = "job_list"

    def _states(self):
        return {
            "job_list": {
                "records": self.schemas._schema_list_of(self.schemas.repair_job())
            },
            "job_detail": {
                "record": self.schemas._schema_dict_of(
                    self.schemas_detail.repair_job_detail()
                ),
                "options": self.schemas._schema_dict_of(
                    {
                        "allow_repair_end": {"type": "boolean", "required": True},
                        "require_photo_on_fail": {
                            "type": "boolean",
                            "required": True,
                        },
                    }
                ),
            },
            "services": {
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "records": self.schemas._schema_list_of(
                    self.schemas.repair_service()
                ),
                "notes": {"type": "string", "required": True},
            },
            "parts": {
                "record": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "parts": self.schemas._schema_list_of(self.schemas.repair_part()),
            },
            "part_detail": {
                "record": self.schemas._schema_dict_of(self.schemas.repair_part()),
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
            },
            "catalog_search": {
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "records": self.schemas._schema_list_of(
                    self.schemas.catalog_product()
                ),
                "size": {"type": "integer", "required": True},
                "page": {"type": "integer", "required": True},
                "page_size": {"type": "integer", "required": True},
                "categories": self.schemas._schema_list_of(
                    self.schemas._simple_record()
                ),
            },
            "catalog_detail": {
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "record": self.schemas._schema_dict_of(
                    self.schemas.catalog_product()
                ),
            },
            "inspection_list": {
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "records": self.schemas._schema_list_of(self.schemas.inspection()),
                "templates": self.schemas._schema_list_of(
                    self.schemas._simple_record()
                ),
                "default_odometer": {"type": "float", "required": True},
                "odometer_unit": {"type": "string", "required": True},
            },
            "inspection_lines": {
                "record": self.schemas._schema_dict_of(self.schemas.inspection()),
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "lines": self.schemas._schema_list_of(
                    self.schemas.inspection_line()
                ),
            },
            "inspection_line_detail": {
                "record": self.schemas._schema_dict_of(
                    self.schemas.inspection_line()
                ),
                "inspection": self.schemas._schema_dict_of(
                    self.schemas.inspection()
                ),
                "job": self.schemas._schema_dict_of(self.schemas.repair_job()),
                "choices": self.schemas._schema_dict_of(
                    self.schemas.inspection_choices()
                ),
            },
        }

    def jobs(self):
        return self._response_schema(next_states=["job_list"])

    def scan(self):
        return self._response_schema(next_states=["job_list", "job_detail"])

    def job(self):
        return self._response_schema(next_states=["job_detail"])

    def start_repair(self):
        return self.job()

    def finish(self):
        return self.job()

    def services(self):
        return self._response_schema(next_states=["services"])

    def service_timer_start(self):
        return self.services()

    def service_timer_stop(self):
        return self.services()

    def parts(self):
        return self._response_schema(next_states=["parts"])

    def scan_part(self):
        return self._response_schema(
            next_states=["parts", "part_detail", "catalog_detail"]
        )

    def set_quantity(self):
        return self._response_schema(next_states=["parts", "part_detail"])

    def consume_all(self):
        return self.set_quantity()

    def reset_part(self):
        return self.set_quantity()

    def shift_timer(self):
        return self._response_schema(
            {"shift_timer": self.schemas._schema_dict_of(self.schemas.shift_timer())}
        )

    def clock_toggle(self):
        return self.shift_timer()

    def catalog_categories(self):
        return self._response_schema(
            {
                "categories": self.schemas._schema_list_of(
                    self.schemas._simple_record()
                )
            }
        )

    def catalog(self):
        return self._response_schema(next_states=["catalog_search"])

    def add_part(self):
        return self._response_schema(next_states=["parts", "catalog_detail"])

    def add_note(self):
        return self._response_schema(next_states=["services", "job_list"])

    def inspections(self):
        return self._response_schema(next_states=["inspection_list"])

    def inspection_create(self):
        return self._response_schema(
            next_states=["inspection_list", "inspection_lines", "job_detail"]
        )

    def inspection(self):
        return self._response_schema(next_states=["inspection_lines"])

    def inspection_line(self):
        return self._response_schema(next_states=["inspection_line_detail"])

    def grade(self):
        return self._response_schema(
            next_states=["inspection_lines", "inspection_line_detail"]
        )

    def set_measurement(self):
        return self._response_schema(
            next_states=["inspection_lines", "inspection_line_detail"]
        )

    def add_photo(self):
        return self._response_schema(
            next_states=["inspection_lines", "inspection_line_detail"]
        )

    def confirm_inspection(self):
        return self._response_schema(
            next_states=["inspection_list", "inspection_lines"]
        )
