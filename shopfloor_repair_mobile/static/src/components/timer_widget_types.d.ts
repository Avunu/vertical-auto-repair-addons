/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

/** The `shift_timer` / `current_job` payload of the `shift_timer` endpoint. */
export interface TimerState {
  running: boolean;
  started_at: string | null;
  elapsed_hours: number;
  job_name?: string;
  service_name?: string | null;
  repair_id?: number;
  service_id?: number;
}

export interface RepairTimerState {
  running: boolean;
  started_at: string | null;
  elapsed_hours: number;
  my_hours: number;
  total_hours: number;
}
