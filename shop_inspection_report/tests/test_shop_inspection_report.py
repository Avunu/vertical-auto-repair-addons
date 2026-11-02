# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import HttpCase, TransactionCase, tagged


class TestShopInspectionReportCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Report Customer", "email": "report.customer@example.com"}
        )
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Reportmake"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Reportmodel", "brand_id": brand.id}
        )
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "REP-1",
                "unit_number": "T-104",
                "owner_id": cls.partner.id,
            }
        )
        cls.repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.partner.id,
                "vehicle_id": cls.vehicle.id,
                "odometer_in": 55000,
            }
        )
        cls.inspection = cls.env["fleet.vehicle.inspection"].create(
            {
                "vehicle_id": cls.vehicle.id,
                "repair_id": cls.repair.id,
            }
        )
        Line = cls.env["fleet.vehicle.inspection.line"]
        cls.line_fail = Line.create(
            {
                "inspection_id": cls.inspection.id,
                "inspection_item_id": cls.env.ref(
                    "shop_inspection.item_brake_lining"
                ).id,
                "severity": "fail_state",
                "result_description": "Pads below spec",
                "condition_ids": [
                    (4, cls.env.ref("shop_inspection.condition_worn_beyond_spec").id)
                ],
                "recommended_action_ids": [
                    (4, cls.env.ref("shop_inspection.action_replace_brakes").id)
                ],
            }
        )
        cls.line_good = Line.create(
            {
                "inspection_id": cls.inspection.id,
                "inspection_item_id": cls.env.ref("shop_inspection.item_horn").id,
                "severity": "good",
            }
        )


@tagged("post_install", "-at_install")
class TestShopInspectionReport(TestShopInspectionReportCommon):
    def test_report_sections(self):
        sections = self.repair._shop_report_sections()
        self.assertEqual(
            [section["severity"] for section in sections], ["good", "fail_state"]
        )
        fail_section = sections[-1]
        self.assertEqual(fail_section["count"], 1)
        self.assertEqual(fail_section["lines"], self.line_fail)
        self.assertEqual(
            fail_section["categories"][0]["category"],
            self.env.ref("shop_inspection.category_state_safety"),
        )

    def test_access_url(self):
        self.assertEqual(
            self.repair.access_url, f"/my/inspections/{self.repair.id}"
        )

    def test_report_renders(self):
        html = self.env["ir.actions.report"]._render_qweb_html(
            "shop_inspection_report.action_report_shop_inspection",
            [self.repair.id],
        )[0]
        self.assertIn(b"Vehicle Inspection Report", html)
        self.assertIn(b"Brake Lining", html)
        self.assertIn(b"Pads below spec", html)
        self.assertIn(b"T-104", html)

    def test_send_report_action(self):
        action = self.repair.action_send_inspection_report()
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertTrue(self.repair.access_token)


@tagged("post_install", "-at_install")
class TestShopInspectionPortal(HttpCase):
    def test_portal_page_with_token(self):
        partner = self.env["res.partner"].create(
            {"name": "Token Customer", "email": "token.customer@example.com"}
        )
        brand = self.env["fleet.vehicle.model.brand"].create({"name": "Tokmake"})
        model = self.env["fleet.vehicle.model"].create(
            {"name": "Tokmodel", "brand_id": brand.id}
        )
        vehicle = self.env["fleet.vehicle"].create(
            {"model_id": model.id, "license_plate": "TOK-1", "owner_id": partner.id}
        )
        repair = self.env["repair.order"].create(
            {"partner_id": partner.id, "vehicle_id": vehicle.id}
        )
        inspection = self.env["fleet.vehicle.inspection"].create(
            {"vehicle_id": vehicle.id, "repair_id": repair.id}
        )
        self.env["fleet.vehicle.inspection.line"].create(
            {
                "inspection_id": inspection.id,
                "inspection_item_id": self.env.ref("shop_inspection.item_horn").id,
                "severity": "good",
            }
        )
        token = repair._portal_ensure_token()
        self.env.flush_all()
        response = self.url_open(
            f"/my/inspections/{repair.id}?access_token={token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Vehicle Inspection Report", response.text)
        # Without a token, anonymous access is denied (redirects away)
        response = self.url_open(f"/my/inspections/{repair.id}")
        self.assertNotIn("Vehicle Inspection Report", response.text)
