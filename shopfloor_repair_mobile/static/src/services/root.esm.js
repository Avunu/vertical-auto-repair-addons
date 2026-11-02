/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * `this.$root` can't be typed by augmenting Vue's own `Vue` interface
 * (`vue/types/vue.d.ts` already declares `$root: Vue`, and TypeScript's
 * declaration merging requires every merged declaration of a member to
 * share the exact same type, not a narrower one) - this small helper casts
 * it to `ShopfloorRoot` at each call site instead.
 */
/** @import {ShopfloorRoot} from "../types/shopfloor-mobile-base" */

/**
 * @param {Vue} vm
 * @returns {ShopfloorRoot}
 */
export function sf_root(vm) {
    return /** @type {ShopfloorRoot} */ (/** @type {unknown} */ (vm.$root));
}

/**
 * `shopfloor.repair.job` inherits `base.shopfloor.process`
 * (shopfloor_base/services/service.py:306-307), which sets both
 * `_requires_header_profile = True` and `_requires_header_menu = True` -
 * every method on it, `shift_timer`/`clock_toggle` included, 400s without
 * a `SERVICE-CTX-MENU-ID` header. Scenario components get that for free
 * from their own route (`ScenarioBaseMixin._get_menu_item_id`, reading
 * `$route.params.menu_id`), but the drawer/app-bar widgets that also call
 * these two endpoints (`app_bar_actions.esm.js`, `nav_items_extra.esm.js`,
 * `pages/clock.esm.js`) render on every page, including ones with no
 * `menu_id` route param at all (`/clock`, `/timesheets`) - so they resolve
 * it here instead, by finding the nav entry whose `scenario` key matches
 * the usage being called (`shopfloor_base/services/menu.py`'s
 * `scenario_key:scenario` field is exactly the `process_registry` key,
 * e.g. "repair_job").
 *
 * @param {Vue} vm
 * @param {string} usage
 * @returns {unknown}
 */
export function menu_id_for(vm, usage) {
    const app_nav = sf_root(vm).getNav().app_nav || [];
    const entry = app_nav.find((item) => item.scenario === usage);
    return entry ? entry.id : undefined;
}
