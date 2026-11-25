import {describe, expect, it} from "vitest";
import type {IsoDateTime} from "../api/api";
import {
  epochMs,
  formatHours,
  fromLocalInput,
  hoursBetween,
  isoDateTime,
  toLocalInput,
} from "./time";

describe("time", () => {
  it("formats decimal hours as h:mm", () => {
    expect(formatHours(0)).toBe("0:00");
    expect(formatHours(1.25)).toBe("1:15");
    expect(formatHours(7.999)).toBe("8:00");
    expect(formatHours(-0.5)).toBe("-0:30");
  });

  it("round-trips the picker's wall clock through an instant", () => {
    const iso = fromLocalInput("2026-01-05T09:30");
    expect(iso).toBeDefined();
    expect(toLocalInput(iso as IsoDateTime)).toBe("2026-01-05T09:30");
    expect(new Date(epochMs(iso as IsoDateTime)).getHours()).toBe(9);
  });

  it("refuses what isn't a whole picker value", () => {
    expect(fromLocalInput(undefined)).toBeUndefined();
    expect(fromLocalInput("2026-01-05")).toBeUndefined();
    expect(fromLocalInput("09:30")).toBeUndefined();
  });

  it("always sends an offset", () => {
    expect(isoDateTime(new Date(Date.UTC(2026, 0, 5, 9)))).toBe(
      "2026-01-05T09:00:00.000Z"
    );
    expect(() => isoDateTime(new Date("nope"))).toThrow(RangeError);
  });

  it("measures hours between instants", () => {
    expect(
      hoursBetween(
        "2026-01-05T09:00:00Z" as IsoDateTime,
        "2026-01-05T10:45:00Z" as IsoDateTime
      )
    ).toBe(1.75);
  });
});
