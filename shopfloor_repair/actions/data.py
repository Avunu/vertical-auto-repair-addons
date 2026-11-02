# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from markupsafe import Markup

from odoo import fields
from odoo.tools import html2plaintext

from odoo.addons.component.core import Component
from odoo.addons.shopfloor_base.utils import ensure_model


class DataAction(Component):
    """List-level payloads for the repair shop floor app."""

    _inherit = "shopfloor.data.action"

    # -- helpers ---------------------------------------------------------

    def _plaintext(self, value):
        """Html field -> a string the Vue app can drop straight into a <span>.

        The technician's concern and notes are Html fields in Odoo but the
        mobile app has no sanitiser, so never ship markup to it.
        """
        if not value:
            return ""
        if isinstance(value, Markup):
            value = str(value)
        return html2plaintext(value).strip()

    def vehicle_description(self, vehicle):
        """Colour/Year/Brand/Model/Plate/Unit, e.g.
        "Silver/2005/Acme/Hauler/SHOP-001/T-104".

        Slash-separated like fleet's own vehicle name, but leading with what
        a technician sees walking up to the car. Missing parts are skipped
        rather than left as empty slots.
        """
        parts = (
            vehicle.color,
            vehicle.model_year,
            vehicle.model_id.brand_id.name,
            vehicle.model_id.name,
            vehicle.license_plate,
            vehicle.unit_number,
        )
        return "/".join(part.strip() for part in parts if part and part.strip())

    def job_label(self, repair):
        """What the app calls a job everywhere it has room for one name."""
        return (
            self.vehicle_description(repair.vehicle_id)
            or repair.partner_id.name
            or repair.name
        )

    # -- repair.order ----------------------------------------------------

    @ensure_model("repair.order")
    def repair_job(self, record, **kw):
        data = self._jsonify(record, self._repair_job_parser, **kw)
        if data is None:
            return None
        data.update(self._repair_job_extra(record))
        return data

    def repair_jobs(self, records, **kw):
        return [self.repair_job(rec, **kw) for rec in records]

    @property
    def _repair_job_parser(self):
        return [
            "id",
            "name",
            "state",
            "priority",
            "schedule_date",
            "timesheet_total_hours:total_hours",
            ("stage_id:stage", self._simple_record_parser()),
            ("partner_id:partner", self._simple_record_parser()),
            ("vehicle_id:vehicle", self._vehicle_parser),
            ("technician_id:technician", self._simple_record_parser()),
        ]

    @property
    def _vehicle_parser(self):
        return [
            "id",
            "display_name:name",
            "license_plate",
            "vin_sn:vin",
            "model_year",
        ]

    def _repair_job_extra(self, record):
        """Values the jsonify parser cannot express.

        Counters are computed here rather than as stored fields because they
        are pure presentation: the app needs "3 of 7 parts consumed" only to
        draw a progress bar.
        """
        parts = self._repair_job_parts(record)
        lines = record._shop_get_inspection_lines()
        return {
            "state_label": self._select_value_to_label(record, "state"),
            "vehicle_description": self.vehicle_description(record.vehicle_id),
            "customer_concern": self._plaintext(record.customer_concern),
            "parts_done": len(parts.filtered("picked")),
            "parts_total": len(parts),
            "inspection_graded": len(lines.filtered("severity")),
            "inspection_total": len(lines),
            "inspection_count": len(
                record.inspection_ids.filtered(lambda i: i.state != "cancel")
            ),
        }

    def _repair_job_parts(self, record):
        """The moves the technician is expected to install.

        Only 'add' lines: 'remove' and 'recycle' moves describe parts coming
        off the vehicle, which this app deliberately does not manage.
        """
        return record.move_ids.filtered(
            lambda move: move.repair_line_type == "add" and move.state != "cancel"
        )

    # -- stock.move (a part on the job) ----------------------------------

    @ensure_model("stock.move")
    def repair_part(self, record, **kw):
        data = self._jsonify(record, self._repair_part_parser, **kw)
        if data is None:
            return None
        data.update(
            {
                "state_label": self._select_value_to_label(record, "state"),
                "tracking": record.product_id.tracking,
                "shopfloor_added": bool(record.shopfloor_added_uid),
                "lots": [
                    {"id": line.lot_id.id, "name": line.lot_id.name}
                    for line in record.move_line_ids
                    if line.lot_id
                ],
            }
        )
        return data

    def repair_parts(self, records, **kw):
        return [self.repair_part(rec, **kw) for rec in records]

    @property
    def _repair_part_parser(self):
        return [
            "id",
            "product_uom_qty:quantity_demand",
            "quantity:quantity_done",
            "picked",
            "state",
            "forecast_availability",
            ("product_id:product", self._catalog_product_parser),
            ("product_uom:uom", self._simple_record_parser()),
        ]

    # -- repair.service (a service line the technician can time) ---------

    @ensure_model("repair.service")
    def repair_service(self, record, running_line=None, **kw):
        data = self._jsonify(record, self._repair_service_parser, **kw)
        if data is None:
            return None
        line = (running_line or self.env["account.analytic.line"].browse())[:1]
        is_running = bool(line) and line.repair_service_id == record
        elapsed = 0.0
        if is_running:
            elapsed = self.env["account.analytic.line"]._duration(
                line.date_time, fields.Datetime.now()
            )
        data["timer"] = {
            "running": is_running,
            "line_id": line.id if is_running else None,
            "started_at": (
                fields.Datetime.to_string(line.date_time) if is_running else None
            ),
            "elapsed_hours": elapsed,
        }
        # Several technicians can log time on the same service, so
        # `actual_time` is everyone's; "Mine" needs this user's share.
        my_lines = record.analytic_line_ids.filtered(
            lambda aal: aal.employee_id == self.env.user.employee_id
        )
        data["my_time"] = sum(my_lines.mapped("unit_amount"))
        return data

    def repair_services(self, records, running_line=None, **kw):
        return [
            self.repair_service(rec, running_line=running_line, **kw)
            for rec in records
        ]

    @property
    def _repair_service_parser(self):
        return [
            "id",
            "display_name:name",
            "estimated_time",
            "actual_time",
            ("product_id:product", self._catalog_product_parser),
        ]

    # -- product.product (catalog) ---------------------------------------

    @ensure_model("product.product")
    def catalog_product(self, record, **kw):
        data = self._jsonify(record, self._catalog_product_parser, **kw)
        if data is None:
            return None
        data.update({"qty_available": record.qty_available})
        return data

    def catalog_products(self, records, **kw):
        return [self.catalog_product(rec, **kw) for rec in records]

    @property
    def _catalog_product_parser(self):
        return [
            "id",
            "display_name:name",
            "default_code",
            "barcode",
            "tracking",
            ("uom_id:uom", self._simple_record_parser()),
        ]

    # -- fleet.vehicle.inspection ----------------------------------------

    @ensure_model("fleet.vehicle.inspection")
    def inspection(self, record, **kw):
        data = self._jsonify(record, self._inspection_parser, **kw)
        if data is None:
            return None
        lines = record.inspection_line_ids
        data.update(
            {
                "state_label": self._select_value_to_label(record, "state"),
                "graded_count": len(lines.filtered("severity")),
                "line_count": len(lines),
                "counts": {
                    "today": record.count_today,
                    "good": record.count_good,
                    "future": record.count_future,
                    "attention": record.count_attention,
                    "fail_state": record.count_fail_state,
                },
            }
        )
        return data

    def inspections(self, records, **kw):
        return [self.inspection(rec, **kw) for rec in records]

    @property
    def _inspection_parser(self):
        return [
            "id",
            "name",
            "state",
            "result",
            "odometer",
            "odometer_unit",
            "date_inspected",
            ("inspection_template_id:template", self._simple_record_parser()),
        ]

    # -- fleet.vehicle.inspection.line -----------------------------------

    @ensure_model("fleet.vehicle.inspection.line")
    def inspection_line(self, record, **kw):
        data = self._jsonify(record, self._inspection_line_parser, **kw)
        if data is None:
            return None
        data.update(
            {
                "name": record.inspection_item_id.name,
                "category": (
                    {
                        "id": record.category_id.id,
                        "name": record.category_id.name,
                    }
                    if record.category_id
                    else None
                ),
                "conditions": self._m2m_ids_names(record.condition_ids),
                "recommended_actions": self._m2m_ids_names(
                    record.recommended_action_ids
                ),
                "measurements": self.measurements(record.measurement_ids),
                "image_count": len(record.inspection_line_image_ids),
            }
        )
        return data

    def inspection_lines(self, records, **kw):
        return [self.inspection_line(rec, **kw) for rec in records]

    @property
    def _inspection_line_parser(self):
        return [
            "id",
            "sequence",
            "severity",
            "result",
            "result_description:note",
            "measurement_summary",
            "measurement_alert",
            "inspection_item_instruction:instruction",
        ]

    def _m2m_ids_names(self, records):
        return [{"id": rec.id, "name": rec.name} for rec in records]

    # -- shop.inspection.measurement -------------------------------------

    @ensure_model("shop.inspection.measurement")
    def measurement(self, record, **kw):
        data = self._jsonify(record, self._measurement_parser, **kw)
        if data is None:
            return None
        data.update(
            {
                "position_label": self._select_value_to_label(record, "position"),
                "uom_label": (
                    self._select_value_to_label(record, "uom") if record.uom else ""
                ),
            }
        )
        return data

    def measurements(self, records, **kw):
        return [self.measurement(rec, **kw) for rec in records]

    @property
    def _measurement_parser(self):
        return [
            "id",
            "name",
            "sequence",
            "position",
            "uom",
            "value",
            "spec_min",
            "spec_max",
            "out_of_spec",
        ]

    # -- account.analytic.line (a technician's own timesheet line) -------

    @ensure_model("account.analytic.line")
    def repair_timesheet(self, record, **kw):
        result = self._jsonify(record, self._repair_timesheet_parser, **kw)
        # `_simple_record_parser()` (shared by every other Many2one on this
        # stack) can only give the job's own `name` (the RO reference) -
        # same `job_label()` as `timer()`'s `job_name` below, since the
        # reference alone means nothing to the technician at a glance.
        repair = record.repair_order_id
        # Two open orders on one vehicle share a description, so the list also
        # needs the order number to tell their rows apart.
        result["job_ref"] = repair.name or ""
        if result.get("job") and repair:
            result["job"]["name"] = self.job_label(repair)
        service = record.repair_service_id
        if result.get("service") and service:
            # Same reasoning as the job name above: the bare relation's own
            # `display_name` (repair.service's own computed description) is
            # a fine fallback, but the product name is what the technician
            # actually recognises the service line by on the Services tab.
            result["service"]["name"] = (
                service.product_id.name or service.display_name
            )
        return result

    def repair_timesheets(self, records, **kw):
        return [self.repair_timesheet(rec, **kw) for rec in records]

    @property
    def _repair_timesheet_parser(self):
        return [
            "id",
            "name",
            "date",
            "date_time",
            "date_time_end",
            "unit_amount",
            ("repair_order_id:job", self._simple_record_parser()),
            ("repair_service_id:service", self._simple_record_parser()),
        ]

    # -- hr.attendance (a technician's own clock-in/out) ------------------

    def attendance_record(self, record):
        return {
            "id": record.id,
            "check_in": fields.Datetime.to_string(record.check_in),
            "check_out": (
                fields.Datetime.to_string(record.check_out) if record.check_out else None
            ),
        }

    def attendance_day(self, date, records):
        """One date's worth of attendance - almost always one record,
        occasionally more (a lunch break, a correction) - `hours` is the
        real day total (summed `worked_hours`, itself computed straight
        from `check_in`/`check_out`), `records` lets the app show/edit
        every pair rather than guessing which one an aggregate came from.
        """
        return {
            "date": fields.Date.to_string(date),
            "hours": sum(records.mapped("worked_hours")),
            "records": [self.attendance_record(rec) for rec in records],
        }

    # -- timer -----------------------------------------------------------

    def timer(self, repair, running_line):
        """Live timer state for one repair order.

        ``elapsed_hours`` is sent so the app can start its client-side ticker
        from the right offset; it is deliberately not persisted anywhere --
        the running analytic line still carries ``unit_amount = 0`` until it
        is stopped, which is exactly how the OCA time control identifies it.
        """
        line = running_line[:1]
        elapsed = 0.0
        if line:
            elapsed = self.env["account.analytic.line"]._duration(
                line.date_time, fields.Datetime.now()
            )
        my_lines = repair.timesheet_ids.filtered(
            lambda aal: aal.employee_id == self.env.user.employee_id
        )
        return {
            "running": bool(line),
            "line_id": line.id or None,
            "started_at": (
                fields.Datetime.to_string(line.date_time) if line else None
            ),
            "elapsed_hours": elapsed,
            "my_hours": sum(my_lines.mapped("unit_amount")),
            "total_hours": repair.timesheet_total_hours,
            # Lets a compact header display label the timer without a
            # second lookup - the job hub screen already has `record.name`
            # from `repair_job()` itself, but the header's compact timer is
            # a separate, globally-mounted component with no other access
            # to which job is current. The vehicle description is what the
            # technician matches against the car in front of them (same
            # label repair-job-card leads with); the RO reference alone
            # doesn't mean anything to them.
            "job_name": self.job_label(repair),
        }

    def service_timer(self, service, running_line):
        """Live timer state for one repair service.

        Same ``job_name`` derivation as ``timer()`` above (the header's
        label logic is unchanged, just re-pointed at whichever job the
        currently-tracked *service* belongs to), plus ``service_name`` for a
        header that wants to show which service specifically is running.
        """
        repair = service.repair_id
        line = running_line[:1]
        elapsed = 0.0
        if line:
            elapsed = self.env["account.analytic.line"]._duration(
                line.date_time, fields.Datetime.now()
            )
        return {
            "running": bool(line),
            "line_id": line.id or None,
            "started_at": (
                fields.Datetime.to_string(line.date_time) if line else None
            ),
            "elapsed_hours": elapsed,
            "my_hours": service.actual_time,
            "total_hours": service.actual_time,
            "job_name": self.job_label(repair),
            "service_name": service.display_name,
            # Lets "My Jobs" put the running timer (and its Stop button) on
            # the right job card - `job_name` alone can't tell apart two jobs
            # on the same vehicle.
            "repair_id": repair.id,
            "service_id": service.id,
        }
