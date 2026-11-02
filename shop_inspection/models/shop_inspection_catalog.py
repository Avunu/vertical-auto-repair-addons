# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ShopInspectionCategory(models.Model):
    _name = "shop.inspection.category"
    _description = "Inspection Checklist Category"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    note = fields.Text(help="Internal notes about when this checklist section applies.")


class ShopInspectionCondition(models.Model):
    _name = "shop.inspection.condition"
    _description = "Inspection Condition Finding"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)


class ShopInspectionAction(models.Model):
    _name = "shop.inspection.action"
    _description = "Inspection Recommended Action"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
