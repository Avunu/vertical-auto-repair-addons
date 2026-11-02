# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component


class ShopfloorSchemaAction(Component):
    """Cerberus schemas mirroring the payloads built in ``actions/data.py``.

    Keep the two in lockstep. base_rest validates responses with
    ``purge_unknown=True``, so a key that is missing here is not an error --
    it is silently stripped from the response and the screen renders blank.
    """

    _inherit = "shopfloor.schema.action"

    # -- reusable primitives ---------------------------------------------

    def _optional_string(self):
        return {"type": "string", "nullable": True, "required": False}

    def _float(self, required=True):
        return {"type": "float", "required": required}

    def _integer(self, required=True):
        return {"type": "integer", "required": required}

    def _nullable_record(self):
        """A {id, name} dict that may be absent altogether."""
        return self._schema_dict_of(self._simple_record(), required=False)

    # -- repair.order -----------------------------------------------------

    def repair_job(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "required": True},
            "state": {"type": "string", "required": True},
            "state_label": {"type": "string", "required": True},
            "vehicle_description": {"type": "string", "required": True},
            "priority": {"type": "string", "nullable": True, "required": False},
            "schedule_date": self._optional_string(),
            "total_hours": self._float(),
            "customer_concern": {"type": "string", "required": True},
            "parts_done": self._integer(),
            "parts_total": self._integer(),
            "inspection_graded": self._integer(),
            "inspection_total": self._integer(),
            "inspection_count": self._integer(),
            "stage": self._nullable_record(),
            "partner": self._nullable_record(),
            "technician": self._nullable_record(),
            "vehicle": self._schema_dict_of(self.vehicle(), required=False),
        }

    def vehicle(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "nullable": True, "required": True},
            "license_plate": self._optional_string(),
            "vin": self._optional_string(),
            "model_year": self._optional_string(),
        }

    # -- stock.move (a part on the job) -----------------------------------

    def repair_part(self):
        return {
            "id": {"required": True, "type": "integer"},
            "quantity_demand": self._float(),
            "quantity_done": self._float(),
            "picked": {"type": "boolean", "required": True},
            "state": {"type": "string", "required": True},
            "state_label": {"type": "string", "required": True},
            "forecast_availability": {
                "type": "float",
                "nullable": True,
                "required": False,
            },
            "tracking": {"type": "string", "nullable": True, "required": False},
            "shopfloor_added": {"type": "boolean", "required": True},
            "product": self._schema_dict_of(self.catalog_product(), required=False),
            "uom": self._nullable_record(),
            "lots": self._schema_list_of(self._simple_record(), required=False),
        }

    # -- repair.service (a service line the technician can time) ----------

    def repair_service_timer(self):
        """Just the running/elapsed part of `timer()` -- a service's own
        row-level timer has no `my_hours`/`total_hours`/`job_name` of its
        own (those live on the row itself as `actual_time`, and on the job
        the service belongs to), unlike the job-level `timer()` schema.
        """
        return {
            "running": {"type": "boolean", "required": True},
            "line_id": {"type": "integer", "nullable": True, "required": False},
            "started_at": self._optional_string(),
            "elapsed_hours": self._float(),
        }

    def repair_service(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "nullable": True, "required": True},
            "estimated_time": self._float(),
            "actual_time": self._float(),
            "my_time": self._float(),
            "product": self._schema_dict_of(self.catalog_product(), required=False),
            "timer": self._schema_dict_of(self.repair_service_timer()),
        }

    # -- product.product ---------------------------------------------------

    def catalog_product(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "nullable": True, "required": True},
            "default_code": self._optional_string(),
            "barcode": self._optional_string(),
            "tracking": {"type": "string", "nullable": True, "required": False},
            "uom": self._nullable_record(),
            # Only present on the catalog endpoints: computing on-hand for
            # every part of a job would be a needless read of stock.quant.
            "qty_available": {"type": "float", "required": False},
        }

    # -- inspections -------------------------------------------------------

    def inspection(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "nullable": True, "required": True},
            "state": {"type": "string", "required": True},
            "state_label": {"type": "string", "required": True},
            "result": {"type": "string", "nullable": True, "required": False},
            "odometer": self._float(required=False),
            "odometer_unit": {"type": "string", "nullable": True, "required": False},
            "date_inspected": self._optional_string(),
            "template": self._nullable_record(),
            "graded_count": self._integer(),
            "line_count": self._integer(),
            "counts": self._schema_dict_of(
                {
                    "today": self._integer(),
                    "good": self._integer(),
                    "future": self._integer(),
                    "attention": self._integer(),
                    "fail_state": self._integer(),
                }
            ),
        }

    def inspection_line(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "nullable": True, "required": True},
            "sequence": self._integer(required=False),
            "severity": {"type": "string", "nullable": True, "required": True},
            "result": {"type": "string", "required": True},
            "note": self._optional_string(),
            "instruction": self._optional_string(),
            "measurement_summary": self._optional_string(),
            "measurement_alert": {"type": "boolean", "required": False},
            "image_count": self._integer(required=False),
            "category": self._nullable_record(),
            "conditions": self._schema_list_of(self._simple_record(), required=False),
            "recommended_actions": self._schema_list_of(
                self._simple_record(), required=False
            ),
            "measurements": self._schema_list_of(self.measurement(), required=False),
        }

    def measurement(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": {"type": "string", "nullable": True, "required": True},
            "sequence": self._integer(required=False),
            "position": {"type": "string", "nullable": True, "required": False},
            "position_label": self._optional_string(),
            "uom": {"type": "string", "nullable": True, "required": False},
            "uom_label": self._optional_string(),
            "value": self._float(),
            "spec_min": self._float(required=False),
            "spec_max": self._float(required=False),
            "out_of_spec": {"type": "boolean", "required": False},
        }

    # -- catalogs of choices shown in the grading form ---------------------

    def inspection_choices(self):
        return {
            "severities": self._schema_list_of(
                {
                    "value": {"type": "string", "required": True},
                    "label": {"type": "string", "required": True},
                }
            ),
            "conditions": self._schema_list_of(self._simple_record()),
            "actions": self._schema_list_of(self._simple_record()),
        }

    # -- account.analytic.line (a technician's own timesheet line) ---------

    def repair_timesheet(self):
        return {
            "id": {"required": True, "type": "integer"},
            "name": self._optional_string(),
            "date": self._optional_string(),
            "date_time": self._optional_string(),
            "date_time_end": self._optional_string(),
            "unit_amount": self._float(),
            "job": self._nullable_record(),
            "job_ref": self._optional_string(),
            "service": self._nullable_record(),
        }

    # -- hr.attendance (a technician's own clock-in/out) --------------------

    def attendance_record(self):
        return {
            "id": {"required": True, "type": "integer"},
            "check_in": {"type": "string", "required": True},
            "check_out": self._optional_string(),
        }

    def attendance_day(self):
        return {
            "date": {"type": "string", "required": True},
            "hours": self._float(),
            "records": self._schema_list_of(self.attendance_record()),
        }

    # -- timer -------------------------------------------------------------

    def timer(self):
        return {
            "running": {"type": "boolean", "required": True},
            "line_id": {"type": "integer", "nullable": True, "required": False},
            "started_at": self._optional_string(),
            "elapsed_hours": self._float(),
            "my_hours": self._float(),
            "total_hours": self._float(),
            "job_name": {"type": "string", "nullable": True, "required": False},
        }

    def service_timer(self):
        schema = self.timer()
        schema["service_name"] = {
            "type": "string",
            "nullable": True,
            "required": False,
        }
        schema["repair_id"] = {"type": "integer", "required": False}
        schema["service_id"] = {"type": "integer", "required": False}
        return schema

    def shift_timer(self):
        return {
            "running": {"type": "boolean", "required": True},
            "started_at": self._optional_string(),
            "elapsed_hours": self._float(),
            # Whichever service (if any) currently has a running work timer,
            # same shape as `timer()` plus `service_name` - lets the app-
            # bar's compact job timer poll this endpoint directly instead
            # of only getting it from the repair_job scenario's own
            # payload.
            "current_job": self._schema_dict_of(self.service_timer(), required=False),
        }
