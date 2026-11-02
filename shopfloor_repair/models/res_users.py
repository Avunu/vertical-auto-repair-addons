# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    shopfloor_default_profile_id = fields.Many2one(
        comodel_name="shopfloor.profile",
        string="Default Shopfloor Profile",
        help="Selected automatically when this user signs in to the shopfloor "
        "app, so the profile only has to be picked once. Set by the app "
        "whenever the user changes their profile.",
    )
