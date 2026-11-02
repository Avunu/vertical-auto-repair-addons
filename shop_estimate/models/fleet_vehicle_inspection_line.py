# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class FleetVehicleInspectionLine(models.Model):
    _inherit = "fleet.vehicle.inspection.line"

    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Quoted As (line)",
        copy=False,
    )
    sale_option_id = fields.Many2one(
        "sale.order.option",
        string="Quoted As (option)",
        copy=False,
    )
    shop_quoted = fields.Boolean(
        compute="_compute_shop_quoted",
        string="Quoted",
    )

    @api.depends("sale_line_id", "sale_option_id")
    def _compute_shop_quoted(self):
        for line in self:
            line.shop_quoted = bool(line.sale_line_id or line.sale_option_id)
