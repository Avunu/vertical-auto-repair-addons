# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import re
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import models
from odoo.osv import expression

from ..facade import facade
from ..schemas import Board, BoardJob, BoardJobType, Ref


class RepairOrder(models.Model):
    """The job board's facade. The technician app's live in repair_tech_app."""

    _inherit = "repair.order"

    @facade
    def board_jobs(self) -> Board:
        """The shop's job board: every open job whose stage has a board status,
        scheduled for today or earlier or not scheduled yet, and the
        technicians who have open work. Not limited to the current user's
        jobs. A job booked for a later day stays off until its day."""
        stages = self.env["repair.order.stage"].search([("board_status", "!=", False)])
        company = [("company_id", "in", self.env.companies.ids)]
        open_jobs = expression.AND([[("state", "not in", ("done", "cancel"))], company])
        # Open jobs from earlier days stay until they are done; only a future
        # booking waits. A job with no date yet (shop_scheduling leaves it
        # empty until it is booked) is not in the future, so it shows.
        due = [
            "|",
            ("schedule_date", "=", False),
            ("schedule_date", "<", self._board_cutoff()),
        ]
        jobs = self.search(
            expression.AND([open_jobs, due, [("stage_id", "in", stages.ids)]]),
            order="id",
        )
        technicians = self.search(
            expression.AND([open_jobs, due, [("technician_id", "!=", False)]])
        ).technician_id.sorted("name")
        # The board's user needn't be a Resource Booking user: the types
        # are only display settings, so read them as superuser.
        types = (
            self.env["resource.booking.type"]
            .sudo()
            .search([("board_icon", "!=", False)])
        )
        return Board(
            jobs=[job._board_job() for job in jobs],
            technicians=[_ref(user) for user in technicians],
            job_types=[_board_job_type(job_type) for job_type in types],
        )

    def _board_cutoff(self):
        """The start of tomorrow in the user's time zone, as the naive UTC the
        database stores: a job scheduled before it is for today or earlier."""
        try:
            zone = ZoneInfo(self.env.context.get("tz") or self.env.user.tz or "UTC")
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        today = datetime.now(zone).date()
        start = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
        return start.astimezone(UTC).replace(tzinfo=None)

    def _board_job(self):
        vehicle = self.vehicle_id
        job_type = self.booking_type_id.sudo()
        return BoardJob(
            id=self.id,
            name=self.name,
            number=_order_number(self.name),
            customer=self.partner_id.name or "",
            vehicle=" ".join(
                part.strip()
                for part in (vehicle.model_year, vehicle.model_id.name)
                if part and part.strip()
            ),
            job_type=_board_job_type(job_type) if job_type.board_icon else None,
            status=self.stage_id.board_status,
            technician_id=self.technician_id.id or None,
        )


def _order_number(name):
    """``RO/00123`` -> ``123``; a name without digits is shown as it is."""
    match = re.search(r"(\d+)\D*$", name or "")
    return str(int(match.group(1))) if match else (name or "")


def _ref(record):
    return Ref(id=record.id, name=record.display_name) if record else None


def _board_job_type(job_type):
    return BoardJobType(
        id=job_type.id, label=job_type._board_label(), icon=job_type.board_icon
    )
