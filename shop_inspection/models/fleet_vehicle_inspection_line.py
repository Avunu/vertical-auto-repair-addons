# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, api, fields, models

SEVERITY_SELECTION = [
    ("today", "Today's Services / Concerns"),
    ("good", "Good"),
    ("future", "Will Need Attention in the Future"),
    ("attention", "Currently Needs Attention"),
    ("fail_state", "Failed State Inspection"),
    ("na", "Not Applicable"),
]

# Keep the OCA pass/fail rollup working: any severity that needs the
# customer's attention counts as a failure, the rest as success.
SEVERITY_TO_RESULT = {
    "today": "failure",
    "good": "success",
    "future": "failure",
    "attention": "failure",
    "fail_state": "failure",
    "na": "success",
}


class FleetVehicleInspectionLine(models.Model):
    _inherit = "fleet.vehicle.inspection.line"
    # OCA leaves the line without a _rec_name, so it renders as
    # "fleet.vehicle.inspection.line,42" wherever it is referenced (breadcrumbs,
    # the inspection-level measurement grid). The checklist item is the name.
    _rec_name = "inspection_item_id"

    severity = fields.Selection(
        SEVERITY_SELECTION,
        tracking=True,
        help="Grading of the finding on the customer report. Setting it "
        "also sets the pass/fail result of the line.",
    )
    category_id = fields.Many2one(
        related="inspection_item_id.category_id",
        store=True,
    )
    condition_ids = fields.Many2many(
        "shop.inspection.condition",
        "inspection_line_condition_rel",
        "line_id",
        "condition_id",
        string="Conditions",
    )
    recommended_action_ids = fields.Many2many(
        "shop.inspection.action",
        "inspection_line_action_rel",
        "line_id",
        "action_id",
        string="Recommended Actions",
    )
    measurement_ids = fields.One2many(
        "shop.inspection.measurement",
        "line_id",
        string="Measurements",
        copy=True,
    )
    measurement_summary = fields.Char(
        compute="_compute_measurement_summary",
        help="Measured values, so the grid does not have to be opened to see "
        "what was recorded.",
    )
    measurement_alert = fields.Boolean(compute="_compute_measurement_summary")

    @api.depends(
        "measurement_ids.value",
        "measurement_ids.position",
        "measurement_ids.uom",
        "measurement_ids.out_of_spec",
    )
    def _compute_measurement_summary(self):
        for line in self:
            # A value of 0 means "not measured": keep it out of the summary.
            measured = line.measurement_ids.filtered("value")
            line.measurement_summary = " · ".join(m._shop_summary() for m in measured)
            line.measurement_alert = any(measured.mapped("out_of_spec"))

    @api.model
    def _shop_apply_severity(self, vals):
        severity = vals.get("severity")
        if severity and "result" not in vals:
            vals["result"] = SEVERITY_TO_RESULT[severity]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._shop_apply_severity(vals)
            # Pre-fill the measurement grid from the item specs (template
            # loading creates lines without triggering onchanges).
            if vals.get("inspection_item_id") and not vals.get("measurement_ids"):
                item = self.env["fleet.vehicle.inspection.item"].browse(
                    vals["inspection_item_id"]
                )
                if item.measurement_spec_ids:
                    vals["measurement_ids"] = [
                        Command.create(spec._prepare_measurement_vals())
                        for spec in item.measurement_spec_ids
                    ]
        return super().create(vals_list)

    def write(self, vals):
        self._shop_apply_severity(vals)
        return super().write(vals)

    @api.onchange("inspection_item_id")
    def _onchange_shop_inspection_item_id(self):
        for line in self:
            specs = line.inspection_item_id.measurement_spec_ids
            line.measurement_ids = [Command.clear()] + [
                Command.create(spec._prepare_measurement_vals()) for spec in specs
            ]
