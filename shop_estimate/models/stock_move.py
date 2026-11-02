# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    shop_job_sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Covered by Job Line",
        copy=False,
        index="btree_not_null",
        help="The flat-rate job line on the sale order that already bills "
        "for this part. The move is deliberately not synced to its own "
        "sale order line.",
    )

    def _create_repair_sale_order_line(self):
        # Parts covered by a flat-rate job must not create their own sale
        # order lines (single choke point: create/write/cancel-draft all
        # funnel through this method).
        return super(
            StockMove,
            self.filtered(lambda move: not move.shop_job_sale_line_id),
        )._create_repair_sale_order_line()
