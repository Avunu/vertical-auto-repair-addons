# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _attendance_action_change(self, geo_information=None):
        """Stop any running repair-job timer when the shift ends.

        `_attendance_action_change` is the one method every clock-in/out
        path funnels through (kiosk barcode/PIN, the systray widget) - see
        `odoo/addons/hr_attendance/models/hr_employee.py`. Whether *this*
        call is actually authorized (self-service via badge/PIN, or -
        currently the only other real path - a manager editing someone
        else's attendance record directly, which is gated by Odoo core's
        own `hr_attendance.group_hr_attendance_officer`/`_manager` via
        `ir.rule`s) is entirely core's concern, untouched here - `super()`
        runs first, under whatever permissions already applied, before
        this module's own side effect runs.
        """
        was_checked_in = self.attendance_state == "checked_in"
        result = super()._attendance_action_change(geo_information)
        if was_checked_in:
            # sudo() for this module's own side effects only (stopping the
            # timer, posting the notice) - not for the clock-out action
            # itself, which already happened above under its own rules.
            self.sudo()._stop_repair_timers_on_clock_out()
        return result

    def _stop_repair_timers_on_clock_out(self):
        AAL = self.env["account.analytic.line"]
        for employee in self:
            running = AAL.search(AAL._repair_running_domain_for_employee(employee))
            if not running:
                continue
            jobs = running.repair_order_id
            running.button_end_work()
            if not employee.user_id:
                continue
            for job in jobs:
                job.message_post(
                    body=self.env._(
                        "Your work timer on this job was stopped "
                        "automatically because %(name)s clocked out "
                        "without stopping it first.",
                        name=employee.name,
                    ),
                    partner_ids=employee.user_id.partner_id.ids,
                )
