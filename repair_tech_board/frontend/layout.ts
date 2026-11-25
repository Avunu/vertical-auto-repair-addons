/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * How many columns fit, in how many rows, and how many cards a column
 * shows. The page is a stage of fixed size (1920 wide, at least 1080 tall),
 * scaled to the screen, so all of this is plain arithmetic.
 */

const CHROME = 156; // the header (68), the key (64) and the board's padding (24)
const ROW_GAP = 14;
const CARD_GAP = 8;
const PAGER = 28; // the pager line and its margin
const COLUMNS_PER_ROW = 5;

/** Card and header sizes, by number of rows of columns (more rows, smaller). */
const DENSITY = {
  1: {card: 100, f1: 27, f2: 22, fwo: 34, ftag: 15, icon: 62, head: 60, fname: 30},
  2: {card: 76, f1: 22, f2: 19, fwo: 28, ftag: 13, icon: 50, head: 56, fname: 28},
  3: {card: 58, f1: 19, f2: 16, fwo: 24, ftag: 11, icon: 40, head: 44, fname: 24},
} as const;

export interface Plan {
  rows: number;
  cols: number;
  density: (typeof DENSITY)[keyof typeof DENSITY];
  /** Cards a column shows when all of them fit, and when it needs a pager. */
  capacity: number;
  pagedCapacity: number;
}

export function planBoard(columns: number, stageHeight: number): Plan {
  const rows = Math.max(1, Math.ceil(columns / COLUMNS_PER_ROW));
  const density = DENSITY[Math.min(rows, 3) as 1 | 2 | 3];
  const rowHeight = (stageHeight - CHROME - (rows - 1) * ROW_GAP) / rows;
  // less the border, the padding, the header and the gap under it
  const area = rowHeight - 2 - 20 - density.head - 10;
  const fit = (height: number) =>
    Math.max(1, Math.floor((height + CARD_GAP) / (density.card + CARD_GAP)));
  return {
    rows,
    cols: Math.ceil(columns / rows),
    density,
    capacity: fit(area),
    pagedCapacity: fit(area - PAGER),
  };
}
