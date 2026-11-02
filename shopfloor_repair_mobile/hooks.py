# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from odoo.addons.shopfloor_base.utils import register_new_services

_logger = logging.getLogger(__name__)

APP_XMLID = "shopfloor_repair_mobile.shopfloor_app_repair_shop"


def post_init_hook(env):
    """Mark the new app as in sync, and try to publish its routes now.

    `endpoint.route.sync.mixin` creates records with `registry_sync = False`
    by design -- routing changes are meant to be batched and applied
    deliberately from the "Sync registry" button. Nobody should have to find
    that button to get a working install, so flip it here.

    Publishing the routes in the same breath is best-effort only:
    `shopfloor.app._get_services()` returns nothing while Odoo is still
    building its registry, which is exactly when a post-init hook runs.
    `register_new_services` is shopfloor_base's workaround, but it too bails
    out when the component registry is absent -- as it is during a plain
    `-i` install. The reliable publication happens on the next boot, in
    `shopfloor.app._boot_base_rest_endpoints`; see models/shopfloor_app.py.
    """
    # Imported here rather than at module scope: the hook module is imported
    # while the addon graph is still being walked.
    from odoo.addons.shopfloor_repair.services.repair_job import ShopfloorRepairJob

    app = env.ref(APP_XMLID, raise_if_not_found=False)
    if not app:
        return
    app.registry_sync = True
    register_new_services(env, ShopfloorRepairJob, apps=app)
    _logger.info("Shop floor app installed; routes under %s", app.api_route)
