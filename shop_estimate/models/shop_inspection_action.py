# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ShopInspectionAction(models.Model):
    _inherit = "shop.inspection.action"

    job_id = fields.Many2one(
        "shop.service.job",
        string="Service Job",
        help="Canned job used to price findings carrying this recommended "
        "action in the estimate builder.",
    )
