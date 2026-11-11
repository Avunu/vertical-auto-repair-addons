# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    repair_match_can_link = fields.Boolean(
        string="Can Match to a Repair Order",
        compute="_compute_repair_match_can_link",
        help="Whether the current user has the access rights to match the "
        "purchase order of this receipt to a repair order. Drives the "
        "Match Repair button; the action checks the same rights itself.",
    )

    @api.depends_context("uid", "allowed_company_ids")
    @api.depends("purchase_id")
    def _compute_repair_match_can_link(self):
        for picking in self:
            picking.repair_match_can_link = bool(
                picking.purchase_id and picking.purchase_id.repair_match_can_link
            )

    def action_match_repair(self):
        """Header button of a validated receipt: the Match Repair dialog
        of its purchase order (`purchase_id` is the one core's
        purchase_stock puts on every incoming picking).
        """
        self.ensure_one()
        if not self.purchase_id:
            raise UserError(_("%s has no purchase order to match.", self.name))
        return self.purchase_id.action_match_repair()

    def action_add_to_repair(self):
        """`repair_purchase_order_parts` receipt button, superseded by Match
        Repair.
        """
        return self.action_match_repair()
