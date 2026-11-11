# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging
import re

from markupsafe import Markup
from typesafe_sdk import Choice, TypeSafeClient, TypeSafeError

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from .typesafe_utils import typesafe_format_datetime

_logger = logging.getLogger(__name__)

CANDIDATE_LIMIT = 25
CONFIRM_TOKEN_SCOPE = "repair_purchase_order_match-confirm"


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    repair_match_unmatched = fields.Boolean(
        string="Not Linked to a Repair Order",
        compute="_compute_repair_match_unmatched",
        search="_search_repair_match_unmatched",
        help="True when none of the order lines is a part on a repair order "
        "that is not cancelled. Searchable only.",
    )
    repair_match_can_link = fields.Boolean(
        string="Can Match to a Repair Order",
        compute="_compute_repair_match_can_link",
        help="Whether the current user has the access rights to match this "
        "purchase order to a repair order. Drives the Match Repair button; "
        "the actions check the same rights themselves.",
    )
    repair_match_parts_html = fields.Html(
        string="Parts",
        compute="_compute_repair_match_parts_html",
        sanitize=False,
    )

    # ----------------------------------------------------------
    # EDI hook
    # ----------------------------------------------------------

    def _edi_confirm_and_notify(self):
        """After an EDI/email-imported purchase order is confirmed, ask
        TypeSafe which open repair order it most likely belongs to, in the
        background so a slow request never delays the import itself.
        """
        res = super()._edi_confirm_and_notify()
        self.with_delay(
            description=_("Match %s to an open repair order", self.name)
        )._repair_auto_match_job()
        return res

    def _repair_auto_match_job(self):
        """Queue job of `_edi_confirm_and_notify`: match this purchase order
        on behalf of the system. The job runs as whoever triggered the
        import - the mail alias' user or the mail gateway's - who is
        typically a low-privilege user that has no right on repair orders,
        so it runs with sudo: what it does is fixed (link by PO number, or
        post a suggestion), nothing a user chooses. Manual matching never
        goes through here and always uses the rights of the user.
        """
        return self.sudo()._repair_auto_link_or_suggest()

    # ----------------------------------------------------------
    # Notices (see `edi_purchase_order_import`'s `_edi_post_notice`)
    # ----------------------------------------------------------

    def _edi_notice_still_needed(self):
        """An outstanding notice about an order that is already matched to a
        repair order (say, by the PO number, before the suggestion or the
        confirmation notice was posted) calls for nobody's attention: it is
        posted without an inbox notification, i.e. already read.
        """
        self.ensure_one()
        return super()._edi_notice_still_needed() and not (
            self._repair_match_linked_repairs()
        )

    def _edi_outstanding_notices(self):
        """Also the suggestion notes on repair orders' chatters that concern
        these purchase orders, so that matching clears them as well."""
        return super()._edi_outstanding_notices() | (
            self.env["mail.message"]
            .sudo()
            .search(
                [
                    ("repair_match_purchase_order_id", "in", self.ids),
                    ("edi_notice_outstanding", "=", True),
                ]
            )
        )

    def _repair_match_linked_repairs(self):
        """The repair orders (sudo) this purchase order is matched to: the
        ones holding a part that came from one of its lines, whether it was
        matched here or by Odoo's own Buy route. Cancelled repair orders
        don't count (see `_repair_match_live_link_domain`). Same definition
        as `repair_match_unmatched`, read fresh.
        """
        self.ensure_one()
        lines = self.sudo().order_line
        moves = lines.move_dest_ids | lines.move_ids.move_dest_ids
        return moves.filtered_domain(self._repair_match_live_link_domain()).repair_id

    # ----------------------------------------------------------
    # Manual matching (Match Order / Match Repair buttons)
    # ----------------------------------------------------------

    @staticmethod
    def _repair_match_live_link_domain():
        """Domain on stock.move for a purchase line that counts as linked:
        a part on a repair order that has not been cancelled (done counts:
        its parts were used). A cancelled repair order is a dead end, so the
        purchase order it was linked to is up for matching again.
        """
        return [
            ("repair_id", "!=", False),
            ("repair_id.state", "!=", "cancel"),
        ]

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_repair_match_can_link(self):
        access = self.env["repair.match.access"]
        repairs = self.env["repair.order"]
        for order in self:
            order.repair_match_can_link = access._can_link(
                order, repairs, order._repair_match_moves_on_other_repairs()
            )

    @api.depends(
        "order_line.move_dest_ids.repair_id.state",
        "order_line.move_ids.move_dest_ids.repair_id.state",
    )
    def _compute_repair_match_unmatched(self):
        # Odoo's own link (purchase_repair `_get_linked_repair_orders`) is
        # the line's `move_dest_ids` or, once the order is confirmed on the
        # Buy route, its receipt moves' `move_dest_ids`.
        for order in self:
            lines = order.sudo().order_line
            moves = lines.move_dest_ids | lines.move_ids.move_dest_ids
            order.repair_match_unmatched = not moves.filtered_domain(
                self._repair_match_live_link_domain()
            )

    def _search_repair_match_unmatched(self, operator, value):
        """`order_line not in (lines linked to a live repair order)`, as one
        SQL sub-select: a purchase order with some lines linked is linked,
        and nothing is loaded into Python however many purchase orders
        there are. The links are read with sudo so the answer does not
        depend on the user's stock access (a purchase user may not read
        stock moves); the purchase orders themselves are still filtered by
        the user's own record rules.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Unsupported search on repair link: %s", operator))
        live_link = self._repair_match_live_link_domain()
        linked_lines = (
            self.env["purchase.order.line"]
            .sudo()
            ._search(
                [
                    "|",
                    ("move_dest_ids", "any", live_link),
                    ("move_ids.move_dest_ids", "any", live_link),
                ]
            )
        )
        unmatched = (operator == "=") == value
        return [("order_line", "not in" if unmatched else "in", linked_lines)]

    @api.model
    def _repair_match_unmatched_domain(self, company=None):
        """Domain for the confirmed purchase orders of `company` (default:
        the current one) that are not linked to any repair order yet.
        """
        company = company or self.env.company
        return [
            ("state", "in", ("purchase", "done")),
            ("company_id", "=", company.id),
            ("repair_match_unmatched", "=", True),
            # Nothing to match without a part: service-only orders and
            # orders of sections and notes are left out.
            (
                "order_line",
                "any",
                [("display_type", "=", False), ("product_id", "!=", False)],
            ),
        ]

    @api.depends(
        "order_line.display_type",
        "order_line.product_id.default_code",
        "order_line.product_qty",
        "order_line.product_uom",
        "order_line.name",
    )
    def _compute_repair_match_parts_html(self):
        """The parts list of each purchase order as a small table (quantity
        and unit, part number, description) for the Match Order dialog.
        Skips the same lines `_prepare_repair_move_vals` skips (sections,
        notes, lines without a product) and escapes every value, since
        descriptions come from vendor emails.
        """
        for order in self:
            rows = [
                Markup(
                    '<tr><td class="text-nowrap pe-2 text-end">{qty} {uom}</td>'
                    '<td class="text-nowrap pe-2 fw-bold">{code}</td>'
                    "<td>{name}</td></tr>"
                ).format(
                    qty=formatLang(
                        self.env, line.product_qty, dp="Product Unit of Measure"
                    ),
                    uom=line.product_uom.name or "",
                    code=line.product_id.default_code or "",
                    name=" ".join((line.name or line.product_id.display_name).split()),
                )
                for line in order.order_line
                if not line.display_type and line.product_id
            ]
            order.repair_match_parts_html = (
                Markup(
                    '<table class="table table-sm table-borderless mb-0">{}</table>'
                ).format(Markup("").join(rows))
                if rows
                else Markup("")
            )

    def action_match_to_repair(self):
        """Card button of the repair order's Match Order dialog (the repair
        order is `repair_id` in the context): link this purchase order to
        it with `_link_to_repair_order`, then close the dialog and reload
        the repair order form underneath.
        """
        self.ensure_one()
        repair = self.env["repair.order"].browse(self.env.context.get("repair_id"))
        if not repair.exists():
            raise UserError(_("No repair order to match this purchase order to."))
        self._repair_match_check_access(repair)
        self._repair_match_validate(repair)
        self._link_to_repair_order(repair)
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    def _repair_match_has_parts(self):
        self.ensure_one()
        return any(
            not line.display_type and line.product_id for line in self.order_line
        )

    def _repair_match_validate(self, repair):
        """Raise a UserError unless this purchase order can be matched to
        `repair`: the repair order is still open, both belong to the same
        company, the purchase order is not cancelled and has parts. Checked
        by every manual way to match (dialogs, chatter links, MCP tools).
        """
        self.ensure_one()
        if repair.state in ("done", "cancel"):
            raise UserError(
                _(
                    "%s is closed, so purchase orders can't be matched to it.",
                    repair.name,
                )
            )
        if repair.company_id != self.company_id:
            raise UserError(
                _(
                    "%(order)s and %(repair)s belong to different companies.",
                    order=self.name,
                    repair=repair.name,
                )
            )
        if self.state == "cancel":
            raise UserError(
                _(
                    "%s is cancelled, so it can't be matched to a repair order.",
                    self.name,
                )
            )
        if not self._repair_match_has_parts():
            raise UserError(_("%s has no parts to add to a repair order.", self.name))

    def _repair_match_moves_on_other_repairs(self, repair=None):
        """The parts this purchase order added to open repair orders other
        than `repair` (any open one without `repair`) that are still to be
        used, i.e. the ones a new match takes back. Searched with the
        user's own access: they only count what they can see.
        """
        moves = self.env["stock.move"]
        lines = self.order_line
        # The domain reads the repair order's state: without the right to
        # read stock moves and repair orders there is nothing to see (and
        # the user can't match anyway, which `repair.match.access` says).
        if (
            not lines
            or not moves.has_access("read")
            or not self.env["repair.order"].has_access("read")
        ):
            return moves
        domain = [
            ("created_purchase_line_ids", "in", lines.ids),
            ("repair_id", "!=", False),
            ("repair_id.state", "not in", ("done", "cancel")),
            ("state", "not in", ("done", "cancel")),
        ]
        if repair:
            domain.append(("repair_id", "!=", repair.id))
        return moves.search(domain)

    def _repair_match_check_access(self, repair):
        """Raise an AccessError unless the current user may link this
        purchase order to `repair`: see `repair.match.access`. The rights
        of the user are never bypassed, whatever the button shows.
        """
        self.ensure_one()
        self.env["repair.match.access"]._check_can_link(
            self,
            repair,
            self._repair_match_moves_on_other_repairs(repair),
        )

    def action_match_repair(self):
        """Header button: pick the open repair order this purchase order
        belongs to, in a dialog. Clicking a row links them, see
        RepairOrder.action_link_purchase_order.
        """
        self.ensure_one()
        self.env["repair.match.access"]._check_can_link(
            self,
            self.env["repair.order"],
            self._repair_match_moves_on_other_repairs(),
        )
        if self.state not in ("purchase", "done"):
            raise UserError(
                _(
                    "%s is not confirmed, so it can't be matched to a repair order.",
                    self.name,
                )
            )
        if not self._repair_match_has_parts():
            raise UserError(_("%s has no parts to add to a repair order.", self.name))
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Repair"),
            "res_model": "repair.order",
            "view_mode": "list",
            "views": [
                (
                    self.env.ref(
                        "repair_purchase_order_match."
                        "view_repair_order_list_choose_for_po"
                    ).id,
                    "list",
                )
            ],
            "target": "new",
            "domain": [
                ("state", "not in", ("done", "cancel")),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {"po_id": self.id, "repair_match_dialog": True},
        }

    def action_add_to_repair(self):
        """`repair_purchase_order_parts` header button, superseded by Match
        Repair: same dialog, which links the way the match flow does (a
        purchase order belongs to one repair order).
        """
        return self.action_match_repair()

    def action_select_for_repair(self):
        """`repair_purchase_order_parts` row click of its repair order ->
        purchase order picker (the repair order is `repair_id` in the context),
        which would add the parts without any of the match flow's checks and
        notes: it links like Match Order does.
        """
        self.ensure_one()
        return self.action_add_selected_to_repair()

    def action_add_selected_to_repair(self):
        """`repair_purchase_order_parts` multi-select button of the same
        picker: links every selected purchase order to the repair order the
        way Match Order does (the rights and the validity of every one are
        checked before any is linked). The ones whose parts are all on the
        repair order already are left alone, and a UserError says so if that
        is every one of them, as the picker always did.
        """
        repair = self._get_repair_from_context()
        for order in self:
            order._repair_match_check_access(repair)
            order._repair_match_validate(repair)
        already_linked = repair.move_ids.created_purchase_line_ids.ids
        to_link = self.filtered(
            lambda order: order._prepare_repair_move_vals(repair, already_linked)
        )
        if not to_link:
            raise UserError(
                _(
                    "Every part on the selected purchase orders is already on "
                    "this repair order."
                )
            )
        for order in to_link:
            order._link_to_repair_order(repair)
        return {"type": "ir.actions.act_window_close"}

    # ----------------------------------------------------------
    # Matching (PO number)
    # ----------------------------------------------------------

    def _repair_match_by_reference(self):
        """The repair order whose number this purchase order carries as its
        PO number (the Source Document, filled by the vendor's import
        template) - or an empty recordset when it names none, or more than
        one.

        Only the number counts, not the letters or separators around it:
        `RO00004`, `RO-4` and `WH/RO/00004` all name the repair order
        `WH/RO/00004`. That's the last run of digits in each, compared as
        integers. Two repair orders sharing a number (another warehouse's
        sequence) is ambiguous, so neither is linked.
        """
        self.ensure_one()
        number = self._repair_number_of(self.origin)
        if number is None:
            return self.env["repair.order"]
        # Every repair order number contains its own number's digits, so
        # this narrows the search; the exact comparison is done below.
        repairs = (
            self.env["repair.order"]
            .search(
                [
                    ("name", "ilike", str(number)),
                    ("company_id", "=", self.company_id.id),
                ]
            )
            .filtered(lambda repair: self._repair_number_of(repair.name) == number)
        )
        return repairs if len(repairs) == 1 else self.env["repair.order"]

    @api.model
    def _repair_number_of(self, reference):
        """The number a repair order reference ends in, as an int: the
        last run of digits in it (`WH/RO/00004` -> 4), or None if it has
        none.
        """
        digits = re.findall(r"\d+", reference or "")
        return int(digits[-1]) if digits else None

    # ----------------------------------------------------------
    # Matching (TypeSafe)
    # ----------------------------------------------------------

    def _repair_auto_link_or_suggest(self):
        """Link this purchase order to the repair order its own PO number
        names, if it names one (the shop sends its repair order number to
        vendors as the PO number). Otherwise ask TypeSafe which open repair
        order it most likely belongs to, and post a confirm-to-link
        suggestion on both records' chatter - that guess is never linked
        without a click on the chatter button (see
        `_link_to_repair_order`, called from the controller it posts to).
        """
        self.ensure_one()
        if self._repair_match_linked_repairs():
            # somebody matched it in the meantime: nothing left to do or say
            return
        referenced = self._repair_match_by_reference()
        if referenced:
            if referenced.state in ("done", "cancel"):
                self._post_closed_repair_reference(referenced)
            else:
                self._link_to_repair_order(referenced, automatic=True)
            return
        match = self._repair_match_via_typesafe()
        if match:
            repair, confidence = match
            self._post_repair_match_suggestion(repair, confidence)
        else:
            self._edi_post_notice(
                _(
                    "TypeSafe could not suggest a repair order for this "
                    "purchase order. Please check the configuration and "
                    "make sure there are open repair orders with vehicles "
                    "and customer concerns."
                ),
                email=True,
                outstanding=True,
            )

    def _repair_match_via_typesafe(self):
        """Return (repair.order, confidence 0-1) for TypeSafe's best guess
        at which open repair order this purchase order belongs to, or
        `None` when matching can't run (no API key configured, or no
        candidate repair orders) or the request fails.
        """
        self.ensure_one()
        api_key = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("repair_purchase_order_match.typesafe_api_key")
        )
        if not api_key:
            return None
        candidates = self._repair_match_candidate_repairs()
        if not candidates:
            return None

        criteria = {
            str(repair.id): repair._typesafe_match_criteria() for repair in candidates
        }
        try:
            with TypeSafeClient(api_key=api_key) as client:
                response = client.system_one(
                    state=self._typesafe_match_state(),
                    questions={
                        "matching_ro": Choice(
                            instructions=(
                                "Which repair order does this purchase "
                                "order's parts most likely belong to?"
                            ),
                            criteria=criteria,
                        )
                    },
                )
        except TypeSafeError:
            _logger.exception(
                "TypeSafe repair-order matching failed for purchase order %s",
                self.name,
            )
            return None

        answer = response.choices.get("matching_ro")
        if not answer:
            return None
        repair = self.env["repair.order"].browse(int(answer.choice))
        if not repair.exists():
            return None
        return repair, answer.confidence

    def _repair_match_candidate_repairs(self, limit=CANDIDATE_LIMIT):
        """Open repair orders with enough vehicle/customer-concern context
        to be worth offering TypeSafe as a candidate, most recently
        scheduled first, capped at `limit` to keep the request bounded.
        """
        self.ensure_one()
        return self.env["repair.order"].search(
            [
                ("state", "not in", ("done", "cancel")),
                ("company_id", "=", self.company_id.id),
                ("vehicle_id", "!=", False),
            ],
            order="schedule_date desc",
            limit=limit,
        )

    def _typesafe_match_state(self):
        """This purchase order, described for TypeSafe: vendor, order
        date, and its lines (part number, description, price, quantity).
        """
        self.ensure_one()
        lines = [
            {
                "Part Number": line.product_id.default_code or line.product_id.name,
                "Description": line.name,
                "Price": line.price_unit,
                "Quantity": line.product_qty,
            }
            for line in self.order_line
            if not line.display_type and line.product_id
        ]
        return {
            "vendor": self.partner_id.name,
            "Order Date": typesafe_format_datetime(self.date_order),
            "lines": lines,
        }

    # ----------------------------------------------------------
    # Linking / suggestion
    # ----------------------------------------------------------

    def _link_to_repair_order(self, repair, automatic=False):
        """Link every line of this purchase order to `repair`'s parts,
        the same way the "Match Repair" button does it by hand.

        A manual link needs the access rights described in
        `repair.match.access` and raises an AccessError without them. An
        `automatic` link is the system's: it runs with sudo (the user the
        job runs as, typically the mail gateway's, may have no right on
        repair orders) and never needs the rights of that user.

        A purchase order belongs to one repair order, so choosing a
        different one moves the parts: whatever this purchase order had
        previously added to another open repair order is taken back off
        it first. `automatic` is for a link nobody clicked (the PO number
        named the repair order): it notifies the same users an
        EDI-imported PO does, since nobody confirmed it.
        """
        self.ensure_one()
        if automatic:
            if not self.env.su:
                # The system's doing, not the user's: see `_repair_auto_match_job`.
                return self.sudo()._link_to_repair_order(repair.sudo(), automatic=True)
        else:
            self._repair_match_check_access(repair)
            repair = repair.with_env(self.env)
        previous = self._repair_remove_parts_from_other_repairs(repair)
        already_linked = repair.move_ids.created_purchase_line_ids.ids
        move_vals = self._prepare_repair_move_vals(repair, already_linked)
        if move_vals:
            self.env["stock.move"].create(move_vals)

        choose_link = self._repair_match_choose_link()
        if automatic:
            po_intro = _(
                "This purchase order's PO number matches repair order %s, "
                "so it was linked automatically.",
                repair._get_html_link(),
            )
            repair_intro = _(
                "Purchase order %s uses this repair order's number as its "
                "PO number, so it was linked automatically.",
                self._get_html_link(),
            )
        else:
            po_intro = _("Linked to repair order %s.", repair._get_html_link())
            repair_intro = _("Linked to purchase order %s.", self._get_html_link())
        parts = _(
            "Every part on the purchase order was added to the repair order's parts "
            "list."
        )
        moved = Markup("")
        if previous:
            moved = Markup(" {}").format(
                _(
                    "The parts were taken off %s.",
                    Markup(", ").join(p._get_html_link() for p in previous),
                )
            )
        po_body = Markup("<p>{} {}{}</p>{}").format(po_intro, parts, moved, choose_link)
        repair_body = Markup("<p>{} {}</p>{}").format(repair_intro, parts, choose_link)

        if automatic:
            # Nobody confirmed this one: tell the notify group, in their
            # inbox only. Informational, so never outstanding, and no email.
            self._edi_post_notice(po_body, email=False, outstanding=False)
            self._repair_match_post_on_repair(
                repair, repair_body, author_id=self.env.ref("base.partner_root").id
            )
        else:
            # The user who linked it knows: a plain internal note.
            self.message_post(body=po_body)
            self._repair_match_post_on_repair(repair, repair_body)
        # Matched, by whatever route: whoever was asked to match it has
        # nothing left to do.
        self._edi_clear_notices()

    def _repair_match_post_on_repair(self, repair, body, purchase_order=None, **kwargs):
        """Post `body` on the repair order's chatter as an *internal note*
        (``mail.mt_note``) - never a discussion message: the customer
        follows the repair order, and a note is never sent to followers who
        are not internal users. Nobody is notified explicitly either.

        With `purchase_order`, the note is a suggestion for that purchase
        order: it is tied to it (``repair_match_purchase_order_id``) and
        flagged outstanding so that matching the purchase order clears the
        inbox notifications it may have caused (e.g. an employee following
        the repair order with notes).
        """
        message = repair.message_post(body=body, subtype_xmlid="mail.mt_note", **kwargs)
        if purchase_order:
            # sudo: a technical marker, not a field users write
            message.sudo().write(
                {
                    "repair_match_purchase_order_id": purchase_order.id,
                    "edi_notice_outstanding": True,
                }
            )
        return message

    def _repair_remove_parts_from_other_repairs(self, repair):
        """Take back the parts this purchase order added to any open repair
        order other than `repair`, and return those repair orders. Parts
        already consumed (done) stay where they are - stock has moved.
        """
        self.ensure_one()
        moves = self._repair_match_moves_on_other_repairs(repair)
        repairs = moves.repair_id
        moves._action_cancel()
        moves.unlink()
        return repairs

    def _repair_match_choose_link(self):
        """A "choose a different repair order" paragraph linking to the
        list of repair orders, where a click on a row links this purchase
        order to that one (RepairOrder.action_link_purchase_order).
        """
        self.ensure_one()
        return Markup('<p><a href="/odoo/{}/action-{}">{}</a></p>').format(
            self.id,
            "repair_purchase_order_match.action_repair_order_choose_for_po",
            _("Not the right repair order? Choose a different one."),
        )

    def _post_closed_repair_reference(self, repair):
        """The PO number names a repair order that's already closed, which
        can't take more parts - say so, with the way to pick another.
        """
        self.ensure_one()
        self._edi_post_notice(
            Markup("<p>{}</p>{}").format(
                _(
                    "This purchase order's PO number matches repair order "
                    "%(repair)s, but that repair order is %(state)s, so its "
                    "parts were not added.",
                    repair=repair._get_html_link(),
                    state=dict(
                        repair._fields["state"]._description_selection(self.env)
                    )[repair.state].lower(),
                ),
                self._repair_match_choose_link(),
            ),
            email=True,
            outstanding=True,
        )

    def _repair_match_confirm_token(self, repair):
        self.ensure_one()
        return tools.hmac(self.env(su=True), CONFIRM_TOKEN_SCOPE, (self.id, repair.id))

    def _repair_match_confirm_token_valid(self, repair, token):
        self.ensure_one()
        # encoded: consteq() refuses a non-ASCII str, and so would a bad link
        return tools.consteq(
            str(token).encode(), self._repair_match_confirm_token(repair).encode()
        )

    def _repair_match_email_link(self):
        """A "View original email" paragraph linking to the EDI exchange
        record this purchase order was imported from (its stored email
        body), or empty markup for a purchase order that wasn't imported
        by email/EDI.
        """
        self.ensure_one()
        exchange_record = self.exchange_record_ids[:1]
        if not exchange_record:
            return Markup("")
        return Markup("<p>{}</p>").format(
            exchange_record._get_html_link(title=_("View original email"))
        )

    def _post_repair_match_suggestion(self, repair, confidence):
        """Post TypeSafe's suggested match, with a Confirm Match button, on
        both this purchase order's and the repair order's chatter.

        On the purchase order it is an outstanding notice
        (`_edi_post_notice`): the notify group gets it in their inbox and
        the shop mailbox that forwarded the vendor's email gets the one
        email, until the order is matched and the notice is cleared. On the
        repair order it is an internal note that emails nobody.
        """
        self.ensure_one()
        token = self._repair_match_confirm_token(repair)
        confirm_url = (
            "/repair_purchase_order_match/confirm"
            f"?purchase_order_id={self.id}&repair_order_id={repair.id}&token={token}"
        )
        confidence_pct = round(confidence * 100)
        button = Markup(
            '<div><a href="{}" class="btn btn-primary">{}</a></div>'
        ).format(confirm_url, _("Confirm Match"))
        # The purchase order's own chatter never links to itself; the
        # repair order's chatter links to the purchase order instead.
        po_message = _(
            "TypeSafe suggests this purchase order belongs to repair "
            "order %(repair)s (%(confidence)d%% confidence).",
            repair=repair._get_html_link(),
            confidence=confidence_pct,
        )
        repair_message = _(
            "TypeSafe suggests purchase order %(purchase_order)s belongs "
            "to this repair order (%(confidence)d%% confidence).",
            purchase_order=self._get_html_link(),
            confidence=confidence_pct,
        )
        email_link = self._repair_match_email_link()
        po_body = Markup("<p>") + po_message + Markup("</p>") + email_link + button
        repair_body = (
            Markup("<p>") + repair_message + Markup("</p>") + email_link + button
        )
        self._edi_post_notice(po_body, email=True, outstanding=True)
        self._repair_match_post_on_repair(
            repair,
            repair_body,
            purchase_order=self,
            author_id=self.env.ref("base.partner_root").id,
        )
