/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

export interface RepairPartLot {
  id: unknown;
  name: string;
}

export interface RepairPartRecord {
  id: unknown;
  picked: boolean;
  quantity_done: number;
  quantity_demand: number;
  tracking: string;
  shopfloor_added?: boolean;
  product: {name: string; default_code?: string};
  uom?: {name: string};
  lots?: RepairPartLot[];
  [key: string]: unknown;
}
