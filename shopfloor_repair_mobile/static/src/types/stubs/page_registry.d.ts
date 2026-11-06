/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Type-only stub - see registry.d.ts for why this exists.
 */
import Vue, {ComponentOptions, VueConstructor} from "vue";
import {BaseRegistry} from "./registry";

export interface PageMetadata {
  tag: string;
  icon?: string;
  display_name?: (instance: Vue, rec: unknown) => string;
  is_enabled?: (instance: Vue, rec: unknown) => boolean;
  [key: string]: unknown;
}

export const page_registry: BaseRegistry<
  VueConstructor | ComponentOptions<any, any, any, any, any>
>;
