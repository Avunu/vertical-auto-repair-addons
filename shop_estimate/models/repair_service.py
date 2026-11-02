# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class RepairService(models.Model):
    _inherit = "repair.service"

    shop_job_sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Covered by Job Line",
        copy=False,
        help="The flat-rate job line on the sale order that already bills "
        "for this labor. The service is deliberately not synced to its "
        "own sale order line.",
    )

    def _create_repair_sale_order_line(self):
        # Labor covered by a flat-rate job must not create its own sale
        # order line.
        return super(
            RepairService,
            self.filtered(lambda service: not service.shop_job_sale_line_id),
        )._create_repair_sale_order_line()
