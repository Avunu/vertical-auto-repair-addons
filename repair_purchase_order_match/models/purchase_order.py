# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging
import re

from markupsafe import Markup
from typesafe_sdk import Choice, TypeSafeClient, TypeSafeError

from odoo import _, api, models, tools

from .typesafe_utils import typesafe_format_datetime

_logger = logging.getLogger(__name__)

CANDIDATE_LIMIT = 25
CONFIRM_TOKEN_SCOPE = "repair_purchase_order_match-confirm"


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # ----------------------------------------------------------
    # EDI hook
    # ----------------------------------------------------------

    def _edi_confirm_and_notify(self):
        """After an EDI/email-imported purchase order is confirmed, ask
        TypeSafe which open repair order it most likely belongs to, in the
        background so a slow request never delays the import itself.
        """
        super()._edi_confirm_and_notify()
        self.with_delay(
            description=_("Match %s to an open repair order", self.name)
        )._repair_auto_link_or_suggest()

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
        repairs = self.env["repair.order"].search(
            [
                ("name", "ilike", str(number)),
                ("company_id", "=", self.company_id.id),
            ]
        ).filtered(lambda repair: self._repair_number_of(repair.name) == number)
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
            self.message_post(
                body=_(
                    "TypeSafe could not suggest a repair order for this "
                    "purchase order. Please check the configuration and "
                    "make sure there are open repair orders with vehicles "
                    "and customer concerns."
                ),
                subtype_xmlid="mail.mt_comment",
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
        the same way the "Add to Repair" button does it by hand.

        A purchase order belongs to one repair order, so choosing a
        different one moves the parts: whatever this purchase order had
        previously added to another open repair order is taken back off
        it first. `automatic` is for a link nobody clicked (the PO number
        named the repair order): it notifies the same users an
        EDI-imported PO does, since nobody confirmed it.
        """
        self.ensure_one()
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
        parts = _("Every part on the purchase order was added to the repair order's parts list.")
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
            self.message_post(
                body=po_body,
                partner_ids=self._edi_notify_partners().ids,
                subtype_xmlid="mail.mt_comment",
                author_id=self.env.ref("base.partner_root").id,
                notify_author=True,
            )
            repair.message_post(
                body=repair_body,
                subtype_xmlid="mail.mt_comment",
                author_id=self.env.ref("base.partner_root").id,
            )
        else:
            self.message_post(body=po_body)
            repair.message_post(body=repair_body)

    def _repair_remove_parts_from_other_repairs(self, repair):
        """Take back the parts this purchase order added to any open repair
        order other than `repair`, and return those repair orders. Parts
        already consumed (done) stay where they are - stock has moved.
        """
        self.ensure_one()
        moves = self.env["stock.move"].search(
            [
                ("created_purchase_line_ids", "in", self.order_line.ids),
                ("repair_id", "!=", False),
                ("repair_id", "!=", repair.id),
                ("repair_id.state", "not in", ("done", "cancel")),
                ("state", "not in", ("done", "cancel")),
            ]
        )
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
        self.message_post(
            body=Markup("<p>{}</p>{}").format(
                _(
                    "This purchase order's PO number matches repair order "
                    "%(repair)s, but that repair order is %(state)s, so its "
                    "parts were not added.",
                    repair=repair._get_html_link(),
                    state=dict(repair._fields["state"]._description_selection(self.env))[
                        repair.state
                    ].lower(),
                ),
                self._repair_match_choose_link(),
            ),
            partner_ids=self._edi_notify_partners().ids,
            subtype_xmlid="mail.mt_comment",
            author_id=self.env.ref("base.partner_root").id,
            notify_author=True,
        )

    def _repair_match_confirm_token(self, repair):
        self.ensure_one()
        return tools.hmac(
            self.env(su=True), CONFIRM_TOKEN_SCOPE, (self.id, repair.id)
        )

    def _repair_match_confirm_token_valid(self, repair, token):
        self.ensure_one()
        return tools.consteq(token, self._repair_match_confirm_token(repair))

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
        both this purchase order's and the repair order's chatter, and
        notify the same users an EDI-imported PO already notifies.
        """
        self.ensure_one()
        token = self._repair_match_confirm_token(repair)
        confirm_url = (
            "/repair_purchase_order_match/confirm"
            f"?purchase_order_id={self.id}&repair_order_id={repair.id}&token={token}"
        )
        confidence_pct = round(confidence * 100)
        button = Markup('<div><a href="{}" class="btn btn-primary">{}</a></div>').format(
            confirm_url, _("Confirm Match")
        )
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
        repair_body = Markup("<p>") + repair_message + Markup("</p>") + email_link + button
        partner_root = self.env.ref("base.partner_root")
        partners = self._edi_notify_partners()
        self.message_post(
            body=po_body,
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_comment",
            author_id=partner_root.id,
            notify_author=True,
        )
        repair.message_post(
            body=repair_body,
            subtype_xmlid="mail.mt_comment",
            author_id=partner_root.id,
        )
