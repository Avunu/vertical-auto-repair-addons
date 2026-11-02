# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

APP_XMLID = "shopfloor_repair_mobile.shopfloor_app_repair_shop"


class ShopfloorApp(models.Model):
    _inherit = "shopfloor.app"

    def _boot_base_rest_endpoints(self):
        """Publish our REST routes once the component registry is up.

        Route rows only get written by `_register_controllers`, and that needs
        `_get_services()` -- which returns nothing while Odoo is still
        building its registry. A post-init hook runs squarely inside that
        window, so installing the module cannot publish the routes by itself
        and a fresh install answers 404 on every endpoint.

        `_register_hook` (whose only job here is `_boot_base_rest_endpoints`)
        runs *after* the registry is assembled, which is the first moment the
        services can be enumerated. Hooking here means the routes appear on
        the next boot with no human in the loop, and it self-heals a restored
        database, where the endpoint_route rows are present but may be stale.
        """
        res = super()._boot_base_rest_endpoints()
        self._shopfloor_repair_publish_routes()
        return res

    @api.model
    def _shopfloor_repair_publish_routes(self):
        app = self.env.ref(APP_XMLID, raise_if_not_found=False)
        if not app or not app.active:
            return
        # Publish only what is missing. Re-registering everything on every boot
        # would be a pointless write on a table the router reads constantly
        # (`update_rules` rewrites each row and bumps the timestamp other
        # workers watch) - but skipping whenever *any* route exists, as this
        # used to, meant an upgrade that adds an endpoint never published it:
        # the new URL answered 404 until somebody found "Sync registry".
        expected = {rule.key for rule in app._prepare_endpoint_rules()}
        if expected and expected <= set(app._registered_endpoint_rule_keys()):
            return
        try:
            app._register_controllers()
        except Exception:  # pragma: no cover - never break the boot
            _logger.exception(
                "Could not publish the shop floor REST routes; "
                "use the Sync registry button on the %s app.",
                app.tech_name,
            )
            return
        _logger.info("Published shop floor REST routes under %s", app.api_route)

    def _make_app_info(self, demo=False):
        info = super()._make_app_info(demo=demo)
        if self.tech_name == "repair_shop":
            # `shopfloor_mobile_base`'s own default is sessionStorage
            # (static/src/main.esm.js), which is cleared the moment the
            # browser tab/window closes - not just on an explicit logout.
            # On a technician's own device (not a shared kiosk - the same
            # assumption this app's OAuth login already banks on; see
            # shopfloor_mobile_base_auth_oauth's README), that means both
            # the selected profile and the signed-in session get forgotten
            # on every fresh open of the app, not just every logout -
            # confirmed live: a same-tab reload keeps the profile, a fresh
            # tab/relaunch loses it. localStorage survives a closed tab or
            # relaunched PWA; the 24h TTL (main.esm.js's own default,
            # untouched here) still expires it on its own after a day.
            info["storage"] = {"driver": "local"}
        return info
