# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import tagged

from .common import RepairJobCase


@tagged("post_install", "-at_install")
class TestJobList(RepairJobCase):
    def test_jobs_lists_my_assigned_jobs(self):
        response = self._dispatch("jobs")
        self.assert_next_state(response, "job_list")
        ids = [rec["id"] for rec in self.state_data(response)["records"]]
        self.assertIn(self.repair.id, ids)

    def test_jobs_excludes_another_technicians_job(self):
        other = self.env["res.users"].sudo().create(
            {"name": "Other Tech", "login": "other.tech"}
        )
        theirs = self._make_repair(technician=other)
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertNotIn(theirs.id, ids)

    def _other_technician(self):
        user = self.env["res.users"].sudo().create(
            {"name": "Other Tech", "login": "other.tech"}
        )
        self.env["hr.employee"].sudo().create(
            {"name": user.name, "user_id": user.id, "company_id": self.company.id}
        )
        return user

    def _booking_type(self, *users):
        combinations = self.env["resource.booking.combination"].sudo()
        for user in users:
            resource = self.env["resource.resource"].sudo().search(
                [("user_id", "=", user.id)]
            )
            combinations |= combinations.create({"resource_ids": [(6, 0, resource.ids)]})
        return (
            self.env["resource.booking.type"]
            .sudo()
            .create(
                {
                    "name": "Alignment",
                    "combination_rel_ids": [
                        (0, 0, {"combination_id": combination.id})
                        for combination in combinations
                    ],
                }
            )
        )

    def _appoint(self, repair, booking_type):
        booking = (
            self.env["resource.booking"]
            .sudo()
            .create(
                {
                    "repair_id": repair.id,
                    "type_id": booking_type.id,
                    "partner_ids": [(6, 0, self.customer.ids)],
                }
            )
        )
        # The office books in its own request, which ends with a flush. A
        # search on a many2many does not flush pending recomputes itself.
        self.env.flush_all()
        return booking

    def test_jobs_include_jobs_of_my_appointment_type(self):
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        self._appoint(theirs, self._booking_type(other, self.technician))
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertIn(theirs.id, ids)

    def test_jobs_exclude_jobs_of_other_appointment_types(self):
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        self._appoint(theirs, self._booking_type(other))
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertNotIn(theirs.id, ids)

    def test_jobs_include_unscheduled_jobs_of_my_appointment_type(self):
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        theirs.sudo().booking_type_id = self._booking_type(other, self.technician)
        self.env.flush_all()
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertIn(theirs.id, ids)

    def test_canceled_appointment_keeps_sharing_the_job(self):
        """The job still needs that kind of work; only the slot is gone."""
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        booking = self._appoint(theirs, self._booking_type(other, self.technician))
        booking.active = False
        self.env.flush_all()
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertIn(theirs.id, ids)

    def test_jobs_includes_unassigned_by_default(self):
        unassigned = self._make_repair()
        unassigned.sudo().technician_id = False
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertIn(unassigned.id, ids)

    def test_jobs_excludes_done_and_draft(self):
        draft = self.env["repair.order"].sudo().create(
            {"partner_id": self.customer.id, "technician_id": self.technician.id}
        )
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertNotIn(draft.id, ids)

    def test_job_payload_shape(self):
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        self.assertEqual(record["id"], self.repair.id)
        self.assertEqual(record["vehicle"]["license_plate"], "SHOP-001")
        self.assertEqual(record["partner"]["name"], self.customer.name)
        self.assertEqual(record["parts_total"], 1)
        self.assertEqual(record["parts_done"], 0)
        self.assertEqual(record["odometer_in"], 42000)
        self.assertFalse(record["timer"]["running"])

    def test_job_payload_carries_stage(self):
        waiting = self.env.ref("repair_stage.stage_waiting_parts")
        self.repair.sudo().stage_id = waiting
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        self.assertEqual(record["stage"], {"id": waiting.id, "name": waiting.name})
        self.assertEqual(record["state"], "confirmed")

    def test_jobs_include_waiting_stages(self):
        """Technicians should see that a job is waiting on parts/customer."""
        self.repair.sudo().stage_id = self.env.ref(
            "repair_stage.stage_waiting_customer"
        )
        ids = [rec["id"] for rec in self.state_data(self._dispatch("jobs"))["records"]]
        self.assertIn(self.repair.id, ids)

    def test_job_named_by_vehicle_description(self):
        self.vehicle.sudo().write({"color": "Silver", "model_year": "2005"})
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        label = "Silver/2005/Acme/Hauler/SHOP-001"
        self.assertEqual(record["vehicle_description"], label)
        self.assertEqual(record["timer"]["job_name"], label)

    def test_vehicle_description_ends_with_unit_number(self):
        self.vehicle.sudo().write(
            {"color": "Silver", "model_year": "2005", "unit_number": "T-104"}
        )
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        self.assertEqual(
            record["vehicle_description"], "Silver/2005/Acme/Hauler/SHOP-001/T-104"
        )

    def test_vehicle_description_skips_missing_parts(self):
        self.vehicle.sudo().write({"color": False, "model_year": "2005"})
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        self.assertEqual(record["vehicle_description"], "2005/Acme/Hauler/SHOP-001")

    def test_job_without_vehicle_falls_back_to_customer(self):
        self.repair.sudo().vehicle_id = False
        record = self.state_data(self._dispatch("job", repair_id=self.repair.id))[
            "record"
        ]
        self.assertEqual(record["vehicle_description"], "")
        self.assertEqual(record["timer"]["job_name"], self.customer.name)

    def test_job_detail_carries_client_options(self):
        data = self.state_data(self._dispatch("job", repair_id=self.repair.id))
        self.assertTrue(data["options"]["allow_repair_end"])
        self.assertFalse(data["options"]["require_photo_on_fail"])

    def test_scan_by_repair_name(self):
        response = self._dispatch("scan", identifier=self.repair.name)
        self.assert_next_state(response, "job_detail")
        self.assertEqual(self.state_data(response)["record"]["id"], self.repair.id)

    def test_scan_by_plate_and_vin(self):
        for code in ("SHOP-001", "1FTFW1ET5DFC10312"):
            response = self._dispatch("scan", identifier=code)
            self.assert_next_state(response, "job_detail")
            self.assertEqual(
                self.state_data(response)["record"]["id"], self.repair.id, code
            )

    def test_scan_by_unit_number(self):
        self.vehicle.sudo().unit_number = "T-104"
        response = self._dispatch("scan", identifier="t-104")
        self.assert_next_state(response, "job_detail")
        self.assertEqual(self.state_data(response)["record"]["id"], self.repair.id)

    def test_scan_plate_returns_the_latest_visit(self):
        newer = self._make_repair()
        response = self._dispatch("scan", identifier="SHOP-001")
        self.assertEqual(self.state_data(response)["record"]["id"], newer.id)

    def test_scan_unknown_falls_back_to_the_list(self):
        response = self._dispatch("scan", identifier="NOPE-404")
        self.assert_next_state(response, "job_list")
        self.assert_error(response)

    def test_start_repair(self):
        response = self._dispatch("start_repair", repair_id=self.repair.id)
        self.assert_no_error(response)
        self.assertEqual(self.repair.state, "under_repair")

    def test_start_repair_twice_is_informative_not_an_error(self):
        self._dispatch("start_repair", repair_id=self.repair.id)
        response = self._dispatch("start_repair", repair_id=self.repair.id)
        self.assert_no_error(response)
        self.assertEqual(response["message"]["message_type"], "info")

    def test_finish_requires_under_repair(self):
        response = self._dispatch("finish", repair_id=self.repair.id)
        self.assert_error(response)
        self.assertNotEqual(self.repair.state, "done")

    def test_finish_completes_the_job(self):
        self._dispatch("start_repair", repair_id=self.repair.id)
        response = self._dispatch("finish", repair_id=self.repair.id)
        self.assert_no_error(response)
        self.assertEqual(self.repair.state, "done")

    def test_finish_blocked_when_the_option_is_off(self):
        self._dispatch("start_repair", repair_id=self.repair.id)
        service = self.service_for(options={"allow_repair_end": False})
        response = service.dispatch("finish", params={"repair_id": self.repair.id})
        self.assert_error(response)
        self.assertEqual(self.repair.state, "under_repair")
