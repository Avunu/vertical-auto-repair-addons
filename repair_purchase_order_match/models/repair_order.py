# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from .typesafe_utils import typesafe_format_datetime


class RepairOrder(models.Model):
    _inherit = "repair.order"

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

    def action_link_purchase_order(self):
        """Row-click action on the repair order list a purchase order's
        "choose a different repair order" chatter link opens (the purchase
        order's id is its `po_id` context): link that purchase order to
        this repair order, then go back to the purchase order.
        """
        self.ensure_one()
        po = self.env["purchase.order"].browse(self.env.context.get("po_id"))
        if not po.exists():
            raise UserError(_("No purchase order to link to this repair order."))
        po._link_to_repair_order(self)
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": po.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }
