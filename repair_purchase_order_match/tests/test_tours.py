# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestMatchOrderTour(HttpCase):
    def _make_records(self):
        unit = self.env.ref("uom.product_uom_unit")
        part = self.env["product.product"].create(
            {
                "name": "Tour Part",
                "default_code": "TOUR-PART-1",
                "type": "consu",
                "is_storable": True,
            }
        )
        item = self.env["product.product"].create(
            {"name": "Tour Widget", "type": "consu", "is_storable": True}
        )
        repair = self.env["repair.order"].create(
            {
                "product_id": item.id,
                "product_uom": unit.id,
                "partner_id": self.env["res.partner"]
                .create({"name": "Tour Customer"})
                .id,
            }
        )
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.env["res.partner"]
                .create({"name": "Tour Vendor"})
                .id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": part.id,
                            "name": part.name,
                            "product_qty": 3.0,
                            "product_uom": unit.id,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return repair, po

    def test_match_order_dialog(self):
        repair, po = self._make_records()
        self.start_tour(
            f"/odoo/action-repair.action_repair_order_tree/{repair.id}",
            "repair_match_order_tour",
            login="admin",
        )
        self.assertEqual(repair.move_ids.created_purchase_line_ids, po.order_line)

    def test_match_repair_dialog(self):
        repair, po = self._make_records()
        self.start_tour(
            f"/odoo/action-purchase.purchase_form_action/{po.id}",
            "repair_match_repair_tour",
            login="admin",
        )
        self.assertEqual(repair.move_ids.created_purchase_line_ids, po.order_line)
