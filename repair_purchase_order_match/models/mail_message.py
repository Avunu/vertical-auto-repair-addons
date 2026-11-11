# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    repair_match_purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Suggested Purchase Order",
        copy=False,
        # decides whose inbox notifications get cleared: not for whoever may
        # write the message (its author, a recipient) to set
        groups="base.group_system",
        ondelete="set null",
        index="btree_not_null",
        help="The purchase order a suggestion note on a repair order's "
        "chatter is about. Matching that purchase order clears the note's "
        "outstanding inbox notifications.",
    )
