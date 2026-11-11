# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest import mock
from unittest.mock import MagicMock, patch

from werkzeug.exceptions import BadRequest
from werkzeug.utils import redirect

from odoo.tests import TransactionCase, tagged

from odoo.addons.repair_purchase_order_match.controllers.main import (
    RepairPurchaseOrderMatchController,
)
from odoo.addons.repair_purchase_order_match.models import purchase_order as po_module

ALIAS_NAME = "match-orders"
ALIAS_DOMAIN = "match-notice-test.example"
ALIAS_EMAIL = f"{ALIAS_NAME}@{ALIAS_DOMAIN}"
SHOP_EMAIL = "orders@shop.example"
VENDOR_EMAIL = "sales@vendor.example"
CUSTOMER_EMAIL = "customer@repair.example"
SUBJECT = "Order confirmation ORD-M1"

RAW_EMAIL = """\
Delivered-To: {alias}
Message-Id: <inbound-match-{n}@vendor.example>
Subject: {subject}
From: Vendor Sales <{vendor_email}>
To: {shop_email}
X-Forwarded-For: {shop_email} {alias}
X-Forwarded-To: {alias}
Date: Mon, 09 Nov 2026 10:00:00 +0000
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Order #: ORD-M{n}
Vendor: MATCH NOTICE TEST VENDOR
PO Number: {po_number}
"""


@tagged("post_install", "-at_install")
class TestMatchNotices(TransactionCase):
    """The notices of `repair_purchase_order_match` end to end: a vendor's
    email forwarded into an exchange record by a mail alias (through the real
    mail gateway) confirms a purchase order; the suggestion is an outstanding
    notice for the notify group and one email to the shop mailbox; matching
    the order by any route clears them; the repair order only gets internal
    notes, so its customer follower is never emailed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # leave the emails queued ("outgoing") instead of sending them
        cls.env = cls.env(context=dict(cls.env.context, mail_notify_force_send=False))
        ref = cls.env.ref
        cls.unit = ref("uom.product_uom_unit")
        cls.vendor = cls.env["res.partner"].create(
            {"name": "MATCH NOTICE TEST VENDOR", "email": VENDOR_EMAIL}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Match Notice Customer", "email": CUSTOMER_EMAIL}
        )
        cls.item = cls.env["product.product"].create(
            {"name": "Notice Widget", "type": "consu", "is_storable": True}
        )
        cls.part = cls.env["product.product"].create(
            {"name": "Notice Part", "type": "consu", "is_storable": True}
        )
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Notice"})
        cls.vehicle_model = cls.env["fleet.vehicle.model"].create(
            {"name": "Notice Model", "brand_id": brand.id}
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "repair_purchase_order_match.typesafe_api_key", "test-key"
        )
        internal = ref("base.group_user")
        # two people of the notify group: one prefers email, to show it makes
        # no difference; a mechanic who follows repair orders' notes
        cls.group = cls.env["res.groups"].create({"name": "Match notice notify"})
        cls.manager = cls._user(
            "manager", internal | cls.group, notification_type="email"
        )
        cls.manager2 = cls._user("manager2", internal | cls.group)
        # prefers the inbox: a note they follow must never be emailed to them
        cls.mechanic = cls._user("mechanic", internal, notification_type="inbox")
        cls.matcher = cls._user(
            "matcher",
            internal
            | ref("purchase.group_purchase_user")
            | ref("stock.group_stock_user"),
        )
        cls.gateway = cls._user(
            "gateway", internal | ref("purchase.group_purchase_user")
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "edi_purchase_order_import.notify_group_id", cls.group.id
        )
        # the shop mailboxes the emailed notices may go to
        cls.env["ir.config_parameter"].sudo().set_param(
            "edi_purchase_order_import.reply_allowed", "@shop.example"
        )
        cls._setup_mail_alias()

    @classmethod
    def _user(cls, login, groups, **vals):
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": f"Match Notice {login}",
                    "login": f"match_notice_{login}",
                    "email": f"{login}@example.com",
                    "groups_id": [(6, 0, groups.ids)],
                    **vals,
                }
            )
        )

    @classmethod
    def _setup_mail_alias(cls):
        ref = cls.env.ref
        template = cls.env["base.import.pdf.template"].create(
            {
                "name": "Match notice test template",
                "extraction_mode": "plaintext",
                "model_id": ref("purchase.model_purchase_order").id,
                "auto_detect_pattern": "Order #:",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "related_model": "header",
                            "field_id": ref(
                                "purchase.field_purchase_order__partner_id"
                            ).id,
                            "pattern": "Vendor: (.*)",
                            "search_field_id": ref("base.field_res_partner__name").id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "sequence": 11,
                            "related_model": "header",
                            "field_id": ref(
                                "purchase.field_purchase_order__partner_ref"
                            ).id,
                            "pattern": "Order #: (.*)",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            # the PO number the shop sent to the vendor
                            "sequence": 12,
                            "related_model": "header",
                            "field_id": ref("purchase.field_purchase_order__origin").id,
                            "pattern": "PO Number: (.*)",
                        },
                    ),
                ],
            }
        )
        backend_type = cls.env["edi.backend.type"].create(
            {"name": "Match notice test type", "code": "match_notice_test_type"}
        )
        backend = cls.env["edi.backend"].create(
            {"name": "Match notice test backend", "backend_type_id": backend_type.id}
        )
        exchange_type = cls.env["edi.exchange.type"].create(
            {
                "name": "Match notice test PO",
                "code": "match_notice_test_po",
                "direction": "input",
                "backend_type_id": backend_type.id,
                "backend_id": backend.id,
                "process_model_id": cls.env["ir.model"]
                ._get("edi.input.process.template")
                .id,
                "import_template_id": template.id,
                "quick_exec": True,
            }
        )
        domain = cls.env["mail.alias.domain"].create({"name": ALIAS_DOMAIN})
        cls.env["mail.alias"].create(
            {
                "alias_name": ALIAS_NAME,
                "alias_domain_id": domain.id,
                "alias_model_id": cls.env["ir.model"]._get("edi.exchange.record").id,
                "alias_contact": "everyone",
                "alias_defaults": repr(
                    {"backend_id": backend.id, "type_code": exchange_type.code}
                ),
            }
        )

    # -- helpers -----------------------------------------------------------

    def _repair(self, follow=True):
        """An open repair order whose customer follows it, to every kind of
        message, as customers do; and a mechanic following its notes."""
        repair = self.env["repair.order"].create(
            {
                "product_id": self.item.id,
                "product_uom": self.unit.id,
                "partner_id": self.customer.id,
                "vehicle_id": self.env["fleet.vehicle"]
                .create({"model_id": self.vehicle_model.id, "model_year": "2005"})
                .id,
                "customer_concern": "Rear brakes need to be replaced",
            }
        )
        if follow:
            subtypes = self.env["mail.message.subtype"].search(
                [("res_model", "in", (False, "repair.order"))]
            )
            repair.message_subscribe(
                partner_ids=self.customer.ids, subtype_ids=subtypes.ids
            )
            repair.message_subscribe(
                partner_ids=self.mechanic.partner_id.ids,
                subtype_ids=self.env.ref("mail.mt_note").ids,
            )
        return repair

    def _receive(self, n, po_number="NOT A REPAIR"):
        """Feed an inbound email through the mail gateway (inline queue
        jobs); return the purchase order it created, with one part line."""
        before = self.env["edi.exchange.record"].search([]).ids
        raw = RAW_EMAIL.format(
            alias=ALIAS_EMAIL,
            n=n,
            subject=SUBJECT,
            vendor_email=VENDOR_EMAIL,
            shop_email=SHOP_EMAIL,
            po_number=po_number,
        )
        # the queue job is run by the tests themselves, when they want it
        with (
            mock.patch.object(
                self.env.registry["purchase.order"],
                "with_delay",
                lambda order, **kwargs: order,
            ),
            mock.patch.object(
                self.env.registry["purchase.order"],
                "_repair_auto_match_job",
                lambda order: None,
            ),
        ):
            self.env["mail.thread"].message_process(None, raw)
        exchange = self.env["edi.exchange.record"].search([("id", "not in", before)])
        self.assertEqual(len(exchange), 1)
        self.assertEqual(
            exchange.edi_exchange_state,
            "input_processed",
            exchange.exchange_error_traceback or exchange.exchange_error,
        )
        po = exchange.record
        self.assertEqual(po.state, "purchase")
        po.write(
            {
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.part.id,
                            "name": self.part.name,
                            "product_qty": 2.0,
                            "product_uom": self.unit.id,
                            "price_unit": 10.0,
                        },
                    )
                ]
            }
        )
        return po

    def _patch_typesafe(self, repair):
        answer = MagicMock()
        answer.choice = str(repair.id)
        answer.confidence = 0.9
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.system_one.return_value.choices = {"matching_ro": answer}
        return patch.object(po_module, "TypeSafeClient", return_value=client)

    def _suggested(self, n, repair=None):
        """An imported order with TypeSafe's suggestion for `repair`
        posted (by the queue job)."""
        repair = repair or self._repair()
        po = self._receive(n)
        with self._patch_typesafe(repair):
            po._repair_auto_match_job()
        return po, repair

    def _notices(self, record, outstanding=None):
        notices = record.message_ids.filtered(
            lambda m: (
                m.subtype_id == self.env.ref("edi_purchase_order_import.mt_edi_notice")
            )
        )
        if outstanding is not None:
            notices = notices.filtered(
                lambda m: m.edi_notice_outstanding == outstanding
            )
        return notices.sorted("id")

    def _unread(self, user):
        return self.env["mail.notification"].search(
            [
                ("res_partner_id", "=", user.partner_id.id),
                ("notification_type", "=", "inbox"),
                ("is_read", "=", False),
            ]
        )

    def _unread_for(self, user, messages):
        return self._unread(user).filtered(lambda n: n.mail_message_id in messages)

    def _mails_of(self, messages):
        return self.env["mail.mail"].search([("mail_message_id", "in", messages.ids)])

    def _parts(self, repair):
        return repair.move_ids.filtered(lambda m: m.repair_line_type == "add")

    def _confirm(self, po, repair, user=None):
        user = user or self.matcher
        request = MagicMock()
        request.env = self.env["res.users"].with_user(user).env
        request.redirect = redirect
        with patch(
            "odoo.addons.repair_purchase_order_match.controllers.main.request",
            request,
        ):
            return RepairPurchaseOrderMatchController().confirm_match(
                str(po.id), str(repair.id), po._repair_match_confirm_token(repair)
            )

    def _everything_sent(self, since_mail_id):
        return self.env["mail.mail"].search([("id", ">", since_mail_id)])

    # -- the suggestion ------------------------------------------------------

    def test_suggestion_is_an_outstanding_notice_with_one_email_to_the_shop(self):
        po, repair = self._suggested(1)

        confirmation, suggestion = self._notices(po, outstanding=True)
        self.assertIn("confirmed automatically", confirmation.body)
        self.assertIn("/repair_purchase_order_match/confirm", suggestion.body)
        self.assertTrue(suggestion.subtype_id.internal)
        # both group members have it unread in the inbox, whatever their
        # preference; the mechanic (not in the group) has not
        for user in (self.manager, self.manager2):
            self.assertEqual(
                self._unread_for(user, suggestion).notification_type, "inbox"
            )
            self.assertEqual(len(self._unread_for(user, confirmation)), 1)
        self.assertFalse(self._unread_for(self.mechanic, suggestion))
        # exactly one email for the suggestion, to the shop mailbox
        mails = self._mails_of(suggestion)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_to, SHOP_EMAIL)
        self.assertFalse(mails.recipient_ids)
        self.assertEqual(mails.subject, "Re: " + SUBJECT)
        # the button is a link to the (login-protected) controller
        self.assertIn("/repair_purchase_order_match/confirm", mails.body_html)
        # nobody else got an email: not the vendor, the customer, the group
        for address in (VENDOR_EMAIL, CUSTOMER_EMAIL):
            self.assertFalse(
                self.env["mail.mail"]
                .search([])
                .filtered(lambda m, a=address: a in (m.email_to or ""))
            )
        for partner in (
            self.vendor,
            self.customer,
            self.manager.partner_id,
            self.manager2.partner_id,
        ):
            self.assertFalse(
                self.env["mail.mail"].search([("recipient_ids", "in", partner.ids)])
            )
        # nothing is linked until somebody confirms
        self.assertFalse(self._parts(repair))

    def test_repair_side_suggestion_is_an_internal_note_that_emails_nobody(self):
        po, repair = self._suggested(2)
        note = repair.message_ids.sorted("id")[-1]
        self.assertIn("/repair_purchase_order_match/confirm", note.body)
        self.assertEqual(note.subtype_id, self.env.ref("mail.mt_note"))
        self.assertEqual(note.repair_match_purchase_order_id, po)
        self.assertTrue(note.edi_notice_outstanding)
        # the customer follows the repair order to every subtype, yet gets
        # neither an email nor a notification
        self.assertIn(self.customer, repair.message_partner_ids)
        self.assertFalse(
            self.env["mail.notification"].search(
                [
                    ("mail_message_id", "=", note.id),
                    ("res_partner_id", "=", self.customer.id),
                ]
            )
        )
        self.assertFalse(self._mails_of(note))
        # a mechanic who follows the notes sees it in the inbox (not email)
        self.assertEqual(len(self._unread_for(self.mechanic, note)), 1)

    def test_the_old_discussion_subtype_would_have_reached_the_customer(self):
        """Guard against regressing to mail.mt_comment on the repair order:
        a discussion message reaches the customer follower, which is why
        the notes are internal."""
        repair = self._repair()
        repair.message_post(body="x", subtype_xmlid="mail.mt_comment")
        self.assertTrue(
            self.env["mail.mail"].search([("recipient_ids", "in", self.customer.ids)])
        )

    def test_could_not_suggest_and_closed_repair_notices_are_outstanding_emails(self):
        po = self._receive(3)
        with self._patch_typesafe(self._repair()) as patcher:
            patcher.return_value.system_one.return_value.choices = {}
            po._repair_auto_match_job()
        failed = self._notices(po, outstanding=True)[-1]
        self.assertIn("could not suggest", failed.body)
        self.assertEqual(self._mails_of(failed).email_to, SHOP_EMAIL)
        self.assertEqual(len(self._unread_for(self.manager, failed)), 1)

        closed = self._repair()
        closed.action_repair_cancel()
        po2 = self._receive(4, po_number=closed.name)
        po2._repair_auto_match_job()
        notice = self._notices(po2, outstanding=True)[-1]
        self.assertIn("parts were not added", notice.body)
        self.assertEqual(self._mails_of(notice).email_to, SHOP_EMAIL)
        self.assertEqual(len(self._unread_for(self.manager2, notice)), 1)

    # -- clearing, by every route ------------------------------------------

    def _assert_cleared(self, po, repairs, since_mail_id):
        messages = self._notices(po, outstanding=True)
        self.assertTrue(messages)
        for user in (self.manager, self.manager2):
            self.assertFalse(self._unread_for(user, messages), user.login)
        repair_notes = self.env["mail.message"].search(
            [("repair_match_purchase_order_id", "=", po.id)]
        )
        for note in repair_notes:
            self.assertFalse(self._unread_for(self.mechanic, note))
        # quietly: the notices stay in the chatter, nothing new was emailed
        # to anybody outside, and nobody got an email
        self.assertTrue(set(messages) <= set(po.message_ids))
        self.assertEqual(self._everything_sent(since_mail_id).mapped("email_to"), [])

    def _route_dialog(self, po, repair):
        repair.with_context(po_id=po.id).action_link_purchase_order()

    def _route_match_repair_dialog(self, po, repair):
        repair.with_context(
            po_id=po.id, repair_match_dialog=True
        ).action_link_purchase_order()

    def _route_match_order_card(self, po, repair):
        po.with_context(repair_id=repair.id).action_match_to_repair()

    def _route_confirm_link(self, po, repair):
        result = self._confirm(po, repair)
        self.assertEqual(result.status_code, 302)

    def _route_mcp(self, po, repair):
        self.env["muk_mcp.mixin"]._mcp_link_purchase_order_to_repair(
            purchase_order_id=po.id, repair_order_id=repair.id
        )

    def _route_automatic(self, po, repair):
        po._link_to_repair_order(repair, automatic=True)

    def _route_queue_job(self, po, repair):
        po.origin = repair.name
        po._repair_auto_match_job()

    def test_every_way_of_matching_clears_the_outstanding_notices(self):
        routes = [
            "_route_dialog",
            "_route_match_repair_dialog",
            "_route_match_order_card",
            "_route_confirm_link",
            "_route_mcp",
            "_route_automatic",
            "_route_queue_job",
        ]
        for n, route in enumerate(routes, start=10):
            with self.subTest(route=route):
                po, repair = self._suggested(n)
                self.assertTrue(self._unread_for(self.manager, po.message_ids))
                last_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
                getattr(self, route)(po, repair)
                self.assertEqual(
                    self._parts(repair).created_purchase_line_ids, po.order_line
                )
                self._assert_cleared(po, repair, last_mail.id)

    def test_suggestions_on_other_repair_orders_are_cleared_too(self):
        po, first = self._suggested(30)
        second = self._repair()
        po._post_repair_match_suggestion(second, 0.5)
        notes = self.env["mail.message"].search(
            [("repair_match_purchase_order_id", "=", po.id)]
        )
        self.assertEqual(len(notes), 2)
        self.assertEqual({n.res_id for n in notes}, {first.id, second.id})
        self.assertEqual(len(self._unread_for(self.mechanic, notes)), 2)
        # matched to a third repair order: both suggestions are cleared
        third = self._repair()
        po._link_to_repair_order(third)
        self.assertFalse(self._unread_for(self.mechanic, notes))

    def test_clearing_is_idempotent_and_leaves_unrelated_notices(self):
        po, repair = self._suggested(31)
        other, _other_repair = self._suggested(32)
        po._link_to_repair_order(repair)
        po._edi_clear_notices()
        self.assertFalse(self._unread_for(self.manager, po.message_ids))
        # another order's notices are untouched
        self.assertTrue(self._unread_for(self.manager, other.message_ids))

    # -- informational messages ----------------------------------------------

    def test_automatic_link_note_is_informational(self):
        po, repair = self._suggested(40)
        po._link_to_repair_order(repair, automatic=True)
        info = po.message_ids.sorted("id")[-1]
        self.assertIn("linked automatically", info.body)
        self.assertFalse(info.edi_notice_outstanding)
        self.assertTrue(info.subtype_id.internal)
        # the group hears about what the system did on its own, in the
        # inbox only; it is not cleared (it was never outstanding), no email
        self.assertEqual(len(self._unread_for(self.manager, info)), 1)
        self.assertFalse(self._mails_of(info))
        # on the repair order: a plain internal note
        repair_info = repair.message_ids.sorted("id")[-1]
        self.assertIn("linked automatically", repair_info.body)
        self.assertEqual(repair_info.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(repair_info.edi_notice_outstanding)
        self.assertFalse(self._mails_of(repair_info))
        self.assertFalse(
            self.env["mail.mail"].search([("recipient_ids", "in", self.customer.ids)])
        )

    def test_manual_link_notes_are_quiet_internal_notes(self):
        po, repair = self._suggested(41)
        before = self.env["mail.mail"].search([], order="id desc", limit=1).id
        po.with_user(self.matcher)._link_to_repair_order(repair)
        info = po.message_ids.sorted("id")[-1]
        self.assertIn("Linked to repair order", info.body)
        self.assertFalse(info.edi_notice_outstanding)
        self.assertFalse(self._unread_for(self.manager, info))
        repair_info = repair.message_ids.sorted("id")[-1]
        self.assertEqual(repair_info.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(self._everything_sent(before))

    # -- already matched ------------------------------------------------------

    def test_notice_for_an_already_matched_order_is_posted_read(self):
        po = self._receive(50)
        repair = self._repair()
        po._link_to_repair_order(repair)
        notice = po._edi_post_notice("Late notice", email=True, outstanding=True)
        self.assertFalse(notice.edi_notice_outstanding)
        for user in (self.manager, self.manager2):
            self.assertFalse(
                self.env["mail.notification"].search(
                    [
                        ("mail_message_id", "=", notice.id),
                        ("res_partner_id", "=", user.partner_id.id),
                    ]
                )
            )
        # the confirmation of an order that was matched on the way
        po._edi_confirm_and_notify()
        self.assertFalse(
            self._unread(self.manager).filtered(
                lambda n: (
                    n.mail_message_id.model == "purchase.order"
                    and n.mail_message_id.res_id == po.id
                    and "confirmed automatically" in n.mail_message_id.body
                )
            )
        )

    def test_matching_by_po_number_during_the_import_leaves_nothing_unread(self):
        """quick_exec: the order is confirmed, matched by the job and only
        then does the gateway post the inbound email and release the held
        back confirmation notice. It must not be left unread."""
        repair = self._repair()
        before = self.env["edi.exchange.record"].search([]).ids
        raw = RAW_EMAIL.format(
            alias=ALIAS_EMAIL,
            n=60,
            subject=SUBJECT,
            vendor_email=VENDOR_EMAIL,
            shop_email=SHOP_EMAIL,
            po_number=repair.name,
        )
        PurchaseOrder = self.env.registry["purchase.order"]
        po_lines = [
            (
                0,
                0,
                {
                    "product_id": self.part.id,
                    "name": self.part.name,
                    "product_qty": 1.0,
                    "product_uom": self.unit.id,
                    "price_unit": 5.0,
                },
            )
        ]
        original = PurchaseOrder._edi_confirm_and_notify

        def with_lines(order):
            order.order_line = po_lines
            return original(order)

        with (
            mock.patch.object(PurchaseOrder, "with_delay", lambda order, **kw: order),
            mock.patch.object(PurchaseOrder, "_edi_confirm_and_notify", with_lines),
        ):
            self.env["mail.thread"].message_process(None, raw)
        exchange = self.env["edi.exchange.record"].search([("id", "not in", before)])
        po = exchange.record
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)
        self.assertFalse(exchange.edi_pending_notices)
        confirmation = self._notices(po).filtered(
            lambda m: "confirmed automatically" in m.body
        )
        self.assertEqual(len(confirmation), 1)
        self.assertFalse(confirmation.edi_notice_outstanding)
        for user in (self.manager, self.manager2):
            self.assertFalse(self._unread_for(user, confirmation))
        # ... while the automatic link itself was announced, as information
        link = self._notices(po).filtered(lambda m: "linked automatically" in m.body)
        self.assertEqual(len(self._unread_for(self.manager, link)), 1)

    def test_suggestion_job_does_nothing_for_an_order_matched_meanwhile(self):
        po = self._receive(51)
        repair = self._repair()
        po._link_to_repair_order(repair)
        count = len(po.message_ids)
        with self._patch_typesafe(self._repair()):
            po._repair_auto_match_job()
        self.assertEqual(len(po.message_ids), count)

    # -- the stale Confirm Match button ----------------------------------------

    def test_stale_confirm_button_does_not_move_parts_of_a_matched_order(self):
        po, suggested = self._suggested(70)
        actual = self._repair()
        po._link_to_repair_order(actual)
        with self.assertRaises(BadRequest) as caught:
            self._confirm(po, suggested)
        self.assertIn(actual.name, str(caught.exception.description))
        self.assertIn("already matched", str(caught.exception.description))
        self.assertTrue(self._parts(actual))
        self.assertFalse(self._parts(suggested))

    def test_stale_confirm_button_for_the_same_repair_is_harmless(self):
        po, repair = self._suggested(71)
        po._link_to_repair_order(repair)
        count = len(po.message_ids) + len(repair.message_ids)
        result = self._confirm(po, repair)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(len(po.message_ids) + len(repair.message_ids), count)
        self.assertEqual(len(self._parts(repair)), 1)

    # -- access ----------------------------------------------------------------

    def test_a_gateway_user_without_repair_rights_still_gets_the_notices(self):
        """The queue job runs as the user of the import (the alias' or the
        gateway's): a purchase user without any right on repair orders. The
        suggestion still reaches the group and the shop, and the system
        clears it when the order is later matched by the job."""
        repair = self._repair()
        po = self._receive(80)
        with self._patch_typesafe(repair):
            po.with_user(self.gateway)._repair_auto_match_job()
        suggestion = self._notices(po, outstanding=True)[-1]
        self.assertIn("/repair_purchase_order_match/confirm", suggestion.body)
        self.assertEqual(self._mails_of(suggestion).email_to, SHOP_EMAIL)
        self.assertEqual(len(self._unread_for(self.manager, suggestion)), 1)
        # the same user matching by PO number
        po.origin = repair.name
        po.with_user(self.gateway)._repair_auto_match_job()
        self.assertTrue(self._parts(repair))
        self.assertFalse(self._unread_for(self.manager, suggestion))
