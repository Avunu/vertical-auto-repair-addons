# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

SEARCH_DAYS = 14


class ShopAppointmentWizard(models.TransientModel):
    _name = "shop.appointment.wizard"
    _description = "Schedule a Repair Order Appointment"

    repair_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(related="repair_id.partner_id")
    vehicle_id = fields.Many2one(related="repair_id.vehicle_id")
    type_id = fields.Many2one(
        "resource.booking.type",
        string="Appointment Type",
        required=True,
        default=lambda self: self._default_type_id(),
    )
    duration = fields.Float(
        string="Duration",
        compute="_compute_duration",
        store=True,
        readonly=False,
        help="How long the technician is booked for. Defaults to the book "
        "hours already on the job.",
    )
    technician_id = fields.Many2one(
        "res.users",
        string="Preferred Technician",
        help="Leave empty to take whichever technician is free in the slot "
        "you pick. Set it to book one specific person, whose own openings "
        "then decide what is bookable.",
    )
    search_days = fields.Integer(
        string="Look Ahead (days)",
        default=SEARCH_DAYS,
        required=True,
    )
    slot_ids = fields.One2many(
        "shop.appointment.slot",
        "wizard_id",
        string="Openings",
    )
    openings_searched = fields.Boolean()
    shop_tz = fields.Selection(
        related="type_id.resource_calendar_id.tz", string="Shop Timezone"
    )

    @api.model
    def _default_type_id(self):
        # Start from the job's own type -- its appointment's, once it has one
        # -- rather than whichever shop type happens to sort first.
        repair = self.env["repair.order"].browse(
            self.env.context.get("default_repair_id")
        )
        return repair.exists().booking_type_id or self.env[
            "resource.booking.type"
        ].search([("shop_repair_ok", "=", True)], limit=1)

    @api.depends("repair_id", "type_id")
    def _compute_duration(self):
        for wizard in self:
            wizard.duration = (
                wizard.repair_id.book_hours
                or wizard.repair_id.planned_duration
                or wizard.type_id.duration
            )

    def action_schedule(self):
        """Open the calendar to place the job's appointment."""
        booking = self._create_booking()
        return booking.action_schedule()

    def action_find_openings(self):
        """List the shop's real openings, without leaving the backend.

        The portal page used to be the only view that computed free slots out
        of every technician's calendar at once, so the front office had to
        leave Odoo to answer "when can you take me?", then come back and
        reproduce the answer on a grid that shows none of it. Same
        computation, same deadline, listed here -- and bookable in one click,
        so the answer and the booking cannot drift apart.
        """
        self.ensure_one()
        self.slot_ids.unlink()
        self.env["shop.appointment.slot"]._shop_from_openings(
            self._probe_booking()._shop_openings(days=self.search_days),
            wizard=self,
        )
        self.openings_searched = True
        return self._reopen()

    def action_open_portal(self):
        """Hand the customer the portal page for this appointment."""
        return self._create_booking().action_open_portal()

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Appointment"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def _probe_booking(self):
        """An appointment that exists only to be asked what is free.

        Openings follow from the type, the duration and the preferred
        technician -- everything the front office has already typed -- so they
        can be answered before anything is created. Nobody wants a trail of
        abandoned appointments from browsing for a slot.
        """
        self.ensure_one()
        combination = self._booking_combination()
        return self.env["resource.booking"].new(
            {
                "type_id": self.type_id.id,
                "duration": self.duration,
                "combination_id": combination.id,
                "combination_auto_assign": not combination,
            }
        )

    def _create_booking(self, start=None):
        """The job's appointment, created only if it has none yet.

        A job has one appointment. Scheduling it again moves that one, so the
        calendar never carries two meetings for the same job.
        """
        self.ensure_one()
        if not self.repair_id.partner_id:
            raise UserError(
                _("Set the customer on %s before booking it.", self.repair_id.name)
            )
        vals = self._prepare_booking_vals()
        if start:
            vals["start"] = start
        booking = self.repair_id.booking_id
        if booking:
            booking.write(vals)
            return booking
        return self.env["resource.booking"].create(vals)

    def _prepare_booking_vals(self):
        self.ensure_one()
        combination = self._booking_combination()
        vals = {
            "name": self._booking_name(),
            "type_id": self.type_id.id,
            "repair_id": self.repair_id.id,
            "partner_ids": [fields.Command.set(self.repair_id.partner_id.ids)],
            "duration": self.duration,
            "combination_auto_assign": not combination,
        }
        if combination:
            vals["combination_id"] = combination.id
        return vals

    def _booking_combination(self):
        """The combination booking the preferred technician, if there is one."""
        self.ensure_one()
        if not self.technician_id:
            return self.env["resource.booking.combination"]
        combination = self.env["resource.booking.combination"].search(
            [
                ("type_rel_ids.type_id", "=", self.type_id.id),
                ("resource_ids.user_id", "=", self.technician_id.id),
            ],
            limit=1,
        )
        if not combination:
            raise UserError(
                _(
                    "%(technician)s is not bookable for %(type)s. Add a "
                    "resource combination for them to that appointment "
                    "type, or leave the preferred technician empty.",
                    technician=self.technician_id.display_name,
                    type=self.type_id.display_name,
                )
            )
        return combination

    def _booking_name(self):
        self.ensure_one()
        if self.vehicle_id:
            return _(
                "%(repair)s - %(vehicle)s",
                repair=self.repair_id.name,
                vehicle=self.vehicle_id.display_name,
            )
        return self.repair_id.name
