# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.base_rest.components.service import to_int
from odoo.addons.component.core import Component


class ShopfloorRepairApp(Component):
    """Remember each user's profile choice.

    `shopfloor_base`'s own app service only hands the client the list of
    profiles; which one is active lives in the browser's storage, so it is
    lost on logout (and again once the storage TTL runs out). The chosen
    profile is kept on the user instead, and returned with the sync data so
    the frontend can select it by itself.
    """

    _inherit = "shopfloor.service.app"

    def _sync_data(self):
        data = super()._sync_data()
        profile = self.env.user.shopfloor_default_profile_id
        profile_ids = {p["id"] for p in data["profiles"]}
        data["default_profile_id"] = (
            profile.id if profile and profile.id in profile_ids else None
        )
        return data

    def set_default_profile(self, profile_id):
        profile_ids = self.component("profile")._search().ids
        if profile_id not in profile_ids:
            # Only profiles the app itself offers: a client must not be able
            # to pin an arbitrary `shopfloor.profile` (and its menus) on the
            # user by guessing an id.
            return self._response(message=self.msg_store.generic_record_not_found())
        # `res.users` is not writable by the user themself beyond the
        # self-writeable preference fields, so this is sudo - the check above
        # and `env.user` (never client input) are the boundary.
        self.env.user.sudo().shopfloor_default_profile_id = profile_id
        return self._response(data={"default_profile_id": profile_id})


class ShopfloorRepairAppValidator(Component):
    _inherit = "shopfloor.service.app.validator"

    def set_default_profile(self):
        return {"profile_id": {"coerce": to_int, "required": True, "type": "integer"}}


class ShopfloorRepairAppValidatorResponse(Component):
    _inherit = "shopfloor.service.app.validator.response"

    def user_config(self):
        schema = super().user_config()
        schema["data"]["schema"]["default_profile_id"] = {
            "type": "integer",
            "nullable": True,
            "required": False,
        }
        return schema

    def set_default_profile(self):
        return self._response_schema(
            {"default_profile_id": {"type": "integer", "required": True}}
        )
