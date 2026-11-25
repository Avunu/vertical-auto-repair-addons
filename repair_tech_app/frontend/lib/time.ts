/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Times, the one way the app makes them. The facades speak IsoDateTime (an
 * instant with its offset); the pickers speak the device's wall clock
 * ("2026-01-05T09:30"). Everything converts here, so neither a naive string
 * nor a local one ever reaches Odoo.
 */
import type {ISODateTimeString} from "@astryxdesign/core/DateTimeInput";
import type {IsoDateTime} from "../api/api";

/** An instant, for the API. */
export function isoDateTime(date: Date): IsoDateTime {
  if (Number.isNaN(date.getTime())) {
    throw new RangeError("Invalid date");
  }
  return date.toISOString() as IsoDateTime;
}

/** Milliseconds since the epoch of an API datetime. */
export function epochMs(value: IsoDateTime): number {
  return Date.parse(value);
}

const pad = (n: number): string => String(n).padStart(2, "0");

/** An API datetime on the device's wall clock, as the date-time picker shows it. */
export function toLocalInput(value: IsoDateTime): ISODateTimeString {
  const d = new Date(epochMs(value));
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}` as ISODateTimeString;
}

/** The picker's wall-clock value as an API datetime; undefined while incomplete. */
export function fromLocalInput(value: string | undefined): IsoDateTime | undefined {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!match) {
    return undefined;
  }
  const [, y, mo, d, h, mi, s] = match.map(Number) as [
    number,
    number,
    number,
    number,
    number,
    number,
    number,
  ];
  return isoDateTime(new Date(y, mo - 1, d, h, mi, Number.isNaN(s) ? 0 : s));
}

/** Decimal hours as h:mm: 1.25 -> "1:15". */
export function formatHours(hours: number): string {
  const minutes = Math.round(hours * 60);
  const sign = minutes < 0 ? "-" : "";
  const abs = Math.abs(minutes);
  return `${sign}${Math.floor(abs / 60)}:${pad(abs % 60)}`;
}

/** The time of day of an API datetime, in the device's locale: "9:30 AM". */
export function formatTime(value: IsoDateTime, locale?: string): string {
  return new Date(epochMs(value)).toLocaleTimeString(locale, {
    hour: "numeric",
    minute: "2-digit",
  });
}

/** A day ("2026-01-05", as the API gives a day) for a heading: "Mon, Jan 5". */
export function formatDay(day: string, locale?: string): string {
  const [y, m, d] = day.split("-").map(Number) as [number, number, number];
  return new Date(y, m - 1, d).toLocaleDateString(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

/** Hours between two API datetimes. */
export function hoursBetween(start: IsoDateTime, end: IsoDateTime): number {
  return (epochMs(end) - epochMs(start)) / 3_600_000;
}
