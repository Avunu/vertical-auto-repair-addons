/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {SeverityValue} from "./severity.esm.js";

export interface InspectionCategory {
    id: number;
    name: string;
}

export interface InspectionAction {
    id: unknown;
    name: string;
}

export interface InspectionCondition {
    id: unknown;
    name: string;
}

export interface InspectionLine {
    id: unknown;
    name: string;
    category?: InspectionCategory;
    severity?: SeverityValue | null;
    measurement_summary?: string;
    measurement_alert?: boolean;
    note?: string;
    instruction?: string;
    image_count?: number;
    recommended_actions: InspectionAction[];
    conditions?: InspectionCondition[];
    measurements?: unknown[];
    [key: string]: unknown;
}

export interface InspectionGroup {
    id: number;
    name: string;
    lines: InspectionLine[];
}

export interface InspectionSeverityCounts {
    today?: number;
    attention?: number;
    future?: number;
    good?: number;
    [key: string]: number | undefined;
}

export interface InspectionRecord {
    id: unknown;
    name: string;
    state: string;
    state_label: string;
    graded_count: number;
    line_count: number;
    counts: InspectionSeverityCounts;
    [key: string]: unknown;
}

export interface InspectionTemplate {
    id: unknown;
    name: string;
}

export interface InspectionLineChoices {
    conditions: InspectionCondition[];
    actions: InspectionAction[];
    severities: {value: string; label: string}[];
}
