# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _repair_running_domain_for_employee(self, employee):
        """A running repair-job timer for a *specific* employee.

        Deliberately not `AAL._running_domain()` (from
        `project_timesheet_time_control`): that domain hardcodes
        `user_id = self.env.user.id` - the *caller*, not necessarily the
        employee in question (e.g. a clock-out triggered from a kiosk's
        shared session, or on someone else's behalf). "Running" still means
        the same thing that convention already established: `unit_amount ==
        0` (see `date_time_end` being a search-unfriendly computed field,
        explained on the constraint below).
        """
        return [
            ("employee_id", "=", employee.id),
            ("repair_order_id", "!=", False),
            ("date_time", "!=", False),
            ("unit_amount", "=", 0),
        ]

    @api.constrains("employee_id", "date_time", "date_time_end", "repair_order_id")
    def _check_repair_timesheet_no_overlap(self):
        """A technician can't be two places at once.

        Scoped to lines with `repair_order_id` set - i.e. timesheets
        recorded through the Shopfloor repair app - deliberately, not every
        account.analytic.line an employee might have. Broadening this to
        every timesheet entry in the database (other apps, back-office
        corrections, imports) risks breaking workflows this module has no
        visibility into; the ask was specifically about repair-job
        timesheets not overlapping each other.

        A line with no `date_time_end` yet (a still-running timer) is
        treated as open-ended for this check - it blocks anything else
        starting before it's stopped, the same way `timer_start` already
        refuses to start a second timer for the same technician.

        `date_time_end` is a *computed* field whose own `search()`
        implementation (`project_timesheet_time_control._search_date_time_
        end`) only accepts a real datetime string, not `True`/`False` - so
        it cannot be filtered by domain for "is this line still open".
        Candidates are fetched with a domain built only from genuinely
        searchable fields, and the actual interval-overlap arithmetic is
        done in Python against the *read* (not searched) field value.
        """
        for line in self:
            if not line.repair_order_id or not line.employee_id or not line.date_time:
                continue
            candidates = self.search(
                [
                    ("id", "!=", line.id),
                    ("employee_id", "=", line.employee_id.id),
                    ("repair_order_id", "!=", False),
                    ("date_time", "!=", False),
                ]
            )
            line_end = line.date_time_end  # falsy => still running/open-ended
            for other in candidates:
                other_end = other.date_time_end
                overlaps = (not line_end or other.date_time < line_end) and (
                    not other_end or other_end > line.date_time
                )
                if overlaps:
                    raise ValidationError(
                        self.env._(
                            "%(name)s overlaps another repair job timesheet "
                            "for %(employee)s (%(other)s). Adjust the "
                            "start/end time so the two don't overlap.",
                            name=line.name or line.repair_order_id.display_name,
                            employee=line.employee_id.name,
                            other=other.repair_order_id.display_name,
                        )
                    )
