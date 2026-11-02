# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class SaleOrderOption(models.Model):
    _inherit = "sale.order.option"

    shop_job_id = fields.Many2one(
        "shop.service.job",
        string="Service Job",
        copy=False,
    )
    shop_repair_id = fields.Many2one(
        "repair.order",
        string="Job Repair Order",
        copy=False,
    )
    shop_finding_line_id = fields.Many2one(
        "fleet.vehicle.inspection.line",
        string="Inspection Finding",
        copy=False,
    )

    def _get_values_to_add_to_order(self):
        # Carry the job metadata onto the sale order line when the customer
        # opts into the job from the portal (or a user adds the option).
        values = super()._get_values_to_add_to_order()
        values.update(
            {
                "shop_job_id": self.shop_job_id.id,
                "shop_repair_id": self.shop_repair_id.id,
                "shop_finding_line_id": self.shop_finding_line_id.id,
            }
        )
        return values
