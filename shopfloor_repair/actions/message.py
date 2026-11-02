# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component


class MessageAction(Component):
    """User-facing messages for the repair shop floor app."""

    _inherit = "shopfloor.message.action"

    # -- jobs -------------------------------------------------------------

    def job_not_found(self):
        return {
            "message_type": "error",
            "body": self.env._("No repair order found for this code."),
        }

    def job_not_started(self):
        return {
            "message_type": "warning",
            "body": self.env._("Start the repair before working on it."),
        }

    def repair_started(self, repair):
        return {
            "message_type": "success",
            "body": self.env._("%(name)s is now under repair.", name=repair.name),
        }

    def repair_not_confirmed(self, repair):
        return {
            "message_type": "warning",
            "body": self.env._(
                "%(name)s hasn't been confirmed yet. You can diagnose it and "
                "log time on its accepted services, but repair work can't "
                "start until the office confirms the repair.",
                name=repair.name,
            ),
        }

    def repair_already_started(self, repair):
        return {
            "message_type": "info",
            "body": self.env._("%(name)s is already under repair.", name=repair.name),
        }

    def repair_finished(self, repair):
        return {
            "message_type": "success",
            "body": self.env._("%(name)s is repaired.", name=repair.name),
        }

    def repair_end_not_allowed(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "Finishing a repair is disabled for this menu. "
                "Ask your service advisor to close the job."
            ),
        }

    def repair_must_be_under_repair(self):
        return {
            "message_type": "error",
            "body": self.env._("Only a job under repair can be finished."),
        }

    # -- timer ------------------------------------------------------------

    def _timer_line_label(self, line):
        """Where a timer line was running, in plain words for technicians.

        The job is named by vehicle *and* order number because two open orders
        on the same vehicle share a description.
        """
        repair = line.repair_order_id
        job = (
            self._actions_for("data").vehicle_description(repair.vehicle_id)
            or repair.partner_id.name
        )
        where = " · ".join(part for part in (job, repair.name) if part)
        service = line.repair_service_id.product_id.name
        if not service:
            return where
        return self.env._("%(service)s (%(job)s)", service=service, job=where)

    def service_timer_started(self, service, clocked_in=False, stopped=None):
        """``stopped`` is the timer line this start ended, if any.

        Starting a timer stops the running one by itself, so the technician is
        told which one - they may not have meant to leave it.
        """
        prefix = ""
        if stopped:
            prefix = (
                self.env._(
                    "Timer stopped on %(name)s.",
                    name=self._timer_line_label(stopped),
                )
                + " "
            )
        if clocked_in:
            # Said out loud on purpose: the day clock now runs until somebody
            # stops it, and the point of the notice is that the technician
            # remembers to clock out at the end of the day.
            return {
                "message_type": "info",
                "body": prefix
                + self.env._(
                    "Timer started on %(name)s. You were not clocked in, so "
                    "you have been clocked in for the day. Remember to clock "
                    "out when you finish.",
                    name=service.display_name,
                ),
            }
        return {
            "message_type": "success",
            "body": prefix
            + self.env._("Timer started on %(name)s.", name=service.display_name),
        }

    def service_timer_stopped(self, service):
        return {
            "message_type": "success",
            "body": self.env._(
                "Timer stopped on %(name)s.", name=service.display_name
            ),
        }

    def service_timer_already_running(self, service):
        return {
            "message_type": "info",
            "body": self.env._(
                "Your timer is already running on %(name)s.",
                name=service.display_name,
            ),
        }

    def service_timer_not_running(self, service):
        return {
            "message_type": "warning",
            "body": self.env._(
                "No timer running on %(name)s.", name=service.display_name
            ),
        }

    def timer_no_employee(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "Your user is not linked to an employee, so no timesheet can "
                "be recorded. Ask an administrator to create your employee record."
            ),
        }

    def timer_no_project(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "No repair timesheet project is configured for this company, "
                "so the timer has nowhere to log. Set it in "
                "Settings > Repair > Timesheet Project."
            ),
        }

    # -- timesheets ---------------------------------------------------------

    def timesheet_updated(self, line):
        return {
            "message_type": "success",
            "body": self.env._(
                "Timesheet on %(name)s updated.",
                name=line.repair_order_id.display_name,
            ),
        }

    def timesheet_end_before_start(self):
        return {
            "message_type": "error",
            "body": self.env._("End time must be after the start time."),
        }

    def attendance_updated(self):
        return {
            "message_type": "success",
            "body": self.env._("Clock-in/out updated."),
        }

    def timesheet_deleted(self):
        return {
            "message_type": "success",
            "body": self.env._("Timesheet deleted."),
        }

    def timesheet_split(self, job_name):
        return {
            "message_type": "success",
            "body": self.env._("Time moved to %(job)s.", job=job_name),
        }

    def timesheet_split_invalid(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "The part to move must lie within the timesheet, and can't be "
                "all of it. A timesheet that is still running can't be split."
            ),
        }

    def timesheet_service_not_on_job(self):
        return {
            "message_type": "error",
            "body": self.env._("That service doesn't belong to the chosen job."),
        }

    def timesheet_break_added(self):
        return {
            "message_type": "success",
            "body": self.env._("Break added."),
        }

    def timesheet_break_outside_line(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "The break must fall inside the timesheet, not touching "
                "its start or end."
            ),
        }

    def break_updated(self):
        return {
            "message_type": "success",
            "body": self.env._("Break updated."),
        }

    def break_deleted(self):
        return {
            "message_type": "success",
            "body": self.env._("Break removed. That time now counts as clocked in."),
        }

    def break_edit_invalid(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "The break has to start after you clocked in and end before "
                "you clocked out again."
            ),
        }

    def job_break_edit_invalid(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "The break has to start after the earlier part of the "
                "timesheet begins and end before the later part ends."
            ),
        }

    def job_break_deleted(self):
        return {
            "message_type": "success",
            "body": self.env._(
                "Break removed. The two parts of the timesheet are joined again."
            ),
        }

    def break_overlaps_job(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "That break would overlap time booked to a job. Adjust the "
                "job time first, or choose different break times."
            ),
        }

    def timesheet_break_added_unclocked(self):
        return {
            "message_type": "info",
            "body": self.env._(
                "Break added to the timesheet. No clock-in is recorded for "
                "that time, so the day's clocked total didn't change."
            ),
        }

    def timesheet_break_outside_attendance(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "The break must fall inside a single clock-in/out period, "
                "so it can come off the day's clocked time. Check your "
                "clock-in and clock-out times for that day."
            ),
        }

    # -- parts ------------------------------------------------------------

    def part_not_found(self):
        return {
            "message_type": "error",
            "body": self.env._("No part found for this code."),
        }

    def part_not_on_job(self, product):
        return {
            "message_type": "warning",
            "body": self.env._(
                "%(product)s is not on this job yet. Add it from the catalog "
                "if you used it.",
                product=product.display_name,
            ),
        }

    def part_quantity_updated(self, move):
        return {
            "message_type": "success",
            "body": self.env._(
                "%(product)s: %(qty)s used.",
                product=move.product_id.display_name,
                qty=f"{move.quantity:g}",
            ),
        }

    def part_reset(self, move):
        return {
            "message_type": "info",
            "body": self.env._(
                "%(product)s reset to not used.",
                product=move.product_id.display_name,
            ),
        }

    def note_added(self):
        return {
            "message_type": "success",
            "body": self.env._("Note added to the job."),
        }

    def note_empty(self):
        return {
            "message_type": "error",
            "body": self.env._("Write something first."),
        }

    def part_added(self, move):
        return {
            "message_type": "success",
            "body": self.env._(
                "%(qty)s x %(product)s added to the job.",
                qty=f"{move.product_uom_qty:g}",
                product=move.product_id.display_name,
            ),
        }

    def part_negative_quantity(self):
        return {
            "message_type": "error",
            "body": self.env._("Quantity cannot be negative."),
        }

    def part_job_closed(self, repair):
        return {
            "message_type": "error",
            "body": self.env._(
                "%(name)s is %(state)s: parts can no longer be changed.",
                name=repair.name,
                state=repair.state,
            ),
        }

    def lot_not_found(self, barcode):
        return {
            "message_type": "error",
            "body": self.env._("No lot or serial number found for %(code)s.", code=barcode),
        }

    def lot_required(self, product):
        return {
            "message_type": "error",
            "body": self.env._(
                "%(product)s is tracked: scan a lot or serial number.",
                product=product.display_name,
            ),
        }

    # -- inspections -------------------------------------------------------

    def inspection_no_vehicle(self, repair):
        return {
            "message_type": "error",
            "body": self.env._(
                "%(name)s has no vehicle, so no inspection can be recorded.",
                name=repair.name,
            ),
        }

    def inspection_odometer_required(self):
        return {
            "message_type": "error",
            "body": self.env._(
                "Enter the odometer reading before starting the inspection."
            ),
        }

    def inspection_created(self, inspection):
        return {
            "message_type": "success",
            "body": self.env._("Inspection %(name)s started.", name=inspection.name),
        }

    def inspection_confirmed(self, inspection):
        return {
            "message_type": "success",
            "body": self.env._("Inspection %(name)s completed.", name=inspection.name),
        }

    def inspection_not_graded(self, count):
        return {
            "message_type": "error",
            "body": self.env._(
                "%(count)s item(s) still need a grade before the inspection "
                "can be completed.",
                count=count,
            ),
        }

    def inspection_locked(self, inspection):
        return {
            "message_type": "error",
            "body": self.env._(
                "Inspection %(name)s is %(state)s and can no longer be edited.",
                name=inspection.name,
                state=inspection.state,
            ),
        }

    def inspection_photo_required(self, line):
        return {
            "message_type": "error",
            "body": self.env._(
                "%(item)s needs a photo before it can be graded as a problem.",
                item=line.inspection_item_id.name,
            ),
        }

    def photo_added(self, line):
        return {
            "message_type": "success",
            "body": self.env._(
                "Photo added to %(item)s.", item=line.inspection_item_id.name
            ),
        }
