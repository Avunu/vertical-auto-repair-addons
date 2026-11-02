# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request


class RepairPurchaseOrderMatchController(http.Controller):
    @http.route(
        "/repair_purchase_order_match/confirm",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def confirm_match(self, purchase_order_id, repair_order_id, token, **kwargs):
        """Land here from the "Confirm Match" button posted to a purchase
        order's and repair order's chatter. Requires a login (auth='user')
        plus a signed token tying this specific PO/RO pair together (see
        purchase.order._repair_match_confirm_token), so the link can't be
        replayed against a different pair or forged from outside Odoo.
        """
        purchase_order = request.env["purchase.order"].browse(int(purchase_order_id))
        repair_order = request.env["repair.order"].browse(int(repair_order_id))
        if not purchase_order.exists() or not repair_order.exists():
            raise Forbidden()
        if not purchase_order._repair_match_confirm_token_valid(repair_order, token):
            raise Forbidden()
        purchase_order._link_to_repair_order(repair_order)
        return request.redirect(
            f"/web#model=purchase.order&id={purchase_order.id}&view_type=form"
        )
