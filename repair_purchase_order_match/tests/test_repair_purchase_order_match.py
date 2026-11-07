# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import MagicMock, patch

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
