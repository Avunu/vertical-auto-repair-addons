# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    # Kept alongside the existing `repair_order_id` (from repair_timesheet)
    # rather than replacing it, so job-level rollups (repair.order.
    # timesheet_ids / timesheet_total_hours) keep working unchanged while
    # this adds a service-level one. `set null`, not `cascade`: archiving or
    # deleting a repair.service must never destroy logged timesheet history.
    repair_service_id = fields.Many2one(
        "repair.service",
        string="Repair Service",
        index=True,
        ondelete="set null",
    )
