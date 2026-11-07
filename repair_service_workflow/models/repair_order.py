# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, models


class RepairOrder(models.Model):
    _inherit = "repair.order"

    def action_create_sale_order(self):
        action = super().action_create_sale_order()
        # Unaccepted services never got a sale.order.line (see
        # RepairService._create_repair_sale_order_line); archive them now
        # rather than leaving them on the Services tab as dead weight.
        # Archived, not unlinked, so they stay recoverable/auditable.
        self.repair_service_ids.filtered(lambda s: not s.accepted).write(
            {"active": False}
        )
        return action

    def action_validate(self):
        self.ensure_one()
        if self.state != "draft" or self.env.context.get("skip_service_confirm_wizard"):
            return super().action_validate()
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Repair"),
            "res_model": "repair.service.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_repair_id": self.id,
                "active_model": "repair.order",
                "active_id": self.id,
            },
        }

    def action_repair_end(self):
        if self.env.context.get("skip_service_finalize_wizard"):
            return super().action_repair_end()
        if self.filtered(lambda repair: repair.state != "under_repair"):
            # Not the happy path: let core raise its own descriptive error
            # instead of duplicating that check here.
            return super().action_repair_end()
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Finalize Repair"),
            "res_model": "repair.service.finalize.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_repair_id": self.id,
                "active_model": "repair.order",
                "active_id": self.id,
            },
        }
