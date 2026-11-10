# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime

from odoo.tests import TransactionCase, tagged

REPORT = "shop_scheduling.report_shop_schedule"


@tagged("post_install", "-at_install")
class TestShopSchedulePrint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = "America/New_York"
        cls.tina = cls.env["res.users"].create(
            {"name": "Tina Torque", "login": "tina.print"}
        )
        cls.wanda = cls.env["res.users"].create(
            {"name": "Wanda Wrench", "login": "wanda.print"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Print Customer"})
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Printmake"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Printmodel", "brand_id": brand.id}
        )
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "PRINT-1",
                "owner_id": cls.partner.id,
            }
        )
        # 2026-11-09 is a Monday. New York is UTC-5 then, so 14:00 UTC is
        # 09:00 on the wall clock.
        cls.afternoon = cls._repair(datetime(2026, 11, 9, 19, 0), cls.wanda, 2.0)
        cls.morning = cls._repair(datetime(2026, 11, 9, 14, 0), cls.tina, 1.5)
        cls.tuesday = cls._repair(datetime(2026, 11, 10, 15, 0), cls.tina, 1.0)
        # 03:00 UTC Tuesday is 22:00 Monday on the wall clock.
        cls.late = cls._repair(datetime(2026, 11, 10, 3, 0), cls.tina, 1.0)
        cls.unscheduled = cls.env["repair.order"].create(
            {"partner_id": cls.partner.id, "vehicle_id": cls.vehicle.id}
        )
        cls.report = cls.env["report.shop_scheduling.report_shop_schedule"]

    @classmethod
    def _repair(cls, start, technician, hours):
        return cls.env["repair.order"].create(
            {
                "partner_id": cls.partner.id,
                "vehicle_id": cls.vehicle.id,
                "schedule_date": start,
                "planned_duration": hours,
                "technician_id": technician.id,
            }
        )

    def _values(self, repairs, **data):
        return self.report._get_report_values(repairs.ids, data)

    def test_only_the_jobs_handed_over_print(self):
        # The calendar sends what its filters left on screen, nothing more.
        values = self._values(self.morning | self.tuesday)
        printed = [line["repair"] for day in values["days"] for line in day["lines"]]
        self.assertEqual(printed, [self.morning, self.tuesday])

    def test_a_day_is_the_users_day_not_utc(self):
        days = self._values(self.morning | self.late | self.tuesday)["days"]
        monday, tuesday = days
        # The 22:00 job is Monday on the wall clock though it is stored as
        # Tuesday, and it follows the morning job.
        self.assertEqual(
            [line["repair"] for line in monday["lines"]], [self.morning, self.late]
        )
        self.assertEqual([line["repair"] for line in tuesday["lines"]], [self.tuesday])
        self.assertIn("Monday", monday["label"])

    def test_the_timezone_the_calendar_draws_in_wins(self):
        days = self.report.with_context(tz="Asia/Tokyo")._shop_schedule_days(
            self.morning | self.late
        )
        # Tokyo is UTC+9: 14:00 UTC is 23:00 Monday, 03:00 UTC is 12:00 Tuesday.
        self.assertEqual([len(day["lines"]) for day in days], [1, 1])

    def test_jobs_list_in_time_order_whatever_the_ids(self):
        values = self._values(self.afternoon | self.morning)
        lines = values["days"][0]["lines"]
        self.assertEqual(
            [line["repair"] for line in lines], [self.morning, self.afternoon]
        )
        self.assertEqual(lines[0]["hours"], "01:30")

    def test_an_unscheduled_job_is_left_off(self):
        values = self._values(self.morning | self.unscheduled)
        self.assertEqual(values["docs"], self.morning)

    def test_a_job_without_a_duration_has_no_end_or_hours(self):
        self.morning.planned_duration = 0
        line = self._values(self.morning)["days"][0]["lines"][0]
        self.assertFalse(line["hours"])
        self.assertNotIn("–", line["time"])

    def test_report_renders_the_jobs_under_the_calendar_title(self):
        html = (
            self.env["ir.actions.report"]
            ._render_qweb_html(
                REPORT, (self.morning | self.tuesday).ids, data={"title": "Week 46"}
            )[0]
            .decode()
        )
        self.assertIn("Week 46", html)
        self.assertIn(self.morning.name, html)
        self.assertIn("PRINT-1", html)
        self.assertIn("Tina Torque", html)

    def test_an_empty_calendar_says_so(self):
        html = self.env["ir.actions.report"]._render_qweb_html(REPORT, [])[0].decode()
        self.assertIn("Nothing is scheduled", html)
