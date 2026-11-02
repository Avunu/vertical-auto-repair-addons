# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model_create_multi
    def create(self, vals_list):
        """Meetings are what actually schedule a booking -- sync from them.

        ``resource.booking.start`` is a stored compute fed by the meeting, so
        dragging an event in any calendar never passes through
        ``resource.booking.write``.
        """
        replaced = self.browse()
        for vals in vals_list:
            self._shop_force_booking_duration(vals)
            self._shop_check_booking_slot(vals)
            replaced |= self._shop_bookings_from_vals(vals).meeting_id
        # Placing an appointment that is already on the calendar moves it.
        # Left in place, the old meeting would stay on everyone's calendar
        # booking nobody -- and, still inviting the technician, would make
        # them look busy for any overlapping new placement. A refused
        # placement rolls this back with the rest of the transaction.
        replaced.unlink()
        events = super().create(vals_list)
        events.resource_booking_ids._shop_sync_repair()
        return events

    def write(self, vals):
        result = super().write(vals)
        self.resource_booking_ids._shop_sync_repair()
        return result

    @api.model
    def _shop_force_booking_duration(self, vals):
        """Keep the duration the front office booked, not the one it clicked.

        ``resource.booking.duration`` follows its meeting once one exists, so
        placing an appointment on the grid would quietly replace the job's
        book hours with whatever the click was worth -- an hour, usually --
        and push that onto the job as its planned duration. Upstream leaves
        this to ``web_calendar_slot_duration``, which is not installed here.

        Resizing the event afterwards still rules: that is a deliberate change
        to how long the bay is taken, and the job follows it.
        """
        # A month-scale click asks for an all-day event through the context
        # rather than the values, so both have to be checked.
        allday = vals.get("allday", self.env.context.get("default_allday"))
        if allday or not vals.get("start"):
            return
        booking = self._shop_bookings_from_vals(vals)[:1]
        if not booking.duration:
            return
        vals["duration"] = booking.duration
        # Replace the clicked end rather than dropping it. Leaving `stop` out
        # and trusting calendar.event._compute_stop() to fill it in does not
        # survive create(): the stored compute has not run by the time the
        # "stop must not precede start" constraint is checked, so the event is
        # rejected outright. Round to the minute exactly as that compute does.
        start = fields.Datetime.to_datetime(vals["start"])
        vals["stop"] = start + timedelta(minutes=round(booking.duration * 60))

    @api.model
    def _shop_check_booking_slot(self, vals):
        """Refuse an unbookable placement before the database does.

        Answering this late -- once the meeting exists -- is not an option.
        ``resource.booking.combination_id`` is computed from the meeting's
        dates, and the availability search behind it reads ``calendar.event``,
        which flushes the booking with its meeting already set and no
        combination chosen yet. Postgres rejects that half-written row through
        the ``combination_required_if_event`` check constraint from inside the
        compute, so the compute never returns and nothing readable is ever
        raised: the front office just gets "The operation cannot be completed:
        Missing resource booking combination."

        So the question gets asked here, while the placement is still only a
        proposal and nothing has been written.

        Appointments pinned to one technician are left alone: their
        combination is not being computed, so the row is never half written,
        and upstream's own scheduling constraint explains those.
        """
        if vals.get("allday") or not vals.get("start") or not vals.get("stop"):
            return
        if self.env.context.get("syncing_booking_ids"):
            # The booking is placing its own meeting, so the window it carries
            # is the one _get_best_combination() just settled on. Asking again
            # here is one availability search per technician for an answer
            # already given.
            return
        booking = self._shop_bookings_from_vals(vals)[:1]
        if not booking or not booking.combination_auto_assign:
            return
        start = fields.Datetime.to_datetime(vals["start"])
        stop = fields.Datetime.to_datetime(vals["stop"])
        if booking._shop_fitting_combinations(start, stop):
            return
        raise ValidationError(booking._shop_unbookable_message(start, stop))

    @api.model
    def _shop_bookings_from_vals(self, vals):
        """Resolve the booking a meeting is being created for.

        The placement action passes it as a context default, which the ORM only
        merges into the values further down in ``create()`` -- a quick create
        on the grid sends no ``resource_booking_ids`` of its own -- so both
        places have to be read. Commands arrive as tuples or as JSON lists.
        """
        commands = vals.get("resource_booking_ids")
        if commands is None:
            commands = self.env.context.get("default_resource_booking_ids")
        booking_ids = []
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or not command:
                continue
            if command[0] == fields.Command.SET and len(command) > 2:
                booking_ids.extend(command[2] or [])
            elif command[0] == fields.Command.LINK and len(command) > 1:
                booking_ids.append(command[1])
        return self.env["resource.booking"].browse(booking_ids).exists()
