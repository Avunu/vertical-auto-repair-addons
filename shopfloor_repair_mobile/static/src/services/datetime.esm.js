/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Odoo sends and accepts naive datetime strings like "2026-09-22 18:00:00"
 * -- always UTC, with no timezone suffix. A bare (no "Z"/offset) datetime
 * string handed to `new Date(...)` is parsed as browser-*local* time per
 * the JS spec, and `<input type="datetime-local">` both produces and
 * expects local wall-clock strings, not UTC ones. Every conversion here
 * has to be explicit about which side of that (UTC vs local) it's on, or a
 * displayed/edited time silently ends up shifted by the browser's UTC
 * offset -- confirmed live as exactly this: timesheet times appearing a
 * fixed 4 hours ahead of the actual time for a UTC-4 browser, because nothing
 * in this module used to account for the offset at all.
 */

/**
 * @param {Number} value
 * @param {Number} [length]
 * @returns {String}
 */
function pad(value, length = 2) {
    return String(value).padStart(length, "0");
}

/**
 * Parse a naive-UTC server datetime string ("2026-09-22 18:00:00") into a Date.
 *
 * @param {string | null | undefined} value
 * @returns {Date | null}
 */
export function server_datetime_to_date(value) {
    if (!value) {
        return null;
    }
    const iso = value.trim().replace(" ", "T") + "Z";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Format a Date as the naive-UTC string format the server expects.
 *
 * @param {Date} d
 * @returns {String}
 */
export function date_to_server_datetime(d) {
    return (
        `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
        `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
    );
}

/**
 * Server UTC string -> the value an `<input type="datetime-local">` needs:
 * local wall-clock, minute precision, no seconds/timezone.
 *
 * @param {string | null | undefined} value
 * @returns {String}
 */
export function server_datetime_to_local_input(value) {
    const d = server_datetime_to_date(value);
    if (!d) {
        return "";
    }
    return (
        `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
        `T${pad(d.getHours())}:${pad(d.getMinutes())}`
    );
}

/**
 * `<input type="datetime-local">` value (local wall-clock) -> server UTC
 * string. The multi-arg `Date` constructor (as opposed to the single
 * string-argument form) is unambiguously local time per spec, which is
 * exactly what a `datetime-local` value represents.
 *
 * @param {String} value
 * @returns {string | null}
 */
export function local_input_to_server_datetime(value) {
    if (!value) {
        return null;
    }
    const [date_part, time_part] = value.split("T");
    const [year, month, day] = date_part.split("-").map(Number);
    const [hour, minute] = (time_part || "").split(":").map(Number);
    if ([year, month, day, hour, minute].some((n) => Number.isNaN(n))) {
        return null;
    }
    const d = new Date(year, month - 1, day, hour, minute, 0);
    return Number.isNaN(d.getTime()) ? null : date_to_server_datetime(d);
}

/**
 * Hours between two naive-UTC server datetime strings; 0 when either is
 * missing/unparseable or the end is before the start.
 *
 * @param {string | null | undefined} start
 * @param {string | null | undefined} end
 * @returns {Number}
 */
export function duration_hours(start, end) {
    const s = server_datetime_to_date(start);
    const e = server_datetime_to_date(end);
    if (!s || !e || e.getTime() < s.getTime()) {
        return 0;
    }
    return (e.getTime() - s.getTime()) / 3600000;
}

/**
 * Same as `duration_hours`, for two `<input type="datetime-local">` values.
 * Both sides are local wall-clock, so the offset cancels out and the plain
 * `Date` parse is fine here (unlike for the server strings above) - except
 * across a DST change, which a shop-floor edit of minutes won't hit.
 *
 * @param {string | null | undefined} start
 * @param {string | null | undefined} end
 * @returns {Number}
 */
export function local_input_duration_hours(start, end) {
    return duration_hours(
        local_input_to_server_datetime(start || ""),
        local_input_to_server_datetime(end || "")
    );
}

/**
 * 1.25 -> "1h 15m", 2 -> "2h", 0.1 -> "6m".
 *
 * @param {Number} hours
 * @returns {String}
 */
export function format_duration(hours) {
    const total_minutes = Math.round(hours * 60);
    const h = Math.floor(total_minutes / 60);
    const m = total_minutes % 60;
    if (h && m) {
        return `${h}h ${m}m`;
    }
    if (h) {
        return `${h}h`;
    }
    return `${m}m`;
}

/**
 * @param {Date} d
 * @returns {String}
 */
export function format_clock(d) {
    return d.toLocaleTimeString(undefined, {hour: "numeric", minute: "2-digit"});
}

/**
 * Time of day only ("3:20 PM"), in the browser's locale and timezone.
 *
 * @param {string | null | undefined} value
 * @returns {String}
 */
export function format_time_of_day(value) {
    const d = server_datetime_to_date(value);
    return d ? format_clock(d) : "";
}

/**
 * `<input type="datetime-local">` value (local wall-clock) -> Date.
 *
 * @param {string | null | undefined} value
 * @returns {Date | null}
 */
export function local_input_to_date(value) {
    return server_datetime_to_date(local_input_to_server_datetime(value || ""));
}

/**
 * Date -> `<input type="datetime-local">` value (local wall-clock).
 *
 * @param {Date} d
 * @returns {String}
 */
export function date_to_local_input(d) {
    return server_datetime_to_local_input(date_to_server_datetime(d));
}
