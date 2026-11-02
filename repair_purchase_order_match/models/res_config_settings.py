# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    repair_match_typesafe_api_key = fields.Char(
        string="TypeSafe API Key",
        config_parameter="repair_purchase_order_match.typesafe_api_key",
        groups="base.group_system",
        help="API key for TypeSafe AI (typesafe.ai), used to decide which "
        "open repair order an imported purchase order most likely belongs "
        "to. Leave empty to disable automatic matching - purchase orders "
        "will need to be linked to a repair order by hand.",
    )
