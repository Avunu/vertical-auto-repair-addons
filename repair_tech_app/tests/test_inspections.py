# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PNG_1PX, TechCase


@tagged("post_install", "-at_install")
class TestInspections(TechCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["shop.inspection.category"].create(
            {"name": "Brakes", "sequence": 10}
        )
        cls.condition = cls.env["shop.inspection.condition"].create({"name": "Worn"})
        cls.action = cls.env["shop.inspection.action"].create({"name": "Replace pads"})
        cls.item = cls.env["fleet.vehicle.inspection.item"].create(
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
        cls.item_2 = cls.env["fleet.vehicle.inspection.item"].create(
            {"name": "Rear brake pads", "category_id": cls.category.id}
        )
        cls.template = cls.env["fleet.vehicle.inspection.template"].create(
            {
                "name": "Brake Check",
                "inspection_template_line_ids": [
                    (
                        0,
                        0,
                        {"inspection_template_item_id": cls.item.id, "sequence": 10},
                    ),
                    (
                        0,
                        0,
                        {"inspection_template_item_id": cls.item_2.id, "sequence": 20},
                    ),
                ],
            }
        )

    def start(self, odometer=42010):
        return self.app.create_inspection(
            repair_id=self.repair.id, template_id=self.template.id, odometer=odometer
        )

    def lines(self, detail):
        return {line["name"]: line for line in detail["lines"]}

    def test_list_offers_the_checklists(self):
        listing = self.app.inspections(repair_id=self.repair.id)
        self.assertIn(self.template.id, self.ids(listing["templates"]))
        self.assertTrue(listing["has_vehicle"])
        self.assertEqual(listing["default_odometer"], 42000)
        self.assertEqual(listing["odometer_unit"], "miles")

    def test_create_from_a_checklist(self):
        detail = self.start()
        inspection = self.repair.inspection_ids
        self.assertEqual(detail["inspection"]["id"], inspection.id)
        self.assertEqual(inspection.vehicle_id, self.vehicle)
        self.assertEqual(inspection.odometer, 42010)
        self.assertEqual(
            list(self.lines(detail)), ["Front brake pads", "Rear brake pads"]
        )
        pads = self.lines(detail)["Front brake pads"]
        self.assertEqual(pads["category"]["name"], "Brakes")
        self.assertEqual(pads["measurements"][0]["name"], "Pad thickness")
        self.assertEqual(pads["measurements"][0]["position_label"], "Left Front")
        self.assertTrue(detail["editable"])

    def test_create_needs_an_odometer(self):
        with self.assertRaises(ValidationError):
            self.start(odometer=0)

    def test_create_needs_a_vehicle(self):
        self.repair.vehicle_id = False
        self.assertFalse(self.app.inspections(repair_id=self.repair.id)["has_vehicle"])
        with self.assertRaisesRegex(UserError, "no vehicle"):
            self.start()

    def test_item_offers_its_own_choices_first(self):
        self.env["shop.inspection.condition"].create({"name": "Aardvark-chewed"})
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        detail = self.app.inspection_line(line_id=line_id)
        self.assertEqual(detail["conditions"][0]["id"], self.condition.id)
        self.assertEqual(detail["actions"][0]["id"], self.action.id)
        self.assertEqual(len(detail["severities"]), 6)

    def test_grade(self):
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        detail = self.app.grade(
            line_id=line_id,
            severity="attention",
            condition_ids=[self.condition.id],
            action_ids=[self.action.id],
            note="Down to the wear indicator",
        )
        pads = self.lines(detail)["Front brake pads"]
        self.assertEqual(pads["severity"], "attention")
        self.assertEqual(pads["note"], "Down to the wear indicator")
        self.assertEqual(
            pads["conditions"], [{"id": self.condition.id, "name": "Worn"}]
        )
        line = self.env["fleet.vehicle.inspection.line"].browse(line_id)
        self.assertEqual(line.result, "failure", "shop_inspection maps the grade")
        self.assertEqual(detail["inspection"]["counts"]["attention"], 1)

    def test_grade_leaves_what_it_isnt_given(self):
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        self.app.grade(
            line_id=line_id, severity="attention", condition_ids=[self.condition.id]
        )
        detail = self.app.grade(line_id=line_id, severity="future")
        self.assertEqual(len(self.lines(detail)["Front brake pads"]["conditions"]), 1)

    def test_not_applicable_passes(self):
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        self.app.grade(line_id=line_id, severity="na")
        line = self.env["fleet.vehicle.inspection.line"].browse(line_id)
        self.assertEqual(line.result, "success")

    def test_an_unknown_grade(self):
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        with self.assertRaises(ValidationError):
            self.app.grade(line_id=line_id, severity="meh")

    def test_measurement_out_of_spec(self):
        pads = self.lines(self.start())["Front brake pads"]
        detail = self.app.set_measurement(
            measurement_id=pads["measurements"][0]["id"], value=2.0
        )
        measurement = detail["line"]["measurements"][0]
        self.assertEqual(measurement["value"], 2.0)
        self.assertTrue(measurement["out_of_spec"])
        self.assertTrue(detail["line"]["measurement_alert"])

    def test_photos(self):
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        detail = self.app.add_photo(
            line_id=line_id,
            image=f"data:image/png;base64,{PNG_1PX}",
            filename="pads.png",
        )
        (photo,) = detail["photos"]
        self.assertEqual(photo["name"], "pads.png")
        self.assertTrue(photo["url"].endswith("/image_512"))
        self.assertEqual(detail["line"]["photo_count"], 1)
        detail = self.app.add_photo(line_id=line_id, image=PNG_1PX)
        self.assertEqual(len(detail["photos"]), 2, "bare base64 too")
        detail = self.app.remove_photo(photo_id=photo["id"])
        self.assertEqual(len(detail["photos"]), 1)

    def test_photo_that_isnt_one(self):
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        with self.assertRaisesRegex(UserError, "didn't arrive whole"):
            self.app.add_photo(line_id=line_id, image="not base64 at all!!")

    def test_photo_required_for_problems(self):
        self.env["ir.config_parameter"].set_param(
            "repair_tech_app.require_photo_on_fail", True
        )
        line_id = self.lines(self.start())["Front brake pads"]["id"]
        with self.assertRaisesRegex(UserError, "Take a photo"):
            self.app.grade(line_id=line_id, severity="today")
        self.app.grade(line_id=line_id, severity="good")  # a clean grade is fine
        self.app.add_photo(line_id=line_id, image=PNG_1PX)
        self.app.grade(line_id=line_id, severity="today")

    def test_confirm_waits_for_every_grade(self):
        detail = self.start()
        with self.assertRaisesRegex(UserError, "2 items still need a grade"):
            self.app.confirm_inspection(inspection_id=detail["inspection"]["id"])

    def test_confirm(self):
        detail = self.start()
        for line in detail["lines"]:
            self.app.grade(line_id=line["id"], severity="good")
        listing = self.app.confirm_inspection(inspection_id=detail["inspection"]["id"])
        (summary,) = listing["records"]
        self.assertEqual(summary["state"], "confirmed")
        self.assertEqual(summary["graded_count"], 2)

    def test_confirmed_is_read_only(self):
        detail = self.start()
        for line in detail["lines"]:
            self.app.grade(line_id=line["id"], severity="good")
        self.app.confirm_inspection(inspection_id=detail["inspection"]["id"])
        line_id = detail["lines"][0]["id"]
        self.assertFalse(self.app.inspection_line(line_id=line_id)["editable"])
        with self.assertRaisesRegex(UserError, "completed"):
            self.app.grade(line_id=line_id, severity="today")
        with self.assertRaisesRegex(UserError, "completed"):
            self.app.add_photo(line_id=line_id, image=PNG_1PX)

    def test_grades_count_on_the_job(self):
        lines = self.start()["lines"]
        self.app.grade(line_id=lines[0]["id"], severity="today")
        job = self.app.job(repair_id=self.repair.id)
        self.assertEqual((job["inspection_graded"], job["inspection_total"]), (1, 2))
        self.assertEqual(job["inspection_count"], 1)
