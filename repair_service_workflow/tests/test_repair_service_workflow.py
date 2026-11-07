# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRepairServiceWorkflow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Acme Trucking"})
        cls.labor = cls.env["product.product"].create(
            {
                "name": "Shop Labor",
                "type": "service",
                "invoice_policy": "order",
                "list_price": 150.0,
            }
        )
        cls.diag_fee = cls.env["product.product"].create(
            {
                "name": "Diagnostic Fee",
                "type": "service",
                "invoice_policy": "order",
                "list_price": 125.0,
            }
        )
        cls.repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.partner.id,
                "repair_service_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.diag_fee.id,
                            "product_uom_qty": 1.0,
                            "accepted": True,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.labor.id,
                            "product_uom_qty": 2.0,
                            "accepted": False,
                        },
                    ),
                ],
            }
        )

    def _service(self, product):
        return self.repair.repair_service_ids.filtered(
            lambda s: s.product_id == product
        )

    def test_only_accepted_services_get_sale_line(self):
        self.repair.action_create_sale_order()
        accepted = self._service(self.diag_fee)
        self.assertTrue(accepted.sale_line_id)

    def test_unaccepted_services_are_archived_on_quotation(self):
        unaccepted = self._service(self.labor)
        self.repair.action_create_sale_order()
        unaccepted.invalidate_recordset()
        self.assertFalse(unaccepted.active)
        self.assertFalse(unaccepted.sale_line_id)
        self.assertNotIn(unaccepted, self.repair.repair_service_ids)

    def test_actual_time_sums_logged_lines(self):
        service = self._service(self.diag_fee)
        self.env["account.analytic.line"].create(
            [
                {
                    "name": "Stint 1",
                    "repair_service_id": service.id,
                    "unit_amount": 1.5,
                },
                {
                    "name": "Stint 2",
                    "repair_service_id": service.id,
                    "unit_amount": 0.5,
                },
            ]
        )
        self.assertEqual(service.actual_time, 2.0)

    def test_confirm_wizard_writes_back_acceptance_and_confirms(self):
        wizard_model = self.env["repair.service.confirm.wizard"].with_context(
            active_model="repair.order", active_id=self.repair.id
        )
        defaults = wizard_model.default_get(list(wizard_model._fields))
        wizard = wizard_model.create(defaults)
        self.assertEqual(len(wizard.service_line_ids), 2)
        line = wizard.service_line_ids.filtered(
            lambda service: service.product_id == self.labor
        )
        line.accepted = True
        wizard.action_confirm()
        self.assertEqual(self.repair.state, "confirmed")
        self.assertTrue(self._service(self.labor).accepted)

    def test_finalize_wizard_only_lists_accepted_services(self):
        self.repair.action_repair_start()
        wizard_model = self.env["repair.service.finalize.wizard"].with_context(
            active_model="repair.order", active_id=self.repair.id
        )
        defaults = wizard_model.default_get(list(wizard_model._fields))
        wizard = wizard_model.create(defaults)
        self.assertEqual(len(wizard.service_line_ids), 1)
        self.assertEqual(wizard.service_line_ids.product_id, self.diag_fee)
        wizard.action_finalize()
        self.assertEqual(self.repair.state, "done")

    def test_quick_create_defaults_apply_only_to_new_products(self):
        # "Ordered Quantities" (ordered_prepaid), not "Based on Timesheets":
        # the latter invoices off qty_delivered, which Odoo only populates
        # from timesheets logged against an auto-created project task -- a
        # mechanism this shop's time tracking (repair.service /
        # account.analytic.line, no project/task involved) never feeds,
        # leaving nothing to invoice. product_uom_qty (synced from
        # actual_time) is what should drive invoicing here instead.
        new_product = (
            self.env["product.product"]
            .with_context(
                default_purchase_ok=False,
                default_type="service",
                default_service_policy="ordered_prepaid",
            )
            .create({"name": "New Diagnostic"})
        )
        self.assertFalse(new_product.purchase_ok)
        self.assertEqual(new_product.type, "service")
        self.assertEqual(new_product.service_policy, "ordered_prepaid")
        self.assertEqual(new_product.invoice_policy, "order")
        # An existing product's own configuration is untouched by the
        # same context.
        self.diag_fee.with_context(
            default_purchase_ok=False, default_type="service"
        ).invalidate_recordset()
        self.assertEqual(self.diag_fee.type, "service")
