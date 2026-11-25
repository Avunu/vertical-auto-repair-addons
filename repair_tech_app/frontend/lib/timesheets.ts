/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * A page of timesheets as the technician reads it: one card per day, with
 * the day's clocked time, its job time, the entries in order, and the breaks.
 *
 * Two kinds of break. On a clocked day a break is the gap between two clocked
 * periods (clock out, clock back in): `update_break`/`delete_break` edit it,
 * by the earlier period. On a day with nothing clocked there is no clock-out
 * to show, so a break is the gap between two entries on the same job and
 * service - what "Add break" and a stop-and-restart leave behind:
 * `update_job_break`/`delete_job_break` edit it, by the two entries.
 */
import type {
  AttendanceDay,
  IsoDateTime,
  TimesheetEntry,
  TimesheetPage,
} from "../api/api";
import {epochMs} from "./time";

export type Break =
  | {
      readonly kind: "clock";
      readonly attendanceId: number;
      readonly start: IsoDateTime;
      readonly end: IsoDateTime;
    }
  | {
      readonly kind: "job";
      readonly lineId: number;
      readonly afterId: number;
      readonly start: IsoDateTime;
      readonly end: IsoDateTime;
    };

/** An entry or a break, in the order the day went. */
export type Moment =
  | {readonly kind: "entry"; readonly entry: TimesheetEntry}
  | {readonly kind: "break"; readonly gap: Break};

export interface Day {
  readonly date: string;
  readonly clockedHours: number | null;
  readonly jobHours: number;
  readonly attendance: AttendanceDay | null;
  /** Oldest first, as the day went. */
  readonly entries: readonly TimesheetEntry[];
  readonly breaks: readonly Break[];
  /** Entries and breaks together, by when they start. */
  readonly timeline: readonly Moment[];
}

function timeline(
  entries: readonly TimesheetEntry[],
  breaks: readonly Break[]
): Moment[] {
  const at = (moment: Moment): number =>
    moment.kind === "entry"
      ? moment.entry.start
        ? epochMs(moment.entry.start)
        : 0
      : epochMs(moment.gap.start);
  return [
    ...entries.map((entry): Moment => ({kind: "entry", entry})),
    ...breaks.map((gap): Moment => ({kind: "break", gap})),
  ].toSorted((a, b) => at(a) - at(b));
}

const byStart = (
  a: {start: IsoDateTime | null},
  b: {start: IsoDateTime | null}
): number => (a.start ? epochMs(a.start) : 0) - (b.start ? epochMs(b.start) : 0);

export function clockBreaks(attendance: AttendanceDay | null): Break[] {
  const records = (attendance?.records ?? []).toSorted(
    (a, b) => epochMs(a.check_in) - epochMs(b.check_in)
  );
  const breaks: Break[] = [];
  for (const [index, earlier] of records.entries()) {
    const later = records[index + 1];
    if (
      later &&
      earlier.check_out &&
      epochMs(later.check_in) > epochMs(earlier.check_out)
    ) {
      breaks.push({
        kind: "clock",
        attendanceId: earlier.id,
        start: earlier.check_out,
        end: later.check_in,
      });
    }
  }
  return breaks;
}

export function jobBreaks(entries: readonly TimesheetEntry[]): Break[] {
  const breaks: Break[] = [];
  const sorted = entries.toSorted(byStart);
  for (const [index, before] of sorted.entries()) {
    // The next entry on the same job and service, wherever it is in the day.
    const after = sorted
      .slice(index + 1)
      .find(
        (entry) =>
          entry.job?.id === before.job?.id && entry.service?.id === before.service?.id
      );
    if (after?.start && before.end && epochMs(after.start) > epochMs(before.end)) {
      breaks.push({
        kind: "job",
        lineId: before.id,
        afterId: after.id,
        start: before.end,
        end: after.start,
      });
    }
  }
  return breaks;
}

export function days(page: TimesheetPage): Day[] {
  const entriesByDay = Map.groupBy(page.records, (entry) => entry.date);
  const attendance = new Map(page.attendance.map((day) => [day.date, day]));
  const jobHours = new Map(page.job_hours.map((day) => [day.date, day.hours]));
  return [...entriesByDay.keys()]
    .toSorted((a, b) => b.localeCompare(a))
    .map((date) => {
      const entries = (entriesByDay.get(date) ?? []).toSorted(byStart);
      const clocked = attendance.get(date) ?? null;
      const clocks = clockBreaks(clocked);
      // With clocked periods the clock is the record of breaks.
      const breaks =
        clocked && clocked.records.length > 0 ? clocks : jobBreaks(entries);
      return {
        date,
        clockedHours: clocked?.hours ?? null,
        jobHours: jobHours.get(date) ?? 0,
        attendance: clocked,
        entries,
        breaks,
        timeline: timeline(entries, breaks),
      };
    });
}
