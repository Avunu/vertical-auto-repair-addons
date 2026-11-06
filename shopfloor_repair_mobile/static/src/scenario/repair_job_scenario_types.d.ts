/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 */
import {RepairJobRecord} from "../components/repair_job_types";
import {RepairTimerState} from "../components/timer_widget_types";
import {RepairPartRecord} from "../components/parts_types";
import {RepairServiceRecord} from "../components/repair_service_types";
import {CatalogCategory, CatalogRecord} from "../components/catalog_types";
import {
  InspectionRecord,
  InspectionTemplate,
  InspectionLine,
  InspectionLineChoices,
} from "../components/inspection_types";

export interface JobHubTimerState extends RepairTimerState {
  job_name: string;
}

export interface JobHubRecord extends RepairJobRecord {
  timer: JobHubTimerState;
}

export interface ClientOptions {
  allow_repair_end: boolean;
  require_photo_on_fail: boolean;
}

export interface ScannedBarcode {
  text: string;
}

/** Loose shapes for each state's `state.data` payload - see repair_job's REST endpoints. */
export interface JobListData {
  records: RepairJobRecord[];
}
export interface JobDetailData {
  record: JobHubRecord;
  options?: ClientOptions;
}
export interface PartsData {
  record: RepairJobRecord;
  job: {id: unknown; name: string};
  parts: RepairPartRecord[];
}
export interface ServicesData {
  job: {id: unknown; name: string};
  records: RepairServiceRecord[];
  notes: string;
}
export interface PartDetailData {
  record: RepairPartRecord;
}
export interface CatalogSearchData {
  records: CatalogRecord[];
  categories: CatalogCategory[];
  size: number;
  page: number;
  page_size: number;
}
export interface CatalogDetailData {
  record: CatalogRecord;
}
export interface InspectionListData {
  job: {id: unknown; name: string};
  records: InspectionRecord[];
  templates: InspectionTemplate[];
  default_odometer: number;
  odometer_unit: string;
}
export interface InspectionLinesData {
  record: InspectionRecord;
  lines: InspectionLine[];
}
export interface InspectionLineDetailData {
  record: InspectionLine;
  inspection: {id: unknown};
  choices: InspectionLineChoices;
}
