# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from werkzeug.exceptions import BadRequest, Forbidden

from odoo import http
from odoo.exceptions import AccessError, UserError
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

        The token only proves the link is genuine, not that this user may
        use it: the match runs with the user's own access rights, and a
        user without them gets a 403 page, not a traceback (nor a way to
        tell whether the records exist).

        A purchase order that is meanwhile matched to the same repair order
        is left alone, and to another one is refused with the reason (400):
        the chatter button must not silently move parts that somebody
        placed since - Match Repair on the purchase order does that, on
        purpose.
        """
        try:
            purchase_order = request.env["purchase.order"].browse(
                int(purchase_order_id)
            )
            repair_order = request.env["repair.order"].browse(int(repair_order_id))
        except ValueError:
            raise Forbidden() from None
        if not purchase_order._repair_match_confirm_token_valid(repair_order, token):
            raise Forbidden()
        try:
            if not purchase_order.exists() or not repair_order.exists():
                raise Forbidden()
            # Both must at least be readable: no hint of what exists otherwise.
            purchase_order.check_access("read")
            repair_order.check_access("read")
            # The button lives on in old chatter messages: don't let a stale
            # one move the parts of an order somebody matched since.
            matched = purchase_order._repair_match_linked_repairs()
            if matched and matched != repair_order.sudo():
                raise UserError(
                    request.env._(
                        "%(order)s is already matched to repair order "
                        "%(repairs)s. To match it to a different one, use "
                        "Match Repair on the purchase order.",
                        order=purchase_order.name,
                        repairs=", ".join(matched.with_env(request.env).mapped("name")),
                    )
                )
            if not matched:
                purchase_order._repair_match_check_access(repair_order)
                purchase_order._repair_match_validate(repair_order)
                purchase_order._link_to_repair_order(repair_order)
        except AccessError:
            raise Forbidden(
                request.env._(
                    "You don't have the access rights to match this purchase order."
                )
            ) from None
        except UserError as error:
            raise BadRequest(error.args[0]) from None
        return request.redirect(
            f"/web#model=purchase.order&id={purchase_order.id}&view_type=form"
        )
