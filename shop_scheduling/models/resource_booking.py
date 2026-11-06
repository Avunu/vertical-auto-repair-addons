# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from pytz import utc

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, format_datetime, format_duration

from odoo.addons.resource_booking.models.resource_booking import (
    _availability_is_fitting,
    _merge_intervals,
)

SUGGESTED_OPENINGS = 5
SUGGESTION_WINDOW = timedelta(days=14)


class ResourceBooking(models.Model):
    _inherit = "resource.booking"

    repair_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        index=True,
        copy=False,
        ondelete="cascade",
        help="Job this appointment belongs to. Its scheduled date, planned "
        "duration and technician follow this appointment.",
    )
    vehicle_id = fields.Many2one(
        related="repair_id.vehicle_id",
        store=True,
        string="Vehicle",
    )
    technician_id = fields.Many2one(
        "res.users",
        string="Technician",
        compute="_compute_technician_id",
        store=True,
        help="First person booked by the assigned resource combination.",
    )

    @api.constrains("repair_id", "active")
    def _check_shop_one_booking_per_repair(self):
        """A job has one live appointment; rescheduling moves it.

        Two would each push their own date and technician onto the same job,
        and whichever was written last would win. Canceled appointments are
        archived and stay behind as history.
        """
        for booking in self.filtered(lambda one: one.repair_id and one.active):
            others = self.search(
                [("repair_id", "=", booking.repair_id.id), ("id", "!=", booking.id)]
            )
            if others:
                raise ValidationError(
                    _(
                        "%(repair)s already has appointment %(booking)s. "
                        "Reschedule that one, or cancel it first.",
                        repair=booking.repair_id.display_name,
                        booking=others[0].display_name,
                    )
                )

    @api.depends("combination_id")
    def _compute_technician_id(self):
        for booking in self:
            users = booking.combination_id.resource_ids.filtered(
                lambda resource: resource.resource_type == "user"
            ).mapped("user_id")
            booking.technician_id = users[:1]

    def _shop_combination_for_user(self, user):
        """Return the combination of this booking's type that books ``user``."""
        self.ensure_one()
        if not user:
            return self.env["resource.booking.combination"]
        combinations = self.type_id.combination_rel_ids.combination_id
        return combinations.filtered(
            lambda combination: user in combination.resource_ids.user_id
        )[:1]

    def _get_best_combination(self):
        """Say why a slot is unbookable instead of failing in the database.

        Upstream only explains itself to the portal; every other caller gets
        an empty combination back, which trips the
        ``combination_required_if_event`` check constraint as soon as the
        meeting is written -- "The operation cannot be completed: Missing
        resource booking combination.", which says nothing about the slot.
        """
        combination = super()._get_best_combination()
        if combination or not self.start or not self.combination_auto_assign:
            return combination
        raise ValidationError(self._shop_unbookable_message())

    def _shop_unbookable_message(self, start=None, stop=None):
        """Explain an unbookable slot, and offer the ones that are free.

        ``start``/``stop`` describe a window that is only being proposed, so
        the refusal can be worded before anything is written.
        """
        self.ensure_one()
        start = start or self.start
        stop = stop or self.stop
        if not self.type_id.combination_rel_ids:
            return _(
                "Nobody is bookable for %(type)s at all, so nothing can be "
                "scheduled for it. Add resource combinations to that "
                "appointment type first.",
                type=self.type_id.display_name,
            )
        duration = (stop - start).total_seconds() / 3600
        lines = [
            _(
                "Nobody bookable for %(type)s is free for %(duration)s from "
                "%(start)s to %(stop)s.",
                type=self.type_id.display_name,
                duration=format_duration(duration),
                start=format_datetime(self.env, start),
                stop=format_datetime(self.env, stop),
            )
        ]
        openings = self._shop_next_openings(start=start)
        if openings:
            lines.append(_("These openings are free:"))
            lines.extend(f"- {opening}" for opening in openings)
        else:
            lines.append(
                _(
                    "Nothing opens up for %(duration)s in the following "
                    "%(days)s days either. Shorten the appointment, or widen "
                    "the availability calendar.",
                    duration=format_duration(duration),
                    days=SUGGESTION_WINDOW.days,
                )
            )
        return "\n".join(lines)

    def _shop_next_openings(self, limit=SUGGESTED_OPENINGS, start=None):
        """Format the first few openings, for a refusal message."""
        self.ensure_one()
        return [
            format_datetime(self.env, opening["start"])
            for opening in self._shop_openings(start=start, technicians=False)[:limit]
        ]

    def _shop_probe(self):
        """Return a copy of this appointment that books nobody in particular.

        ``combination_id`` names whoever the appointment currently books, and
        ``_get_intervals()`` narrows the openings down to them. Ask on a
        detached copy that books nobody, so every technician the type can call
        on counts. It is also the only way to ask mid-compute, where the field
        is protected and still holds the value being replaced.

        An appointment pinned to one technician is returned as-is: there the
        pin is the answer, not noise.
        """
        self.ensure_one()
        if not self.combination_id or not self.combination_auto_assign:
            return self
        probe = self.new(origin=self)
        probe.combination_id = False
        return probe

    def _shop_combination_intervals(self, start_dt, end_dt):
        """Merged free intervals per bookable combination over a window.

        One availability search per technician for the whole window, rather
        than one per candidate slot: each search reads every meeting in range,
        so asking it slot by slot is what makes an openings list unusable.
        """
        self.ensure_one()
        if self.combination_id and not self.combination_auto_assign:
            combinations = self.combination_id
        else:
            combinations = self.combination_id + (
                self.type_id._get_combinations_priorized() - self.combination_id
            )
        return {
            combination: _merge_intervals(
                self._get_intervals(start_dt, end_dt, combination)
            )
            for combination in combinations
        }

    def _shop_fitting_combinations(self, start, stop):
        """Who could take this appointment in a window, changing nothing.

        The same answer ``_get_best_combination()`` gives, asked without
        writing anything -- which is what makes it usable before the meeting
        that would carry the window exists.
        """
        self.ensure_one()
        start_dt = fields.Datetime.context_timestamp(self, start)
        stop_dt = fields.Datetime.context_timestamp(self, stop)
        free = self.env["resource.booking.combination"]
        for combination, available in self._shop_combination_intervals(
            start_dt, stop_dt
        ).items():
            if _availability_is_fitting(available, start_dt, stop_dt):
                free |= combination
        return free

    def _shop_openings(self, days=SUGGESTION_WINDOW.days, start=None, technicians=True):
        """Return the openings this appointment would really fit in.

        Same source as the portal's opening list, deadline included, so the
        backend and the portal can never disagree about what is bookable. Each
        opening also carries who is free for it, which the portal never says.

        Pass ``technicians=False`` to skip that attribution: it costs one
        availability search per technician, and a refusal message only needs
        the times.
        """
        self.ensure_one()
        if self.type_id.slot_duration <= 0:
            return []
        probe = self._shop_probe()
        start_dt = fields.Datetime.context_timestamp(
            self, start or self.start or fields.Datetime.now()
        )
        end_dt = start_dt + timedelta(days=days)
        slots = probe._get_available_slots(start_dt, end_dt)
        if not slots:
            return []
        booking_duration = timedelta(hours=probe.duration)
        per_combination = {}
        if technicians:
            # _get_available_slots() walks from midnight, so the attribution
            # pass has to cover the same ground or an early opening matches
            # nobody.
            per_combination = probe._shop_combination_intervals(
                start_dt.replace(hour=0, minute=0, second=0, microsecond=0), end_dt
            )
        openings = []
        for day in sorted(slots):
            for slot in slots[day]:
                stop = slot + booking_duration
                free = self.env["resource.booking.combination"]
                for combination, available in per_combination.items():
                    if _availability_is_fitting(available, slot, stop):
                        free |= combination
                openings.append(
                    {
                        "start": slot.astimezone(utc).replace(tzinfo=None),
                        "stop": stop.astimezone(utc).replace(tzinfo=None),
                        "combinations": free,
                    }
                )
        return openings

    def action_shop_show_openings(self):
        """List the openings this appointment would really fit in."""
        self.ensure_one()
        slots = self.env["shop.appointment.slot"]._shop_from_openings(
            self._shop_openings(), booking=self
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Openings"),
            "res_model": "shop.appointment.slot",
            "view_mode": "list",
            "views": [
                (
                    self.env.ref("shop_scheduling.shop_appointment_slot_view_list").id,
                    "list",
                )
            ],
            "domain": [("id", "in", slots.ids)],
            "target": "new",
        }

    def _shop_booked_action(self):
        """Where to land once an opening has been taken."""
        self.ensure_one()
        if self.repair_id:
            return self.action_view_repair()
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment"),
            "res_model": "resource.booking",
            "view_mode": "form",
            "res_id": self.id,
        }

    def _shop_sync_repair(self):
        """Push appointment start, duration and technician onto the job.

        The appointment owns the schedule: whatever the resource engine
        settled on -- a slot the whole shop was free for, then narrowed to
        one technician -- is what the repair order shows.
        """
        for booking in self.filtered("repair_id"):
            repair = booking.repair_id
            if repair.state in ("done", "cancel"):
                continue
            vals = {}
            if booking.start and repair.schedule_date != booking.start:
                vals["schedule_date"] = booking.start
            if booking.duration and float_compare(
                booking.duration, repair.planned_duration, precision_digits=2
            ):
                vals["planned_duration"] = booking.duration
            if booking.technician_id and repair.technician_id != booking.technician_id:
                vals["technician_id"] = booking.technician_id.id
            if vals:
                repair.with_context(shop_scheduling_sync=True).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        bookings = super().create(vals_list)
        bookings._shop_sync_repair()
        return bookings

    def write(self, vals):
        result = super().write(vals)
        # Always sync back, even for job-driven writes: rescheduling can hand
        # the work to a different technician, and the job has to say so. The
        # loop stops on the repair side, which skips its own push-back.
        self._shop_sync_repair()
        return result

    def action_schedule(self):
        """Place appointments on a pinned week grid.

        The stock meetings calendar declares no scale, so it opens in whatever
        scale this browser session last used, and a click in month scale
        creates an all-day event -- 00:00 to 23:59, which fits no work
        interval and so books nobody. The shop view pins the scale and drops
        the all-day row.
        """
        action = super().action_schedule()
        view = self.env.ref(
            "shop_scheduling.calendar_event_view_calendar_shop",
            raise_if_not_found=False,
        )
        if view:
            action["view_id"] = view.id
            action["views"] = [
                (view.id, "calendar"),
                (False, "list"),
                (False, "form"),
            ]
        return action

    def action_unschedule(self):
        result = super().action_unschedule()
        for booking in self.filtered("repair_id"):
            booking.repair_id.message_post(
                body=_(
                    "Appointment %(booking)s was unscheduled. The scheduled "
                    "date is now stale until the job is booked again.",
                    booking=booking.display_name,
                )
            )
        return result

    def action_view_repair(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Repair Order"),
            "res_model": "repair.order",
            "view_mode": "form",
            "res_id": self.repair_id.id,
        }

    def action_shop_create_repair(self):
        """Open a draft job for an appointment booked without one.

        This is the web-booked path: the customer picked a slot from the
        portal, and the front office turns it into a job at intake.
        """
        self.ensure_one()
        repair = self.env["repair.order"].create(self._shop_prepare_repair_vals())
        self.repair_id = repair
        return {
            "type": "ir.actions.act_window",
            "name": _("Repair Order"),
            "res_model": "repair.order",
            "view_mode": "form",
            "res_id": repair.id,
        }

    def _shop_prepare_repair_vals(self):
        self.ensure_one()
        vals = {
            "partner_id": self.partner_ids[:1].id,
            "technician_id": self.technician_id.id,
            "service_advisor_id": self.user_id.id,
        }
        if self.start:
            vals["schedule_date"] = self.start
        if self.duration:
            vals["planned_duration"] = self.duration
        return vals
