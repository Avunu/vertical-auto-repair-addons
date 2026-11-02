# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # A job that is not scheduled yet has no date, but its parts still need
    # one: core copies the job's date onto every move (the parts list's
    # ``default_date``, the date sync on write) and the move's own date is
    # required. Until the job is booked its parts carry the time they were
    # added; booking the job moves them, as core already does.
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "date" in vals and not vals["date"]:
                vals["date"] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        if "date" in vals and not vals["date"]:
            vals = {key: value for key, value in vals.items() if key != "date"}
        return super().write(vals)
