# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component


class ShopfloorSchemaDetailAction(Component):
    """Schema for the job hub payload built by ``data_detail.repair_job_detail``."""

    _inherit = "shopfloor.schema.detail.action"

    def repair_job_detail(self):
        schema = self.repair_job()
        schema.update(
            {
                "internal_notes": {"type": "string", "required": True},
                "repair_request": {"type": "string", "required": True},
                "odometer_in": {"type": "float", "required": True},
                "odometer_unit": {"type": "string", "required": True},
                "under_warranty": {"type": "boolean", "required": True},
                "sale_order": self._nullable_record(),
                "timer": self._schema_dict_of(self.timer()),
            }
        )
        return schema

    def repair_timesheet_detail(self):
        schema = self.repair_timesheet()
        schema.update(
            {
                "jobs": self._schema_list_of(self._timesheet_job_choice()),
            }
        )
        return schema

    def _timesheet_job_choice(self):
        schema = self._simple_record()
        schema.update(
            {
                "ref": {"type": "string", "required": True},
                "customer": {"type": "string", "required": True},
                "services": self._schema_list_of(self._simple_record()),
            }
        )
        return schema
