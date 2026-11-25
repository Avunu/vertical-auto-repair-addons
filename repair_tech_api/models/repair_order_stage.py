# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class RepairOrderStage(models.Model):
    _inherit = "repair.order.stage"

    board_status = fields.Selection(
        [
            ("diag", "Waiting for diagnostics"),
            ("pa", "Waiting for PA inspection"),
            ("cust", "Waiting on customer"),
            ("parts", "Waiting on parts"),
            ("ready", "Ready for repair"),
            ("repair", "Under repair"),
        ],
        string="Job Board Status",
        help="Orders in this stage are shown on the shop's job board, in this "
        "status's color. Leave empty to keep the stage's orders off the board.",
    )
