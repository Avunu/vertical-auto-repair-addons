/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

/** A service row's own timer has no `my_hours`/`total_hours`/`job_name` of
 * its own -- those live on the row (`my_time`/`actual_time`) and the job it
 * belongs to -- unlike the job-level `RepairTimerState`. */
export interface RepairServiceTimerState {
    running: boolean;
    started_at: string | null;
    elapsed_hours: number;
}

export interface RepairServiceRecord {
    id: unknown;
    name: string;
    estimated_time: number;
    actual_time: number;
    my_time: number;
    product?: {id: unknown; name: string; [key: string]: unknown};
    timer: RepairServiceTimerState;
    [key: string]: unknown;
}
