# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.tools import babel_locale_parse, format_datetime, get_lang, posix_to_ldml


class ShopAppointmentSlot(models.TransientModel):
    _name = "shop.appointment.slot"
    _description = "Shop Appointment Opening"
    _order = "start"

    wizard_id = fields.Many2one(
        "shop.appointment.wizard",
        string="Wizard",
        index=True,
        ondelete="cascade",
    )
    booking_id = fields.Many2one(
        "resource.booking",
        string="Appointment",
        index=True,
        ondelete="cascade",
        help="Appointment this opening was listed for, when it already exists.",
    )
    name = fields.Char(compute="_compute_name", string="Opening")
    start = fields.Datetime(required=True)
    stop = fields.Datetime()
    technician_ids = fields.Many2many(
        "res.users",
        string="Free",
        help="Everyone bookable for this appointment type who is free for the "
        "whole opening. Whoever is still free when you take it gets the job.",
    )
    technician_count = fields.Integer(
        compute="_compute_technician_count",
        string="Free technicians",
    )

    @api.depends("start", "wizard_id.type_id", "booking_id.type_id")
    def _compute_name(self):
        """Label openings in the shop's own timezone.

        The shop's hours, the technicians' hours and the reader's preference
        are three different timezones, and quietly rendering openings in the
        third is how an opening at 9am reads as one at 3pm.

        The date half is pinned so a long list of openings reads as a compact
        agenda, but the clock half has to come from the active language --
        hard-coding it kept showing a 24-hour clock on instances whose
        res.lang says otherwise. ``short_time_format`` is the seconds-less
        one, which is what a slot label wants regardless of how the full
        format is configured.
        """
        lang = get_lang(self.env)
        clock = posix_to_ldml(
            lang.short_time_format, locale=babel_locale_parse(lang.code)
        )
        for slot in self:
            type_ = slot.wizard_id.type_id or slot.booking_id.type_id
            slot.name = format_datetime(
                slot.env,
                slot.start,
                tz=type_.resource_calendar_id.tz,
                dt_format=f"EEE d MMM, {clock}",
            )

    @api.depends("technician_ids")
    def _compute_technician_count(self):
        for slot in self:
            slot.technician_count = len(slot.technician_ids)

    @api.model
    def _shop_from_openings(self, openings, wizard=None, booking=None):
        """Turn ``resource.booking._shop_openings()`` output into rows."""
        return self.create(
            [
                {
                    "wizard_id": wizard.id if wizard else False,
                    "booking_id": booking.id if booking else False,
                    "start": opening["start"],
                    "stop": opening["stop"],
                    "technician_ids": [
                        fields.Command.set(
                            opening["combinations"]
                            .resource_ids.filtered(
                                lambda resource: resource.resource_type == "user"
                            )
                            .user_id.ids
                        )
                    ],
                }
                for opening in openings
            ]
        )

    def action_book(self):
        """Take this opening.

        Booking straight from a listed opening is the one path that cannot
        land on an unbookable slot, because the list is the availability
        answer itself rather than a grid drawn next to it.
        """
        self.ensure_one()
        booking = self.booking_id
        if booking:
            booking.start = self.start
        else:
            booking = self.wizard_id._create_booking(start=self.start)
        return booking._shop_booked_action()
