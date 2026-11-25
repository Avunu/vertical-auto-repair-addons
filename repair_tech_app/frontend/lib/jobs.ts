/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import type {JobSummary} from "../api/api";

type BadgeVariant =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "error"
  | "blue"
  | "green"
  | "orange"
  | "purple";

/** A repair state's badge: the same colour family wherever a job shows. */
export const STATE_BADGE: Readonly<Record<JobSummary["state"], BadgeVariant>> = {
  draft: "neutral",
  confirmed: "info",
  under_repair: "warning",
  done: "success",
  cancel: "error",
};
