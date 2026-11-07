/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

export interface TimesheetJobChoice {
  id: number;
  name: string;
  /** The repair order's reference ("RO/00012"). */
  ref: string;
  customer: string;
  /** Accepted services only - the ones time can be booked against. */
  services: {id: number; name: string}[];
}

export interface TimesheetRecord {
  id: unknown;
  job?: {id: unknown};
  service?: {id: unknown} | null;
  jobs: TimesheetJobChoice[];
  date_time: string | null;
  date_time_end: string | null;
}

/** What `repair-job-picker` reads and emits (`v-model`). */
export interface JobPickerValue {
  job_id: number | null;
  service_id: number | null;
}
