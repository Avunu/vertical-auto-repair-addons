# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import json

from odoo import api
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TechCase


@tagged("post_install", "-at_install")
class TestJobList(TechCase):
    def _other_technician(self):
        return self._make_technician("Other Tech", "other.tech")

    def _booking_type(self, *users):
        combinations = self.env["resource.booking.combination"]
        for user in users:
            resource = self.env["resource.resource"].search([("user_id", "=", user.id)])
            combinations |= combinations.create(
                {"resource_ids": [(6, 0, resource.ids)]}
            )
        return self.env["resource.booking.type"].create(
            {
                "name": "Alignment",
                "combination_rel_ids": [
                    (0, 0, {"combination_id": combination.id})
                    for combination in combinations
                ],
            }
        )

    def _appoint(self, repair, booking_type):
        booking = self.env["resource.booking"].create(
            {
                "repair_id": repair.id,
                "type_id": booking_type.id,
                "partner_ids": [(6, 0, self.customer.ids)],
            }
        )
        # The office books in its own request, which ends with a flush; a
        # search on a many2many doesn't flush pending recomputes itself.
        self.env.flush_all()
        return booking

    def test_my_jobs(self):
        self.assertIn(self.repair.id, self.ids(self.app.jobs()))

    def test_not_another_technicians_job(self):
        theirs = self._make_repair(technician=self._other_technician())
        self.assertNotIn(theirs.id, self.ids(self.app.jobs()))

    def test_jobs_of_my_appointment_type(self):
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        self._appoint(theirs, self._booking_type(other, self.technician))
        jobs = {job["id"]: job for job in self.app.jobs()}
        self.assertIn(theirs.id, jobs)
        self.assertFalse(jobs[theirs.id]["is_mine"])
        self.assertTrue(jobs[self.repair.id]["is_mine"])

    def test_not_jobs_of_other_appointment_types(self):
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        self._appoint(theirs, self._booking_type(other))
        self.assertNotIn(theirs.id, self.ids(self.app.jobs()))

    def test_unscheduled_job_of_my_appointment_type(self):
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        theirs.booking_type_id = self._booking_type(other, self.technician)
        self.env.flush_all()
        self.assertIn(theirs.id, self.ids(self.app.jobs()))

    def test_canceled_appointment_keeps_sharing_the_job(self):
        """The job still needs that kind of work; only the slot is gone."""
        other = self._other_technician()
        theirs = self._make_repair(technician=other)
        booking = self._appoint(theirs, self._booking_type(other, self.technician))
        booking.active = False
        self.env.flush_all()
        self.assertIn(theirs.id, self.ids(self.app.jobs()))

    def test_unassigned_jobs_by_default(self):
        nobodys = self._make_repair()
        nobodys.technician_id = False
        self.assertIn(nobodys.id, self.ids(self.app.jobs()))
        self.env["ir.config_parameter"].set_param(
            "repair_tech_app.show_unassigned", False
        )
        self.assertNotIn(nobodys.id, self.ids(self.app.jobs()))

    def test_jobs_im_responsible_for_when_the_shop_says_so(self):
        theirs = self._make_repair(technician=self._other_technician())
        theirs.user_id = self.technician
        self.assertNotIn(theirs.id, self.ids(self.app.jobs()))
        self.env["ir.config_parameter"].set_param(
            "repair_tech_app.include_responsible", True
        )
        self.assertIn(theirs.id, self.ids(self.app.jobs()))

    def test_done_and_bare_draft_jobs_stay_off(self):
        draft = self._make_repair(state="draft", services=False)
        done = self._make_repair(state="under_repair")
        done.with_context(skip_service_finalize_wizard=True).action_repair_end()
        ids = self.ids(self.app.jobs())
        self.assertNotIn(draft.id, ids)
        self.assertNotIn(done.id, ids)

    def test_draft_job_with_an_accepted_service_shows(self):
        """The office accepts Diagnostics and sends the job out before the
        repair is confirmed."""
        draft = self._make_repair(state="draft")
        self.assertIn(draft.id, self.ids(self.app.jobs()))

    def test_summary(self):
        job = next(job for job in self.app.jobs() if job["id"] == self.repair.id)
        self.assertEqual(job["state"], "confirmed")
        self.assertEqual(job["label"], "Acme/Hauler/SHOP-001")
        self.assertEqual(job["vehicle"]["license_plate"], "SHOP-001")
        self.assertEqual(job["customer_concern"], "Squeals when braking")
        self.assertEqual((job["parts_done"], job["parts_total"]), (0, 1))
        self.assertEqual(job["stage"]["id"], self.repair.stage_id.id)
        self.assertNotIn("services", job, "a summary carries no detail")
        json.dumps(job)

    def test_label_leads_with_what_you_see_and_ends_with_the_unit(self):
        self.vehicle.write(
            {"color": "Silver", "model_year": "2005", "unit_number": "T-104"}
        )
        job = self.app.job(repair_id=self.repair.id)
        self.assertEqual(job["label"], "Silver/2005/Acme/Hauler/SHOP-001/T-104")
        self.assertEqual(job["vehicle"]["unit_number"], "T-104")

    def test_job_without_a_vehicle_is_named_by_its_customer(self):
        bare = self._make_repair()
        bare.vehicle_id = False
        self.assertEqual(self.app.job(repair_id=bare.id)["label"], "Wile E. Coyote")


@tagged("post_install", "-at_install")
class TestJob(TechCase):
    def test_detail(self):
        job = self.app.job(repair_id=self.repair.id)
        self.assertEqual(
            [s["name"] for s in job["services"]], ["Brake Job", "Diagnostics"]
        )
        self.assertFalse(job["services"][0]["timer"]["running"])
        self.assertEqual(job["odometer_in"], 42000)
        self.assertTrue(job["can_start"])
        self.assertFalse(job["can_finish"])
        self.assertTrue(job["can_edit_parts"])

    def test_unknown_job(self):
        with self.assertRaisesRegex(UserError, "no longer exists"):
            self.app.job(repair_id=999999999)

    def test_find_job_by_reference_plate_vin_and_unit(self):
        self.vehicle.unit_number = "T-104"
        for code in (self.repair.name, "shop-001", "1FTFW1ET5DFC10312", "T-104"):
            self.assertEqual(self.app.find_job(code=code)["id"], self.repair.id, code)

    def test_find_job_by_plate_finds_the_latest_visit(self):
        latest = self._make_repair()
        self.assertEqual(self.app.find_job(code="SHOP-001")["id"], latest.id)

    def test_find_nothing(self):
        self.assertIsNone(self.app.find_job(code="NO-SUCH-THING"))
        with self.assertRaises(ValidationError):
            self.app.find_job(code="")

    def test_start_repair(self):
        job = self.app.start_repair(repair_id=self.repair.id)
        self.assertEqual(job["state"], "under_repair")
        self.assertFalse(job["can_start"])
        self.assertTrue(job["can_finish"])
        # Again is harmless: the job simply is under repair.
        self.assertEqual(
            self.app.start_repair(repair_id=self.repair.id)["state"], "under_repair"
        )

    def test_start_repair_waits_for_the_office(self):
        draft = self._make_repair(state="draft")
        with self.assertRaisesRegex(UserError, "isn't confirmed yet"):
            self.app.start_repair(repair_id=draft.id)
        self.assertEqual(draft.state, "draft")

    def test_finish(self):
        self.app.start_repair(repair_id=self.repair.id)
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        job = self.app.finish(repair_id=self.repair.id)
        self.assertEqual(job["state"], "done")
        self.assertFalse(job["timer_running"], "finishing stops the timer")
        self.assertNotIn(self.repair.id, self.ids(self.app.jobs()))

    def test_finish_needs_the_job_under_repair(self):
        with self.assertRaisesRegex(UserError, "under repair"):
            self.app.finish(repair_id=self.repair.id)

    def test_finish_when_the_shop_doesnt_allow_it(self):
        self.app.start_repair(repair_id=self.repair.id)
        self.env["ir.config_parameter"].set_param("repair_tech_app.allow_finish", False)
        self.assertFalse(self.app.job(repair_id=self.repair.id)["can_finish"])
        self.assertFalse(self.app.session()["options"]["allow_finish"])
        with self.assertRaisesRegex(UserError, "office closes jobs"):
            self.app.finish(repair_id=self.repair.id)

    def test_through_call_kw(self):
        """The path the app takes: /web/dataset/call_kw -> api.call_kw."""
        job = api.call_kw(self.app, "job", [], {"repair_id": self.repair.id})
        self.assertEqual(job["id"], self.repair.id)
        with self.assertRaisesRegex(ValidationError, "repair_id"):
            api.call_kw(self.app, "job", [], {"repair_id": "seven"})


@tagged("post_install", "-at_install")
class TestNotes(TechCase):
    def test_note_lands_in_the_repair_notes(self):
        job = self.app.add_note(repair_id=self.repair.id, note="Rotors scored\nreplace")
        self.assertIn("Rotors scored\nreplace", job["internal_notes"], "lines are kept")
        self.assertTrue(job["internal_notes"].startswith("[Tina Technician] "))
        self.assertIn("<br>", str(self.repair.internal_notes), "lines are kept")

    def test_note_is_posted_as_a_technician_note(self):
        self.app.add_note(repair_id=self.repair.id, note="Needs a tow")
        message = self.repair.message_ids[:1]
        self.assertEqual(
            message.subtype_id,
            self.env.ref("repair_tech_app.mt_repair_technician_note"),
        )
        self.assertIn("Needs a tow", message.body)

    def test_note_by_a_technician_without_an_email(self):
        """Nor a company email: the note still goes up."""
        self.technician.email = False
        self.company.email = False
        self.app.add_note(repair_id=self.repair.id, note="Still fine")
        self.assertIn("Still fine", self.repair.message_ids[:1].body)

    def test_markup_is_escaped(self):
        self.app.add_note(repair_id=self.repair.id, note="<script>x</script>")
        self.assertNotIn("<script>", str(self.repair.internal_notes))

    def test_empty_note(self):
        with self.assertRaisesRegex(UserError, "empty"):
            self.app.add_note(repair_id=self.repair.id, note="   ")


@tagged("post_install", "-at_install")
class TestSessionAndShift(TechCase):
    def test_session(self):
        session = self.app.session()
        self.assertEqual(session["uid"], self.technician.id)
        self.assertEqual(session["employee"]["id"], self.employee.id)
        self.assertEqual(
            session["options"], {"allow_finish": True, "require_photo_on_fail": False}
        )

    def test_clock_in_and_out(self):
        shift = self.app.clock_toggle()
        self.assertTrue(shift["clocked_in"])
        self.assertTrue(shift["since"].endswith("Z"))
        shift = self.app.clock_toggle()
        self.assertFalse(shift["clocked_in"])
        self.assertGreaterEqual(shift["hours_today"], 0)

    def test_clocking_out_stops_the_job_timer(self):
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        self.assertTrue(self.app.shift()["clocked_in"], "the timer clocked in")
        shift = self.app.clock_toggle()
        self.assertFalse(shift["clocked_in"])
        self.assertIsNone(shift["running"])
        self.assertIn("stopped automatically", self.repair.message_ids[:1].body)

    def test_shift_shows_the_running_timer(self):
        self.app.timer_start(repair_id=self.repair.id, service_id=self.brakes.id)
        running = self.app.shift()["running"]
        self.assertEqual(
            (running["repair_id"], running["service_id"]),
            (self.repair.id, self.brakes.id),
        )
        self.assertEqual(running["service_name"], "Brake Job")

    def test_no_employee(self):
        self.employee.user_id = False
        self.assertIsNone(self.app.session()["employee"])
        self.assertFalse(self.app.shift()["clocked_in"])
        with self.assertRaisesRegex(UserError, "no employee"):
            self.app.clock_toggle()


@tagged("post_install", "-at_install")
class TestPlaintext(TechCase):
    def test_markup_becomes_lines(self):
        from ..models.repair_tech_app import plaintext

        html = (
            "<p><b>[Tina]</b> 9:30<br/>Rotors <i>scored</i>.<br>Replace.</p><p>Next</p>"
        )
        self.assertEqual(plaintext(html), "[Tina] 9:30\nRotors scored.\nReplace.\nNext")
        self.assertEqual(plaintext(False), "")
        self.assertEqual(plaintext("plain"), "plain")
