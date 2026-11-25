/* eslint-disable */
/**
 * GENERATED - do not edit. Source: the @facade methods in api.schema.json,
 * via repair_tech_api/tools/generate_api_types.mjs. Regenerate with
 * `pnpm run generate`.
 */

/**
 * Facades defined by repair_tech_api.
 */
export interface RepairTechBoardApi {
  "repair.order": RepairOrderMethods;
}
/**
 * Facades on repair.order.
 *
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "RepairOrderMethods".
 */
export interface RepairOrderMethods {
  board_jobs: BoardJobsMethod;
}
/**
 * The shop's job board: every open job whose stage has a board status,
 * scheduled for today or earlier or not scheduled yet, and the
 * technicians who have open work. Not limited to the current user's
 * jobs. A job booked for a later day stays off until its day.
 *
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "BoardJobsMethod".
 */
export interface BoardJobsMethod {
  params: BoardJobsParams;
  result: Board;
}
/**
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "BoardJobsParams".
 */
export interface BoardJobsParams {}
/**
 * Everything the shop's job board draws.
 *
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "Board".
 */
export interface Board {
  /**
   * Every appointment type with a board icon, for the board's key.
   */
  job_types: BoardJobType[];
  /**
   * Open jobs whose stage has a board status, scheduled for today or
   * earlier or not scheduled yet.
   */
  jobs: BoardJob[];
  /**
   * Everyone with an open job that shows, by name: one column each.
   */
  technicians: Ref[];
}
/**
 * An appointment type with a job board icon.
 *
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "BoardJobType".
 */
export interface BoardJobType {
  icon: "car" | "truck";
  id: number;
  /**
   * For the board's key, e.g. ``Heavy truck``.
   */
  label: string;
}
/**
 * One card on the shop's job board.
 *
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "BoardJob".
 */
export interface BoardJob {
  customer: string;
  id: number;
  /**
   * The job's appointment type, when that type has a board icon.
   */
  job_type: BoardJobType | null;
  /**
   * The order's reference, e.g. ``RO/00123``.
   */
  name: string;
  /**
   * The digits of ``name`` without leading zeros, for the card: ``123``.
   */
  number: string;
  /**
   * From the job's stage (``repair.order.stage.board_status``).
   */
  status: "diag" | "pa" | "cust" | "parts" | "ready" | "repair";
  /**
   * ``None`` puts the card in the board's unassigned column.
   */
  technician_id: number | null;
  /**
   * Model year and model, e.g. ``2019 Cascadia``. Empty without a vehicle.
   */
  vehicle: string;
}
/**
 * Any record shown by name.
 *
 * This interface was referenced by `RepairTechBoardApi`'s JSON-Schema
 * via the `definition` "Ref".
 */
export interface Ref {
  id: number;
  name: string;
}

/** Every facade, by model and method: what client.ts types calls with. */
export type Api = RepairTechBoardApi;

/** An ISO 8601 datetime with its offset, e.g. `2026-01-05T09:00:00Z`. */
export type IsoDateTime = string & {readonly __brand: "IsoDateTime"};
