# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component
from odoo.addons.shopfloor_base.utils import ensure_model


class DataDetailAction(Component):
    """Detail payloads: everything the job hub screen needs in one call."""

    _inherit = "shopfloor.data.detail.action"

    @ensure_model("repair.order")
    def repair_job_detail(self, record, running_line=None, **kw):
        data = self.data.repair_job(record, **kw)
        if data is None:
            return None
        if running_line is None:
            running_line = self.env["account.analytic.line"].browse()
        data.update(
            {
                "internal_notes": self.data._plaintext(record.internal_notes),
                "repair_request": record.repair_request or "",
                "odometer_in": record.odometer_in,
                "odometer_unit": record.vehicle_odometer_unit or "",
                "under_warranty": record.under_warranty,
                "sale_order": (
                    {"id": record.sale_order_id.id, "name": record.sale_order_id.name}
                    if record.sale_order_id
                    else None
                ),
                "timer": self.data.timer(record, running_line),
            }
        )
        return data

    def repair_timesheet_detail(self, record, jobs=None, **kw):
        data = self.data.repair_timesheet(record, **kw)
        if data is None:
            return None
        if jobs is None:
            jobs = self.env["repair.order"].browse()
        data.update(
            {
                # Same `job_label()` as `data.repair_timesheet()`'s own
                # `job.name` and `data.timer()`'s `job_name` - this picker
                # was the one place still left showing the bare RO
                # reference instead.
                "jobs": [
                    {
                        "id": job.id,
                        "name": self.data.job_label(job),
                        # Two open ROs for the same vehicle share a
                        # description, so the picker needs more than the
                        # name to tell them apart.
                        "ref": job.name,
                        "customer": job.partner_id.name or "",
                        "services": [
                            {
                                "id": service.id,
                                "name": service.product_id.name
                                or service.display_name,
                            }
                            for service in job.repair_service_ids.filtered(
                                "accepted"
                            )
                        ],
                    }
                    for job in jobs
                ],
            }
        )
        return data

    @property
    def data(self):
        return self._actions_for("data")
