# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Defaults live in data/ir_config_parameter.xml: a boolean parameter set
    # to False is deleted, so "missing" must mean the default, which for two
    # of these is True.
    repair_tech_allow_finish = fields.Boolean(
        string="Technicians can finish jobs",
        config_parameter="repair_tech_app.allow_finish",
        help="Technicians close a job (Repaired) from the app. Off: the office "
        "does.",
    )
    repair_tech_show_unassigned = fields.Boolean(
        string="Show unassigned jobs",
        config_parameter="repair_tech_app.show_unassigned",
        help="Jobs with no technician appear on every technician's list, for "
        "whoever picks them up.",
    )
    repair_tech_include_responsible = fields.Boolean(
        string="Include jobs they are responsible for",
        config_parameter="repair_tech_app.include_responsible",
        help="Also list jobs where the technician is the order's Responsible.",
    )
    repair_tech_require_photo_on_fail = fields.Boolean(
        string="Photo required for problems",
        config_parameter="repair_tech_app.require_photo_on_fail",
        help="An inspection item graded as a problem needs a photo first.",
    )
    repair_tech_catalog_page_size = fields.Integer(
        string="Catalog page size",
        config_parameter="repair_tech_app.catalog_page_size",
        default=30,
    )
