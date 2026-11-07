/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Typed constructor form of shopfloor_mobile_base's `ScenarioBaseMixin` (a
 * plain, untyped Vue 2 mixin object), for `extendComponent` to build the
 * scenario on - `Vue.extend()` turns it into one. This changes nothing
 * about the mixin's runtime behavior (`Vue.extend(plainObject)` is how Vue
 * itself would build a mixin's constructor form internally), it only gives
 * it a typed shape - `ScenarioBaseMixinInterface` - to extend from.
 */

/* global Vue */

/** @import {VueConstructor} from "vue" */
/** @import {ScenarioBaseMixinInterface} from "./scenario_base_mixin_types" */
import {ScenarioBaseMixin} from "/shopfloor_mobile_base/static/src/scenario/mixins.esm.js";

export const ScenarioBaseMixinClass =
    /** @type {VueConstructor<ScenarioBaseMixinInterface>} */ (
        /** @type {unknown} */ (Vue.extend(/** @type {any} */ (ScenarioBaseMixin)))
    );
