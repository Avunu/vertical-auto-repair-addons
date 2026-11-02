# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import tagged

from .common import RepairJobCase


@tagged("post_install", "-at_install")
class TestCatalog(RepairJobCase):
    def test_catalog_search_by_name(self):
        response = self._dispatch(
            "catalog", repair_id=self.repair.id, search="Oil Filter"
        )
        self.assert_next_state(response, "catalog_search")
        codes = [
            rec["default_code"] for rec in self.state_data(response)["records"]
        ]
        self.assertIn("OF-200", codes)

    def test_catalog_search_by_barcode(self):
        response = self._dispatch(
            "catalog", repair_id=self.repair.id, search="SFR-TEST-OF-200"
        )
        ids = [rec["id"] for rec in self.state_data(response)["records"]]
        self.assertEqual(ids, [self.other_part.id])

    def test_catalog_is_paged(self):
        service = self.service_for(options={"catalog_page_size": 1})
        response = service.dispatch(
            "catalog", params={"repair_id": self.repair.id, "page": 1}
        )
        data = self.state_data(response)
        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["page_size"], 1)
        self.assertGreater(data["size"], 1)

    def test_add_part_creates_an_add_move(self):
        response = self._dispatch(
            "add_part",
            repair_id=self.repair.id,
            product_id=self.other_part.id,
            quantity=3.0,
        )
        self.assert_no_error(response)
        self.assert_next_state(response, "parts")
        move = self.repair.move_ids.filtered(
            lambda m: m.product_id == self.other_part
        )
        self.assertEqual(len(move), 1)
        self.assertEqual(move.repair_line_type, "add")
        self.assertEqual(move.product_uom_qty, 3.0)

    def test_add_part_is_flagged_with_the_technician(self):
        """Decision (b): the line is billed, but the advisor can see who added it."""
        self._dispatch(
            "add_part", repair_id=self.repair.id, product_id=self.other_part.id
        )
        move = self.repair.move_ids.filtered(
            lambda m: m.product_id == self.other_part
        )
        self.assertEqual(move.shopfloor_added_uid, self.technician)

    def test_add_part_works_without_a_technician_email(self):
        """message_post would raise "configure the sender's email address"."""
        self.technician.sudo().email = False
        self.technician.partner_id.sudo().email = False
        response = self._dispatch(
            "add_part", repair_id=self.repair.id, product_id=self.other_part.id
        )
        self.assert_no_error(response)
        self.assertTrue(
            self.repair.move_ids.filtered(lambda m: m.product_id == self.other_part)
        )

    def test_add_part_posts_to_the_chatter(self):
        before = len(self.repair.message_ids)
        self._dispatch(
            "add_part", repair_id=self.repair.id, product_id=self.other_part.id
        )
        messages = self.repair.message_ids
        self.assertGreater(len(messages), before)
        self.assertIn(self.other_part.name, messages[0].body)

    def test_add_part_syncs_to_the_sale_order(self):
        """Core behaviour we deliberately do NOT suppress."""
        sale_order = self.env["sale.order"].sudo().create(
            {"partner_id": self.customer.id}
        )
        self.repair.sudo().sale_order_id = sale_order
        self._dispatch(
            "add_part",
            repair_id=self.repair.id,
            product_id=self.other_part.id,
            quantity=2.0,
        )
        move = self.repair.move_ids.filtered(
            lambda m: m.product_id == self.other_part
        )
        self.assertTrue(move.sale_line_id)
        self.assertEqual(move.sale_line_id.order_id, sale_order)

    def test_add_part_chatter_mentions_the_quote(self):
        sale_order = self.env["sale.order"].sudo().create(
            {"partner_id": self.customer.id}
        )
        self.repair.sudo().sale_order_id = sale_order
        self._dispatch(
            "add_part", repair_id=self.repair.id, product_id=self.other_part.id
        )
        self.assertIn(sale_order.name, self.repair.message_ids[0].body)

    def test_add_part_and_consume_now(self):
        self._dispatch(
            "add_part",
            repair_id=self.repair.id,
            product_id=self.other_part.id,
            quantity=1.0,
            consume_now=True,
        )
        move = self.repair.move_ids.filtered(
            lambda m: m.product_id == self.other_part
        )
        self.assertEqual(move.quantity, 1.0)
        self.assertTrue(move.picked)

    def test_add_part_rejects_zero_quantity(self):
        response = self._dispatch(
            "add_part",
            repair_id=self.repair.id,
            product_id=self.other_part.id,
            quantity=0.0,
        )
        self.assert_error(response)
        self.assertFalse(
            self.repair.move_ids.filtered(lambda m: m.product_id == self.other_part)
        )

    def test_catalog_categories(self):
        response = self._dispatch("catalog_categories")
        self.assertTrue(response["data"]["categories"])
