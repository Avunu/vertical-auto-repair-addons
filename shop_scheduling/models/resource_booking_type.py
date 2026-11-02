# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from random import randint

from odoo import fields, models


class ResourceBookingType(models.Model):
    _inherit = "resource.booking.type"

    shop_repair_ok = fields.Boolean(
        string="Shop Appointment Type",
        help="Offered when scheduling a repair order. The first type with "
        "this box ticked is proposed by default.",
    )
    color = fields.Integer(
        default=lambda self: randint(1, 11),
        help="Colour of this type's repair orders on the repair calendar.",
    )
