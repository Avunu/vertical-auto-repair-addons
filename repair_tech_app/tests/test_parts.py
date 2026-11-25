# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TechCase


@tagged("post_install", "-at_install")
class TestParts(TechCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.move = cls.repair.move_ids.filtered(lambda m: m.product_id == cls.part)

    def tracked(self, tracking="serial"):
        product = self._make_product(
            "Turbo", "TB-1", "RTA-TEST-TB-1", tracking=tracking
        )
        repair = self._make_repair(parts=[(product, 1.0)])
        move = repair.move_ids.filtered(lambda m: m.product_id == product)
        lot = self.env["stock.lot"].create(
            {"name": "SN-0001", "product_id": product.id}
        )
        return move, lot

    def test_parts(self):
        result = self.app.parts(repair_id=self.repair.id)
        self.assertTrue(result["can_edit"])
        (part,) = result["parts"]
        self.assertEqual(part["id"], self.move.id)
        self.assertEqual(part["product"]["default_code"], "BP-100")
        self.assertEqual((part["quantity_demand"], part["quantity_done"]), (2.0, 0.0))
        self.assertFalse(part["added_by_technician"])

    def test_set_quantity_writes_usage_only(self):
        """Never the demand: that would rewrite the approved quote."""
        part = self.app.set_part_quantity(move_id=self.move.id, quantity=1.0)["parts"][
            0
        ]
        self.assertEqual((part["quantity_done"], part["picked"]), (1.0, True))
        self.assertEqual(self.move.product_uom_qty, 2.0)

    def test_set_quantity_leaves_the_quote_alone(self):
        order = self.env["sale.order"].create({"partner_id": self.customer.id})
        sale_line = self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": self.part.id, "product_uom_qty": 2.0}
        )
        self.move.sale_line_id = sale_line
        self.app.set_part_quantity(move_id=self.move.id, quantity=1.0)
        self.assertEqual(sale_line.product_uom_qty, 2.0)

    def test_decimal_quantity(self):
        """Parts come in litres and metres too."""
        part = self.app.set_part_quantity(move_id=self.move.id, quantity=1.25)["parts"][
            0
        ]
        self.assertEqual(part["quantity_done"], 1.25)

    def test_negative_quantity(self):
        with self.assertRaises(ValidationError):
            self.app.set_part_quantity(move_id=self.move.id, quantity=-1)

    def test_use_all_and_reset(self):
        part = self.app.use_all(move_id=self.move.id)["parts"][0]
        self.assertEqual(part["quantity_done"], 2.0)
        result = self.app.reset_part(move_id=self.move.id)
        self.assertEqual(result["parts"][0]["quantity_done"], 0.0)
        self.assertFalse(result["parts"][0]["picked"])
        self.assertEqual(result["job"]["parts_done"], 0)

    def test_tracked_part_needs_its_serial(self):
        move, _lot = self.tracked()
        with self.assertRaisesRegex(UserError, "tracked"):
            self.app.use_all(move_id=move.id)
        with self.assertRaisesRegex(UserError, "tracked"):
            self.app.set_part_quantity(move_id=move.id, quantity=1.0)
        self.assertEqual(move.quantity, 0.0)

    def test_tracked_part_with_a_picked_serial(self):
        move, lot = self.tracked()
        result = self.app.set_part_quantity(
            move_id=move.id, quantity=1.0, lot_id=lot.id
        )
        self.assertEqual(move.quantity, 1.0)
        self.assertIn(lot, move.move_line_ids.lot_id)
        self.assertEqual(
            result["parts"][0]["lots"], [{"id": lot.id, "name": "SN-0001"}]
        )

    def test_tracked_part_with_a_scanned_serial(self):
        move, lot = self.tracked()
        self.app.set_part_quantity(move_id=move.id, quantity=1.0, lot_name="SN-0001")
        self.assertIn(lot, move.move_line_ids.lot_id)
        with self.assertRaisesRegex(UserError, "No lot or serial"):
            self.app.set_part_quantity(move_id=move.id, quantity=1.0, lot_name="SN-9")

    def test_serial_of_another_product(self):
        move, _lot = self.tracked()
        stranger = self.env["stock.lot"].create(
            {"name": "SN-X", "product_id": self.part.id}
        )
        self.part.tracking = "lot"
        with self.assertRaisesRegex(UserError, "isn't one of"):
            self.app.set_part_quantity(
                move_id=move.id, quantity=1.0, lot_id=stranger.id
            )

    def test_parts_lock_when_the_job_is_done(self):
        self.app.start_repair(repair_id=self.repair.id)
        self.app.finish(repair_id=self.repair.id)
        self.assertFalse(self.app.parts(repair_id=self.repair.id)["can_edit"])
        with self.assertRaisesRegex(UserError, "closed"):
            self.app.set_part_quantity(move_id=self.move.id, quantity=1.0)

    def test_a_move_that_isnt_a_part(self):
        with self.assertRaisesRegex(UserError, "no longer on the job"):
            self.app.use_all(move_id=999999999)

    def test_scan_a_part_on_the_job(self):
        for code in ("RTA-TEST-BP-100", "bp-100"):
            scan = self.app.scan_part(repair_id=self.repair.id, code=code)
            self.assertEqual(scan, {"move_id": self.move.id, "product": None}, code)

    def test_scan_prefers_the_jobs_part_over_a_namesake(self):
        """Internal references aren't unique: the part on the job wins."""
        twin = self._make_product("Brake Pad Set", "BP-100", "RTA-TEST-BP-TWIN")
        twin.default_code = "BP-100"
        scan = self.app.scan_part(repair_id=self.repair.id, code="BP-100")
        self.assertEqual(scan["move_id"], self.move.id)

    def test_scan_a_part_the_job_doesnt_have(self):
        scan = self.app.scan_part(repair_id=self.repair.id, code="RTA-TEST-OF-200")
        self.assertIsNone(scan["move_id"])
        self.assertEqual(scan["product"]["id"], self.other_part.id)

    def test_scan_a_serial(self):
        move, _lot = self.tracked()
        scan = self.app.scan_part(repair_id=move.repair_id.id, code="SN-0001")
        self.assertEqual(scan["move_id"], move.id)

    def test_scan_nothing_known(self):
        with self.assertRaisesRegex(UserError, "No part matches"):
            self.app.scan_part(repair_id=self.repair.id, code="NOPE")


@tagged("post_install", "-at_install")
class TestCatalog(TechCase):
    def test_search_by_name_code_and_barcode(self):
        for search in ("oil filt", "OF-200", "RTA-TEST-OF-200"):
            page = self.app.catalog(search=search)
            self.assertIn(self.other_part.id, self.ids(page["records"]), search)

    def test_paged(self):
        self.env["ir.config_parameter"].set_param(
            "repair_tech_app.catalog_page_size", 1
        )
        category = self.env["product.category"].create({"name": "Brakes and filters"})
        (self.part | self.other_part).categ_id = category
        first = self.app.catalog(category_id=category.id)
        second = self.app.catalog(category_id=category.id, page=2)
        self.assertEqual((first["page_size"], first["total"]), (1, 2))
        self.assertEqual(len(first["records"]), 1)
        self.assertNotEqual(self.ids(first["records"]), self.ids(second["records"]))
        with self.assertRaises(ValidationError):
            self.app.catalog(page=0)

    def test_category(self):
        category = self.env["product.category"].create({"name": "Filters"})
        self.other_part.categ_id = category
        page = self.app.catalog(category_id=category.id)
        self.assertEqual(self.ids(page["records"]), [self.other_part.id])
        self.assertIn(category.id, self.ids(self.app.catalog_categories()))

    def test_add_part(self):
        result = self.app.add_part(
            repair_id=self.repair.id, product_id=self.other_part.id, quantity=2
        )
        added = next(
            p for p in result["parts"] if p["product"]["id"] == self.other_part.id
        )
        self.assertEqual(added["quantity_demand"], 2.0)
        self.assertEqual(added["quantity_done"], 0.0)
        self.assertTrue(added["added_by_technician"])
        move = self.env["stock.move"].browse(added["id"])
        self.assertEqual(move.repair_line_type, "add")
        self.assertEqual(move.tech_added_uid, self.technician)
        self.assertIn("from the technician app", self.repair.message_ids[:1].body)

    def test_add_part_and_use_it(self):
        result = self.app.add_part(
            repair_id=self.repair.id, product_id=self.other_part.id, used=True
        )
        added = next(
            p for p in result["parts"] if p["product"]["id"] == self.other_part.id
        )
        self.assertEqual(added["quantity_done"], 1.0)

    def test_add_part_by_a_technician_without_an_email(self):
        self.technician.email = False
        self.app.add_part(repair_id=self.repair.id, product_id=self.other_part.id)

    def test_add_part_reaches_the_quote(self):
        """On purpose: core adds it to the quote, and the note says so."""
        order = self.env["sale.order"].create({"partner_id": self.customer.id})
        self.repair.sale_order_id = order
        self.app.add_part(repair_id=self.repair.id, product_id=self.other_part.id)
        move = self.repair.move_ids.filtered(lambda m: m.product_id == self.other_part)
        self.assertEqual(move.sale_line_id.order_id, order)
        self.assertIn(order.name, self.repair.message_ids[:1].body)

    def test_add_part_needs_a_quantity(self):
        with self.assertRaises(ValidationError):
            self.app.add_part(
                repair_id=self.repair.id, product_id=self.other_part.id, quantity=0
            )
