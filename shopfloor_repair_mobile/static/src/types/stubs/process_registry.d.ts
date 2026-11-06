/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Type-only stub - see registry.d.ts for why this exists.
 */
import {ComponentOptions, VueConstructor} from "vue";
import {BaseRegistry} from "./registry";

export const process_registry: BaseRegistry<
  VueConstructor | ComponentOptions<any, any, any, any, any>
>;
