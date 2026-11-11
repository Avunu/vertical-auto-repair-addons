# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, models
from odoo.exceptions import AccessError


class RepairMatchAccess(models.AbstractModel):
    """What a user must be allowed to do to match a purchase order to a
    repair order - one place for the buttons (visibility), the dialogs and
    the link itself, so that they can't disagree.

    Matching reads the purchase order and its lines, posts to its chatter
    (which, as for any document, takes write access to it), writes to the
    repair order (it posts to its chatter and its parts change) and creates
    the repair's `stock.move` parts. When the repair order has a quotation
    core repair adds a line to it for each part; taking the parts back off
    another repair order unlinks those moves (and quotation lines). Every
    check goes through `has_access()`, i.e. the access rights
    (`ir.model.access`) *and* the record rules (multi-company) of the
    current user, on the concrete records when there are some. Nothing here
    uses sudo.
    """

    _name = "repair.match.access"
    _description = "Repair / Purchase Order Match Access"

    @api.model
    def _missing_rights(self, orders, repairs, removable_moves=None):
        """What the current user lacks to link `orders` to `repairs`, as a
        list of readable phrases (empty when nothing is missing).

        `orders` and `repairs` may be empty recordsets: the rights on the
        model are checked then (a button on a form that does not know the
        other side yet). `removable_moves` are the parts the link would
        take off other repair orders.
        """
        env = self.env
        missing = []

        def need(records, operation, phrase):
            if not records.has_access(operation) and phrase not in missing:
                missing.append(phrase)

        Order = env["purchase.order"]
        Repair = env["repair.order"]
        # Whatever env the records come with, the rights are the ones of the
        # current user: a sudo'd record never makes a user more able.
        orders = orders.with_env(env) if orders else Order
        repairs = repairs.with_env(env) if repairs else Repair
        removable_moves = removable_moves.with_env(env) if removable_moves else None
        need(orders, "read", _("read purchase orders"))
        # Posting on a document takes write access to it (`_mail_post_access`).
        need(orders, "write", _("edit purchase orders"))
        need(env["purchase.order.line"], "read", _("read purchase order lines"))
        need(repairs, "read", _("read repair orders"))
        need(repairs, "write", _("edit repair orders"))
        need(env["stock.move"], "create", _("add parts to a repair order"))
        if repairs.has_access("read") and repairs.sale_order_id:
            # Core repair mirrors every added part on the quotation. Writing
            # to the quotation itself stands for the record rule of its lines
            # (a salesman edits their own quotations only).
            need(
                env["sale.order.line"],
                "create",
                _("add lines to the quotation of a repair order"),
            )
            need(
                repairs.sale_order_id,
                "write",
                _("add lines to the quotation of a repair order"),
            )
        if removable_moves:
            need(
                removable_moves,
                "unlink",
                _("take parts off another repair order"),
            )
            if removable_moves.has_access("read") and removable_moves.sale_line_id:
                need(
                    env["sale.order.line"],
                    "unlink",
                    _("remove lines from the quotation of a repair order"),
                )
        return missing

    @api.model
    def _can_link(self, orders, repairs, removable_moves=None):
        return not self._missing_rights(orders, repairs, removable_moves)

    @api.model
    def _check_can_link(self, orders, repairs, removable_moves=None):
        """Raise a clear AccessError naming the missing rights."""
        missing = self._missing_rights(orders, repairs, removable_moves)
        if missing:
            raise AccessError(
                _(
                    "You are not allowed to match purchase orders and repair "
                    "orders: you can't %s. It takes the Purchase and Inventory "
                    "user access rights (plus Inventory Administrator to take "
                    "parts off another repair order, and Sales: User for a "
                    "repair order with a quotation).",
                    ", ".join(missing),
                )
            )
