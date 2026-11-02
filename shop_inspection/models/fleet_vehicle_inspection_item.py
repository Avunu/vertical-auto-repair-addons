# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class FleetVehicleInspectionItem(models.Model):
    _inherit = "fleet.vehicle.inspection.item"

    category_id = fields.Many2one(
        "shop.inspection.category",
        string="Checklist Category",
        index=True,
        help="Drives the section grouping on the customer inspection report.",
    )
    condition_ids = fields.Many2many(
        "shop.inspection.condition",
        "inspection_item_condition_rel",
        "item_id",
        "condition_id",
        string="Typical Conditions",
        help="Condition findings commonly reported for this item.",
    )
    recommended_action_ids = fields.Many2many(
        "shop.inspection.action",
        "inspection_item_action_rel",
        "item_id",
        "action_id",
        string="Typical Recommended Actions",
        help="Actions commonly recommended for this item.",
    )
    measurement_spec_ids = fields.One2many(
        "shop.inspection.measurement.spec",
        "item_id",
        string="Measurements",
        help="Measurement rows pre-filled on inspection lines for this item.",
    )
