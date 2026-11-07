# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Builds a worked repair-shop scenario in USA Demo Company.

Written in Python rather than XML data files because most of what makes the
scenario useful is *state*: repair orders that have been confirmed, quotes the
customer accepted, invoices that were posted and paid, appointments relative
to today. None of that is expressible as a static record.

Everything created is registered with an XML ID under this module, so the whole
scenario disappears cleanly on uninstall and re-running the seed is a no-op
rather than a second copy.
"""

import logging
from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import demo_data

_logger = logging.getLogger(__name__)

COMPANY_NAME = "USA Demo Company"


class ShopDemoSeed(models.AbstractModel):
    _name = "shop.demo.seed"
    _description = "Repair Shop Demo Data Seeder"

    # ------------------------------------------------------------------
    # plumbing
    # ------------------------------------------------------------------

    @api.model
    def _company(self):
        company = self.env["res.company"].search([("name", "=", COMPANY_NAME)], limit=1)
        if not company:
            raise UserError(
                _(
                    "shop_demo seeds the %(name)s company, which does not exist "
                    "in this database. Create it (or rename the target company) "
                    "before installing this module.",
                    name=COMPANY_NAME,
                )
            )
        return company

    @api.model
    def _ref(self, key):
        return self.env.ref(f"shop_demo.{key}", raise_if_not_found=False)

    @api.model
    def _make(self, key, model, values):
        """Get-or-create `model` under the XML ID `shop_demo.<key>`.

        The XML ID is what makes the seed both idempotent and cleanly
        removable -- without it a second run would duplicate everything and
        uninstall would leave it all behind.
        """
        existing = self._ref(key)
        if existing:
            return existing
        record = self.env[model].create(values)
        self.env["ir.model.data"]._update_xmlids(
            [{"xml_id": f"shop_demo.{key}", "record": record, "noupdate": True}]
        )
        return record

    @api.model
    def _adopt(self, key, record):
        """Give an XML ID to a record we found rather than created.

        Used for pre-existing configuration the scenario leans on. `noupdate`
        keeps module updates off it, and because we did not create it,
        uninstall removing the XML ID is the right outcome -- the record stays.
        """
        if record and not self._ref(key):
            self.env["ir.model.data"]._update_xmlids(
                [{"xml_id": f"shop_demo.{key}", "record": record, "noupdate": True}]
            )
        return record

    @api.model
    def _find_or_make(self, key, model, domain, values):
        """Reuse a matching record if the database already has one.

        The target company may be a working sandbox with some configuration already
        in it (labor products, a Diagnostic template). Seeding must not create a
        second "Diagnostic Fee" next to the one already there.
        """
        existing = self._ref(key)
        if existing:
            return existing
        found = self.env[model].search(domain, limit=1)
        if found:
            return self._adopt(key, found)
        return self._make(key, model, values)

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    @api.model
    def seed(self):
        company = self._company()
        env = self.with_company(company).with_context(
            allowed_company_ids=[company.id],
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            no_reset_password=True,
        )
        _logger.info("shop_demo: seeding %s", company.name)
        env._seed_settings(company)
        products = env._seed_products(company)
        env._seed_stock(company, products)
        jobs = env._seed_service_jobs(company, products)
        staff = env._seed_staff(company)
        partners = env._seed_partners(company)
        vehicles = env._seed_vehicles(company, partners)
        env._seed_workflow(company, products, jobs, staff, partners, vehicles)
        _logger.info("shop_demo: done")
        return True

    def action_reseed(self):
        """Server-action entry point so the scenario can be topped up from the UI."""
        self.seed()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Demo data seeded"),
                "message": _("The repair-shop demo scenario is up to date."),
                "type": "success",
                "sticky": False,
            },
        }

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    def _seed_settings(self, company):
        # Miles, not kilometres -- this is a US shop and the odometer reading
        # is captured on every visit.
        self.env["ir.default"].set("fleet.vehicle", "odometer_unit", "miles")

        labor_project = self._find_or_make(
            "project_shop_labor",
            "project.project",
            [("name", "=", "Shop Labor"), ("company_id", "=", company.id)],
            {
                "name": "Shop Labor",
                "company_id": company.id,
                "allow_timesheets": True,
            },
        )
        # Point the repair order timer at it, so Start Timer on a repair order
        # is one tap instead of a project picker. Only if unset: this is real
        # configuration, and the shop may have chosen its own.
        if not company.repair_timesheet_project_id:
            company.repair_timesheet_project_id = labor_project

    def _uom(self, xmlid):
        return self.env.ref(xmlid)

    def _seed_products(self, company):
        """Labor services and parts.

        Labor is time-based because the shop bills flat rate: the quantity on
        the line is book hours, not wrench time.
        """
        products = {}
        hour = self._uom("uom.product_uom_hour")
        unit = self._uom("uom.product_uom_unit")

        for key, name, price, cost in demo_data.LABOR:
            products[key] = self._find_or_make(
                f"product_{key}",
                "product.product",
                [("name", "=", name), ("company_id", "in", [company.id, False])],
                {
                    "name": name,
                    "type": "service",
                    "company_id": company.id,
                    "uom_id": hour.id,
                    "uom_po_id": hour.id,
                    "list_price": price,
                    "standard_price": cost,
                    "invoice_policy": "order",
                    "purchase_ok": False,
                },
            )

        vendors = {}
        for key, name in demo_data.VENDORS:
            vendors[key] = self._make(
                f"vendor_{key}",
                "res.partner",
                {
                    "name": name,
                    "is_company": True,
                    "supplier_rank": 1,
                    "company_id": False,
                },
            )

        for key, name, price, cost, vendor_key, lead in demo_data.PARTS:
            product = self._make(
                f"product_{key}",
                "product.product",
                {
                    "name": name,
                    "type": "consu",
                    "is_storable": True,
                    "company_id": company.id,
                    "uom_id": unit.id,
                    "uom_po_id": unit.id,
                    "list_price": price,
                    "standard_price": cost,
                    "purchase_ok": True,
                    "seller_ids": [
                        fields.Command.create(
                            {
                                "partner_id": vendors[vendor_key].id,
                                "price": cost,
                                "delay": lead,
                                "company_id": company.id,
                            }
                        )
                    ],
                },
            )
            products[key] = product

        self._apply_special_order_routes(products)
        return products

    def _apply_special_order_routes(self, products):
        """Put the parts the shop does not stock on MTO + Buy.

        This is what makes "parts you don't stock order themselves" visible:
        a repair order needing one of these raises a per-job RFQ instead of
        waiting for someone to notice. Stocked parts are left alone -- they
        replenish against the shelf, not per job.
        """
        buy = self.env.ref(
            "purchase_stock.route_warehouse0_buy", raise_if_not_found=False
        )
        mto = self.env.ref("stock.route_warehouse0_mto", raise_if_not_found=False)
        if not buy or not mto:
            return
        # Odoo ships the MTO route archived; nothing can use it until it is on.
        if not mto.active:
            mto.active = True
        special_order = [
            key
            for key, *_rest in demo_data.PARTS
            if key not in demo_data.ON_HAND and key in products
        ]
        for key in special_order:
            products[key].route_ids = [fields.Command.set([buy.id, mto.id])]

    def _seed_stock(self, company, products):
        """Put the fast-moving parts on the shelf.

        Left deliberately uneven: some parts are stocked, some are not, so the
        "parts availability" behaviour on a repair order has something to show.
        """
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse:
            return
        location = warehouse.lot_stock_id
        Quant = self.env["stock.quant"].sudo()
        for key, quantity in demo_data.ON_HAND.items():
            product = products.get(key)
            if not product:
                continue
            Quant.with_context(inventory_mode=True).create(
                {
                    "product_id": product.id,
                    "location_id": location.id,
                    "inventory_quantity": quantity,
                }
            )._apply_inventory()

    def _seed_service_jobs(self, company, products):
        """Canned jobs, and the inspection actions that price themselves with them.

        This is the hinge of the estimate builder: a technician picks a
        recommended action on an inspection line, and the wizard reaches through
        `action.job_id` to price it.
        """
        jobs = {}
        for spec in demo_data.SERVICE_JOBS:
            values = {
                "name": spec["name"],
                "company_id": company.id,
                "customer_description": spec.get("description"),
                "pricing": spec.get("pricing", "fixed"),
                "price_fixed": spec.get("price", 0.0),
                "labor_product_id": products[spec["labor"]].id,
                "labor_hours": spec.get("hours", 0.0),
            }
            part_lines = [
                fields.Command.create(
                    {"product_id": products[part_key].id, "quantity": quantity}
                )
                for part_key, quantity in spec.get("parts", [])
                if part_key in products
            ]
            if part_lines:
                values["part_line_ids"] = part_lines
            job = self._make(f"job_{spec['key']}", "shop.service.job", values)
            jobs[spec["key"]] = job

            for action_name in spec.get("actions", []):
                action = self.env["shop.inspection.action"].search(
                    [("name", "=", action_name)], limit=1
                )
                if not action:
                    action = self._make(
                        f"action_{spec['key']}",
                        "shop.inspection.action",
                        {"name": action_name},
                    )
                if not action.job_id:
                    action.job_id = job.id
        return jobs

    def _seed_staff(self, company):
        """Technicians and service advisors.

        A technician needs the full stack to be bookable -- user, employee,
        resource on a working calendar, and a booking combination -- because
        openings are computed from the union of every combination.
        """
        staff = {"technicians": [], "advisor": None}
        calendar = self.env["resource.calendar"].search(
            [("company_id", "=", company.id)], limit=1
        ) or self.env["resource.calendar"].search([], limit=1)

        tech_group = self.env.ref(
            "resource_booking.group_user", raise_if_not_found=False
        )
        for key, name, login, is_advisor in demo_data.STAFF:
            employee = self._ref(f"employee_{key}")
            if not employee:
                found = self.env["hr.employee"].search(
                    [("name", "=", name), ("company_id", "=", company.id)], limit=1
                )
                if found:
                    employee = self._adopt(f"employee_{key}", found)
            if not employee:
                user = self._make(
                    f"user_{key}",
                    "res.users",
                    {
                        "name": name,
                        "login": login,
                        "company_id": company.id,
                        "company_ids": [fields.Command.link(company.id)],
                        "groups_id": [
                            fields.Command.link(self.env.ref("base.group_user").id),
                            fields.Command.link(
                                self.env.ref("fleet.fleet_group_user").id
                            ),
                        ]
                        + ([fields.Command.link(tech_group.id)] if tech_group else []),
                    },
                )
                employee = self._make(
                    f"employee_{key}",
                    "hr.employee",
                    {
                        "name": name,
                        "user_id": user.id,
                        "company_id": company.id,
                        "resource_calendar_id": calendar.id,
                    },
                )
            if is_advisor:
                staff["advisor"] = employee
            else:
                staff["technicians"].append(employee)
                self._make(
                    f"combination_{key}",
                    "resource.booking.combination",
                    {
                        "resource_ids": [fields.Command.link(employee.resource_id.id)],
                    },
                )
        self._seed_booking_types(company, staff)
        return staff

    def _seed_booking_types(self, company, staff):
        """Appointment kinds, each holding the technicians qualified for it."""
        combinations = self.env["resource.booking.combination"]
        for tech in staff["technicians"]:
            combinations |= combinations.search(
                [("resource_ids", "in", tech.resource_id.ids)]
            )
        if not combinations:
            return
        calendar = self.env["resource.calendar"].search(
            [("company_id", "=", company.id)], limit=1
        )
        for key, name, duration in demo_data.BOOKING_TYPES:
            booking_type = self._find_or_make(
                f"booking_type_{key}",
                "resource.booking.type",
                [("name", "=", name), ("company_id", "=", company.id)],
                {
                    "name": name,
                    "company_id": company.id,
                    "duration": duration,
                    "shop_repair_ok": True,
                    "resource_calendar_id": calendar.id if calendar else False,
                },
            )
            # Combinations hang off the type through an ordered rel model --
            # the order is what decides who gets an auto-assigned booking.
            attached = booking_type.combination_rel_ids.combination_id
            booking_type.write(
                {
                    "shop_repair_ok": True,
                    "combination_rel_ids": [
                        fields.Command.create(
                            {"combination_id": c.id, "sequence": 10 * (index + 1)}
                        )
                        for index, c in enumerate(combinations - attached)
                    ],
                }
            )

    # ------------------------------------------------------------------
    # master data
    # ------------------------------------------------------------------

    def _seed_partners(self, company):
        partners = {}
        for spec in demo_data.CUSTOMERS:
            partners[spec["key"]] = self._make(
                f"partner_{spec['key']}",
                "res.partner",
                {
                    "name": spec["name"],
                    "is_company": spec.get("is_company", False),
                    "street": spec.get("street"),
                    "city": spec.get("city", "Springfield"),
                    "state_id": self.env.ref("base.state_us_23").id,  # Missouri
                    "zip": spec.get("zip", "65804"),
                    "country_id": self.env.ref("base.us").id,
                    "phone": spec.get("phone"),
                    "email": spec.get("email"),
                    "customer_rank": 1,
                    "company_id": False,
                },
            )
        return partners

    def _seed_vehicles(self, company, partners):
        vehicles = {}
        for spec in demo_data.VEHICLES:
            model = self.env.ref(
                f"shop_vehicle_catalog.{spec['model']}", raise_if_not_found=False
            )
            if not model:
                _logger.warning("shop_demo: no catalog model %s", spec["model"])
                continue
            vehicles[spec["key"]] = self._make(
                f"vehicle_{spec['key']}",
                "fleet.vehicle",
                {
                    "model_id": model.id,
                    "model_year": str(spec["year"]),
                    "license_plate": spec["plate"],
                    "vin_sn": spec["vin"],
                    "color": spec.get("color"),
                    "owner_id": partners[spec["owner"]].id,
                    "driver_id": partners[spec["owner"]].id,
                    "odometer_unit": "miles",
                    "company_id": company.id,
                },
            )
            # Core fleet refuses an odometer lower than the last reading, and
            # finished jobs push it forward -- so on a re-seed the starting
            # value is already in the past. Only ever move it up.
            vehicle = vehicles[spec["key"]]
            if spec["odometer"] > vehicle.odometer:
                vehicle.odometer = spec["odometer"]
        return vehicles

    # ------------------------------------------------------------------
    # the job lifecycle
    # ------------------------------------------------------------------

    def _seed_workflow(self, company, products, jobs, staff, partners, vehicles):
        """Walk each scenario as far along the lifecycle as it is meant to go.

        Driven through the real buttons rather than by writing states directly,
        so the resulting data is internally consistent: stock moves exist,
        odometer history is written, the estimate carries its optional lines,
        and the chatter reads the way it would after a real job.
        """
        technicians = staff["technicians"]
        for index, spec in enumerate(demo_data.SCENARIOS):
            key = spec["key"]
            if self._ref(f"repair_{key}"):
                continue
            vehicle = vehicles.get(spec["vehicle"])
            if not vehicle:
                continue
            technician = technicians[index % len(technicians)] if technicians else False
            try:
                with self.env.cr.savepoint():
                    self._seed_one_job(
                        company, products, jobs, staff, vehicle, technician, spec
                    )
            except Exception as error:  # noqa: BLE001 - one bad scenario must not
                # abort the rest of the seed; the log says which one and why.
                _logger.warning(
                    "shop_demo: scenario %s could not be built: %s", key, error
                )

    def _seed_one_job(self, company, products, jobs, staff, vehicle, technician, spec):
        key = spec["key"]
        opened = fields.Datetime.now() + timedelta(days=spec.get("day_offset", 0))

        repair = self._make(
            f"repair_{key}",
            "repair.order",
            {
                "partner_id": vehicle.owner_id.id,
                "vehicle_id": vehicle.id,
                "company_id": company.id,
                "odometer_in": vehicle.odometer,
                "customer_concern": f"<p>{spec['concern']}</p>",
                "internal_notes": spec.get("notes") and f"<p>{spec['notes']}</p>",
                "schedule_date": opened,
                # technician_id / service_advisor_id are res.users; the
                # employee is what carries the bookable resource and timesheets.
                "technician_id": technician.user_id.id if technician else False,
                "service_advisor_id": staff["advisor"].user_id.id
                if staff["advisor"]
                else False,
            },
        )

        if spec.get("inspection"):
            self._seed_inspection(repair, vehicle, technician, staff, spec)

        stage = spec["stage"]
        if stage != "booked":
            self._add_job_lines(repair, products, jobs, spec)

        # Booked after the lines exist, so the appointment is as long as the
        # work actually sold. Booking a token slot for a six-hour job is the
        # most common scheduling mistake.
        try:
            self._seed_appointment(repair, spec, technician)
        except Exception as error:  # noqa: BLE001 - the job matters, the slot does not
            _logger.info(
                "shop_demo: %s could not be scheduled (%s); leaving it unbooked",
                key,
                error,
            )
        if stage == "booked":
            return

        if spec.get("estimate"):
            self._seed_estimate(repair, spec)
        if stage == "quoted":
            return

        # Past this point the job was approved, which means there has to be a
        # quotation to approve -- scenarios that skipped the estimate builder
        # get the plain "Create Quotation" path the writer would use.
        if not repair.sale_order_id:
            repair.action_create_sale_order()

        if stage == "declined":
            repair.action_repair_cancel()
            order = repair.sale_order_id
            if order and order.state in ("draft", "sent"):
                order.action_confirm()
                self._invoice_and_pay(order, opened)
            return

        # Everything from here is work the customer approved.
        order = repair.sale_order_id
        if order and order.state in ("draft", "sent"):
            order.action_confirm()

        repair.action_validate()
        if repair.state == "draft":
            repair._action_repair_confirm()
        if stage == "waiting_parts":
            return

        repair.action_repair_start()
        self._log_timesheets(repair, technician, spec)
        if stage == "in_bay":
            self._consume_parts(repair, partial=True)
            return

        self._consume_parts(repair, partial=False)
        repair.action_repair_end()
        vehicle.odometer = vehicle.odometer + spec.get("miles_since", 0)

        if stage == "invoiced" and order:
            self._invoice_and_pay(order, opened, pay=spec.get("paid", True))

    def _seed_appointment(self, repair, spec, technician):
        """Put the job on the shop schedule through the booking wizard.

        Uses the wizard rather than creating a resource.booking directly, so
        the appointment is built exactly the way the front office builds it.

        The slot is taken from OCA's own openings rather than invented: a
        booking whose start falls outside every technician's working calendar
        is rejected, and hard-coding a clock time would break the moment the
        shop's hours or the seed's run date changed.

        Finished jobs get no appointment. `_get_available_slots` clamps its
        search to the future, so a past slot is unreachable by design -- and a
        shop schedule showing last month's work would be noise anyway.
        """
        if self._ref(f"booking_{spec['key']}") or spec.get("day_offset", 0) < 0:
            return
        booking_type = self._ref(f"booking_type_{spec.get('booking', 'intake_diag')}")
        if not booking_type:
            return

        wizard = self.env["shop.appointment.wizard"].create(
            {"repair_id": repair.id, "type_id": booking_type.id}
        )
        booking = wizard._create_booking()
        self.env["ir.model.data"]._update_xmlids(
            [
                {
                    "xml_id": f"shop_demo.booking_{spec['key']}",
                    "record": booking,
                    "noupdate": True,
                }
            ]
        )
        # Book the hours that were sold. The wizard derives this from the job's
        # time-UoM service lines; fall back to the appointment type's default
        # for a job that has not been written up yet.
        sold_hours = sum(hours for _key, hours, _desc in spec.get("labor", []))
        booking.duration = (
            spec.get("duration")
            or sold_hours
            or wizard.duration
            or booking_type.duration
            or 1.0
        )

        slot = self._first_opening(booking, repair.schedule_date)
        if slot:
            booking.start = slot
        # No opening in the window: the booking stays unscheduled, which is a
        # real state ("requested, not yet placed") rather than a broken one.

    def _first_opening(self, booking, target):
        """First real opening at or after `target`, searched over two weeks."""
        tz = pytz.timezone(self.env.user.tz or "UTC")
        start_dt = pytz.UTC.localize(target).astimezone(tz)
        try:
            slots = booking._get_available_slots(
                start_dt, start_dt + timedelta(days=14)
            )
        except Exception as error:  # noqa: BLE001 - availability is best effort
            _logger.debug("shop_demo: no openings for %s: %s", booking.name, error)
            return None
        for day in sorted(slots):
            for slot in sorted(slots[day]):
                return slot.astimezone(pytz.UTC).replace(tzinfo=None)
        return None

    def _add_job_lines(self, repair, products, jobs, spec):
        """Parts and labor as the writer would enter them.

        Demand is what the customer is quoted; actual usage goes in `quantity`
        later, which is the distinction the whole billing model rests on.
        """
        moves = []
        for part_key, quantity in spec.get("parts", []):
            product = products.get(part_key)
            if not product:
                continue
            moves.append(
                fields.Command.create(
                    {
                        "repair_id": repair.id,
                        "product_id": product.id,
                        "product_uom_qty": quantity,
                        "name": product.name,
                        "company_id": repair.company_id.id,
                        # 'add' is what makes this a billable part rather than
                        # a removal: stock.move only raises a sale order line
                        # for moves of that type, and the source and
                        # destination locations are computed from it.
                        "repair_line_type": "add",
                    }
                )
            )
        if moves:
            repair.move_ids = moves
        for labor_key, hours, description in spec.get("labor", []):
            product = products.get(labor_key)
            if not product:
                continue
            # repair.service carries its description in display_name (a stored
            # Text on the OCA model), not in a `name` field.
            self.env["repair.service"].create(
                {
                    "repair_id": repair.id,
                    "product_id": product.id,
                    "product_uom_qty": hours,
                    "display_name": description or product.name,
                }
            )

    def _seed_inspection(self, repair, vehicle, technician, staff, spec):
        template = self.env["fleet.vehicle.inspection.template"].search(
            [("name", "=", spec["inspection"]["template"])], limit=1
        )
        if not template:
            return
        inspection = self._make(
            f"inspection_{spec['key']}",
            "fleet.vehicle.inspection",
            {
                "vehicle_id": vehicle.id,
                "inspection_template_id": template.id,
                "name": template.name,
                "odometer": vehicle.odometer,
                "repair_id": repair.id,
                "technician_id": technician.user_id.id if technician else False,
                "service_advisor_id": staff["advisor"].user_id.id
                if staff["advisor"]
                else False,
                "company_id": repair.company_id.id,
            },
        )
        if not inspection.inspection_line_ids:
            inspection.inspection_line_ids = [
                fields.Command.create(
                    inspection._compute_line_data_for_template_change(template_line)
                )
                for template_line in template.inspection_template_line_ids.sorted(
                    "sequence"
                )
            ]

        findings = dict(spec["inspection"].get("findings", []))
        for line in inspection.inspection_line_ids:
            item_name = line.inspection_item_id.name
            severity, action_name, note = findings.get(item_name, ("good", None, None))
            values = {"severity": severity}
            if note:
                # OCA calls the technician's free-text finding result_description.
                values["result_description"] = note
            if action_name:
                action = self.env["shop.inspection.action"].search(
                    [("name", "=", action_name)], limit=1
                )
                if action:
                    values["recommended_action_ids"] = [fields.Command.link(action.id)]
            line.write(values)
            # Give the measurement grid plausible readings so the customer
            # report has numbers on it rather than a column of zeros.
            for measurement in line.measurement_ids:
                measurement.value = self._measurement_value(measurement, severity)

        if spec["inspection"].get("confirmed", True):
            inspection.button_confirm()

    def _measurement_value(self, measurement, severity):
        """A reading inside spec for a good line, below it for a bad one."""
        low = measurement.spec_min or 0.0
        high = measurement.spec_max or (low * 2 if low else 10.0)
        if severity in ("today", "fail_state"):
            return round(low * 0.6, 2) if low else round(high * 0.2, 2)
        if severity in ("future", "attention"):
            return round(low * 1.1, 2) if low else round(high * 0.45, 2)
        return round((low + high) / 2, 2) if high else round(low * 2, 2)

    def _seed_estimate(self, repair, spec):
        """Run the real estimate builder so the quote carries optional lines."""
        Wizard = self.env["shop.estimate.builder"].with_context(
            active_model="repair.order", active_id=repair.id
        )
        defaults = Wizard.default_get(["repair_id", "line_ids"])
        if not defaults.get("line_ids"):
            # No priced findings -- fall back to a plain quotation so the
            # scenario still has something for the customer to approve.
            if not repair.sale_order_id:
                repair.action_create_sale_order()
            return
        wizard = Wizard.create(defaults)
        wizard.line_ids.filtered(lambda line: not line.job_id).include = False
        if not wizard.line_ids.filtered("include"):
            if not repair.sale_order_id:
                repair.action_create_sale_order()
            return
        wizard.action_generate()
        order = repair.sale_order_id
        if order and spec.get("estimate") == "sent" and order.state == "draft":
            order.state = "sent"

    def _log_timesheets(self, repair, technician, spec):
        project = self._ref("project_shop_labor")
        if not project or not spec.get("timesheets"):
            return
        task = self._make(
            f"task_{spec['key']}",
            "project.task",
            {
                "name": f"{repair.name} — {repair.vehicle_id.display_name}",
                "project_id": project.id,
                "company_id": repair.company_id.id,
            },
        )
        for offset, hours, description in spec["timesheets"]:
            self.env["account.analytic.line"].create(
                {
                    "name": description,
                    "project_id": project.id,
                    "task_id": task.id,
                    # Without this the hours exist but the repair order's own
                    # Timesheets tab reads empty -- the tab and its Total Hours
                    # are keyed on the repair order, not on the task.
                    "repair_order_id": repair.id,
                    "unit_amount": hours,
                    "employee_id": technician and technician.id,
                    "date": fields.Date.today() + timedelta(days=offset),
                    "company_id": repair.company_id.id,
                }
            )

    def _consume_parts(self, repair, partial):
        """Record what was actually used, in `quantity` -- never in demand.

        Editing demand after approval silently rewrites the customer's order,
        which is the one thing technicians must never do.
        """
        moves = repair.move_ids
        for index, move in enumerate(moves):
            if partial and index >= max(1, len(moves) // 2):
                continue
            move.quantity = move.product_uom_qty
            move.picked = True

    def _invoice_and_pay(self, order, invoice_date, pay=True):
        invoiceable = order.order_line.filtered(lambda line: line.qty_to_invoice > 0)
        if not invoiceable:
            return
        invoices = order._create_invoices()
        if not invoices:
            return
        invoices.invoice_date = fields.Date.to_date(invoice_date)
        invoices.action_post()
        if not pay:
            return
        for invoice in invoices:
            journal = self.env["account.journal"].search(
                [
                    ("type", "in", ("bank", "cash")),
                    ("company_id", "=", invoice.company_id.id),
                ],
                limit=1,
            )
            if not journal:
                continue
            wizard = (
                self.env["account.payment.register"]
                .with_context(active_model="account.move", active_ids=invoice.ids)
                .create({"journal_id": journal.id, "amount": invoice.amount_total})
            )
            wizard.action_create_payments()
