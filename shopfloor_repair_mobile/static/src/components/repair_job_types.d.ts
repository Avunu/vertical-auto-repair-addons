/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Best-effort shapes for the plain JSON records the repair.job REST
 * endpoints return, reverse-engineered from every field this module's
 * templates and methods actually read. Odoo's own JSON responses aren't
 * typed, so treat unfamiliar fields as `any` rather than assuming this is
 * exhaustive.
 */

export interface RepairJobVehicle {
    license_plate?: string;
    model_year?: string | number;
    name?: string;
    [key: string]: unknown;
}

export interface RepairJobPartner {
    name: string;
    [key: string]: unknown;
}

/** repair.order.stage: the board column, e.g. "Waiting for Parts". */
export interface RepairJobStage {
    id: number;
    name: string;
}

export interface RepairJobRecord {
    id: unknown;
    name: string;
    state: string;
    state_label: string;
    stage?: RepairJobStage | null;
    /** "Colour/Year/Brand/Model/Plate"; empty when the job has no vehicle. */
    vehicle_description?: string;
    vehicle?: RepairJobVehicle;
    partner?: RepairJobPartner;
    /** repair.order.technician_id; null when nobody is assigned. */
    technician?: RepairJobPartner | null;
    customer_concern?: string;
    parts_done: number;
    parts_total: number;
    inspection_graded: number;
    inspection_total: number;
    total_hours: number;
    schedule_date?: string;
    [key: string]: unknown;
}
