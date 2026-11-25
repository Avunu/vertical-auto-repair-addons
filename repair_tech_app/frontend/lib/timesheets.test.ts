import {describe, expect, it} from "vitest";
import type {IsoDateTime, Ref, TimesheetEntry, TimesheetPage} from "../api/api";
import {clockBreaks, days, jobBreaks} from "./timesheets";

const at = (time: string) => `2026-01-05T${time}:00Z` as IsoDateTime;
const job: Ref = {id: 1, name: "Acme/Hauler"};
const brakes: Ref = {id: 10, name: "Brake Job"};
const diag: Ref = {id: 11, name: "Diagnostics"};

function entry(
  id: number,
  start: string,
  end: string,
  service: Ref = brakes
): TimesheetEntry {
  return {
    id,
    description: "Work",
    date: "2026-01-05",
    start: at(start),
    end: at(end),
    hours: 1,
    job,
    job_ref: "RO/1",
    service,
  };
}

describe("breaks", () => {
  it("finds the gaps between clocked periods", () => {
    const breaks = clockBreaks({
      date: "2026-01-05",
      hours: 8.5,
      records: [
        {id: 2, check_in: at("10:30"), check_out: at("17:00")},
        {id: 1, check_in: at("08:00"), check_out: at("10:00")},
      ],
    });
    expect(breaks).toEqual([
      {kind: "clock", attendanceId: 1, start: at("10:00"), end: at("10:30")},
    ]);
  });

  it("leaves an open period with no break after it", () => {
    expect(
      clockBreaks({
        date: "2026-01-05",
        hours: 2,
        records: [{id: 1, check_in: at("08:00"), check_out: null}],
      })
    ).toEqual([]);
  });

  it("finds a break between two parts of one service only", () => {
    const breaks = jobBreaks([
      entry(2, "10:30", "12:00"),
      entry(1, "09:00", "10:00"),
      entry(3, "10:05", "10:20", diag),
    ]);
    expect(breaks).toEqual([
      {kind: "job", lineId: 1, afterId: 2, start: at("10:00"), end: at("10:30")},
    ]);
  });

  it("sees no break between entries that touch", () => {
    expect(jobBreaks([entry(1, "09:00", "10:00"), entry(2, "10:00", "11:00")])).toEqual(
      []
    );
  });
});

describe("days", () => {
  const page: TimesheetPage = {
    records: [
      entry(3, "13:00", "14:00"),
      entry(1, "09:00", "10:00"),
      {...entry(9, "09:00", "10:00"), date: "2026-01-04"},
    ],
    total: 3,
    page: 1,
    page_size: 20,
    attendance: [
      {
        date: "2026-01-05",
        hours: 8,
        records: [{id: 1, check_in: at("08:00"), check_out: at("17:00")}],
      },
    ],
    job_hours: [{date: "2026-01-05", hours: 2}],
  };

  it("puts the newest day first and each day's entries in order", () => {
    const [today, yesterday] = days(page);
    expect(today?.date).toBe("2026-01-05");
    expect(today?.entries.map((e) => e.id)).toEqual([1, 3]);
    expect(today?.clockedHours).toBe(8);
    expect(today?.jobHours).toBe(2);
    expect(yesterday?.clockedHours).toBeNull();
  });

  it("uses the clock for breaks on a clocked day", () => {
    expect(days(page)[0]?.breaks).toEqual([]);
    expect(days(page)[1]?.breaks).toEqual([]);
  });
});

describe("timeline", () => {
  it("puts a break between the entries it separates", () => {
    const page: TimesheetPage = {
      records: [entry(2, "10:30", "12:00"), entry(1, "09:00", "10:00")],
      total: 2,
      page: 1,
      page_size: 20,
      attendance: [],
      job_hours: [],
    };
    const [day] = days(page);
    expect(
      day?.timeline.map((m) => (m.kind === "entry" ? `e${m.entry.id}` : "break"))
    ).toEqual(["e1", "break", "e2"]);
  });
});
