# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.tools import float_compare


class RepairOrder(models.Model):
    _inherit = "repair.order"

    # A new job is not scheduled yet. Core stamps "now" on it, which reads as
    # an appointment that was never made; the date is meant to come from the
    # appointment, so leave it empty until the job is booked.
    schedule_date = fields.Datetime(default=None, required=False)
    planned_duration = fields.Float(default=None)
    booking_ids = fields.One2many(
        "resource.booking",
        "repair_id",
        string="Appointments",
    )
    booking_id = fields.Many2one(
        "resource.booking",
        string="Appointment",
        compute="_compute_booking_id",
        help="Appointment driving this job's scheduled date and technician.",
    )
    booking_count = fields.Integer(compute="_compute_booking_id")
    booking_type_id = fields.Many2one(
        "resource.booking.type",
        string="Appointment Type",
        compute="_compute_booking_type_id",
        store=True,
        readonly=False,
        tracking=True,
        help="Kind of work this job needs. Every technician bookable for it "
        "sees the job in the shop floor app, even before it is scheduled. "
        "Scheduling starts from it, and once the job has an appointment it "
        "follows that appointment's type.",
    )
    booking_type_color = fields.Integer(
        related="booking_type_id.color",
        string="Appointment Type Colour",
        help="Colours the job on the repair calendar.",
    )
    shop_vehicle_label = fields.Char(
        string="Vehicle Label",
        compute="_compute_shop_vehicle_label",
        help="Colour/Year/Brand/Model/Plate/Unit, for the repair calendar.",
    )
    booking_type_user_ids = fields.Many2many(
        "res.users",
        "repair_order_booking_type_user_rel",
        "repair_id",
        "user_id",
        string="Appointment Type Technicians",
        compute="_compute_booking_type_user_ids",
        store=True,
        help="Everyone bookable for this job's appointment type. They can all "
        "pick the job up, whoever it is assigned to.",
    )
    book_hours = fields.Float(
        string="Book Hours",
        compute="_compute_book_hours",
        help="Flat-rate hours on the service lines. Seeds the appointment "
        "duration, so a technician's day is booked for as long as the job "
        "was sold for.",
    )

    @api.depends("booking_ids.start")
    def _compute_booking_id(self):
        for repair in self:
            bookings = repair.booking_ids
            scheduled = bookings.filtered("start").sorted("start")
            repair.booking_id = scheduled[-1:] or bookings[-1:]
            repair.booking_count = len(bookings)

    # The appointment owns the type once there is one, the same way it owns
    # the date and the technician. Without one -- not scheduled yet, or its
    # appointment canceled -- the job keeps whatever type it already had.
    @api.depends("booking_ids.start", "booking_ids.type_id")
    def _compute_booking_type_id(self):
        for repair in self:
            repair.booking_type_id = repair.booking_id.type_id or repair.booking_type_id

    # Stored so it can be searched by people who cannot read appointment
    # types -- technicians filtering their job list, for one.
    @api.depends(
        "booking_type_id.combination_rel_ids.combination_id.active",
        "booking_type_id.combination_rel_ids.combination_id.resource_ids.user_id",
    )
    def _compute_booking_type_user_ids(self):
        for repair in self:
            combinations = repair.booking_type_id.combination_rel_ids.combination_id
            repair.booking_type_user_ids = (
                combinations.filtered("active").resource_ids.user_id
            )

    @api.depends(
        "vehicle_id.color",
        "vehicle_id.model_year",
        "vehicle_id.model_id.name",
        "vehicle_id.model_id.brand_id.name",
        "vehicle_id.license_plate",
        "vehicle_id.unit_number",
    )
    def _compute_shop_vehicle_label(self):
        # The same line the shop floor app shows for a job
        # (shopfloor_repair's vehicle_description).
        for repair in self:
            vehicle = repair.vehicle_id
            parts = (
                vehicle.color,
                vehicle.model_year,
                vehicle.model_id.brand_id.name,
                vehicle.model_id.name,
                vehicle.license_plate,
                vehicle.unit_number,
            )
            repair.shop_vehicle_label = "/".join(
                part.strip() for part in parts if part and part.strip()
            )

    @api.depends("repair_service_ids.product_uom_qty", "repair_service_ids.product_uom")
    def _compute_book_hours(self):
        time_category = self.env.ref("uom.uom_categ_wtime", raise_if_not_found=False)
        for repair in self:
            services = repair.repair_service_ids
            if time_category:
                services = services.filtered(
                    lambda service: service.product_uom.category_id == time_category
                )
            repair.book_hours = sum(services.mapped("product_uom_qty"))

    def action_shop_schedule(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Appointment"),
            "res_model": "shop.appointment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repair_id": self.id},
        }

    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Appointments"),
            "res_model": "resource.booking",
            "context": {"default_repair_id": self.id},
        }
        if len(self.booking_ids) == 1:
            action.update(view_mode="form", res_id=self.booking_ids.id)
        else:
            action.update(
                view_mode="list,calendar,form",
                domain=[("repair_id", "=", self.id)],
            )
        return action

    @api.model
    def default_get(self, fields_list):
        # repair_scheduled_date_calendar_view always fills the configured
        # duration here, so the field default alone is not enough.
        defaults = super().default_get(fields_list)
        defaults.pop("planned_duration", None)
        return defaults

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("shop_scheduling_sync"):
            self._shop_push_to_booking(vals)
        return result

    def unlink(self):
        # Unlink in Python so each booking also drops its meeting; a database
        # cascade would leave the calendar events behind.
        self.booking_ids.unlink()
        return super().unlink()

    def _shop_push_to_booking(self, vals):
        """Send job-side rescheduling back to the appointment.

        Only appointments that are already scheduled are moved: a pending
        appointment is booked through the wizard or the portal, where the
        openings are actually offered.
        """
        if not {"schedule_date", "planned_duration", "technician_id"} & vals.keys():
            return
        for repair in self:
            booking = repair.booking_id
            if not booking or not booking.start:
                continue
            booking_vals = {}
            # Clearing the date does not unschedule the appointment; that is
            # what Unschedule is for.
            if (
                "schedule_date" in vals
                and repair.schedule_date
                and repair.schedule_date != booking.start
            ):
                booking_vals["start"] = repair.schedule_date
            if (
                "planned_duration" in vals
                and repair.planned_duration
                and float_compare(
                    repair.planned_duration, booking.duration, precision_digits=2
                )
            ):
                booking_vals["duration"] = repair.planned_duration
            if (
                "technician_id" in vals
                and repair.technician_id != booking.technician_id
            ):
                booking_vals.update(repair._shop_technician_booking_vals(booking))
            if booking_vals:
                booking.with_context(shop_scheduling_sync=True).write(booking_vals)

    def _shop_technician_booking_vals(self, booking):
        """Reassign the appointment to the job's technician when possible."""
        self.ensure_one()
        combination = booking._shop_combination_for_user(self.technician_id)
        if combination:
            return {
                "combination_id": combination.id,
                "combination_auto_assign": False,
            }
        if self.technician_id:
            booking.message_post(
                body=_(
                    "%(technician)s was put on job %(repair)s but has no "
                    "bookable resource combination in appointment type "
                    "%(type)s, so this appointment still books "
                    "%(booked)s.",
                    technician=self.technician_id.display_name,
                    repair=self.name,
                    type=booking.type_id.display_name,
                    booked=booking.combination_id.display_name or _("nobody"),
                )
            )
        return {}
