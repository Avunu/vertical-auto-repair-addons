# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    shopfloor_added_uid = fields.Many2one(
        "res.users",
        string="Added on the Shop Floor by",
        copy=False,
        index="btree_not_null",
        help="Set when a technician added this part from the shop floor app "
        "rather than it arriving with the approved estimate. The move still "
        "syncs to its own sale order line the way core does -- this flag plus "
        "the chatter note on the repair order are what let the service "
        "advisor spot the delta against what the customer approved.",
    )

    def _create_repair_sale_order_line(self):
        """Let a technician's catalog add reach the quote.

        Core creates the sale.order.line from inside ``stock.move.create``.
        A shop floor technician has stock rights, not sales rights, so that
        create raises AccessError and the whole add fails -- the technician
        cannot record a part they genuinely installed.

        The elevation is deliberately narrow: only moves this app stamped,
        and only for the line core would have created anyway. The line's
        create_uid becomes the superuser, so the audit trail that names the
        technician is the chatter note the service posts on the repair order.
        """
        added_here = self.filtered("shopfloor_added_uid")
        if added_here:
            super(StockMove, added_here.sudo())._create_repair_sale_order_line()
        return super(StockMove, self - added_here)._create_repair_sale_order_line()
