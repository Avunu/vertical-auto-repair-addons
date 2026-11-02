/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * How a repair job is named on the job list row and the job card: the
 * vehicle description ("Silver/2005/Acme/Hauler/SHOP-001", built
 * server side) on top, then customer · RO reference underneath. Two open
 * orders on one vehicle share a description, so the RO reference is always
 * shown.
 */
/** @import {RepairJobRecord} from "../components/repair_job_types" */

/**
 * @param {RepairJobRecord} record
 * @returns {string}
 */
export function job_label(record) {
    return record.vehicle_description || (record.partner && record.partner.name) || record.name;
}

/**
 * The line under the label, minus whatever the label already fell back to.
 *
 * @param {RepairJobRecord} record
 * @returns {string}
 */
export function job_meta(record) {
    const label = job_label(record);
    return [record.partner && record.partner.name, record.name]
        .filter((part) => part && part !== label)
        .join(" · ");
}

/**
 * The status chip's text. The stage ("Waiting for Parts") says more than the
 * status it belongs to ("Confirmed"); the chip's colour still follows the
 * status.
 *
 * @param {RepairJobRecord} record
 * @returns {string}
 */
export function job_status_label(record) {
    return (record.stage && record.stage.name) || record.state_label;
}
