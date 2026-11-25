# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Taking over from shopfloor_repair.

The technician app replaces shopfloor_repair and shopfloor_repair_mobile (the
OCA shopfloor scenario). What the shop set up there must survive the switch:

- ``pre_init_hook`` hands shopfloor_repair's records - the Shop Floor
  Technician group, its inspection rules and access rights, the Technician
  Note subtype - to this module, under the same ids. This module's data then
  updates them instead of creating twins, and uninstalling shopfloor_repair
  no longer deletes them: every technician keeps the group, and every note
  keeps its subtype.
- ``post_init_hook`` copies who added which part from the floor
  (``shopfloor_added_uid``) to ``tech_added_uid``, and marks the two
  shopfloor modules for removal. Odoo uninstalls modules marked so at the end
  of the same update (``odoo.modules.loading``, after the installs), so one
  ``-i repair_tech_app`` does the whole switch.
"""

import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)

REPLACED = ("shopfloor_repair_mobile", "shopfloor_repair")

ADOPTED = (
    "group_shop_technician",
    "rule_inspection_shop_technician",
    "rule_inspection_line_shop_technician",
    "mt_repair_technician_note",
    "shop_technician_inspection",
    "shop_technician_inspection_line",
    "shop_technician_inspection_line_image",
    "shop_technician_measurement",
    "shop_technician_inspection_item",
    "shop_technician_measurement_spec",
    "shop_technician_template",
    "shop_technician_template_line",
    "shop_technician_category",
    "shop_technician_condition",
    "shop_technician_action",
)


def pre_init_hook(env):
    env.cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'repair_tech_app'
         WHERE module = 'shopfloor_repair' AND name IN %s
        """,
        (ADOPTED,),
    )
    if env.cr.rowcount:
        _logger.info("Took over %s records from shopfloor_repair", env.cr.rowcount)


def post_init_hook(env):
    if column_exists(env.cr, "stock_move", "shopfloor_added_uid"):
        env.cr.execute(
            """
            UPDATE stock_move
               SET tech_added_uid = shopfloor_added_uid
             WHERE shopfloor_added_uid IS NOT NULL AND tech_added_uid IS NULL
            """
        )
    replaced = env["ir.module.module"].search(
        [("name", "in", REPLACED), ("state", "in", ("installed", "to upgrade"))]
    )
    if replaced:
        _logger.warning(
            "The technician app replaces %s: uninstalling them at the end of "
            "this update",
            ", ".join(replaced.mapped("name")),
        )
        replaced.button_uninstall()
