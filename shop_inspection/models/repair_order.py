# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models


class RepairOrder(models.Model):
    _inherit = "repair.order"

    inspection_ids = fields.One2many(
        "fleet.vehicle.inspection",
        "repair_id",
        string="Inspections",
    )
    inspection_count = fields.Integer(compute="_compute_inspection_count")
    technician_id = fields.Many2one(
        "res.users",
        string="Technician",
        tracking=True,
    )
    service_advisor_id = fields.Many2one(
        "res.users",
        string="Service Advisor",
        tracking=True,
        default=lambda self: self.env.user,
    )
    count_today = fields.Integer(compute="_compute_severity_counts")
    count_good = fields.Integer(compute="_compute_severity_counts")
    count_future = fields.Integer(compute="_compute_severity_counts")
    count_attention = fields.Integer(compute="_compute_severity_counts")
    count_fail_state = fields.Integer(compute="_compute_severity_counts")

    @api.depends("inspection_ids")
    def _compute_inspection_count(self):
        for repair in self:
            repair.inspection_count = len(repair.inspection_ids)

    @api.depends("inspection_ids.state", "inspection_ids.inspection_line_ids.severity")
    def _compute_severity_counts(self):
        for repair in self:
            lines = repair._shop_get_inspection_lines()
            repair.count_today = len(
                lines.filtered(lambda line: line.severity == "today")
            )
            repair.count_good = len(
                lines.filtered(lambda line: line.severity == "good")
            )
            repair.count_future = len(
                lines.filtered(lambda line: line.severity == "future")
            )
            repair.count_attention = len(
                lines.filtered(lambda line: line.severity == "attention")
            )
            repair.count_fail_state = len(
                lines.filtered(lambda line: line.severity == "fail_state")
            )

    def _shop_get_inspection_lines(self):
        """All inspection lines of the visit's non-cancelled inspections."""
        self.ensure_one()
        return self.inspection_ids.filtered(
            lambda inspection: inspection.state != "cancel"
        ).inspection_line_ids

    def action_view_inspections(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "res_model": "fleet.vehicle.inspection",
            "name": _("Inspections"),
            "view_mode": "list,form",
            "domain": [("repair_id", "=", self.id)],
            "context": self._shop_inspection_context(),
        }
        if self.inspection_count == 1:
            action.update({"view_mode": "form", "res_id": self.inspection_ids.id})
        return action

    def action_new_inspection(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "fleet.vehicle.inspection",
            "name": _("New Inspection"),
            "view_mode": "form",
            "target": "current",
            "context": self._shop_inspection_context(),
        }

    def _shop_inspection_context(self):
        self.ensure_one()
        context = {
            "default_repair_id": self.id,
            "default_vehicle_id": self.vehicle_id.id,
            "default_technician_id": self.technician_id.id or self.env.user.id,
            "default_service_advisor_id": self.service_advisor_id.id,
        }
        if self.vehicle_id.odometer_unit:
            context["default_odometer_unit"] = self.vehicle_id.odometer_unit
        if self.odometer_in:
            context["default_odometer"] = self.odometer_in
        return context
