# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, api, fields, models


class RepairServiceConfirmWizard(models.TransientModel):
    _name = "repair.service.confirm.wizard"
    _description = "Confirm Repair -- Review Services, Technician and Parts"

    repair_id = fields.Many2one("repair.order", required=True, readonly=True)
    # Editable: writes straight back to repair_id.technician_id, same as any
    # other related field with readonly=False.
    technician_id = fields.Many2one(related="repair_id.technician_id", readonly=False)
    move_ids = fields.One2many(related="repair_id.move_ids", readonly=True)
    service_line_ids = fields.One2many(
        "repair.service.confirm.wizard.line", "wizard_id", string="Services"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") != "repair.order":
            return res
        repair = self.env["repair.order"].browse(
            self.env.context.get("active_id")
        )
        if not repair:
            return res
        if "repair_id" in fields_list:
            res["repair_id"] = repair.id
        if "service_line_ids" in fields_list:
            res["service_line_ids"] = [
                Command.create(
                    {"service_id": service.id, "accepted": service.accepted}
                )
                for service in repair.repair_service_ids
            ]
        return res

    def action_confirm(self):
        self.ensure_one()
        for line in self.service_line_ids.filtered("service_id"):
            if line.accepted != line.service_id.accepted:
                line.service_id.accepted = line.accepted
        return self.repair_id.with_context(
            skip_service_confirm_wizard=True
        ).action_validate()

    def action_add_parts_catalog(self):
        self.ensure_one()
        return self.repair_id.action_add_from_catalog()

    def action_add_parts_po(self):
        self.ensure_one()
        return self.repair_id.action_add_parts_from_purchase_order()


class RepairServiceConfirmWizardLine(models.TransientModel):
    _name = "repair.service.confirm.wizard.line"
    _description = "Confirm Repair -- Service Line"

    wizard_id = fields.Many2one(
        "repair.service.confirm.wizard", required=True, ondelete="cascade"
    )
    # Deliberately NOT readonly=True (a required field that is also
    # Python-readonly is dropped from the create payload of a brand-new
    # record) AND deliberately NOT required=True either: this field has
    # still turned up empty on save even without those two combined, most
    # likely via the same list-cell single-click boolean toggle shortcut
    # `accepted` intentionally keeps (list_renderer.js's onCellClicked) not
    # reliably preserving a sibling column's data in every path. Rather
    # than chase every way the client can drop it, the DB-level NOT NULL
    # constraint is removed so that ever happening again degrades to "this
    # one line is silently skipped" (see action_confirm) instead of
    # crashing the whole save. views/repair_service_confirm_wizard_views.xml
    # also sets force_save="1" on it to make the drop itself less likely.
    service_id = fields.Many2one("repair.service")
    product_id = fields.Many2one(related="service_id.product_id", readonly=True)
    display_name = fields.Text(related="service_id.display_name", readonly=True)
    estimated_time = fields.Float(
        related="service_id.estimated_time", readonly=True
    )
    accepted = fields.Boolean()
