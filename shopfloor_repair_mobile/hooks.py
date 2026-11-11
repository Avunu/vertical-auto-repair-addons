# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

_logger = logging.getLogger(__name__)

APP_XMLID = "shopfloor_repair_mobile.shopfloor_app_repair_shop"


def post_init_hook(env):
    """Mark the new app as in sync.

    `endpoint.route.sync.mixin` creates records with `registry_sync = False`
    by design -- routing changes are meant to be batched and applied
    deliberately from the "Sync registry" button. Nobody should have to find
    that button to get a working install, so flip it here.

    The routes themselves are not published here: service routes are
    generated when the routing map is built (shopfloor_base's
    `register_new_services` is deprecated for that reason), and
    `shopfloor.app._boot_base_rest_endpoints` publishes them on the next boot;
    see models/shopfloor_app.py.
    """
    app = env.ref(APP_XMLID, raise_if_not_found=False)
    if not app:
        return
    app.registry_sync = True
    _logger.info("Shop floor app installed; routes under %s", app.api_route)
