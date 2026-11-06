/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

export interface AttendanceRecord {
  id: number;
  check_in: string;
  check_out: string | null;
}

export interface AttendanceDay {
  date: string;
  hours: number;
  records: AttendanceRecord[];
}
