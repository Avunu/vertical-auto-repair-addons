# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestShopEstimate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Estimate Customer"})
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Estmake"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Estmodel", "brand_id": brand.id}
        )
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "EST-1",
                "owner_id": cls.partner.id,
            }
        )
        cls.labor = cls.env["product.product"].create(
            {
                "name": "Shop Labor",
                "type": "service",
                "list_price": 100.0,
                "invoice_policy": "order",
            }
        )
        cls.pads = cls.env["product.product"].create(
            {
                "name": "Brake Pads",
                "type": "consu",
                "is_storable": True,
                "list_price": 80.0,
            }
        )
        cls.rotors = cls.env["product.product"].create(
            {
                "name": "Rotors",
                "type": "consu",
                "is_storable": True,
                "list_price": 120.0,
            }
        )
        cls.brake_job = cls.env["shop.service.job"].create(
            {
                "name": "Front Brake Job",
                "pricing": "fixed",
                "price_fixed": 450.0,
                "customer_description": "Replace front pads and rotors",
                "labor_product_id": cls.labor.id,
                "labor_hours": 2.0,
                "part_line_ids": [
                    (0, 0, {"product_id": cls.pads.id, "quantity": 1}),
                    (0, 0, {"product_id": cls.rotors.id, "quantity": 2}),
                ],
            }
        )
        cls.env.ref("shop_inspection.action_replace_brakes").job_id = cls.brake_job
        cls.wiper_job = cls.env["shop.service.job"].create(
            {
                "name": "Wiper Replacement",
                "pricing": "computed",
                "labor_product_id": cls.labor.id,
                "labor_hours": 0.5,
            }
        )
        cls.env.ref("shop_inspection.action_replace_wipers").job_id = cls.wiper_job

        cls.repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.partner.id,
                "vehicle_id": cls.vehicle.id,
            }
        )
        cls.inspection = cls.env["fleet.vehicle.inspection"].create(
            {"vehicle_id": cls.vehicle.id, "repair_id": cls.repair.id}
        )
        Line = cls.env["fleet.vehicle.inspection.line"]
        cls.finding_brakes = Line.create(
            {
                "inspection_id": cls.inspection.id,
                "inspection_item_id": cls.env.ref(
                    "shop_inspection.item_brake_lining"
                ).id,
                "severity": "fail_state",
                "result_description": "Front pads at 2/32",
                "recommended_action_ids": [
                    (4, cls.env.ref("shop_inspection.action_replace_brakes").id)
                ],
            }
        )
        cls.finding_wipers = Line.create(
            {
                "inspection_id": cls.inspection.id,
                "inspection_item_id": cls.env.ref("shop_inspection.item_wipers").id,
                "severity": "attention",
                "recommended_action_ids": [
                    (4, cls.env.ref("shop_inspection.action_replace_wipers").id)
                ],
            }
        )

    def _run_builder(self):
        wizard = (
            self.env["shop.estimate.builder"]
            .with_context(
                active_model="repair.order", active_id=self.repair.id
            )
            .create({})
        )
        return wizard

    def test_job_pricing(self):
        self.assertEqual(self.brake_job.price_total, 450.0)
        self.assertEqual(self.wiper_job.price_total, 50.0)

    def test_builder_defaults(self):
        wizard = self._run_builder()
        self.assertEqual(len(wizard.line_ids), 2)
        brake_line = wizard.line_ids.filtered(
            lambda line: line.finding_line_id == self.finding_brakes
        )
        self.assertTrue(brake_line.must_do)
        self.assertEqual(brake_line.job_id, self.brake_job)
        self.assertEqual(brake_line.price_unit, 450.0)
        wiper_line = wizard.line_ids - brake_line
        self.assertFalse(wiper_line.must_do)
        self.assertEqual(wiper_line.job_id, self.wiper_job)

    def test_full_flow(self):
        wizard = self._run_builder()
        wizard.action_generate()
        order = self.repair.sale_order_id
        self.assertTrue(order)
        self.assertTrue(order.require_signature)

        # Must-do finding became a firm order line, optional one an option
        job_lines = order.order_line.filtered("shop_job_id")
        self.assertEqual(len(job_lines), 1)
        self.assertEqual(job_lines.shop_job_id, self.brake_job)
        self.assertEqual(job_lines.price_unit, 450.0)
        self.assertIn("Front pads at 2/32", job_lines.name)
        options = order.sale_order_option_ids
        self.assertEqual(len(options), 1)
        self.assertEqual(options.shop_job_id, self.wiper_job)
        self.assertFalse(options.line_id)
        self.assertTrue(self.finding_brakes.shop_quoted)
        self.assertTrue(self.finding_wipers.shop_quoted)

        # Customer opts into the wiper job from the portal
        options.add_option_to_order()
        wiper_line = options.line_id
        self.assertEqual(wiper_line.shop_job_id, self.wiper_job)
        self.assertEqual(wiper_line.shop_repair_id, self.repair)

        line_count_before = len(order.order_line)
        order.action_confirm()

        # Approved jobs exploded into the repair order…
        moves = self.repair.move_ids.filtered("shop_job_sale_line_id")
        self.assertEqual(len(moves), 2)
        rotor_move = moves.filtered(lambda m: m.product_id == self.rotors)
        self.assertEqual(rotor_move.product_uom_qty, 2)
        self.assertEqual(rotor_move.repair_line_type, "add")
        services = self.repair.repair_service_ids.filtered(
            "shop_job_sale_line_id"
        )
        self.assertEqual(len(services), 2)
        self.assertEqual(
            sorted(services.mapped("product_uom_qty")), [0.5, 2.0]
        )
        # …without creating extra sale order lines (no double billing)
        self.assertEqual(len(order.order_line), line_count_before)
        self.assertFalse(moves.sale_line_id)
        self.assertFalse(services.sale_line_id)
        self.assertTrue(
            order.order_line.filtered("shop_job_id").mapped("shop_job_exploded")
        )

        # Chatter summary on the repair order mentions the approved job
        messages = self.repair.message_ids.mapped("body")
        self.assertTrue(
            any("Front Brake Job" in message for message in messages)
        )

    def test_declined_option_stays_declined(self):
        wizard = self._run_builder()
        wizard.action_generate()
        order = self.repair.sale_order_id
        option = order.sale_order_option_ids
        order.action_confirm()
        # The declined job never touches the repair order
        self.assertFalse(option.line_id)
        self.assertFalse(
            self.repair.repair_service_ids.filtered(
                lambda s: s.shop_job_sale_line_id.shop_job_id == self.wiper_job
            )
        )
        messages = self.repair.message_ids.mapped("body")
        self.assertTrue(
            any("Wiper Replacement" in message for message in messages)
        )

    def test_rerun_excludes_quoted_findings(self):
        wizard = self._run_builder()
        wizard.action_generate()
        rerun = self._run_builder()
        self.assertFalse(rerun.line_ids)

    def test_job_product_autocreated(self):
        self.assertFalse(self.brake_job.product_id)
        wizard = self._run_builder()
        wizard.action_generate()
        product = self.brake_job.product_id
        self.assertTrue(product)
        self.assertEqual(product.type, "service")
        self.assertEqual(product.invoice_policy, "order")
        # Re-running keeps the same product
        self.assertEqual(self.brake_job._ensure_product(), product)
