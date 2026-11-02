# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models

POSITION_SELECTION = [
    ("lf", "Left Front"),
    ("rf", "Right Front"),
    ("lr", "Left Rear"),
    ("rr", "Right Rear"),
    ("front", "Front"),
    ("rear", "Rear"),
    ("none", "N/A"),
]

UOM_SELECTION = [
    ("in32", "32nds in"),
    ("inch", "in"),
    ("mm", "mm"),
    ("psi", "PSI"),
    ("cca", "CCA"),
    ("degf", "°F"),
    ("percent", "%"),
    ("volt", "V"),
]

# Compact position tags for the one-line summary shown on the inspection lines.
POSITION_SHORT = {
    "lf": "LF",
    "rf": "RF",
    "lr": "LR",
    "rr": "RR",
    "front": "F",
    "rear": "R",
    "none": "",
}


class ShopInspectionMeasurementSpec(models.Model):
    _name = "shop.inspection.measurement.spec"
    _description = "Inspection Measurement Specification"
    _order = "sequence, id"

    item_id = fields.Many2one(
        "fleet.vehicle.inspection.item",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    position = fields.Selection(POSITION_SELECTION, default="none", required=True)
    uom = fields.Selection(UOM_SELECTION, string="Unit")
    spec_min = fields.Float(
        string="Min / Discard Spec",
        help="Measured values below this are out of specification "
        "(e.g. rotor discard thickness, minimum tread depth).",
    )
    spec_max = fields.Float(
        string="Max Spec",
        help="Measured values above this are out of specification "
        "(e.g. maximum coolant freeze point).",
    )

    def _prepare_measurement_vals(self):
        self.ensure_one()
        return {
            "spec_id": self.id,
            "name": self.name,
            "sequence": self.sequence,
            "position": self.position,
            "uom": self.uom,
            "spec_min": self.spec_min,
            "spec_max": self.spec_max,
        }


class ShopInspectionMeasurement(models.Model):
    _name = "shop.inspection.measurement"
    _description = "Inspection Measurement"
    # line_sequence first so the inspection-level grid follows the checklist
    # order; within a line it degrades to the original "sequence, id".
    _order = "line_sequence, line_id, sequence, id"

    line_id = fields.Many2one(
        "fleet.vehicle.inspection.line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    line_sequence = fields.Integer(
        related="line_id.sequence",
        string="Line Sequence",
        store=True,
    )
    inspection_id = fields.Many2one(
        related="line_id.inspection_id",
        store=True,
        index=True,
    )
    spec_id = fields.Many2one("shop.inspection.measurement.spec", ondelete="set null")
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    position = fields.Selection(POSITION_SELECTION, default="none", required=True)
    uom = fields.Selection(UOM_SELECTION, string="Unit")
    value = fields.Float(
        help="Measured value. A value of 0 is treated as 'not measured'."
    )
    spec_min = fields.Float(string="Min / Discard Spec")
    spec_max = fields.Float(string="Max Spec")
    out_of_spec = fields.Boolean(compute="_compute_out_of_spec", store=True)

    def _shop_summary(self):
        """Compact "Tread LF: 6 32nds in" rendering for the inline line list."""
        self.ensure_one()
        label = self.name
        short = POSITION_SHORT.get(self.position)
        if short:
            label = f"{label} {short}"
        value = f"{self.value:g}"
        if self.uom:
            value = f"{value} {dict(UOM_SELECTION)[self.uom]}"
        return f"{label}: {value}"

    @api.depends("value", "spec_min", "spec_max")
    def _compute_out_of_spec(self):
        for measurement in self:
            value = measurement.value
            measurement.out_of_spec = bool(value) and (
                (bool(measurement.spec_min) and value < measurement.spec_min)
                or (bool(measurement.spec_max) and value > measurement.spec_max)
            )
