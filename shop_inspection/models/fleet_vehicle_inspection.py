# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicleInspection(models.Model):
    _inherit = "fleet.vehicle.inspection"

    repair_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        index=True,
        tracking=True,
        help="The shop visit this inspection belongs to.",
    )
    technician_id = fields.Many2one(
        "res.users",
        string="Technician",
        tracking=True,
        default=lambda self: self.env.user,
    )
    service_advisor_id = fields.Many2one(
        "res.users",
        string="Service Advisor",
        tracking=True,
    )
    # Flattened view of every line's measurements, so the values can be typed
    # in one grid instead of opening each line.
    measurement_ids = fields.One2many(
        "shop.inspection.measurement",
        "inspection_id",
        string="Measurements",
    )
    count_today = fields.Integer(compute="_compute_severity_counts")
    count_good = fields.Integer(compute="_compute_severity_counts")
    count_future = fields.Integer(compute="_compute_severity_counts")
    count_attention = fields.Integer(compute="_compute_severity_counts")
    count_fail_state = fields.Integer(compute="_compute_severity_counts")

    @api.depends("inspection_line_ids.severity")
    def _compute_severity_counts(self):
        for inspection in self:
            lines = inspection.inspection_line_ids
            inspection.count_today = len(
                lines.filtered(lambda line: line.severity == "today")
            )
            inspection.count_good = len(
                lines.filtered(lambda line: line.severity == "good")
            )
            inspection.count_future = len(
                lines.filtered(lambda line: line.severity == "future")
            )
            inspection.count_attention = len(
                lines.filtered(lambda line: line.severity == "attention")
            )
            inspection.count_fail_state = len(
                lines.filtered(lambda line: line.severity == "fail_state")
            )

    @api.constrains("repair_id", "vehicle_id")
    def _check_repair_vehicle(self):
        for inspection in self:
            if (
                inspection.repair_id
                and inspection.repair_id.vehicle_id
                and inspection.vehicle_id != inspection.repair_id.vehicle_id
            ):
                raise ValidationError(
                    _(
                        "The inspection vehicle (%(vehicle)s) must match the "
                        "vehicle of repair order %(repair)s.",
                        vehicle=inspection.vehicle_id.display_name,
                        repair=inspection.repair_id.name,
                    )
                )

    @api.onchange("repair_id")
    def _onchange_shop_repair_id(self):
        for inspection in self:
            repair = inspection.repair_id
            if not repair:
                continue
            if repair.vehicle_id:
                inspection.vehicle_id = repair.vehicle_id
                if repair.vehicle_id.odometer_unit:
                    inspection.odometer_unit = repair.vehicle_id.odometer_unit
            if repair.odometer_in and not inspection.odometer:
                inspection.odometer = repair.odometer_in
            if repair.technician_id:
                inspection.technician_id = repair.technician_id
            if repair.service_advisor_id:
                inspection.service_advisor_id = repair.service_advisor_id

    def action_view_repair_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "res_id": self.repair_id.id,
            "view_mode": "form",
        }
