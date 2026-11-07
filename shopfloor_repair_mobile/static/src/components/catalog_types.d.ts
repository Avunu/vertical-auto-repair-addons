/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

export interface CatalogCategory {
  id: number;
  name: string;
}

export interface CatalogRecord {
  id: unknown;
  name: string;
  default_code?: string;
  barcode?: string;
  qty_available: number;
  tracking: string;
  uom?: {name: string};
  [key: string]: unknown;
}
