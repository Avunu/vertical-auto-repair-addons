/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */

/** An object without its undefined keys: under exactOptionalPropertyTypes an
 * absent key and an undefined one are different types, and a URL wants the
 * former. */
export function compact<T extends Record<string, unknown>>(
  value: T
): {[K in keyof T]?: Exclude<T[K], undefined>} {
  return Object.fromEntries(
    Object.entries(value).filter(([, v]) => v !== undefined)
  ) as {[K in keyof T]?: Exclude<T[K], undefined>};
}
