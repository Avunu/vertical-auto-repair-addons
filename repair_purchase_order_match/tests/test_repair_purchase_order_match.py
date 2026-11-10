# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.repair_purchase_order_match.models import purchase_order as po_module


def _make_choice_answer(choice, confidence=0.9):
    answer = MagicMock()
    answer.choice = choice
    answer.confidence = confidence
    return answer


@tagged("post_install", "-at_install")
class TestRepairPurchaseOrderMatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.customer = cls.env["res.partner"].create({"name": "Repair Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "NAPA Vendor"})
        cls.item_to_repair = cls.env["product.product"].create(
            {"name": "Widget", "type": "consu", "is_storable": True}
        )
        cls.part_a = cls.env["product.product"].create(
            {"name": "Brake Pad", "type": "consu", "is_storable": True}
        )
        cls.brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Toyota"})
        cls.vehicle_model = cls.env["fleet.vehicle.model"].create(
            {"name": "Corolla Matrix", "brand_id": cls.brand.id}
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "repair_purchase_order_match.typesafe_api_key", "test-key"
        )

    def _make_vehicle(self, model_year="2005"):
        return self.env["fleet.vehicle"].create(
            {"model_id": self.vehicle_model.id, "model_year": model_year}
        )

    def _make_repair(
        self, vehicle=None, customer_concern="Rear brakes need to be replaced"
    ):
        return self.env["repair.order"].create(
            {
                "product_id": self.item_to_repair.id,
                "product_uom": self.unit.id,
                "partner_id": self.customer.id,
                "vehicle_id": (vehicle or self._make_vehicle()).id,
                "customer_concern": customer_concern,
            }
        )

    def _make_po(self, lines=None):
        lines = lines or [(self.part_a, 2.0)]
        return self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.name,
                            "product_qty": qty,
                            "product_uom": self.unit.id,
                            "price_unit": 10.0,
                        },
                    )
                    for product, qty in lines
                ],
            }
        )

    def _confirmed_po(self, lines=None, **vals):
        po = self._make_po(lines)
        if vals:
            po.write(vals)
        po.button_confirm()
        return po

    def _unmatched_ids(self, company=None):
        return set(
            self.env["purchase.order"]
            .search(self.env["purchase.order"]._repair_match_unmatched_domain(company))
            .ids
        )

    def _patch_typesafe(self, choice=None, confidence=0.9):
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        response = MagicMock()
        response.choices = (
            {"matching_ro": _make_choice_answer(choice, confidence)} if choice else {}
        )
        client.system_one.return_value = response
        return patch.object(po_module, "TypeSafeClient", return_value=client), client

    # ----------------------------------------------------------
    # _repair_match_via_typesafe
    # ----------------------------------------------------------

    def test_no_match_without_api_key(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "repair_purchase_order_match.typesafe_api_key", ""
        )
        po = self._make_po()
        self.assertIsNone(po._repair_match_via_typesafe())

    def test_no_match_without_candidate_repairs(self):
        po = self._make_po()
        self.assertIsNone(po._repair_match_via_typesafe())

    def test_match_returns_repair_and_confidence(self):
        repair = self._make_repair()
        po = self._make_po()

        patcher, client = self._patch_typesafe(choice=str(repair.id), confidence=0.97)
        with patcher:
            match = po._repair_match_via_typesafe()

        self.assertEqual(match, (repair, 0.97))
        # The candidate repair order's vehicle/customer-concern context
        # was sent as criteria, keyed by its id.
        _state, kwargs = client.system_one.call_args
        criteria = kwargs["questions"]["matching_ro"].criteria
        self.assertIn(str(repair.id), criteria)
        self.assertEqual(criteria[str(repair.id)]["Manufacturer"], "Toyota")
        self.assertEqual(criteria[str(repair.id)]["Model"], "Corolla Matrix")

    def test_match_state_describes_the_purchase_order(self):
        po = self._make_po([(self.part_a, 3.0)])
        self.assertEqual(po._typesafe_match_state()["vendor"], "NAPA Vendor")
        self.assertEqual(po._typesafe_match_state()["lines"][0]["Quantity"], 3.0)

    def test_repairs_without_a_vehicle_are_not_candidates(self):
        self.env["repair.order"].create(
            {
                "product_id": self.item_to_repair.id,
                "product_uom": self.unit.id,
                "partner_id": self.customer.id,
            }
        )
        po = self._make_po()
        self.assertFalse(po._repair_match_candidate_repairs())

    def test_no_match_when_typesafe_returns_no_answer(self):
        self._make_repair()
        po = self._make_po()
        patcher, _client = self._patch_typesafe(choice=None)
        with patcher:
            self.assertIsNone(po._repair_match_via_typesafe())

    def test_no_match_when_typesafe_errors(self):
        self._make_repair()
        po = self._make_po()
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.system_one.side_effect = po_module.TypeSafeError("boom")
        with (
            patch.object(po_module, "TypeSafeClient", return_value=client),
            mute_logger(po_module.__name__),
        ):
            self.assertIsNone(po._repair_match_via_typesafe())

    # ----------------------------------------------------------
    # Suggestion + confirm token
    # ----------------------------------------------------------

    def test_auto_link_or_suggest_posts_confirm_button_on_both_chatters(self):
        repair = self._make_repair()
        po = self._make_po()

        patcher, _client = self._patch_typesafe(choice=str(repair.id), confidence=0.85)
        with patcher:
            po._repair_auto_link_or_suggest()

        # Nothing is linked yet - only suggested.
        self.assertFalse(repair.move_ids.created_purchase_line_ids)
        po_message = po.message_ids.sorted("id")[-1]
        repair_message = repair.message_ids.sorted("id")[-1]
        self.assertIn("85%", po_message.body)
        self.assertIn("/repair_purchase_order_match/confirm", po_message.body)
        self.assertIn("/repair_purchase_order_match/confirm", repair_message.body)

    def test_suggestion_links_purchase_order_and_original_email(self):
        repair = self._make_repair()
        po = self._make_po()
        exchange_type = self.env["edi.exchange.type"].search([], limit=1)
        # An exchange record's backend has to fit its type: the type's own backend
        # if it has one, otherwise any backend of the type's backend type.
        backend = exchange_type.backend_id or self.env["edi.backend"].search(
            [("backend_type_id", "=", exchange_type.backend_type_id.id)], limit=1
        )
        if not (backend and exchange_type):
            self.skipTest("No EDI backend/exchange type available")
        exchange_record = self.env["edi.exchange.record"].create(
            {"type_id": exchange_type.id, "backend_id": backend.id}
        )
        exchange_record._set_related_record(po)

        patcher, _client = self._patch_typesafe(choice=str(repair.id), confidence=0.85)
        with patcher:
            po._repair_auto_link_or_suggest()

        po_body = po.message_ids.sorted("id")[-1].body
        repair_body = repair.message_ids.sorted("id")[-1].body
        email_marker = (
            f'data-oe-model="edi.exchange.record" data-oe-id="{exchange_record.id}"'
        )
        po_marker = f'data-oe-model="purchase.order" data-oe-id="{po.id}"'
        self.assertIn(email_marker, po_body)
        self.assertIn(email_marker, repair_body)
        self.assertIn(po_marker, repair_body)
        self.assertNotIn(po_marker, po_body)

    def test_suggestion_without_exchange_record_has_no_email_link(self):
        repair = self._make_repair()
        po = self._make_po()

        patcher, _client = self._patch_typesafe(choice=str(repair.id), confidence=0.85)
        with patcher:
            po._repair_auto_link_or_suggest()

        self.assertNotIn("edi.exchange.record", po.message_ids.sorted("id")[-1].body)
        self.assertNotIn(
            "edi.exchange.record", repair.message_ids.sorted("id")[-1].body
        )

    def test_confirm_token_is_specific_to_the_po_repair_pair(self):
        repair_1 = self._make_repair()
        repair_2 = self._make_repair()
        po = self._make_po()

        token = po._repair_match_confirm_token(repair_1)
        self.assertTrue(po._repair_match_confirm_token_valid(repair_1, token))
        self.assertFalse(po._repair_match_confirm_token_valid(repair_2, token))
        self.assertFalse(po._repair_match_confirm_token_valid(repair_1, "tampered"))

    # ----------------------------------------------------------
    # Linking (unchanged mechanism, still used post-confirm)
    # ----------------------------------------------------------

    def test_link_to_repair_order_adds_parts_and_posts_both_chatters(self):
        repair = self._make_repair()
        po = self._make_po()

        po._link_to_repair_order(repair)

        parts = repair.move_ids.filtered(lambda m: m.repair_line_type == "add")
        self.assertEqual(parts.created_purchase_line_ids, po.order_line)
        self.assertIn(repair, po._get_linked_repair_orders())

    # ----------------------------------------------------------
    # PO number -> repair order (automatic link)
    # ----------------------------------------------------------

    def _parts_on(self, repair):
        return repair.move_ids.filtered(lambda m: m.repair_line_type == "add")

    def test_po_number_matching_a_repair_order_links_it_automatically(self):
        repair = self._make_repair()
        other = self._make_repair()
        po = self._make_po()
        po.origin = repair.name

        # TypeSafe is never consulted when the PO number settles it.
        patcher, client = self._patch_typesafe(choice=str(other.id))
        with patcher:
            po._repair_auto_link_or_suggest()

        client.system_one.assert_not_called()
        self.assertEqual(
            self._parts_on(repair).created_purchase_line_ids, po.order_line
        )
        self.assertFalse(self._parts_on(other))
        po_message = po.message_ids.sorted("id")[-1]
        repair_message = repair.message_ids.sorted("id")[-1]
        self.assertIn("linked automatically", po_message.body)
        self.assertIn("linked automatically", repair_message.body)
        # The user is notified, and can pick a different repair order.
        self.assertTrue(po_message.partner_ids)
        self.assertIn("action-repair_purchase_order_match.", po_message.body)

    def test_po_number_matches_on_the_number_not_the_letters(self):
        repair = self._make_repair()
        number = int(repair.name.rsplit("/", 1)[-1])
        po = self._make_po()
        for reference in (
            f"RO{number:05d}",
            f"ro-{number}",
            f"  WH/RO/{number:05d} ",
            f"RO {number}",
        ):
            po.origin = reference
            self.assertEqual(po._repair_match_by_reference(), repair, reference)

    def test_po_number_with_a_different_number_matches_nothing(self):
        repair = self._make_repair()
        number = int(repair.name.rsplit("/", 1)[-1])
        po = self._make_po()
        for reference in (f"RO{number + 100:05d}", "no digits here", False):
            po.origin = reference
            self.assertFalse(po._repair_match_by_reference(), reference)

    def test_vendor_reference_is_not_a_po_number(self):
        repair = self._make_repair()
        po = self._make_po()
        po.partner_ref = repair.name

        self.assertFalse(po._repair_match_by_reference())

    def test_po_number_shared_by_two_repair_orders_is_ambiguous(self):
        repair = self._make_repair()
        twin = self._make_repair()
        twin.name = repair.name.replace("RO/", "RO2/")
        po = self._make_po()
        po.origin = repair.name

        self.assertFalse(po._repair_match_by_reference())

    def test_po_number_that_is_not_a_repair_order_falls_back_to_typesafe(self):
        repair = self._make_repair()
        po = self._make_po()
        po.origin = "ORD-00000TESTA"

        self.assertFalse(po._repair_match_by_reference())
        patcher, _client = self._patch_typesafe(choice=str(repair.id))
        with patcher:
            po._repair_auto_link_or_suggest()

        self.assertFalse(self._parts_on(repair))
        self.assertIn(
            "/repair_purchase_order_match/confirm", po.message_ids.sorted("id")[-1].body
        )

    def test_po_number_naming_a_closed_repair_order_is_not_linked(self):
        repair = self._make_repair()
        repair.action_repair_cancel()
        po = self._make_po()
        po.origin = repair.name

        po._repair_auto_link_or_suggest()

        self.assertFalse(self._parts_on(repair))
        self.assertIn("parts were not added", po.message_ids.sorted("id")[-1].body)

    # ----------------------------------------------------------
    # Choosing a different repair order
    # ----------------------------------------------------------

    def test_choosing_a_different_repair_order_moves_the_parts(self):
        wrong = self._make_repair()
        right = self._make_repair()
        po = self._make_po()
        po.origin = wrong.name
        po._repair_auto_link_or_suggest()
        self.assertTrue(self._parts_on(wrong))

        right.with_context(po_id=po.id).action_link_purchase_order()

        self.assertFalse(self._parts_on(wrong))
        self.assertEqual(self._parts_on(right).created_purchase_line_ids, po.order_line)

    def test_list_row_action_returns_to_the_purchase_order(self):
        repair = self._make_repair()
        po = self._make_po()

        action = repair.with_context(po_id=po.id).action_link_purchase_order()

        self.assertEqual(
            (action["res_model"], action["res_id"]), ("purchase.order", po.id)
        )

    def test_choose_action_gives_the_list_the_purchase_order_id(self):
        action = self.env.ref(
            "repair_purchase_order_match.action_repair_order_choose_for_po"
        )
        self.assertIn("active_id", action.context)

    # ----------------------------------------------------------
    # MCP tools
    # ----------------------------------------------------------

    def test_mcp_find_repair_order_matches(self):
        repair = self._make_repair()
        po = self._make_po()

        patcher, _client = self._patch_typesafe(choice=str(repair.id), confidence=0.9)
        with patcher:
            result = self.env["muk_mcp.mixin"]._mcp_find_repair_order_matches(
                purchase_order_id=po.id
            )

        self.assertEqual(result["match"]["repair_id"], repair.id)
        self.assertEqual(result["match"]["confidence"], 0.9)

    def test_mcp_link_purchase_order_to_repair(self):
        repair = self._make_repair()
        po = self._make_po([(self.part_a, 2.0)])

        result = self.env["muk_mcp.mixin"]._mcp_link_purchase_order_to_repair(
            purchase_order_id=po.id, repair_order_id=repair.id
        )

        self.assertTrue(result["linked"])
        parts = repair.move_ids.filtered(lambda m: m.repair_line_type == "add")
        self.assertEqual(set(parts.product_id.ids), {self.part_a.id})

    # ----------------------------------------------------------
    # Match Order (repair order -> purchase order)
    # ----------------------------------------------------------

    def test_unmatched_domain_includes_a_confirmed_unlinked_po(self):
        po = self._confirmed_po()
        self.assertIn(po.id, self._unmatched_ids())
        self.assertTrue(po.repair_match_unmatched)

    def test_unmatched_domain_excludes_fully_linked_po(self):
        repair = self._make_repair()
        po = self._confirmed_po()
        po._link_to_repair_order(repair)
        self.assertNotIn(po.id, self._unmatched_ids())
        self.assertFalse(po.repair_match_unmatched)

    def test_unmatched_domain_excludes_partially_linked_po(self):
        repair = self._make_repair()
        part_b = self.env["product.product"].create(
            {"name": "Brake Rotor", "type": "consu", "is_storable": True}
        )
        po = self._confirmed_po([(self.part_a, 1.0), (part_b, 1.0)])
        # Only the first line is on a repair order.
        moves = self.env["stock.move"].create(
            po._prepare_repair_move_vals(repair, po.order_line[1:].ids)
        )
        self.assertEqual(moves.created_purchase_line_ids, po.order_line[:1])
        self.assertNotIn(po.id, self._unmatched_ids())

    def test_unmatched_domain_excludes_buy_route_po_linked_by_receipt_move(self):
        """Once a purchase order made by the Buy route is confirmed, the
        repair part is linked through the receipt move, not through the
        order line (purchase_stock clears the line's `move_dest_ids`).
        """
        repair = self._make_repair()
        po = self._make_po()
        self.env["stock.move"].create(po._prepare_repair_move_vals(repair, []))
        po.button_confirm()
        self.assertFalse(po.order_line.move_dest_ids)
        self.assertEqual(po._get_linked_repair_orders(), repair)

        self.assertFalse(po.repair_match_unmatched)
        self.assertNotIn(po.id, self._unmatched_ids())

        repair.action_repair_cancel()
        self.assertIn(po.id, self._unmatched_ids())

    def test_unmatched_domain_excludes_po_without_parts(self):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "Freight",
                            "product_qty": 0,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        self.assertNotIn(po.id, self._unmatched_ids())
        repair = self._make_repair()
        with self.assertRaises(UserError):
            po.with_context(repair_id=repair.id).action_match_to_repair()

    def test_unmatched_domain_excludes_rfq_and_cancelled_po(self):
        rfq = self._make_po()
        cancelled = self._confirmed_po()
        cancelled.button_cancel()
        unmatched = self._unmatched_ids()
        self.assertNotIn(rfq.id, unmatched)
        self.assertNotIn(cancelled.id, unmatched)

    def test_unmatched_domain_is_per_company(self):
        other_company = self.env["res.company"].create({"name": "Other Shop"})
        po = self._make_po()
        po.write({"company_id": other_company.id, "state": "purchase"})
        self.assertNotIn(po.id, self._unmatched_ids())
        self.assertIn(po.id, self._unmatched_ids(other_company))

    def test_po_linked_only_to_a_cancelled_repair_is_unmatched_again(self):
        repair = self._make_repair()
        po = self._confirmed_po()
        po._link_to_repair_order(repair)
        self.assertNotIn(po.id, self._unmatched_ids())

        repair.action_repair_cancel()

        self.assertIn(po.id, self._unmatched_ids())

    def test_po_linked_to_a_done_repair_stays_matched(self):
        repair = self._make_repair()
        po = self._confirmed_po()
        po._link_to_repair_order(repair)
        repair.action_validate()
        repair.action_repair_start()
        repair.action_repair_end()
        self.assertEqual(repair.state, "done")
        self.assertNotIn(po.id, self._unmatched_ids())

    def test_unmatched_search_negation(self):
        repair = self._make_repair()
        linked = self._confirmed_po()
        linked._link_to_repair_order(repair)
        free = self._confirmed_po()
        orders = linked | free
        search = self.env["purchase.order"].search
        self.assertEqual(
            search([("id", "in", orders.ids), ("repair_match_unmatched", "=", False)]),
            linked,
        )
        self.assertEqual(
            search([("id", "in", orders.ids), ("repair_match_unmatched", "!=", False)]),
            free,
        )
        with self.assertRaises(UserError):
            search([("repair_match_unmatched", "ilike", True)])

    def test_unmatched_search_needs_no_stock_access(self):
        """A purchase user who cannot read stock moves still sees the right
        purchase orders."""
        repair = self._make_repair()
        linked = self._confirmed_po()
        linked._link_to_repair_order(repair)
        free = self._confirmed_po()
        buyer = self.env["res.users"].create(
            {
                "name": "Buyer",
                "login": "buyer_match",
                "groups_id": [
                    (6, 0, [self.env.ref("purchase.group_purchase_user").id])
                ],
            }
        )
        found = (
            self.env["purchase.order"]
            .with_user(buyer)
            .search(
                [
                    ("id", "in", (linked | free).ids),
                    ("repair_match_unmatched", "=", True),
                ]
            )
        )
        self.assertEqual(found, free)

    def test_parts_html_lists_quantity_part_number_and_description(self):
        self.part_a.default_code = "BP-100"
        po = self._make_po([(self.part_a, 2.0)])
        html = str(po.repair_match_parts_html)
        self.assertIn("BP-100", html)
        self.assertIn("Brake Pad", html)
        self.assertIn("2.00", html)
        self.assertIn(self.unit.name, html)

    def test_parts_html_escapes_user_provided_strings(self):
        evil = self.env["product.product"].create(
            {
                "name": "<script>alert(1)</script>",
                "default_code": "<b>X</b>",
                "type": "consu",
            }
        )
        po = self._make_po([(evil, 1.0)])
        html = str(po.repair_match_parts_html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>X</b>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_parts_html_skips_sections_notes_and_lines_without_product(self):
        po = self._make_po([(self.part_a, 1.0)])
        po.write(
            {
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "SECTION-X",
                            "product_qty": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "display_type": "line_note",
                            "name": "NOTE-X",
                            "product_qty": 0,
                        },
                    ),
                ]
            }
        )
        html = str(po.repair_match_parts_html)
        self.assertIn("Brake Pad", html)
        self.assertNotIn("SECTION-X", html)
        self.assertNotIn("NOTE-X", html)
        self.assertEqual(html.count("<tr>"), 1)

    def test_parts_html_is_empty_without_parts(self):
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        self.assertFalse(po.repair_match_parts_html)

    def test_action_match_order_opens_dialog_of_unmatched_orders(self):
        repair = self._make_repair()
        free = self._confirmed_po()
        linked = self._confirmed_po()
        linked._link_to_repair_order(self._make_repair())

        action = repair.action_match_order()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "purchase.order")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["view_mode"], "kanban")
        self.assertEqual(action["views"][0][1], "kanban")
        self.assertEqual(action["context"]["repair_id"], repair.id)
        found = self.env["purchase.order"].search(action["domain"])
        self.assertIn(free, found)
        self.assertNotIn(linked, found)
        # The dialog's views really load, parts list included.
        kanban = self.env["purchase.order"].get_view(action["views"][0][0], "kanban")
        self.assertIn("repair_match_parts_html", kanban["arch"])
        self.assertIn('name="action_match_to_repair"', kanban["arch"])
        self.assertTrue(action["search_view_id"][0])

    def test_action_match_order_raises_for_closed_repair(self):
        repair = self._make_repair()
        repair.action_repair_cancel()
        with self.assertRaises(UserError):
            repair.action_match_order()

    def test_search_view_has_email_filter(self):
        search = self.env.ref(
            "repair_purchase_order_match.view_purchase_order_search_match_repair"
        )
        arch = self.env["purchase.order"].get_view(search.id, "search")["arch"]
        self.assertIn('name="imported_from_email"', arch)
        self.assertIn("exchange_related_record_ids", arch)
        exchange_type = self.env["edi.exchange.type"].search([], limit=1)
        backend = exchange_type.backend_id or self.env["edi.backend"].search(
            [("backend_type_id", "=", exchange_type.backend_type_id.id)], limit=1
        )
        plain = self._confirmed_po()
        # The filter's domain must be searchable.
        domain = [("exchange_related_record_ids", "!=", False)]
        self.assertNotIn(plain, self.env["purchase.order"].search(domain))
        if backend and exchange_type:
            imported = self._confirmed_po()
            record = self.env["edi.exchange.record"].create(
                {"type_id": exchange_type.id, "backend_id": backend.id}
            )
            record._set_related_record(imported)
            self.assertIn(imported, self.env["purchase.order"].search(domain))

    def test_action_match_to_repair_links_posts_and_reloads(self):
        repair = self._make_repair()
        po = self._confirmed_po()

        action = po.with_context(repair_id=repair.id).action_match_to_repair()

        self.assertEqual(action, {"type": "ir.actions.client", "tag": "soft_reload"})
        self.assertEqual(
            self._parts_on(repair).created_purchase_line_ids, po.order_line
        )
        self.assertIn(repair.name, po.message_ids.sorted("id")[-1].body)
        self.assertIn(po.name, repair.message_ids.sorted("id")[-1].body)
        self.assertNotIn(po.id, self._unmatched_ids())

    def test_action_match_to_repair_moves_parts_from_previous_repair(self):
        wrong = self._make_repair()
        right = self._make_repair()
        po = self._confirmed_po()
        po._link_to_repair_order(wrong)

        po.with_context(repair_id=right.id).action_match_to_repair()

        self.assertFalse(self._parts_on(wrong))
        self.assertEqual(self._parts_on(right).created_purchase_line_ids, po.order_line)

    def test_action_match_to_repair_validates(self):
        po = self._confirmed_po()
        with self.assertRaises(UserError):
            po.action_match_to_repair()  # no repair in the context
        with self.assertRaises(UserError):
            po.with_context(repair_id=0).action_match_to_repair()
        closed = self._make_repair()
        closed.action_repair_cancel()
        with self.assertRaises(UserError):
            po.with_context(repair_id=closed.id).action_match_to_repair()
        other_company = self.env["res.company"].create({"name": "Other Shop"})
        foreign = self._make_repair()
        foreign.company_id = other_company
        with self.assertRaises(UserError):
            po.with_context(repair_id=foreign.id).action_match_to_repair()
        cancelled = self._confirmed_po()
        cancelled.button_cancel()
        with self.assertRaises(UserError):
            cancelled.with_context(
                repair_id=self._make_repair().id
            ).action_match_to_repair()

    # ----------------------------------------------------------
    # Match Repair (purchase order -> repair order)
    # ----------------------------------------------------------

    def test_action_match_repair_opens_dialog_of_open_repairs(self):
        open_repair = self._make_repair()
        closed = self._make_repair()
        closed.action_repair_cancel()
        po = self._confirmed_po()

        action = po.action_match_repair()

        self.assertEqual(action["res_model"], "repair.order")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["po_id"], po.id)
        found = self.env["repair.order"].search(action["domain"])
        self.assertIn(open_repair, found)
        self.assertNotIn(closed, found)
        view = self.env["repair.order"].get_view(action["views"][0][0], "list")
        self.assertIn('action="action_link_purchase_order"', view["arch"])

    def test_row_click_from_match_repair_dialog_reloads_the_form(self):
        repair = self._make_repair()
        po = self._confirmed_po()
        action = po.action_match_repair()

        result = repair.with_context(**action["context"]).action_link_purchase_order()

        self.assertEqual(result, {"type": "ir.actions.client", "tag": "soft_reload"})
        self.assertEqual(
            self._parts_on(repair).created_purchase_line_ids, po.order_line
        )

    def test_row_click_refuses_a_closed_repair(self):
        repair = self._make_repair()
        repair.action_repair_cancel()
        po = self._confirmed_po()
        with self.assertRaises(UserError):
            repair.with_context(po_id=po.id).action_link_purchase_order()

    # ----------------------------------------------------------
    # Buttons in the combined form views
    # ----------------------------------------------------------

    def _form_arch(self, model, user):
        return self.env[model].with_user(user).get_view(view_type="form")["arch"]

    def test_repair_form_has_match_order_button_before_the_statusbar(self):
        arch = self._form_arch("repair.order", self.env.ref("base.user_admin"))
        self.assertIn('name="action_match_order"', arch)
        self.assertLess(
            arch.index('name="action_match_order"'),
            arch.index('widget="statusbar"'),
        )

    def test_purchase_form_has_one_match_repair_button_and_no_add_to_repair(self):
        arch = self._form_arch("purchase.order", self.env.ref("base.user_admin"))
        self.assertEqual(arch.count('name="action_match_repair"'), 1)
        self.assertNotIn("action_add_to_repair", arch)
        self.assertNotIn("Add to Repair", arch)

    def test_buttons_follow_the_access_rights_not_a_purchase_group(self):
        """The buttons are shown to who can really match (see
        `repair.match.access`): the form carries the flag their `invisible`
        reads, and no `groups` restricts them to purchase users."""
        arch = self._form_arch("repair.order", self.env.ref("base.user_admin"))
        self.assertIn('name="repair_match_can_link"', arch)
        button = arch[arch.index('name="action_match_order"') :]
        button = button[: button.index("/>")]
        self.assertIn("repair_match_can_link", button)
        self.assertNotIn("groups", button)

    def test_dialogs_open_for_a_purchase_and_stock_user(self):
        """Opening the dialogs must not need Settings rights (the search
        view's name is read with sudo).
        """
        user = self.env["res.users"].create(
            {
                "name": "Purchase Manager",
                "login": "purchase_manager_match",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("purchase.group_purchase_user").id,
                            self.env.ref("stock.group_stock_user").id,
                        ],
                    )
                ],
            }
        )
        repair = self._make_repair()
        po = self._confirmed_po()

        action = repair.with_user(user).action_match_order()
        self.assertEqual(action["res_model"], "purchase.order")
        self.assertEqual(len(action["search_view_id"]), 2)
        self.assertIn(
            po, self.env["purchase.order"].with_user(user).search(action["domain"])
        )
        self.assertEqual(
            po.with_user(user).action_match_repair()["res_model"], "repair.order"
        )
