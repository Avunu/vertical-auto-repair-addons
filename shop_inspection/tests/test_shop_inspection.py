# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestShopInspection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Inspection Customer"})
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Testmake"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Testmodel", "brand_id": brand.id}
        )
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "SHOP-1",
                "owner_id": cls.partner.id,
            }
        )
        cls.repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.partner.id,
                "vehicle_id": cls.vehicle.id,
                "odometer_in": 120000,
            }
        )

    def _create_inspection(self):
        return self.env["fleet.vehicle.inspection"].create(
            {
                "vehicle_id": self.vehicle.id,
                "repair_id": self.repair.id,
            }
        )

    def test_severity_sets_result(self):
        inspection = self._create_inspection()
        line = self.env["fleet.vehicle.inspection.line"].create(
            {
                "inspection_id": inspection.id,
                "inspection_item_id": self.env.ref(
                    "shop_inspection.item_engine_oil"
                ).id,
                "severity": "attention",
            }
        )
        self.assertEqual(line.result, "failure")
        line.severity = "good"
        self.assertEqual(line.result, "success")
        line.severity = "fail_state"
        self.assertEqual(line.result, "failure")

    def test_measurements_prefilled_from_item(self):
        inspection = self._create_inspection()
        line = self.env["fleet.vehicle.inspection.line"].create(
            {
                "inspection_id": inspection.id,
                "inspection_item_id": self.env.ref(
                    "shop_inspection.item_tires_wheels"
                ).id,
            }
        )
        # 4 tread depth + 4 pressure specs
        self.assertEqual(len(line.measurement_ids), 8)
        tread_lf = line.measurement_ids.filtered(
            lambda m: m.spec_id == self.env.ref("shop_inspection.spec_tread_lf")
        )
        self.assertEqual(tread_lf.position, "lf")
        self.assertEqual(tread_lf.spec_min, 4)
        self.assertFalse(tread_lf.out_of_spec)
        tread_lf.value = 3
        self.assertTrue(tread_lf.out_of_spec)
        tread_lf.value = 9
        self.assertFalse(tread_lf.out_of_spec)

    def test_out_of_spec_max(self):
        inspection = self._create_inspection()
        line = self.env["fleet.vehicle.inspection.line"].create(
            {
                "inspection_id": inspection.id,
                "inspection_item_id": self.env.ref("shop_inspection.item_coolant").id,
            }
        )
        freeze = line.measurement_ids
        self.assertEqual(len(freeze), 1)
        # Freeze point of -34°F is below the -20°F max: in spec
        freeze.value = -34
        self.assertFalse(freeze.out_of_spec)
        freeze.value = -10
        self.assertTrue(freeze.out_of_spec)

    def test_measurement_summary(self):
        inspection = self._create_inspection()
        line = self.env["fleet.vehicle.inspection.line"].create(
            {
                "inspection_id": inspection.id,
                "inspection_item_id": self.env.ref(
                    "shop_inspection.item_tires_wheels"
                ).id,
            }
        )
        # Nothing measured yet
        self.assertFalse(line.measurement_summary)
        self.assertFalse(line.measurement_alert)
        tread_lf = line.measurement_ids.filtered(
            lambda m: m.spec_id == self.env.ref("shop_inspection.spec_tread_lf")
        )
        tread_lf.value = 6
        self.assertEqual(line.measurement_summary, "Tread Depth LF: 6 32nds in")
        self.assertFalse(line.measurement_alert)
        tread_lf.value = 3
        self.assertTrue(line.measurement_alert)

    def test_measurements_flattened_on_inspection(self):
        inspection = self._create_inspection()
        for xmlid in ("item_tires_wheels", "item_coolant"):
            self.env["fleet.vehicle.inspection.line"].create(
                {
                    "inspection_id": inspection.id,
                    "inspection_item_id": self.env.ref(
                        f"shop_inspection.{xmlid}"
                    ).id,
                }
            )
        # 8 tire specs + 1 coolant freeze point, reachable in one grid
        self.assertEqual(len(inspection.measurement_ids), 9)
        self.assertEqual(
            inspection.measurement_ids.mapped("line_id"),
            inspection.inspection_line_ids,
        )
        # The line renders as its checklist item in that grid
        tire_line = inspection.inspection_line_ids[0]
        self.assertEqual(
            tire_line.display_name,
            tire_line.inspection_item_id.display_name,
        )

    def test_severity_counts(self):
        inspection = self._create_inspection()
        items = [
            ("item_engine_oil", "attention"),
            ("item_belts", "good"),
            ("item_battery", "good"),
            ("item_brake_lining", "fail_state"),
            ("item_test_drive", "today"),
            ("item_wipers", "future"),
        ]
        for xmlid, severity in items:
            self.env["fleet.vehicle.inspection.line"].create(
                {
                    "inspection_id": inspection.id,
                    "inspection_item_id": self.env.ref(f"shop_inspection.{xmlid}").id,
                    "severity": severity,
                }
            )
        self.assertEqual(inspection.count_good, 2)
        self.assertEqual(inspection.count_attention, 1)
        self.assertEqual(inspection.count_fail_state, 1)
        self.assertEqual(inspection.count_today, 1)
        self.assertEqual(inspection.count_future, 1)
        # Aggregated on the repair order
        self.assertEqual(self.repair.count_good, 2)
        self.assertEqual(self.repair.count_fail_state, 1)
        self.assertEqual(self.repair.inspection_count, 1)

    def test_repair_vehicle_mismatch_blocked(self):
        other_vehicle = self.env["fleet.vehicle"].create(
            {
                "model_id": self.vehicle.model_id.id,
                "license_plate": "SHOP-2",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["fleet.vehicle.inspection"].create(
                {
                    "vehicle_id": other_vehicle.id,
                    "repair_id": self.repair.id,
                }
            )

    def test_onchange_repair_fills_vehicle(self):
        with Form(self.env["fleet.vehicle.inspection"]) as form:
            form.repair_id = self.repair
            self.assertEqual(form.vehicle_id, self.vehicle)
            self.assertEqual(form.odometer, 120000)

    def test_template_load_prefills_measurements(self):
        with Form(self.env["fleet.vehicle.inspection"]) as form:
            form.vehicle_id = self.vehicle
            # The OCA odometer inverse refuses to save an empty odometer
            form.odometer = 120001
            form.inspection_template_id = self.env.ref(
                "shop_inspection.template_courtesy"
            )
        inspection = form.save()
        self.assertEqual(len(inspection.inspection_line_ids), 15)
        tire_line = inspection.inspection_line_ids.filtered(
            lambda line: (
                line.inspection_item_id
                == self.env.ref("shop_inspection.item_tires_wheels")
            )
        )
        self.assertEqual(len(tire_line.measurement_ids), 8)

    def test_confirm_with_severities(self):
        inspection = self._create_inspection()
        self.env["fleet.vehicle.inspection.line"].create(
            {
                "inspection_id": inspection.id,
                "inspection_item_id": self.env.ref("shop_inspection.item_horn").id,
                "severity": "good",
            }
        )
        inspection.button_confirm()
        self.assertEqual(inspection.state, "confirmed")
        self.assertEqual(inspection.result, "success")
