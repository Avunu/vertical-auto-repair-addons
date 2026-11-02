# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64

from odoo.tests.common import tagged

from .common import RepairJobCase

# 1x1 transparent PNG -- small enough to inline, real enough for image.mixin.
PNG_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@tagged("post_install", "-at_install")
class TestInspection(RepairJobCase):
    @classmethod
    def setUpClassBaseData(cls):
        super().setUpClassBaseData()
        cls.category = (
            cls.env["shop.inspection.category"]
            .sudo()
            .create({"name": "Brakes", "sequence": 10})
        )
        cls.condition = (
            cls.env["shop.inspection.condition"].sudo().create({"name": "Worn"})
        )
        cls.action = (
            cls.env["shop.inspection.action"].sudo().create({"name": "Replace pads"})
        )
        cls.item = (
            cls.env["fleet.vehicle.inspection.item"]
            .sudo()
            .create(
                {
                    "name": "Front brake pads",
                    "category_id": cls.category.id,
                    "condition_ids": [(4, cls.condition.id)],
                    "recommended_action_ids": [(4, cls.action.id)],
                    "measurement_spec_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Pad thickness",
                                "position": "lf",
                                "uom": "mm",
                                "spec_min": 3.0,
                            },
                        )
                    ],
                }
            )
        )
        cls.item_2 = (
            cls.env["fleet.vehicle.inspection.item"]
            .sudo()
            .create({"name": "Rear brake pads", "category_id": cls.category.id})
        )
        cls.template = (
            cls.env["fleet.vehicle.inspection.template"]
            .sudo()
            .create(
                {
                    "name": "Brake Check",
                    "inspection_template_line_ids": [
                        (0, 0, {"inspection_template_item_id": cls.item.id,
                                "sequence": 10}),
                        (0, 0, {"inspection_template_item_id": cls.item_2.id,
                                "sequence": 20}),
                    ],
                }
            )
        )

    def _new_inspection(self, odometer=42000):
        response = self._dispatch(
            "inspection_create",
            repair_id=self.repair.id,
            template_id=self.template.id,
            odometer=odometer,
        )
        return response

    def test_inspection_list_offers_templates(self):
        response = self._dispatch("inspections", repair_id=self.repair.id)
        self.assert_next_state(response, "inspection_list")
        data = self.state_data(response)
        self.assertIn(
            self.template.id, [tpl["id"] for tpl in data["templates"]]
        )
        self.assertEqual(data["default_odometer"], 42000)

    def test_inspection_create_loads_the_template(self):
        response = self._new_inspection()
        self.assert_no_error(response)
        self.assert_next_state(response, "inspection_lines")
        lines = self.state_data(response)["lines"]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["name"], "Front brake pads")
        self.assertEqual(lines[0]["category"]["name"], "Brakes")

    def test_inspection_create_prefills_measurements(self):
        lines = self.state_data(self._new_inspection())["lines"]
        measurements = lines[0]["measurements"]
        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0]["name"], "Pad thickness")
        self.assertEqual(measurements[0]["spec_min"], 3.0)
        self.assertEqual(measurements[0]["value"], 0.0)

    def test_inspection_create_links_to_the_job_and_vehicle(self):
        self._new_inspection()
        inspection = self.repair.inspection_ids
        self.assertEqual(len(inspection), 1)
        self.assertEqual(inspection.vehicle_id, self.vehicle)
        self.assertEqual(inspection.technician_id, self.technician)
        self.assertEqual(inspection.odometer, 42000)

    def test_inspection_create_refuses_a_blank_odometer(self):
        """The OCA odometer inverse raises; we want a usable message instead."""
        response = self._new_inspection(odometer=0)
        self.assert_error(response)
        self.assert_next_state(response, "inspection_list")
        self.assertFalse(self.repair.inspection_ids)

    def test_inspection_create_needs_a_vehicle(self):
        repair = self.env["repair.order"].sudo().create(
            {"partner_id": self.customer.id, "technician_id": self.technician.id}
        )
        response = self._dispatch(
            "inspection_create",
            repair_id=repair.id,
            template_id=self.template.id,
            odometer=1000,
        )
        self.assert_error(response)

    def test_line_detail_offers_the_items_choices_first(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids.filtered(
            lambda ln: ln.inspection_item_id == self.item
        )
        data = self.state_data(
            self._dispatch("inspection_line", line_id=line.id)
        )
        self.assertEqual(data["choices"]["conditions"][0]["id"], self.condition.id)
        self.assertEqual(data["choices"]["actions"][0]["id"], self.action.id)
        self.assertEqual(len(data["choices"]["severities"]), 6)

    def test_grade_sets_severity_and_the_oca_result(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids[0]
        response = self._dispatch(
            "grade",
            line_id=line.id,
            severity="attention",
            condition_ids=[self.condition.id],
            action_ids=[self.action.id],
            note="Down to the wear indicator",
        )
        self.assert_no_error(response)
        self.assertEqual(line.severity, "attention")
        # shop_inspection maps severity onto the pass/fail result the OCA
        # confirm gate reads.
        self.assertEqual(line.result, "failure")
        self.assertEqual(line.condition_ids, self.condition)
        self.assertEqual(line.result_description, "Down to the wear indicator")

    def test_grade_na_counts_as_a_pass(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids[0]
        self._dispatch("grade", line_id=line.id, severity="na")
        self.assertEqual(line.result, "success")

    def test_set_measurement_flags_out_of_spec(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids.filtered(
            lambda ln: ln.inspection_item_id == self.item
        )
        measurement = line.measurement_ids
        response = self._dispatch(
            "set_measurement", measurement_id=measurement.id, value=2.0
        )
        self.assert_no_error(response)
        self.assertEqual(measurement.value, 2.0)
        self.assertTrue(measurement.out_of_spec)

    def test_add_photo_accepts_a_data_url(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids[0]
        response = self._dispatch(
            "add_photo",
            line_id=line.id,
            image_b64=f"data:image/png;base64,{PNG_1PX}",
            filename="pads.png",
        )
        self.assert_no_error(response)
        self.assertEqual(len(line.inspection_line_image_ids), 1)
        self.assertEqual(
            base64.b64encode(base64.b64decode(PNG_1PX)).decode(),
            PNG_1PX,
        )

    def test_add_photo_rejects_junk(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids[0]
        response = self._dispatch(
            "add_photo", line_id=line.id, image_b64="not base64 at all!!"
        )
        self.assert_error(response)
        self.assertFalse(line.inspection_line_image_ids)

    def test_confirm_blocked_while_items_are_ungraded(self):
        self._new_inspection()
        inspection = self.repair.inspection_ids
        response = self._dispatch(
            "confirm_inspection", inspection_id=inspection.id
        )
        self.assert_error(response)
        self.assertIn("2", response["message"]["body"])
        self.assertEqual(inspection.state, "draft")

    def test_confirm_when_everything_is_graded(self):
        self._new_inspection()
        inspection = self.repair.inspection_ids
        for line in inspection.inspection_line_ids:
            self._dispatch("grade", line_id=line.id, severity="good")
        response = self._dispatch(
            "confirm_inspection", inspection_id=inspection.id
        )
        self.assert_no_error(response)
        self.assert_next_state(response, "inspection_list")
        self.assertEqual(inspection.state, "confirmed")

    def test_confirmed_inspection_is_read_only(self):
        self._new_inspection()
        inspection = self.repair.inspection_ids
        for line in inspection.inspection_line_ids:
            self._dispatch("grade", line_id=line.id, severity="good")
        self._dispatch("confirm_inspection", inspection_id=inspection.id)
        response = self._dispatch(
            "grade", line_id=inspection.inspection_line_ids[0].id, severity="today"
        )
        self.assert_error(response)

    def test_photo_required_option_blocks_a_problem_grade(self):
        self._new_inspection()
        line = self.repair.inspection_ids.inspection_line_ids[0]
        service = self.service_for(options={"require_photo_on_fail": True})
        response = service.dispatch(
            "grade", params={"line_id": line.id, "severity": "today"}
        )
        self.assert_error(response)
        self.assertFalse(line.severity)
        # A clean grade is unaffected.
        response = service.dispatch(
            "grade", params={"line_id": line.id, "severity": "good"}
        )
        self.assert_no_error(response)

    def test_severity_counters_roll_up_to_the_job(self):
        self._new_inspection()
        lines = self.repair.inspection_ids.inspection_line_ids
        self._dispatch("grade", line_id=lines[0].id, severity="today")
        self._dispatch("grade", line_id=lines[1].id, severity="good")
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        self.assertEqual(record["inspection_total"], 2)
        self.assertEqual(record["inspection_graded"], 2)
