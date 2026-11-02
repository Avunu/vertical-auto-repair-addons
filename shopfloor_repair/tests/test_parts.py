# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import tagged

from .common import RepairJobCase


@tagged("post_install", "-at_install")
class TestParts(RepairJobCase):
    @property
    def move(self):
        return self.repair.move_ids.filtered(
            lambda m: m.product_id == self.part and m.repair_line_type == "add"
        )

    def test_parts_lists_the_add_moves(self):
        response = self._dispatch("parts", repair_id=self.repair.id)
        self.assert_next_state(response, "parts")
        parts = self.state_data(response)["parts"]
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["product"]["default_code"], "BP-100")
        self.assertEqual(parts[0]["quantity_demand"], 2.0)
        self.assertEqual(parts[0]["quantity_done"], 0.0)
        self.assertFalse(parts[0]["picked"])

    def test_set_quantity_writes_done_only(self):
        """The whole point: never touch product_uom_qty from the shop floor."""
        move = self.move
        demand_before = move.product_uom_qty
        response = self._dispatch(
            "set_quantity", move_id=move.id, quantity=1.0
        )
        self.assert_no_error(response)
        self.assertEqual(move.quantity, 1.0)
        self.assertTrue(move.picked)
        self.assertEqual(move.product_uom_qty, demand_before)

    def test_set_quantity_does_not_rewrite_the_sale_order_line(self):
        """Editing demand would rewrite the customer's approved quote."""
        move = self.move
        sale_order = self.env["sale.order"].sudo().create(
            {"partner_id": self.customer.id}
        )
        sale_line = self.env["sale.order.line"].sudo().create(
            {
                "order_id": sale_order.id,
                "product_id": self.part.id,
                "product_uom_qty": 2.0,
            }
        )
        move.sudo().sale_line_id = sale_line
        self._dispatch("set_quantity", move_id=move.id, quantity=1.0)
        self.assertEqual(sale_line.product_uom_qty, 2.0)

    def test_consume_all_uses_the_demanded_quantity(self):
        response = self._dispatch("consume_all", move_id=self.move.id)
        self.assert_no_error(response)
        self.assertEqual(self.move.quantity, 2.0)
        self.assertTrue(self.move.picked)

    def test_reset_part(self):
        self._dispatch("consume_all", move_id=self.move.id)
        response = self._dispatch("reset_part", move_id=self.move.id)
        self.assert_no_error(response)
        self.assertEqual(self.move.quantity, 0.0)
        self.assertFalse(self.move.picked)

    def test_negative_quantity_refused(self):
        response = self._dispatch(
            "set_quantity", move_id=self.move.id, quantity=-1.0
        )
        self.assert_error(response)
        self.assertEqual(self.move.quantity, 0.0)

    def test_scan_part_on_the_job_opens_the_part(self):
        response = self._dispatch(
            "scan_part", repair_id=self.repair.id, barcode="SFR-TEST-BP-100"
        )
        self.assert_next_state(response, "part_detail")
        self.assertEqual(self.state_data(response)["record"]["id"], self.move.id)

    def test_scan_part_by_internal_reference(self):
        response = self._dispatch(
            "scan_part", repair_id=self.repair.id, barcode="BP-100"
        )
        self.assert_next_state(response, "part_detail")

    def test_scan_part_not_on_the_job_offers_to_add_it(self):
        response = self._dispatch(
            "scan_part", repair_id=self.repair.id, barcode="SFR-TEST-OF-200"
        )
        self.assert_next_state(response, "catalog_detail")
        self.assertEqual(
            self.state_data(response)["record"]["id"], self.other_part.id
        )

    def test_scan_unknown_part(self):
        response = self._dispatch(
            "scan_part", repair_id=self.repair.id, barcode="NOT-A-PART"
        )
        self.assert_next_state(response, "parts")
        self.assert_error(response)

    def test_tracked_part_requires_a_lot(self):
        tracked = self._make_product("Turbo", "TB-1", "SFR-TEST-TB-1", tracking="serial")
        repair = self._make_repair(parts=[(tracked, 1.0)])
        move = repair.move_ids.filtered(lambda m: m.product_id == tracked)
        response = self._dispatch("consume_all", move_id=move.id)
        self.assert_error(response)
        self.assertEqual(move.quantity, 0.0)

    def test_tracked_part_consumed_with_a_lot(self):
        tracked = self._make_product("Turbo", "TB-2", "SFR-TEST-TB-2", tracking="serial")
        repair = self._make_repair(parts=[(tracked, 1.0)])
        move = repair.move_ids.filtered(lambda m: m.product_id == tracked)
        lot = self.env["stock.lot"].sudo().create(
            {"name": "SN-0001", "product_id": tracked.id, "company_id": self.company.id}
        )
        response = self._dispatch(
            "set_quantity", move_id=move.id, quantity=1.0, lot_id=lot.id
        )
        self.assert_no_error(response)
        self.assertEqual(move.quantity, 1.0)
        self.assertIn(lot, move.move_line_ids.lot_id)

    def test_parts_locked_once_the_job_is_done(self):
        self._dispatch("start_repair", repair_id=self.repair.id)
        self._dispatch("finish", repair_id=self.repair.id)
        response = self._dispatch("set_quantity", move_id=self.move.id, quantity=1.0)
        self.assert_error(response)
