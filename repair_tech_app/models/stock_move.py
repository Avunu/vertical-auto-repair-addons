# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    tech_added_uid = fields.Many2one(
        "res.users",
        string="Added by Technician",
        copy=False,
        index="btree_not_null",
        help="Set when a technician added this part from the technician app "
        "rather than it arriving with the approved estimate. The move still "
        "reaches its own quote line as core does; this and the note on the "
        "repair order are how the service advisor spots the difference from "
        "what the customer approved.",
    )

    def _create_repair_sale_order_line(self):
        """Let a technician's catalog add reach the quote.

        Core creates the sale.order.line from inside ``stock.move.create``. A
        technician has stock rights, not sales rights, so that create would
        raise AccessError and the technician couldn't record a part they
        installed. The elevation is narrow: only moves the app stamped, and
        only the line core would have created anyway. The line's creator
        becomes the superuser, so the note the app logs on the repair order is
        what names the technician.
        """
        added = self.filtered("tech_added_uid")
        if added:
            super(StockMove, added.sudo())._create_repair_sale_order_line()
        return super(StockMove, self - added)._create_repair_sale_order_line()
