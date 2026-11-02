# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component


class ScanRepairHandler(Component):
    """Let the generic "scan anything" screen resolve repair orders too.

    This is separate from the scenario's own ``/scan`` endpoint: it is what
    makes a work-order barcode meaningful from the app's global scan page,
    outside any job.
    """

    _name = "shopfloor.scan.repair.handler"
    _inherit = "shopfloor.scan.anything.handler"

    record_type = "repair_job"

    def search(self, identifier):
        return self._search.repair_from_scan(identifier)

    @property
    def converter(self):
        return self._data_detail.repair_job_detail

    def schema(self):
        return self._schema_detail.repair_job_detail()
