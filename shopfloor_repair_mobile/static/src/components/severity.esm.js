/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Severity vocabulary shared by the checklist and the grading form.
 * The colours deliberately match the customer-facing PDF that
 * shop_inspection_report renders, so "red on the tablet" and "red on the
 * report the customer is holding" mean the same thing.
 */

/** @typedef {"good" | "future" | "attention" | "today" | "fail_state" | "na"} SeverityValue */

/** @type {Record<SeverityValue, string>} */
export const SEVERITY_COLORS = {
    good: "#2e7d32",
    future: "#e5ab00",
    attention: "#ef6c00",
    today: "#c22a4a",
    fail_state: "#7b1030",
    na: "#757575",
};

/** @type {Record<SeverityValue, string>} */
export const SEVERITY_ICONS = {
    good: "mdi-check-circle",
    future: "mdi-clock-alert-outline",
    attention: "mdi-alert",
    today: "mdi-wrench",
    fail_state: "mdi-close-octagon",
    na: "mdi-minus-circle-outline",
};

/**
 * @param {string | null} value
 * @returns {String}
 */
export function severity_color(value) {
    return SEVERITY_COLORS[/** @type {SeverityValue} */ (value)] || "#bdbdbd";
}

/**
 * @param {string | null} value
 * @returns {String}
 */
export function severity_icon(value) {
    return (
        SEVERITY_ICONS[/** @type {SeverityValue} */ (value)] ||
        "mdi-help-circle-outline"
    );
}

/**
 * Grades that put a problem in front of the customer.
 * Mirrors PROBLEM_SEVERITIES in the service.
 *
 * @type {SeverityValue[]}
 */
export const PROBLEM_SEVERITIES = ["today", "attention", "fail_state"];
