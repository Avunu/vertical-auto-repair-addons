# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from .typesafe_utils import typesafe_format_datetime


class RepairOrder(models.Model):
    _inherit = "repair.order"

    repair_match_can_link = fields.Boolean(
        string="Can Match Purchase Orders",
        compute="_compute_repair_match_can_link",
        help="Whether the current user has the access rights to match "
        "purchase orders to this repair order. Drives the Match Order "
        "button; the actions check the same rights themselves.",
    )

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_repair_match_can_link(self):
        access = self.env["repair.match.access"]
        orders = self.env["purchase.order"]
        for repair in self:
            repair.repair_match_can_link = access._can_link(orders, repair)

    def _typesafe_match_criteria(self):
        """This repair order, described for TypeSafe as one named option
        of the "matching_ro" choice - vehicle info and the customer's own
        words, the same fields a service writer would use to recognize
        which job a vendor's part is for.
        """
        self.ensure_one()
        vehicle = self.vehicle_id
        model = vehicle.model_id
        return {
            "Repair Date": typesafe_format_datetime(self.schedule_date),
            "Manufacturer": model.brand_id.name if model else None,
            "Model": model.name if model else None,
            "Model Year": vehicle.model_year or None,
            "customer concerns": (
                html2plaintext(self.customer_concern) if self.customer_concern else None
            ),
        }

    def action_match_order(self):
        """Header button: pick, in a dialog, the purchase order this repair
        order's parts come from. The dialog lists the confirmed purchase
        orders not linked to any repair order yet - each card with its
        parts list and a Match button (PurchaseOrder.action_match_to_repair,
        which reads this repair order from the context).
        """
        self.ensure_one()
        self.env["repair.match.access"]._check_can_link(
            self.env["purchase.order"], self
        )
        if self.state in ("done", "cancel"):
            raise UserError(
                _("%s is closed, so purchase orders can't be matched to it.", self.name)
            )
        kanban = self.env.ref(
            "repair_purchase_order_match.view_purchase_order_kanban_match_repair"
        )
        search = self.env.ref(
            "repair_purchase_order_match.view_purchase_order_search_match_repair"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Order"),
            "res_model": "purchase.order",
            "view_mode": "kanban",
            "views": [(kanban.id, "kanban")],
            # ir.ui.view names are readable by Settings users only.
            "search_view_id": (search.id, search.sudo().name),
            "target": "new",
            "domain": self.env["purchase.order"]._repair_match_unmatched_domain(
                self.company_id
            ),
            "context": {
                "repair_id": self.id,
                "dialog_size": "extra-large",
                "create": False,
            },
        }

    def action_link_purchase_order(self):
        """Row-click action on the repair order list a purchase order's
        "choose a different repair order" chatter link opens (the purchase
        order's id is its `po_id` context): link that purchase order to
        this repair order, then go back to the purchase order. The same
        list opened as the purchase order's Match Repair dialog
        (`repair_match_dialog` in the context) closes and reloads the
        purchase order form it was opened from instead.
        """
        self.ensure_one()
        po = self.env["purchase.order"].browse(self.env.context.get("po_id"))
        if not po.exists():
            raise UserError(_("No purchase order to link to this repair order."))
        po._repair_match_check_access(self)
        po._repair_match_validate(self)
        po._link_to_repair_order(self)
        if self.env.context.get("repair_match_dialog"):
            return {"type": "ir.actions.client", "tag": "soft_reload"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": po.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    @api.model_create_multi
    def create(self, vals_list):
        """A repair order created with `po_id` in its context (the purchase
        order's old "Create New Repair" picker) used to get that purchase
        order's parts added without a word: it is linked the way Match Repair
        does instead - rights and validity checked, notes posted, the
        purchase order's outstanding notices cleared.
        """
        order = self.env["purchase.order"].browse(self.env.context.get("po_id"))
        if not order.exists():
            return super().create(vals_list)
        records = super(RepairOrder, self.with_context(po_id=False)).create(vals_list)
        for repair in records:
            order._repair_match_check_access(repair)
            order._repair_match_validate(repair)
            order._link_to_repair_order(repair)
        return records

    def action_select_po_for_repair(self):
        """`repair_purchase_order_parts` row click of its purchase order ->
        repair order picker (the purchase order is `po_id` in the context):
        links it the way Match Repair does.
        """
        self.ensure_one()
        order = self.env["purchase.order"].browse(self.env.context.get("po_id"))
        if not order.exists():
            raise UserError(_("No purchase order to link to this repair order."))
        order._repair_match_check_access(self)
        order._repair_match_validate(self)
        if not order._prepare_repair_move_vals(
            self, self.move_ids.created_purchase_line_ids.ids
        ):
            raise UserError(
                _("Every part on %s is already on this repair order.", order.name)
            )
        order._link_to_repair_order(self)
        return {"type": "ir.actions.act_window_close"}

    def action_add_parts_from_purchase_order(self):
        """`repair_purchase_order_parts` Parts-tab button, superseded by
        Match Order: the same dialog as the header button, which links the
        way the match flow does (a purchase order belongs to one repair
        order).
        """
        return self.action_match_order()
