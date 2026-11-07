# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.muk_mcp.core.tool import mcp_tool


class MCPMixin(models.AbstractModel):
    _inherit = "muk_mcp.mixin"

    @api.model
    @mcp_tool(
        name="find_repair_order_matches",
        description=(
            "For a purchase order, ask TypeSafe which open repair order "
            "(with a vehicle and customer concern on file) its parts most "
            "likely belong to. Returns the single best guess with a "
            "confidence score, not a ranked list - use "
            "link_purchase_order_to_repair to confirm it, or link a "
            "different repair order if this guess is wrong. Requires the "
            "TypeSafe API key to be configured (Settings > Purchase)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "purchase_order_id": {
                    "type": "integer",
                    "description": "The purchase.order record id.",
                },
            },
            "required": ["purchase_order_id"],
        },
        category="read",
    )
    def _mcp_find_repair_order_matches(self, purchase_order_id):
        po = self.env["purchase.order"].browse(purchase_order_id)
        if not po.exists():
            raise UserError(_("Purchase order %s not found.", purchase_order_id))
        match = po._repair_match_via_typesafe()
        if not match:
            return {"match": None}
        repair, confidence = match
        return {
            "match": {
                "repair_id": repair.id,
                "repair_name": repair.display_name,
                "confidence": confidence,
            }
        }

    @api.model
    @mcp_tool(
        name="link_purchase_order_to_repair",
        description=(
            "Add every product line on a purchase order to a repair "
            "order's parts list, the same way the purchase order's Add "
            "to Repair button does it by hand. Use "
            "find_repair_order_matches first to pick the right repair "
            "order id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "purchase_order_id": {
                    "type": "integer",
                    "description": "The purchase.order record id.",
                },
                "repair_order_id": {
                    "type": "integer",
                    "description": "The repair.order record id to link it to.",
                },
            },
            "required": ["purchase_order_id", "repair_order_id"],
        },
        category="write",
    )
    def _mcp_link_purchase_order_to_repair(self, purchase_order_id, repair_order_id):
        po = self.env["purchase.order"].browse(purchase_order_id)
        repair = self.env["repair.order"].browse(repair_order_id)
        if not po.exists():
            raise UserError(_("Purchase order %s not found.", purchase_order_id))
        if not repair.exists():
            raise UserError(_("Repair order %s not found.", repair_order_id))
        po._link_to_repair_order(repair)
        return {"linked": True, "purchase_order": po.name, "repair_order": repair.name}
