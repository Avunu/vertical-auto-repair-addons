# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Clear the way for checklist lines that carry XML IDs.

Until this version the seeded checklists were built with ``Command.create()``
inline on the template, so the lines existed with no ``ir.model.data`` entry of
their own. Two consequences:

* Any install that loaded the data twice ended up with every line duplicated.
  ``noupdate="1"`` masked it going forward, but installs that drifted before
  the flag went on are still carrying the doubles.
* Loading the new per-line records on top of the old anonymous ones would add
  a *third* copy rather than adopting them, because there is nothing to match
  the existing rows against.

So drop the unmanaged lines on the four seeded templates first, and let the
data file recreate them with identities. Lines a shop added itself against its
own items are left alone; lines it added that happen to use a seeded item come
back from the data file anyway.

Nothing references a template line -- inspections copy the *item* onto their
own lines when a template is loaded -- so deleting these cannot orphan a
technician's completed work.
"""

import logging

_logger = logging.getLogger(__name__)

TEMPLATES = (
    "template_check_in",
    "template_pre_inspection",
    "template_courtesy",
    "template_state_safety",
)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        DELETE FROM fleet_vehicle_inspection_template_line line
        WHERE line.inspection_template_id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'shop_inspection'
                  AND model = 'fleet.vehicle.inspection.template'
                  AND name = ANY(%s)
            )
          AND line.inspection_template_item_id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'shop_inspection'
                  AND model = 'fleet.vehicle.inspection.item'
            )
          -- Only the anonymous ones. A line that already has an identity is
          -- either from a re-run of this migration or hand-registered, and
          -- the data file will update it in place.
          AND NOT EXISTS (
                SELECT 1 FROM ir_model_data d
                WHERE d.model = 'fleet.vehicle.inspection.template.line'
                  AND d.res_id = line.id
            )
        """,
        (list(TEMPLATES),),
    )
    _logger.info(
        "shop_inspection: removed %s unmanaged checklist line(s); "
        "the data file will recreate them with XML IDs",
        cr.rowcount,
    )
