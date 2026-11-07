# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, api, fields, models


class RepairServiceFinalizeWizard(models.TransientModel):
    _name = "repair.service.finalize.wizard"
    _description = "Finalize Repair -- Confirm Billable Parts and Services"

    repair_id = fields.Many2one("repair.order", required=True, readonly=True)
    technician_id = fields.Many2one(related="repair_id.technician_id", readonly=True)
    move_ids = fields.One2many(related="repair_id.move_ids", readonly=True)
    service_line_ids = fields.One2many(
        "repair.service.finalize.wizard.line", "wizard_id", string="Services"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") != "repair.order":
            return res
        repair = self.env["repair.order"].browse(self.env.context.get("active_id"))
        if not repair:
            return res
        if "repair_id" in fields_list:
            res["repair_id"] = repair.id
        if "service_line_ids" in fields_list:
            res["service_line_ids"] = [
                Command.create({"service_id": service.id})
                for service in repair.repair_service_ids.filtered("accepted")
            ]
        return res

    def action_finalize(self):
        self.ensure_one()
        return self.repair_id.with_context(
            skip_service_finalize_wizard=True
        ).action_repair_end()


class RepairServiceFinalizeWizardLine(models.TransientModel):
    _name = "repair.service.finalize.wizard.line"
    _description = "Finalize Repair -- Billable Service Line"

    wizard_id = fields.Many2one(
        "repair.service.finalize.wizard", required=True, ondelete="cascade"
    )
    # See the equivalent field on repair.service.confirm.wizard.line for
    # why this is neither readonly=True nor required=True: both together
    # or even required alone have turned up empty on save via more than
    # one client-side path, so the DB-level NOT NULL constraint is removed
    # entirely rather than chasing each new way to trigger it.
    # force_save="1" in the view makes the drop itself less likely.
    service_id = fields.Many2one("repair.service")
    product_id = fields.Many2one(related="service_id.product_id", readonly=True)
    display_name = fields.Text(related="service_id.display_name", readonly=True)
    product_uom_qty = fields.Float(
        related="service_id.product_uom_qty", readonly=True, string="Invoiced"
    )
    estimated_time = fields.Float(related="service_id.estimated_time", readonly=True)
    actual_time = fields.Float(related="service_id.actual_time", readonly=True)
