# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ShopfloorApp(models.Model):
    _inherit = "shopfloor.app"

    category = fields.Selection(selection_add=[("repair", "Repair Shop")])
