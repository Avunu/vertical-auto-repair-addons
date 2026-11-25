# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResourceBookingType(models.Model):
    _inherit = "resource.booking.type"

    # The job board marks each card with its appointment type: an icon on
    # the card and the label in the board's key. Types left without an icon
    # get no mark and stay out of the key.
    board_icon = fields.Selection(
        [("car", "Car"), ("truck", "Heavy truck")],
        string="Job Board Icon",
        help="Icon on the shop's job board for repair orders of this "
        "appointment type. Leave empty for no icon.",
    )
    board_label = fields.Char(
        string="Job Board Label",
        translate=True,
        help="What the job board's key calls this type, e.g. Heavy truck. "
        "Defaults to the type's name.",
    )

    def _board_label(self):
        self.ensure_one()
        return self.board_label or self.name
