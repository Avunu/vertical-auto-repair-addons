# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from dateutil.relativedelta import MO, relativedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestShopScheduling(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.calendar = cls.env["resource.calendar"].create(
            {
                "name": "Shop Hours",
                "tz": "UTC",
                "attendance_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"Day {day}",
                            "dayofweek": str(day),
                            "hour_from": 8.0,
                            "hour_to": 18.0,
                        },
                    )
                    for day in range(5)
                ],
            }
        )
        cls.tech_1 = cls._create_technician("Tina Torque", "tina.torque")
        cls.tech_2 = cls._create_technician("Wanda Wrench", "wanda.wrench")
        cls.combination_1 = cls._create_combination(cls.tech_1)
        cls.combination_2 = cls._create_combination(cls.tech_2)
        cls.booking_type = cls.env["resource.booking.type"].create(
            {
                "name": "Shop Intake",
                "duration": 1.0,
                "slot_duration": 0.5,
                "modifications_deadline": 0.0,
                "shop_repair_ok": True,
                "combination_assignment": "sorted",
                "resource_calendar_id": cls.calendar.id,
                "combination_rel_ids": [
                    (0, 0, {"combination_id": cls.combination_1.id, "sequence": 1}),
                    (0, 0, {"combination_id": cls.combination_2.id, "sequence": 2}),
                ],
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Scheduling Customer"})
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Schedmake"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Schedmodel", "brand_id": brand.id}
        )
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "SCHED-1",
                "owner_id": cls.partner.id,
            }
        )
        cls.labor = cls.env["product.product"].create(
            {
                "name": "Shop Labor",
                "type": "service",
                "uom_id": cls.env.ref("uom.product_uom_hour").id,
                "uom_po_id": cls.env.ref("uom.product_uom_hour").id,
                "list_price": 120.0,
            }
        )
        cls.repair = cls._create_repair()
        # Next Monday 09:00 UTC: inside the shop calendar, always in the future.
        cls.slot = (
            fields.Datetime.now() + relativedelta(weekday=MO(+1), weeks=1)
        ).replace(hour=9, minute=0, second=0, microsecond=0)

    @classmethod
    def _create_technician(cls, name, login):
        user = cls.env["res.users"].create(
            {
                "name": name,
                "login": login,
                "email": f"{login}@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.env["resource.resource"].create(
            {
                "name": name,
                "resource_type": "user",
                "user_id": user.id,
                "tz": "UTC",
                "calendar_id": cls.calendar.id,
                "company_id": cls.company.id,
            }
        )
        return user

    @classmethod
    def _create_combination(cls, user):
        resource = cls.env["resource.resource"].search(
            [("user_id", "=", user.id), ("calendar_id", "=", cls.calendar.id)],
            limit=1,
        )
        return cls.env["resource.booking.combination"].create(
            {"resource_ids": [(6, 0, resource.ids)]}
        )

    @classmethod
    def _create_repair(cls):
        return cls.env["repair.order"].create(
            {
                "partner_id": cls.partner.id,
                "vehicle_id": cls.vehicle.id,
            }
        )

    def _book(self, repair, start, technician=None, duration=None):
        """Run the wizard the way the front office does, then take a slot."""
        wizard = Form(
            self.env["shop.appointment.wizard"].with_context(
                default_repair_id=repair.id
            )
        )
        # Whichever shop type the database offers first is not this one; the
        # front office picks, so pick.
        wizard.type_id = self.booking_type
        if technician:
            wizard.technician_id = technician
        if duration is not None:
            wizard.duration = duration
        wizard = wizard.save()
        wizard.action_schedule()
        booking = repair.booking_id
        booking.start = start
        return booking

    def _open_calendar(self, wizard):
        """Take the wizard's "Open Calendar" branch, as the front office does."""
        action = wizard.action_schedule()
        return wizard.repair_id.booking_id, action

    def test_wizard_defaults_to_a_shop_appointment_type(self):
        wizard = Form(
            self.env["shop.appointment.wizard"].with_context(
                default_repair_id=self.repair.id
            )
        )
        self.assertTrue(wizard.type_id.shop_repair_ok)

    def test_wizard_starts_from_the_jobs_appointment_type(self):
        alignment = self.booking_type.copy({"name": "Alignment"})
        self.repair.booking_type_id = alignment
        wizard = Form(
            self.env["shop.appointment.wizard"].with_context(
                default_repair_id=self.repair.id
            )
        )
        self.assertEqual(wizard.type_id, alignment)

    def test_booking_sets_the_jobs_appointment_type(self):
        self._book(self.repair, self.slot)
        self.assertEqual(self.repair.booking_type_id, self.booking_type)
        self.assertEqual(self.repair.booking_type_user_ids, self.tech_1 | self.tech_2)

    def test_new_job_is_not_scheduled(self):
        repair = self.env["repair.order"].create({"partner_id": self.partner.id})
        self.assertFalse(repair.schedule_date)
        self.assertFalse(repair.planned_duration)
        self.assertFalse(repair.booking_ids)
        defaults = self.env["repair.order"].default_get(
            ["schedule_date", "planned_duration"]
        )
        self.assertFalse(defaults.get("schedule_date"))
        self.assertFalse(defaults.get("planned_duration"))

    def test_form_opens_without_a_date_or_duration(self):
        form = Form(self.env["repair.order"])
        self.assertFalse(form.schedule_date)
        self.assertFalse(form.planned_duration)

    def test_parts_can_be_added_to_an_unscheduled_job(self):
        repair = self.env["repair.order"].create({"partner_id": self.partner.id})
        part = self.env["product.product"].create({"name": "Shop Part"})
        move = self.env["stock.move"].create(
            {
                "repair_id": repair.id,
                "repair_line_type": "add",
                "product_id": part.id,
                "product_uom_qty": 1,
                "product_uom": part.uom_id.id,
                "location_id": repair.location_id.id,
                "location_dest_id": repair.location_dest_id.id,
                "company_id": repair.company_id.id,
                "date": False,
            }
        )
        self.assertTrue(move.date)
        # Booking the job carries the parts to its date, as core does.
        repair.schedule_date = self.slot
        self.assertEqual(move.date, self.slot)
        # Clearing the date later leaves the parts where they were.
        repair.schedule_date = False
        self.assertEqual(move.date, self.slot)

    def test_clearing_the_date_keeps_the_appointment(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        self.repair.schedule_date = False
        self.assertEqual(booking.start, self.slot)
        self.assertEqual(booking.meeting_id.start, self.slot)

    def test_calendar_colour_follows_the_appointment_type(self):
        self.booking_type.color = 7
        self.repair.booking_type_id = self.booking_type
        self.assertEqual(self.repair.booking_type_color, 7)
        self.booking_type.color = 3
        self.assertEqual(self.repair.booking_type_color, 3)

    def test_calendar_vehicle_label_skips_missing_parts(self):
        self.assertEqual(self.repair.shop_vehicle_label, "Schedmake/Schedmodel/SCHED-1")
        self.repair.vehicle_id = False
        self.assertFalse(self.repair.shop_vehicle_label)

    def test_canceled_appointment_leaves_the_jobs_appointment_type(self):
        booking = self._book(self.repair, self.slot)
        booking.active = False
        self.assertFalse(self.repair.booking_id)
        self.assertEqual(self.repair.booking_type_id, self.booking_type)

    def test_wizard_defaults_duration_to_book_hours(self):
        self.env["repair.service"].create(
            {
                "repair_id": self.repair.id,
                "product_id": self.labor.id,
                "product_uom": self.labor.uom_id.id,
                "product_uom_qty": 3.5,
            }
        )
        self.assertEqual(self.repair.book_hours, 3.5)
        wizard = Form(
            self.env["shop.appointment.wizard"].with_context(
                default_repair_id=self.repair.id
            )
        )
        self.assertEqual(wizard.duration, 3.5)

    def test_booking_stamps_schedule_and_technician(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        self.assertEqual(booking.technician_id, self.tech_1)
        self.assertEqual(self.repair.schedule_date, self.slot)
        self.assertEqual(self.repair.technician_id, self.tech_1)
        self.assertEqual(self.repair.planned_duration, 2.0)
        self.assertEqual(self.repair.booking_id, booking)
        self.assertEqual(self.repair.booking_count, 1)
        self.assertEqual(booking.vehicle_id, self.vehicle)

    def test_second_job_falls_to_the_next_free_technician(self):
        self._book(self.repair, self.slot, duration=2.0)
        other_repair = self._create_repair()
        booking = self._book(other_repair, self.slot, duration=2.0)
        self.assertEqual(booking.technician_id, self.tech_2)
        self.assertEqual(other_repair.technician_id, self.tech_2)

    def test_third_job_finds_nobody_free(self):
        self._book(self.repair, self.slot, duration=2.0)
        self._book(self._create_repair(), self.slot, duration=2.0)
        with self.assertRaises(ValidationError):
            self._book(self._create_repair(), self.slot, duration=2.0)

    def test_slot_outside_shop_hours_is_refused(self):
        saturday = self.slot + timedelta(days=5)
        with self.assertRaises(ValidationError):
            self._book(self.repair, saturday, duration=2.0)

    def test_unbookable_slot_says_what_is_wrong_with_it(self):
        saturday = self.slot + timedelta(days=5)
        with self.assertRaises(ValidationError) as caught:
            self._book(self.repair, saturday, duration=2.0)
        message = str(caught.exception)
        self.assertIn(self.booking_type.display_name, message)
        # Not the bare check constraint the database would have raised.
        self.assertNotIn("cannot be completed", message)

    def test_unbookable_slot_offers_the_openings_instead(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        openings = booking._shop_next_openings()
        self.assertEqual(len(openings), 5)

    def test_appointment_type_with_nobody_bookable_says_so(self):
        empty_type = self.booking_type.copy(
            {"name": "Nobody Bookable", "combination_rel_ids": []}
        )
        wizard = self.env["shop.appointment.wizard"].create(
            {
                "repair_id": self.repair.id,
                "type_id": empty_type.id,
                "duration": 1.0,
            }
        )
        booking, _action = self._open_calendar(wizard)
        with self.assertRaises(ValidationError) as caught:
            booking.start = self.slot
        self.assertIn("nobody is bookable", str(caught.exception).lower())

    def test_preferred_technician_is_honoured(self):
        booking = self._book(self.repair, self.slot, technician=self.tech_2)
        self.assertFalse(booking.combination_auto_assign)
        self.assertEqual(booking.technician_id, self.tech_2)
        self.assertEqual(self.repair.technician_id, self.tech_2)

    def test_preferred_technician_must_be_bookable(self):
        stranger = self.env["res.users"].create(
            {"name": "Sam Stranger", "login": "sam.stranger"}
        )
        wizard = self.env["shop.appointment.wizard"].create(
            {
                "repair_id": self.repair.id,
                "type_id": self.booking_type.id,
                "technician_id": stranger.id,
                "duration": 1.0,
            }
        )
        with self.assertRaises(UserError):
            wizard.action_schedule()

    def test_dragging_the_meeting_reschedules_the_job(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        moved = self.slot + timedelta(hours=3)
        booking.meeting_id.write({"start": moved, "stop": moved + timedelta(hours=2)})
        self.assertEqual(booking.start, moved)
        self.assertEqual(self.repair.schedule_date, moved)

    def test_rescheduling_the_job_moves_the_appointment(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        moved = self.slot + timedelta(hours=4)
        self.repair.schedule_date = moved
        self.assertEqual(booking.start, moved)
        self.assertEqual(booking.meeting_id.start, moved)

    def test_rescheduling_onto_a_busy_window_hands_the_job_over(self):
        self._book(self.repair, self.slot, duration=2.0)
        other_repair = self._create_repair()
        booking = self._book(other_repair, self.slot + timedelta(hours=4), duration=2.0)
        self.assertEqual(booking.technician_id, self.tech_1)
        # tech_1 is busy at the earlier slot, so the auto-assigned appointment
        # moves to whoever is free -- and the job says so too.
        other_repair.schedule_date = self.slot
        self.assertEqual(booking.technician_id, self.tech_2)
        self.assertEqual(other_repair.technician_id, self.tech_2)

    def test_rescheduling_a_pinned_technician_onto_a_busy_window_is_refused(self):
        self._book(self.repair, self.slot, duration=2.0)
        other_repair = self._create_repair()
        self._book(
            other_repair,
            self.slot + timedelta(hours=4),
            technician=self.tech_1,
            duration=2.0,
        )
        # Pinned to tech_1, who already has the earlier window: no silent
        # double-booking, and no silent hand-over either.
        with self.assertRaises(ValidationError):
            other_repair.schedule_date = self.slot

    def test_reassigning_the_job_reassigns_the_appointment(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        self.repair.technician_id = self.tech_2
        self.assertEqual(booking.combination_id, self.combination_2)
        self.assertFalse(booking.combination_auto_assign)

    def test_reassigning_to_an_unbookable_user_only_warns(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        helper = self.env["res.users"].create(
            {"name": "Hank Helper", "login": "hank.helper"}
        )
        messages_before = len(booking.message_ids)
        self.repair.technician_id = helper
        self.assertEqual(booking.combination_id, self.combination_1)
        self.assertGreater(len(booking.message_ids), messages_before)

    def test_duration_change_on_the_job_reaches_the_meeting(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        self.repair.planned_duration = 3.0
        self.assertEqual(booking.duration, 3.0)
        self.assertEqual(booking.stop, self.slot + timedelta(hours=3))

    def test_web_booked_appointment_opens_a_job(self):
        booking = self.env["resource.booking"].create(
            {
                "name": "Web booking",
                "type_id": self.booking_type.id,
                "partner_ids": [(6, 0, self.partner.ids)],
                "duration": 1.0,
            }
        )
        booking.start = self.slot
        action = booking.action_shop_create_repair()
        repair = self.env["repair.order"].browse(action["res_id"])
        self.assertEqual(booking.repair_id, repair)
        self.assertEqual(repair.partner_id, self.partner)
        self.assertEqual(repair.schedule_date, self.slot)
        self.assertEqual(repair.technician_id, booking.technician_id)

    def test_unscheduling_leaves_a_trail(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        messages_before = len(self.repair.message_ids)
        booking.action_unschedule()
        self.assertFalse(booking.start)
        self.assertEqual(booking.state, "pending")
        self.assertGreater(len(self.repair.message_ids), messages_before)

    def test_placing_on_the_grid_keeps_the_hours_the_job_was_sold_for(self):
        self.env["repair.service"].create(
            {
                "repair_id": self.repair.id,
                "product_id": self.labor.id,
                "product_uom": self.labor.uom_id.id,
                "product_uom_qty": 3.5,
            }
        )
        wizard = self.env["shop.appointment.wizard"].create(
            {"repair_id": self.repair.id, "type_id": self.booking_type.id}
        )
        self.assertEqual(wizard.duration, 3.5)
        booking, _action = self._open_calendar(wizard)
        # The grid hands over whatever the click was worth, not the job hours.
        meeting = self.env["calendar.event"].create(
            {
                "name": booking.name,
                "start": self.slot,
                "stop": self.slot + timedelta(hours=1),
                "resource_booking_ids": [(6, 0, booking.ids)],
            }
        )
        self.assertEqual(meeting.duration, 3.5)
        self.assertEqual(meeting.stop, self.slot + timedelta(hours=3, minutes=30))
        self.assertEqual(booking.start, self.slot)
        self.assertEqual(booking.duration, 3.5)
        self.assertEqual(self.repair.planned_duration, 3.5)

    def test_quick_creating_on_the_grid_books_the_appointment(self):
        wizard = self.env["shop.appointment.wizard"].create(
            {
                "repair_id": self.repair.id,
                "type_id": self.booking_type.id,
                "duration": 2.0,
            }
        )
        booking, action = self._open_calendar(wizard)
        # A quick create sends no booking of its own: it rides on the action's
        # context defaults, which the ORM only merges in further down.
        meeting = (
            self.env["calendar.event"]
            .with_context(**action["context"])
            .create(
                {
                    "name": booking.name,
                    "start": self.slot,
                    "stop": self.slot + timedelta(hours=1),
                    "duration": 1.0,
                }
            )
        )
        self.assertEqual(meeting.resource_booking_ids, booking)
        self.assertEqual(meeting.duration, 2.0)
        self.assertEqual(booking.duration, 2.0)
        self.assertEqual(self.repair.planned_duration, 2.0)

    def test_placement_calendar_is_pinned_to_the_week_grid(self):
        wizard = self.env["shop.appointment.wizard"].create(
            {"repair_id": self.repair.id, "type_id": self.booking_type.id}
        )
        _booking, action = self._open_calendar(wizard)
        view = self.env.ref("shop_scheduling.calendar_event_view_calendar_shop")
        self.assertEqual(action["view_id"], view.id)
        arch = self.env["calendar.event"].get_view(view.id, "calendar")["arch"]
        self.assertIn('mode="week"', arch)
        self.assertIn('scales="day,week"', arch)
        # No all-day row, so no all-day placement that books nobody.
        self.assertNotIn("all_day", arch)

    def _wizard(self, duration=2.0, technician=None):
        return self.env["shop.appointment.wizard"].create(
            {
                "repair_id": self.repair.id,
                "type_id": self.booking_type.id,
                "duration": duration,
                "technician_id": technician.id if technician else False,
                "search_days": 21,
            }
        )

    def _opening_at(self, wizard, start):
        openings = wizard._probe_booking()._shop_openings(days=21)
        return next(one for one in openings if one["start"] == start)

    def test_placing_on_an_unbookable_slot_says_why(self):
        booking, _action = self._open_calendar(self._wizard())
        saturday = self.slot + timedelta(days=5)
        with self.assertRaises(ValidationError) as caught:
            self.env["calendar.event"].create(
                {
                    "name": booking.name,
                    "start": saturday,
                    "stop": saturday + timedelta(hours=2),
                    "resource_booking_ids": [(6, 0, booking.ids)],
                }
            )
        message = str(caught.exception)
        self.assertIn(self.booking_type.display_name, message)
        # Not the check constraint, which the database raises from inside the
        # availability search itself, before anything readable can be said.
        self.assertNotIn("cannot be completed", message)

    def test_openings_say_who_is_free(self):
        opening = self._opening_at(self._wizard(), self.slot)
        self.assertEqual(
            opening["combinations"], self.combination_1 | self.combination_2
        )

    def test_openings_narrow_as_technicians_get_booked(self):
        self._book(self.repair, self.slot, duration=2.0)
        opening = self._opening_at(self._wizard(), self.slot)
        self.assertEqual(opening["combinations"], self.combination_2)

    def test_openings_for_a_pinned_technician_are_only_theirs(self):
        wizard = self._wizard(technician=self.tech_2)
        openings = wizard._probe_booking()._shop_openings(days=21)
        self.assertTrue(openings)
        for opening in openings:
            self.assertEqual(opening["combinations"], self.combination_2)

    def test_finding_openings_books_one_in_a_click(self):
        wizard = self._wizard()
        wizard.action_find_openings()
        self.assertTrue(wizard.openings_searched)
        slot = wizard.slot_ids.filtered(lambda one: one.start == self.slot)
        self.assertEqual(len(slot), 1)
        self.assertEqual(set(slot.technician_ids.ids), {self.tech_1.id, self.tech_2.id})
        slot.action_book()
        booking = self.repair.booking_ids
        self.assertEqual(len(booking), 1)
        self.assertEqual(booking.start, self.slot)
        self.assertEqual(self.repair.schedule_date, self.slot)
        self.assertEqual(self.repair.technician_id, self.tech_1)

    def test_openings_are_labelled_in_the_shops_timezone(self):
        wizard = self._wizard()
        wizard.action_find_openings()
        slot = wizard.slot_ids.filtered(lambda one: one.start == self.slot)
        # Shop calendar is UTC, and the slot is 09:00 there.
        self.assertIn("09:00", slot.name)

    def test_showing_openings_for_a_pending_appointment_books_it(self):
        booking, _action = self._open_calendar(self._wizard())
        action = booking.action_shop_show_openings()
        slots = self.env["shop.appointment.slot"].search(action["domain"])
        self.assertTrue(slots)
        slots[0].action_book()
        self.assertEqual(booking.start, slots[0].start)
        self.assertEqual(self.repair.schedule_date, booking.start)

    def test_deleting_the_job_takes_its_meetings_with_it(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        meeting = booking.meeting_id
        self.repair.unlink()
        self.assertFalse(booking.exists())
        self.assertFalse(meeting.exists())

    def test_scheduling_a_job_again_moves_its_appointment(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        meeting = booking.meeting_id
        later = self.slot + timedelta(days=1)
        self.assertEqual(self._book(self.repair, later, duration=2.0), booking)
        self.assertEqual(self.repair.booking_count, 1)
        self.assertEqual(booking.meeting_id, meeting)
        self.assertEqual(meeting.start, later)
        self.assertEqual(self.repair.schedule_date, later)

    def test_placing_a_scheduled_appointment_again_moves_its_meeting(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        old_meeting = booking.meeting_id
        wizard = (
            self.env["shop.appointment.wizard"]
            .with_context(default_repair_id=self.repair.id)
            .create({"repair_id": self.repair.id, "duration": 2.0})
        )
        # Rescheduling keeps the appointment's type, not the first shop type.
        self.assertEqual(wizard.type_id, booking.type_id)
        same_booking, action = self._open_calendar(wizard)
        self.assertEqual(same_booking, booking)
        # Overlapping the old placement: the technician must not count as
        # busy with the meeting being replaced.
        nudged = self.slot + timedelta(minutes=30)
        meeting = (
            self.env["calendar.event"]
            .with_context(**action["context"])
            .create(
                {
                    "name": booking.name,
                    "start": nudged,
                    "stop": nudged + timedelta(hours=1),
                }
            )
        )
        self.assertFalse(old_meeting.exists())
        self.assertEqual(booking.meeting_id, meeting)
        self.assertEqual(booking.technician_id, self.tech_1)
        self.assertEqual(self.repair.schedule_date, nudged)
        self.assertEqual(self.repair.booking_count, 1)

    def test_a_job_has_one_live_appointment(self):
        booking = self._book(self.repair, self.slot, duration=2.0)
        vals = {
            "type_id": self.booking_type.id,
            "repair_id": self.repair.id,
            "partner_ids": [(6, 0, self.partner.ids)],
        }
        with self.assertRaises(ValidationError):
            self.env["resource.booking"].create(vals)
        # A canceled appointment is history, not a second schedule.
        booking.action_cancel()
        self.env["resource.booking"].create(vals)
        with self.assertRaises(ValidationError):
            booking.active = True
