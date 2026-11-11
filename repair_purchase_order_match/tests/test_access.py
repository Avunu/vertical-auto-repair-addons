# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import MagicMock, patch

from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.utils import redirect

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.repair_purchase_order_match.controllers.main import (
    RepairPurchaseOrderMatchController,
)


@tagged("post_install", "-at_install")
class TestRepairMatchAccess(TransactionCase):
    """Who can use the Match Order / Match Repair buttons, checked with real
    low-privilege users: the group combinations, the multi-company rule, the
    quotation of the repair order and the parts taken off another repair
    order each decide it, and every entry point enforces it on the server.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.customer = cls.env["res.partner"].create({"name": "Access Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "Access Vendor"})
        cls.item = cls.env["product.product"].create(
            {"name": "Access Widget", "type": "consu", "is_storable": True}
        )
        cls.part = cls.env["product.product"].create(
            {"name": "Access Part", "type": "consu", "is_storable": True}
        )
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Other Shop"})

        group = cls.env.ref
        internal = group("base.group_user")
        purchase = group("purchase.group_purchase_user")
        stock = group("stock.group_stock_user")
        cls.purchase_only = cls._user("purchase_only", internal | purchase)
        cls.stock_only = cls._user("stock_only", internal | stock)
        cls.purchase_stock = cls._user("purchase_stock", internal | purchase | stock)
        cls.stock_manager = cls._user(
            "stock_manager",
            internal | purchase | group("stock.group_stock_manager"),
        )
        cls.salesman_stock = cls._user(
            "salesman_stock",
            internal | purchase | stock | group("sales_team.group_sale_salesman"),
        )
        cls.nobody = cls._user("nobody", internal)
        cls.other_company_stock = cls._user(
            "other_company_stock",
            internal | purchase | stock,
            company=cls.other_company,
        )

    @classmethod
    def _user(cls, login, groups, company=None):
        company = company or cls.company
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": login,
                    "login": f"access_{login}",
                    "email": f"{login}@example.com",
                    "company_id": company.id,
                    "company_ids": [(6, 0, company.ids)],
                    "groups_id": [(6, 0, groups.ids)],
                }
            )
        )

    def _u(self, record, user):
        """`record` as `user`, in the user's own company."""
        return record.with_user(user).with_context(
            allowed_company_ids=user.company_id.ids
        )

    def _repair(self, company=None):
        return (
            self.env["repair.order"]
            .with_company(company or self.company)
            .create(
                {
                    "product_id": self.item.id,
                    "product_uom": self.unit.id,
                    "partner_id": self.customer.id,
                    "company_id": (company or self.company).id,
                }
            )
        )

    def _po(self, company=None):
        po = (
            self.env["purchase.order"]
            .with_company(company or self.company)
            .create(
                {
                    "partner_id": self.vendor.id,
                    "company_id": (company or self.company).id,
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
                    ],
                }
            )
        )
        po.button_confirm()
        return po

    def _parts(self, repair):
        return repair.move_ids.filtered(lambda m: m.repair_line_type == "add")

    def _quote(self, repair, salesperson=None):
        """Give the repair order a quotation, as a confirmed repair has."""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "user_id": salesperson.id if salesperson else False,
            }
        )
        repair.sale_order_id = order
        return order

    # ----------------------------------------------------------
    # Visibility of the buttons
    # ----------------------------------------------------------

    def test_buttons_are_shown_to_a_purchase_and_inventory_user(self):
        """The group combination that can match: Purchase (edit the order,
        post on it) and Inventory (edit the repair order and its parts)."""
        repair, po = self._repair(), self._po()
        for user in (self.purchase_stock, self.stock_manager):
            with self.subTest(user=user.login):
                self.assertTrue(self._u(repair, user).repair_match_can_link)
                self.assertTrue(self._u(po, user).repair_match_can_link)

    def test_buttons_are_hidden_from_a_purchase_only_user(self):
        """A purchase user has no access to repair orders at all."""
        repair, po = self._repair(), self._po()
        self.assertFalse(self._u(po, self.purchase_only).repair_match_can_link)
        self.assertFalse(self._u(repair, self.purchase_only).repair_match_can_link)

    def test_buttons_are_hidden_from_an_inventory_only_user(self):
        """An inventory user reads purchase orders but can't post on them."""
        repair, po = self._repair(), self._po()
        self.assertFalse(self._u(po, self.stock_only).repair_match_can_link)
        self.assertFalse(self._u(repair, self.stock_only).repair_match_can_link)

    def test_buttons_are_hidden_from_an_internal_user_without_groups(self):
        repair, po = self._repair(), self._po()
        self.assertFalse(self._u(po, self.nobody).repair_match_can_link)
        self.assertFalse(self._u(repair, self.nobody).repair_match_can_link)

    def test_buttons_are_hidden_from_a_user_in_another_company(self):
        repair, po = self._repair(), self._po()
        user = self.other_company_stock
        self.assertFalse(self._u(po, user).repair_match_can_link)
        self.assertFalse(self._u(repair, user).repair_match_can_link)
        # ... and shown for the records of their own company.
        own_repair = self._repair(self.other_company)
        own_po = self._po(self.other_company)
        self.assertTrue(self._u(own_repair, user).repair_match_can_link)
        self.assertTrue(self._u(own_po, user).repair_match_can_link)

    def test_match_order_needs_quotation_rights_on_a_quoted_repair(self):
        """Core repair mirrors every added part on the quotation: that
        takes Sales: User, and for them the quotation to be their own (or
        nobody's)."""
        repair = self._repair()
        self._quote(repair)
        self.assertFalse(self._u(repair, self.purchase_stock).repair_match_can_link)
        self.assertTrue(self._u(repair, self.salesman_stock).repair_match_can_link)
        own = self._repair()
        self._quote(own, self.salesman_stock)
        self.assertTrue(self._u(own, self.salesman_stock).repair_match_can_link)
        foreign = self._repair()
        self._quote(foreign, self.purchase_only)
        self.assertFalse(self._u(foreign, self.salesman_stock).repair_match_can_link)

    def test_match_repair_is_hidden_when_it_would_take_parts_off_a_repair(self):
        """Taking parts off another repair order unlinks stock moves, which
        only an Inventory Administrator may do."""
        po = self._po()
        po._link_to_repair_order(self._repair())
        self.assertFalse(self._u(po, self.purchase_stock).repair_match_can_link)
        self.assertTrue(self._u(po, self.stock_manager).repair_match_can_link)

    def test_receipt_button_follows_its_purchase_order(self):
        po = self._po()
        picking = po.picking_ids
        self.assertTrue(self._u(picking, self.purchase_stock).repair_match_can_link)
        self.assertFalse(self._u(picking, self.stock_only).repair_match_can_link)
        po._link_to_repair_order(self._repair())
        self.env.invalidate_all()
        self.assertFalse(self._u(picking, self.purchase_stock).repair_match_can_link)
        self.assertTrue(self._u(picking, self.stock_manager).repair_match_can_link)
        self.assertFalse(self.env["stock.picking"].new().repair_match_can_link)

    # ----------------------------------------------------------
    # The actions enforce the same rights
    # ----------------------------------------------------------

    def test_match_order_dialog(self):
        repair = self._repair()
        action = self._u(repair, self.purchase_stock).action_match_order()
        self.assertEqual(action["res_model"], "purchase.order")
        for user in (
            self.purchase_only,
            self.stock_only,
            self.nobody,
            self.other_company_stock,
        ):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(repair, user).action_match_order()

    def test_match_repair_dialog(self):
        po = self._po()
        action = self._u(po, self.purchase_stock).action_match_repair()
        self.assertEqual(action["res_model"], "repair.order")
        for user in (
            self.purchase_only,
            self.stock_only,
            self.nobody,
            self.other_company_stock,
        ):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(po, user).action_match_repair()

    def test_match_repair_dialog_of_a_quoted_repair_order_needs_nothing_more(self):
        """The quotation matters when linking, not when opening the dialog."""
        self._quote(self._repair())
        po = self._po()
        action = self._u(po, self.purchase_stock).action_match_repair()
        self.assertEqual(action["res_model"], "repair.order")

    def test_card_button_links_with_the_rights_of_the_user(self):
        repair, po = self._repair(), self._po()
        self._u(po, self.purchase_stock).with_context(
            repair_id=repair.id
        ).action_match_to_repair()
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)
        self.assertIn(repair.name, po.message_ids.sorted("id")[-1].body)
        self.assertIn(po.name, repair.message_ids.sorted("id")[-1].body)

    def test_card_button_refuses_users_without_the_rights(self):
        repair = self._repair()
        for user in (
            self.purchase_only,
            self.stock_only,
            self.nobody,
            self.other_company_stock,
        ):
            po = self._po()
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(po, user).with_context(
                    repair_id=repair.id
                ).action_match_to_repair()
            self.assertFalse(self._parts(repair))
            self.assertTrue(po.repair_match_unmatched)

    def test_row_click_links_with_the_rights_of_the_user(self):
        repair, po = self._repair(), self._po()
        action = self._u(repair, self.purchase_stock).with_context(
            po_id=po.id, repair_match_dialog=True
        )
        action.action_link_purchase_order()
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)

    def test_row_click_refuses_users_without_the_rights(self):
        repair, po = self._repair(), self._po()
        for user in (self.purchase_only, self.nobody):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(repair, user).with_context(
                    po_id=po.id
                ).action_link_purchase_order()
        self.assertFalse(self._parts(repair))

    def test_row_click_refuses_a_repair_of_another_company(self):
        foreign = self._repair(self.other_company)
        po = self._po()
        with self.assertRaises(UserError) as caught:
            foreign.with_context(po_id=po.id).action_link_purchase_order()
        self.assertIn("different companies", str(caught.exception))

    def test_moving_parts_to_another_repair_needs_to_unlink_moves(self):
        first, second = self._repair(), self._repair()
        po = self._po()
        po._link_to_repair_order(first)
        action = self._u(po, self.purchase_stock).with_context(repair_id=second.id)
        with self.assertRaises(AccessError) as caught:
            action.action_match_to_repair()
        self.assertIn("take parts off another repair order", str(caught.exception))
        # Nothing moved.
        self.assertTrue(self._parts(first))
        self.assertFalse(self._parts(second))
        self._u(po, self.stock_manager).with_context(
            repair_id=second.id
        ).action_match_to_repair()
        self.assertFalse(self._parts(first))
        self.assertTrue(self._parts(second))

    def test_quoted_repair_needs_quotation_rights_to_link(self):
        repair, po = self._repair(), self._po()
        self._quote(repair)
        action = self._u(po, self.purchase_stock).with_context(repair_id=repair.id)
        with self.assertRaises(AccessError) as caught:
            action.action_match_to_repair()
        self.assertIn("quotation", str(caught.exception))
        self.assertFalse(self._parts(repair))
        self._u(po, self.salesman_stock).with_context(
            repair_id=repair.id
        ).action_match_to_repair()
        self.assertTrue(self._parts(repair))

    def test_a_purchase_user_can_not_link_even_without_the_button(self):
        """Calling the method directly is refused the same as clicking."""
        repair, po = self._repair(), self._po()
        with self.assertRaises(AccessError) as caught:
            self._u(po, self.purchase_only)._link_to_repair_order(repair)
        self.assertIn("repair orders", str(caught.exception))
        self.assertFalse(self._parts(repair))

    # ----------------------------------------------------------
    # System-initiated link (queue job)
    # ----------------------------------------------------------

    def test_automatic_link_works_for_a_gateway_user_without_repair_rights(self):
        """The import runs as the mail alias' user: a purchase user with no
        access to repair orders. The queue job still links by PO number,
        on behalf of the system, which a manual click of that user can not."""
        repair, po = self._repair(), self._po()
        po.origin = repair.name
        gateway_po = self._u(po, self.purchase_only)
        gateway_po._repair_auto_match_job()
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)
        self.assertIn("linked automatically", repair.message_ids.sorted("id")[-1].body)

    def test_automatic_link_directly_for_a_gateway_user(self):
        repair, po = self._repair(), self._po()
        self._u(po, self.purchase_only)._link_to_repair_order(repair, automatic=True)
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)

    def test_confirmed_import_queues_the_system_job(self):
        po = self._po()
        with patch.object(
            type(po), "with_delay", autospec=True, return_value=MagicMock()
        ) as with_delay:
            po._edi_confirm_and_notify()
        with_delay.return_value._repair_auto_match_job.assert_called_once_with()

    # ----------------------------------------------------------
    # Search filter
    # ----------------------------------------------------------

    def test_unmatched_filter_only_narrows_what_the_user_can_read(self):
        mine, foreign = self._po(), self._po(self.other_company)
        linked = self._po()
        linked._link_to_repair_order(self._repair())
        ids = (mine | foreign | linked).ids
        domain = [("id", "in", ids), ("repair_match_unmatched", "=", True)]
        PurchaseOrder = self.env["purchase.order"]
        self.assertEqual(
            self._u(PurchaseOrder, self.purchase_stock).search(domain), mine
        )
        self.assertEqual(
            self._u(PurchaseOrder, self.other_company_stock).search(domain),
            foreign,
        )
        with self.assertRaises(AccessError):
            self._u(PurchaseOrder, self.nobody).search(domain)

    # ----------------------------------------------------------
    # MCP tools
    # ----------------------------------------------------------

    def test_mcp_tools_use_the_rights_of_the_user(self):
        repair, po = self._repair(), self._po()
        mixin = self.env["muk_mcp.mixin"]
        for user in (self.purchase_only, self.nobody):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(mixin, user)._mcp_link_purchase_order_to_repair(
                    purchase_order_id=po.id, repair_order_id=repair.id
                )
        self.assertFalse(self._parts(repair))
        for user in (self.purchase_only, self.nobody):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(mixin, user)._mcp_find_repair_order_matches(
                    purchase_order_id=po.id
                )
        result = self._u(mixin, self.purchase_stock)._mcp_link_purchase_order_to_repair(
            purchase_order_id=po.id, repair_order_id=repair.id
        )
        self.assertTrue(result["linked"])
        self.assertTrue(self._parts(repair))

    def test_mcp_link_refuses_a_closed_repair_order(self):
        repair, po = self._repair(), self._po()
        repair.action_repair_cancel()
        with self.assertRaises(UserError) as caught:
            self._u(
                self.env["muk_mcp.mixin"], self.purchase_stock
            )._mcp_link_purchase_order_to_repair(
                purchase_order_id=po.id, repair_order_id=repair.id
            )
        self.assertIn("closed", str(caught.exception))

    # ----------------------------------------------------------
    # Confirm Match controller
    # ----------------------------------------------------------

    def _confirm(self, user, po, repair, token=None):
        """Call the controller as `user`, without an HTTP server."""
        request = MagicMock()
        request.env = self._u(self.env["res.users"], user).env
        request.redirect = redirect
        if token is None:
            token = po._repair_match_confirm_token(repair)
        with patch(
            "odoo.addons.repair_purchase_order_match.controllers.main.request",
            request,
        ):
            return RepairPurchaseOrderMatchController().confirm_match(
                str(po.id), str(repair.id), token
            )

    def test_confirm_match_links_for_a_user_with_the_rights(self):
        repair, po = self._repair(), self._po()
        result = self._confirm(self.purchase_stock, po, repair)
        self.assertEqual(result.status_code, 302)
        self.assertIn(f"id={po.id}", result.headers["Location"])
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)

    def test_confirm_match_is_a_403_without_the_rights(self):
        repair = self._repair()
        for user in (
            self.purchase_only,
            self.stock_only,
            self.nobody,
            self.other_company_stock,
        ):
            po = self._po()
            with self.subTest(user=user.login), self.assertRaises(Forbidden):
                self._confirm(user, po, repair)
            self.assertFalse(self._parts(repair))

    def test_confirm_match_checks_the_token(self):
        repair, po = self._repair(), self._po()
        with self.assertRaises(Forbidden):
            self._confirm(self.purchase_stock, po, repair, token="forged")
        # A token for another pair does not work either.
        other = self._repair()
        with self.assertRaises(Forbidden):
            self._confirm(
                self.purchase_stock,
                po,
                repair,
                token=po._repair_match_confirm_token(other),
            )
        self.assertFalse(self._parts(repair))

    def test_confirm_match_is_a_403_for_a_non_ascii_token(self):
        repair, po = self._repair(), self._po()
        with self.assertRaises(Forbidden):
            self._confirm(self.purchase_stock, po, repair, token="ééééé")
        self.assertFalse(self._parts(repair))

    def test_confirm_match_is_a_403_for_unknown_records(self):
        repair, po = self._repair(), self._po()
        request = MagicMock()
        request.env = self._u(self.env["res.users"], self.purchase_stock).env
        with patch(
            "odoo.addons.repair_purchase_order_match.controllers.main.request",
            request,
        ):
            with self.assertRaises(Forbidden):
                RepairPurchaseOrderMatchController().confirm_match(
                    "abc", str(repair.id), "x"
                )
            with self.assertRaises(Forbidden):
                RepairPurchaseOrderMatchController().confirm_match(
                    str(po.id), "999999999", "x"
                )

    def test_confirm_match_on_a_closed_repair_is_a_400_not_a_traceback(self):
        repair, po = self._repair(), self._po()
        token = po._repair_match_confirm_token(repair)
        repair.action_repair_cancel()
        with self.assertRaises(BadRequest):
            self._confirm(self.purchase_stock, po, repair, token=token)

    # ----------------------------------------------------------
    # One button per place, in the real combined views
    # ----------------------------------------------------------

    def _arch(self, model):
        return self.env[model].get_view(view_type="form")["arch"]

    def test_purchase_form_has_exactly_one_match_button(self):
        arch = self._arch("purchase.order")
        self.assertEqual(arch.count('name="action_match_repair"'), 1)
        self.assertNotIn("action_add_to_repair", arch)
        self.assertNotIn("Add to Repair", arch)

    def test_picking_form_has_exactly_one_match_button(self):
        arch = self._arch("stock.picking")
        self.assertEqual(arch.count('name="action_match_repair"'), 1)
        self.assertNotIn("action_add_to_repair", arch)
        self.assertNotIn("Add to Repair", arch)
        self.assertIn("Match Repair", arch)

    def test_repair_form_has_exactly_one_match_button(self):
        arch = self._arch("repair.order")
        self.assertEqual(arch.count('name="action_match_order"'), 1)
        self.assertNotIn("action_add_from_purchase_order_repair", arch)
        # The core catalog button of the Parts tab is still there.
        self.assertIn("action_add_from_catalog_repair", arch)

    # ----------------------------------------------------------
    # The superseded entry points are the match flow now
    # ----------------------------------------------------------

    def test_add_to_repair_entry_points_open_the_match_dialogs(self):
        repair, po = self._repair(), self._po()
        action = po.action_add_to_repair()
        self.assertEqual(action["name"], "Match Repair")
        self.assertTrue(action["context"]["repair_match_dialog"])
        action = repair.action_add_parts_from_purchase_order()
        self.assertEqual(action["name"], "Match Order")
        self.assertEqual(action["context"]["repair_id"], repair.id)
        action = (
            self.env["stock.move"]
            .with_context(order_id=repair.id)
            .action_add_from_purchase_order_repair()
        )
        self.assertEqual(action["name"], "Match Order")
        picking = po.picking_ids
        self.assertEqual(picking.action_match_repair()["name"], "Match Repair")
        self.assertEqual(picking.action_add_to_repair()["name"], "Match Repair")

    def test_picking_without_a_purchase_order_has_nothing_to_match(self):
        picking = self.env["stock.picking"].new({})
        with self.assertRaises(UserError) as caught:
            picking.action_match_repair()
        self.assertIn("no purchase order", str(caught.exception))

    # ----------------------------------------------------------
    # The pickers of repair_purchase_order_parts follow the same rules
    # ----------------------------------------------------------

    def test_picker_row_click_on_a_purchase_order_matches_it(self):
        repair, po = self._repair(), self._po()
        notice = po._edi_post_notice("Please match", email=False)
        result = (
            self._u(po, self.purchase_stock)
            .with_context(repair_id=repair.id)
            .action_select_for_repair()
        )
        self.assertEqual(result["type"], "ir.actions.act_window_close")
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)
        # the match flow's notes and clearing happened
        self.assertTrue(
            repair.message_ids.filtered(lambda m: "Linked to purchase order" in m.body)
        )
        self.assertTrue(notice.edi_notice_outstanding)
        self.assertFalse(
            self.env["mail.notification"].search(
                [("mail_message_id", "=", notice.id), ("is_read", "=", False)]
            )
        )

    def test_picker_multi_select_matches_every_purchase_order(self):
        repair = self._repair()
        pos = self._po() | self._po()
        self._u(pos, self.purchase_stock).with_context(
            repair_id=repair.id
        ).action_add_selected_to_repair()
        self.assertEqual(self._parts(repair).created_purchase_line_ids, pos.order_line)

    def test_picker_actions_refuse_users_who_can_not_match(self):
        repair, po = self._repair(), self._po()
        for user in (self.stock_only, self.purchase_only, self.nobody):
            for method in ("action_select_for_repair", "action_add_selected_to_repair"):
                picker = self._u(po, user).with_context(repair_id=repair.id)
                with (
                    self.subTest(user=user.login, method=method),
                    self.assertRaises(AccessError),
                ):
                    getattr(picker, method)()
        self.assertFalse(self._parts(repair))

    def test_picker_refuses_a_cancelled_purchase_order_and_checks_all_first(self):
        repair, good, bad = self._repair(), self._po(), self._po()
        bad.button_cancel()
        with self.assertRaises(UserError):
            (good | bad).with_user(self.purchase_stock).with_context(
                repair_id=repair.id, allowed_company_ids=self.company.ids
            ).action_add_selected_to_repair()
        self.assertFalse(self._parts(repair))

    def test_picker_row_click_on_a_repair_order_matches_it(self):
        repair, po = self._repair(), self._po()
        self._u(repair, self.purchase_stock).with_context(
            po_id=po.id
        ).action_select_po_for_repair()
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)
        for user in (self.stock_only, self.purchase_only):
            other, other_po = self._repair(), self._po()
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._u(other, user).with_context(
                    po_id=other_po.id
                ).action_select_po_for_repair()
            self.assertFalse(self._parts(other))

    def test_creating_a_repair_order_with_po_id_in_the_context_matches_it(self):
        po = self._po()
        vals = {
            "product_id": self.item.id,
            "product_uom": self.unit.id,
            "partner_id": self.customer.id,
        }
        repair = self.env["repair.order"].with_context(po_id=po.id).create(vals)
        self.assertEqual(self._parts(repair).created_purchase_line_ids, po.order_line)
        self.assertTrue(
            repair.message_ids.filtered(lambda m: "Linked to purchase order" in m.body)
        )
        # the rights are checked all the same, and nothing is left behind
        before = self.env["repair.order"].search_count([])
        with self.assertRaises(AccessError):
            self._u(self.env["repair.order"], self.stock_only).with_context(
                po_id=self._po().id
            ).create(vals)
        self.assertEqual(self.env["repair.order"].search_count([]), before)

    def test_message_flags_are_not_writable_by_the_message_recipient(self):
        po, repair = self._po(), self._repair()
        message = po.message_post(
            body="Mine", partner_ids=[self.purchase_stock.partner_id.id]
        )
        message = message.with_user(self.purchase_stock)
        for field, value in (
            ("edi_notice_outstanding", True),
            ("repair_match_purchase_order_id", po.id),
        ):
            with self.subTest(field=field), self.assertRaises(AccessError):
                message.write({field: value})
        self.assertFalse(repair.message_ids.sudo().filtered("edi_notice_outstanding"))
