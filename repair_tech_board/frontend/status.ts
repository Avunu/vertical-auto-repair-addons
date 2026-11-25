/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The board's six statuses, in the order the key lists them. The ids are
 * the API's (repair.order.stage.board_status); the colors are the --<id>
 * custom properties in app.css.
 */
import type {BoardJob} from "./api/api";

export type Status = BoardJob["status"];

export const STATUSES: readonly {id: Status; tag: string; label: string}[] = [
  {id: "diag", tag: "DIAG", label: "Waiting for diagnostics"},
  {id: "pa", tag: "PA", label: "Waiting for PA inspection"},
  {id: "cust", tag: "CUST", label: "Waiting on customer"},
  {id: "parts", tag: "PARTS", label: "Waiting on parts"},
  {id: "ready", tag: "READY", label: "Ready for repair"},
  {id: "repair", tag: "REPAIR", label: "Under repair"},
];

export const STATUS = Object.fromEntries(STATUSES.map((s) => [s.id, s])) as Record<
  Status,
  (typeof STATUSES)[number]
>;

/** Ready for repair first, then the oldest order first. */
export function byUrgency(a: BoardJob, b: BoardJob): number {
  return Number(b.status === "ready") - Number(a.status === "ready") || a.id - b.id;
}
