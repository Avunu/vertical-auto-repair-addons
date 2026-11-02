# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Stop future upgrades from resetting the Repair Shop Floor app's config.

`data/shopfloor_app.xml`'s `shopfloor_app_repair_shop` record was never
marked `noupdate="1"`, so every module upgrade rewrote its fields -
`auth_type` included - back to whatever the data file said, silently
discarding whatever an admin had configured through the UI in between
(this is what kept sending Auth Type back to "API key" even after
switching the app to Social login).

The file is `noupdate="1"` as of this version, which protects any *fresh*
install from this point on - but Odoo only reads a record's `noupdate`
attribute the first time its `ir.model.data` row is created; a later
reload, XML change included, never rewrites it (see
`ir.model.data._build_update_xmlids_query`, whose `ON CONFLICT` clause
touches `model`/`res_id`/`write_date` only). An install upgrading from
before this version still has that row stored as `noupdate=False`, so it
would keep being overwritten on every future upgrade regardless of the
file. This flips the already-installed row directly, once, so this and
every later upgrade leave the record's live configuration alone.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_model_data
        SET noupdate = true
        WHERE module = 'shopfloor_repair_mobile'
          AND name = 'shopfloor_app_repair_shop'
        """
    )
    _logger.info(
        "shopfloor_repair_mobile: marked shopfloor_app_repair_shop's data "
        "record noupdate; future upgrades will no longer overwrite its "
        "configuration."
    )
