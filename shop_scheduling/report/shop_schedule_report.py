# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

import pytz

from odoo import api, models
from odoo.tools import format_date, format_duration, format_time


class ReportShopSchedule(models.AbstractModel):
    """The repair calendar's Print button: the jobs on screen, as a PDF.

    The calendar hands over the ids it is drawing, so whatever its search,
    sidebar filters, scale and date select is what prints.
    """

    _name = "report.shop_scheduling.report_shop_schedule"
    _description = "Shop Schedule Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        repairs = (
            self.env["repair.order"]
            .browse(docids)
            .exists()
            .filtered("schedule_date")
            .sorted(lambda r: (r.schedule_date, r.technician_id.name or "", r.id))
        )
        return {
            "doc_ids": repairs.ids,
            "doc_model": "repair.order",
            "docs": repairs,
            "title": data.get("title"),
            "days": self._shop_schedule_days(repairs),
        }

    @api.model
    def _shop_tz_name(self):
        # The calendar draws in the browser's timezone, which it passes along.
        return self.env.context.get("tz") or self.env.user.tz or "UTC"

    @api.model
    def _shop_schedule_days(self, repairs):
        """The jobs grouped by day, a list of ``{"label", "lines"}``."""
        tz_name = self._shop_tz_name()
        tz = pytz.timezone(tz_name)
        days = {}
        for repair in repairs:
            start = repair.schedule_date
            day = pytz.utc.localize(start).astimezone(tz).date()
            end = (
                start + timedelta(hours=repair.planned_duration)
                if repair.planned_duration
                else False
            )
            time_label = format_time(self.env, start, tz=tz_name, time_format="short")
            if end:
                time_label = "{} – {}".format(
                    time_label,
                    format_time(self.env, end, tz=tz_name, time_format="short"),
                )
            days.setdefault(day, []).append(
                {
                    "repair": repair,
                    "time": time_label,
                    "hours": format_duration(repair.planned_duration)
                    if repair.planned_duration
                    else "",
                    "vehicle": repair.shop_vehicle_label,
                    "services": ", ".join(
                        name
                        for name in repair.repair_service_ids.mapped("display_name")
                        if name
                    ),
                }
            )
        return [
            {
                "label": format_date(self.env, day, date_format="full"),
                "lines": lines,
            }
            for day, lines in sorted(days.items())
        ]
