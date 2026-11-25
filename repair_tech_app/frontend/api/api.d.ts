/* eslint-disable */
/**
 * GENERATED - do not edit. Source: the @facade methods in api.schema.json,
 * via repair_tech_api/tools/generate_api_types.mjs. Regenerate with
 * `pnpm run generate`.
 */

/**
 * Facades defined by repair_tech_app.
 */
export interface RepairTechApp {
  "repair.tech.app": RepairTechAppMethods;
}
/**
 * Facades on repair.tech.app.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "RepairTechAppMethods".
 */
export interface RepairTechAppMethods {
  add_break: AddBreakMethod;
  add_note: AddNoteMethod;
  add_part: AddPartMethod;
  add_photo: AddPhotoMethod;
  catalog: CatalogMethod;
  catalog_categories: CatalogCategoriesMethod;
  clock_toggle: ClockToggleMethod;
  confirm_inspection: ConfirmInspectionMethod;
  create_inspection: CreateInspectionMethod;
  delete_break: DeleteBreakMethod;
  delete_job_break: DeleteJobBreakMethod;
  delete_timesheet: DeleteTimesheetMethod;
  find_job: FindJobMethod;
  finish: FinishMethod;
  grade: GradeMethod;
  inspection: InspectionMethod;
  inspection_line: InspectionLineMethod;
  inspections: InspectionsMethod;
  job: JobMethod;
  jobs: JobsMethod;
  parts: PartsMethod;
  remove_photo: RemovePhotoMethod;
  reset_part: ResetPartMethod;
  scan_part: ScanPartMethod;
  session: SessionMethod;
  set_measurement: SetMeasurementMethod;
  set_part_quantity: SetPartQuantityMethod;
  shift: ShiftMethod;
  split_timesheet: SplitTimesheetMethod;
  start_repair: StartRepairMethod;
  stop_running: StopRunningMethod;
  timer_start: TimerStartMethod;
  timer_stop: TimerStopMethod;
  timesheet: TimesheetMethod;
  timesheets: TimesheetsMethod;
  update_attendance: UpdateAttendanceMethod;
  update_break: UpdateBreakMethod;
  update_job_break: UpdateJobBreakMethod;
  update_timesheet: UpdateTimesheetMethod;
  use_all: UseAllMethod;
}
/**
 * Cut a break out of the middle of an entry.
 *
 * The entry is split around the gap, and so is the clocked period that
 * holds the break (clocked out at its start, back in at its end), so the
 * break comes off the day's clocked total too. When nothing is clocked
 * over the entry (a day entered by hand), only the job time splits. When
 * the entry is clocked but no single period holds the break, it is
 * refused: splitting the job time alone would leave the two disagreeing
 * about the same hours.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddBreakMethod".
 */
export interface AddBreakMethod {
  params: AddBreakParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddBreakParams".
 */
export interface AddBreakParams {
  end: IsoDateTime;
  line_id: number;
  start: IsoDateTime;
}
/**
 * A change done; what to tell the technician.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Notice".
 */
export interface Notice {
  message: string;
}
/**
 * Add a note to the job's Repair Notes. It is also posted to the
 * chatter as a Technician Note, so who hears about it is the order's
 * ordinary follower settings.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddNoteMethod".
 */
export interface AddNoteMethod {
  params: AddNoteParams;
  result: JobDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddNoteParams".
 */
export interface AddNoteParams {
  note: string;
  repair_id: number;
}
/**
 * The job hub: everything one screen shows about a job.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobDetail".
 */
export interface JobDetail {
  can_edit_parts: boolean;
  /**
   * Under repair, and the shop lets technicians close jobs.
   */
  can_finish: boolean;
  /**
   * Confirmed and not started: the Start Repair button.
   */
  can_start: boolean;
  /**
   * Plain text, never markup.
   */
  customer_concern: string;
  id: number;
  inspection_count: number;
  inspection_graded: number;
  inspection_total: number;
  /**
   * The order's Repair Notes as plain text; technicians' notes land here.
   */
  internal_notes: string;
  /**
   * Assigned to the current user (others' jobs show through a shared
   * appointment type, or because nobody has them yet).
   */
  is_mine: boolean;
  /**
   * Vehicle description, else customer, else the order's reference.
   */
  label: string;
  /**
   * The order's reference, e.g. ``RO/00123``.
   */
  name: string;
  odometer_in: number;
  odometer_unit: string;
  partner: Ref | null;
  parts_done: number;
  parts_total: number;
  priority: boolean;
  repair_request: string;
  sale_order: Ref | null;
  schedule_date: IsoDateTime | null;
  services: Service[];
  stage: Ref | null;
  state: "draft" | "confirmed" | "under_repair" | "done" | "cancel";
  state_label: string;
  technician: Ref | null;
  /**
   * The current user's timer is running on this job.
   */
  timer_running: boolean;
  under_warranty: boolean;
  vehicle: Vehicle | null;
}
/**
 * Any record shown by name.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Ref".
 */
export interface Ref {
  id: number;
  name: string;
}
/**
 * An accepted service line the technician logs time against.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Service".
 */
export interface Service {
  /**
   * Everyone's logged time.
   */
  actual_hours: number;
  estimated_hours: number;
  id: number;
  /**
   * The current user's share of ``actual_hours``, stopped timers only.
   */
  my_hours: number;
  name: string;
  timer: Timer;
}
/**
 * The current user's timer on one service.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Timer".
 */
export interface Timer {
  running: boolean;
  started_at: IsoDateTime | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Vehicle".
 */
export interface Vehicle {
  /**
   * Colour/Year/Brand/Model/Plate/Unit: what a technician sees walking up
   * to the car.
   */
  description: string;
  id: number;
  license_plate: string | null;
  model_year: string | null;
  unit_number: string | null;
  vin: string | null;
}
/**
 * Add a part from the catalog to the job; ``used`` records it as
 * installed straight away (untracked parts only).
 *
 * The part reaches the customer's quote, as core does for any part added
 * to a repair - on purpose. It is flagged as added by the technician and
 * a note on the order says so, so the service advisor sees what was added
 * on top of what the customer approved and decides what to bill.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddPartMethod".
 */
export interface AddPartMethod {
  params: AddPartParams;
  result: PartList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddPartParams".
 */
export interface AddPartParams {
  product_id: number;
  quantity?: number;
  repair_id: number;
  used?: boolean;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "PartList".
 */
export interface PartList {
  can_edit: boolean;
  job: JobSummary;
  parts: Part[];
}
/**
 * One row of "My Jobs".
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobSummary".
 */
export interface JobSummary {
  /**
   * Plain text, never markup.
   */
  customer_concern: string;
  id: number;
  inspection_graded: number;
  inspection_total: number;
  /**
   * Assigned to the current user (others' jobs show through a shared
   * appointment type, or because nobody has them yet).
   */
  is_mine: boolean;
  /**
   * Vehicle description, else customer, else the order's reference.
   */
  label: string;
  /**
   * The order's reference, e.g. ``RO/00123``.
   */
  name: string;
  partner: Ref | null;
  parts_done: number;
  parts_total: number;
  priority: boolean;
  schedule_date: IsoDateTime | null;
  stage: Ref | null;
  state: "draft" | "confirmed" | "under_repair" | "done" | "cancel";
  state_label: string;
  technician: Ref | null;
  /**
   * The current user's timer is running on this job.
   */
  timer_running: boolean;
  vehicle: Vehicle | null;
}
/**
 * A part to install: an ``add`` move on the repair.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Part".
 */
export interface Part {
  /**
   * Added from the app, on top of the estimate the customer approved.
   */
  added_by_technician: boolean;
  /**
   * Reserved in stock, so it can be picked now.
   */
  available: boolean;
  id: number;
  lots: Ref[];
  picked: boolean;
  product: Product;
  quantity_demand: number;
  quantity_done: number;
  state: "draft" | "waiting" | "confirmed" | "partially_available" | "assigned" | "done" | "cancel";
  state_label: string;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Product".
 */
export interface Product {
  barcode: string | null;
  default_code: string | null;
  id: number;
  name: string;
  tracking: "none" | "lot" | "serial";
  uom: Ref;
}
/**
 * Attach a photo to a checklist item: base64, bare or as a ``data:``
 * URL. The app downscales it first (a tablet shot is 4-8 MB).
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddPhotoMethod".
 */
export interface AddPhotoMethod {
  params: AddPhotoParams;
  result: InspectionLineDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AddPhotoParams".
 */
export interface AddPhotoParams {
  filename?: string | null;
  image: string;
  line_id: number;
}
/**
 * One item, with everything its grading form needs.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionLineDetail".
 */
export interface InspectionLineDetail {
  /**
   * The item's usual recommended actions first, then the rest.
   */
  actions: Ref[];
  /**
   * The item's usual conditions first, then the rest.
   */
  conditions: Ref[];
  editable: boolean;
  inspection: InspectionSummary;
  line: InspectionLine;
  photos: Photo[];
  severities: SeverityChoice[];
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionSummary".
 */
export interface InspectionSummary {
  counts: SeverityCounts;
  date_inspected: IsoDateTime | null;
  graded_count: number;
  id: number;
  line_count: number;
  name: string;
  odometer: number;
  odometer_unit: string;
  result: "todo" | "success" | "failure";
  state: "draft" | "confirmed" | "cancel";
  state_label: string;
  template: Ref | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SeverityCounts".
 */
export interface SeverityCounts {
  attention: number;
  fail_state: number;
  future: number;
  good: number;
  today: number;
}
/**
 * One checklist item.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionLine".
 */
export interface InspectionLine {
  actions: Ref[];
  category: Ref | null;
  conditions: Ref[];
  id: number;
  instruction: string;
  measurement_alert: boolean;
  measurement_summary: string;
  measurements: Measurement[];
  name: string;
  note: string;
  photo_count: number;
  severity: ("today" | "good" | "future" | "attention" | "fail_state" | "na") | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Measurement".
 */
export interface Measurement {
  id: number;
  name: string;
  out_of_spec: boolean;
  position: string;
  position_label: string;
  spec_max: number;
  spec_min: number;
  uom_label: string;
  /**
   * 0 means not measured yet.
   */
  value: number;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Photo".
 */
export interface Photo {
  full_url: string;
  id: number;
  name: string;
  /**
   * A 512px rendition, for the thumbnail strip.
   */
  url: string;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SeverityChoice".
 */
export interface SeverityChoice {
  label: string;
  value: "today" | "good" | "future" | "attention" | "fail_state" | "na";
}
/**
 * Browse the parts catalog: goods that can be purchased, by name,
 * internal reference or barcode.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CatalogMethod".
 */
export interface CatalogMethod {
  params: CatalogParams;
  result: CatalogPage;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CatalogParams".
 */
export interface CatalogParams {
  category_id?: number | null;
  page?: number;
  search?: string | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CatalogPage".
 */
export interface CatalogPage {
  page: number;
  page_size: number;
  records: CatalogProduct[];
  total: number;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CatalogProduct".
 */
export interface CatalogProduct {
  barcode: string | null;
  default_code: string | null;
  id: number;
  name: string;
  qty_available: number;
  tracking: "none" | "lot" | "serial";
  uom: Ref;
}
/**
 * Product categories, for the catalog's filter.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CatalogCategoriesMethod".
 */
export interface CatalogCategoriesMethod {
  params: CatalogCategoriesParams;
  result: Ref[];
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CatalogCategoriesParams".
 */
export interface CatalogCategoriesParams {}
/**
 * Clock in, or out. Clocking out stops a running job timer
 * (models/hr_employee.py).
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ClockToggleMethod".
 */
export interface ClockToggleMethod {
  params: ClockToggleParams;
  result: Shift;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ClockToggleParams".
 */
export interface ClockToggleParams {}
/**
 * The technician's day: clocked in or not, and the job timer running.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Shift".
 */
export interface Shift {
  clocked_in: boolean;
  /**
   * Everything clocked today, the open period up to now included.
   */
  hours_today: number;
  running: RunningTimer | null;
  /**
   * When the current clock-in started.
   */
  since: IsoDateTime | null;
}
/**
 * The one work timer the technician has running, wherever it is.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "RunningTimer".
 */
export interface RunningTimer {
  job_label: string;
  repair_id: number;
  service_id: number;
  service_name: string;
  started_at: IsoDateTime;
}
/**
 * Complete the inspection (OCA's ``button_confirm``). Every item needs
 * a grade first; Not Applicable is the deliberate skip.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ConfirmInspectionMethod".
 */
export interface ConfirmInspectionMethod {
  params: ConfirmInspectionParams;
  result: InspectionList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ConfirmInspectionParams".
 */
export interface ConfirmInspectionParams {
  inspection_id: number;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionList".
 */
export interface InspectionList {
  default_odometer: number;
  has_vehicle: boolean;
  job: JobSummary;
  odometer_unit: string;
  records: InspectionSummary[];
  templates: Ref[];
}
/**
 * Start an inspection of the job's vehicle from a checklist template,
 * at the odometer reading the technician reads off the dash.
 *
 * The odometer is required: fleet_vehicle_inspection's inverse raises on
 * an empty one.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CreateInspectionMethod".
 */
export interface CreateInspectionMethod {
  params: CreateInspectionParams;
  result: InspectionDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "CreateInspectionParams".
 */
export interface CreateInspectionParams {
  odometer: number;
  repair_id: number;
  template_id: number;
}
/**
 * The checklist.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionDetail".
 */
export interface InspectionDetail {
  editable: boolean;
  inspection: InspectionSummary;
  job: JobSummary;
  lines: InspectionLine[];
}
/**
 * Remove the break after a clocked period by joining it to the next.
 * The break's time counts as clocked; job entries stay as they are.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DeleteBreakMethod".
 */
export interface DeleteBreakMethod {
  params: DeleteBreakParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DeleteBreakParams".
 */
export interface DeleteBreakParams {
  attendance_id: number;
}
/**
 * Join two parts of one job back into one entry.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DeleteJobBreakMethod".
 */
export interface DeleteJobBreakMethod {
  params: DeleteJobBreakParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DeleteJobBreakParams".
 */
export interface DeleteJobBreakParams {
  after_id: number;
  line_id: number;
}
/**
 * Remove an entry made by mistake.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DeleteTimesheetMethod".
 */
export interface DeleteTimesheetMethod {
  params: DeleteTimesheetParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DeleteTimesheetParams".
 */
export interface DeleteTimesheetParams {
  line_id: number;
}
/**
 * A job from a scanned or typed code: its reference, its quote's
 * number, the VIN, the plate or the unit number. ``None`` if nothing
 * matches.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "FindJobMethod".
 */
export interface FindJobMethod {
  params: FindJobParams;
  result: JobSummary | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "FindJobParams".
 */
export interface FindJobParams {
  code: string;
}
/**
 * Complete the repair (core ``action_repair_end``). The technician's
 * timer on the job stops: the work is done.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "FinishMethod".
 */
export interface FinishMethod {
  params: FinishParams;
  result: JobDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "FinishParams".
 */
export interface FinishParams {
  repair_id: number;
}
/**
 * Grade a checklist item. ``None`` leaves conditions, actions or the
 * note as they are. The severity is enough for the pass/fail result:
 * shop_inspection maps it.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "GradeMethod".
 */
export interface GradeMethod {
  params: GradeParams;
  result: InspectionDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "GradeParams".
 */
export interface GradeParams {
  action_ids?: number[] | null;
  condition_ids?: number[] | null;
  line_id: number;
  note?: string | null;
  severity: "today" | "good" | "future" | "attention" | "fail_state" | "na";
}
/**
 * An inspection's checklist, by category.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionMethod".
 */
export interface InspectionMethod {
  params: InspectionParams;
  result: InspectionDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionParams".
 */
export interface InspectionParams {
  inspection_id: number;
}
/**
 * One checklist item, with its photos and grading choices.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionLineMethod".
 */
export interface InspectionLineMethod {
  params: InspectionLineParams;
  result: InspectionLineDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionLineParams".
 */
export interface InspectionLineParams {
  line_id: number;
}
/**
 * The job's inspections, and the checklists one can start from.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionsMethod".
 */
export interface InspectionsMethod {
  params: InspectionsParams;
  result: InspectionList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "InspectionsParams".
 */
export interface InspectionsParams {
  repair_id: number;
}
/**
 * The job hub: the vehicle, the concern, the services with their
 * timers, and what the technician may do next.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobMethod".
 */
export interface JobMethod {
  params: JobParams;
  result: JobDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobParams".
 */
export interface JobParams {
  repair_id: number;
}
/**
 * The technician's jobs: assigned, shared through the appointment
 * type, or unassigned. Priority first, then by schedule.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobsMethod".
 */
export interface JobsMethod {
  params: JobsParams;
  result: JobSummary[];
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobsParams".
 */
export interface JobsParams {}
/**
 * The parts the job expects, and what has been used so far.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "PartsMethod".
 */
export interface PartsMethod {
  params: PartsParams;
  result: PartList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "PartsParams".
 */
export interface PartsParams {
  repair_id: number;
}
/**
 * Delete a photo taken by mistake.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "RemovePhotoMethod".
 */
export interface RemovePhotoMethod {
  params: RemovePhotoParams;
  result: InspectionLineDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "RemovePhotoParams".
 */
export interface RemovePhotoParams {
  photo_id: number;
}
/**
 * Undo the part's usage: back to nothing used.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ResetPartMethod".
 */
export interface ResetPartMethod {
  params: ResetPartParams;
  result: PartList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ResetPartParams".
 */
export interface ResetPartParams {
  move_id: number;
}
/**
 * What a scanned barcode is: one of the job's parts, or a product the
 * job doesn't have yet (to offer adding it). Matches the barcode, then
 * the internal reference, then a lot or serial number.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ScanPartMethod".
 */
export interface ScanPartMethod {
  params: ScanPartParams;
  result: PartScan;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ScanPartParams".
 */
export interface ScanPartParams {
  code: string;
  repair_id: number;
}
/**
 * What a scanned code is: a part on the job, or a product to add.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "PartScan".
 */
export interface PartScan {
  /**
   * The job's part with that product, when it has one.
   */
  move_id: number | null;
  /**
   * The product, when the code names one but the job doesn't have it.
   */
  product: CatalogProduct | null;
}
/**
 * The signed-in technician, their company and employee, and the
 * shop's settings for the app.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SessionMethod".
 */
export interface SessionMethod {
  params: SessionParams;
  result: TechSession;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SessionParams".
 */
export interface SessionParams {}
/**
 * Who is using the app; fetched once at startup.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TechSession".
 */
export interface TechSession {
  company: Ref;
  /**
   * ``None`` means timers and clocking in are refused: time is logged per
   * employee.
   */
  employee: Ref | null;
  lang: string;
  name: string;
  options: AppOptions;
  tz: string | null;
  uid: number;
}
/**
 * Shop settings the app needs to hide what it must not offer (Settings >
 * Inventory > Technician App).
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AppOptions".
 */
export interface AppOptions {
  /**
   * Technicians may close a job from the app.
   */
  allow_finish: boolean;
  /**
   * A problem grade needs a photo on the item first.
   */
  require_photo_on_fail: boolean;
}
/**
 * Record a measured value; 0 means not measured.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SetMeasurementMethod".
 */
export interface SetMeasurementMethod {
  params: SetMeasurementParams;
  result: InspectionLineDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SetMeasurementParams".
 */
export interface SetMeasurementParams {
  measurement_id: number;
  value: number;
}
/**
 * Record how much of a part was used, with its lot or serial when it
 * is tracked: ``lot_id`` from a picker, ``lot_name`` from a scanner.
 *
 * Writes ``stock.move.quantity`` only: changing the demand
 * (``product_uom_qty``) would make core rewrite the customer's approved
 * quote line.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SetPartQuantityMethod".
 */
export interface SetPartQuantityMethod {
  params: SetPartQuantityParams;
  result: PartList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SetPartQuantityParams".
 */
export interface SetPartQuantityParams {
  lot_id?: number | null;
  lot_name?: string | null;
  move_id: number;
  quantity: number;
}
/**
 * Clocked in or not, today's clocked hours, and the job timer running
 * anywhere. Polled by the app's header.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ShiftMethod".
 */
export interface ShiftMethod {
  params: ShiftParams;
  result: Shift;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "ShiftParams".
 */
export interface ShiftParams {}
/**
 * Move the slice ``start``-``end`` of an entry to another job.
 *
 * The slice may touch either end of the entry or sit inside it. The entry
 * shrinks to what is left, and copies carry the slice (on the chosen job)
 * and, for a slice inside, the tail after it (on the entry's job), so
 * together they cover exactly the original time. The entry shrinks
 * *first*: the no-overlap constraint is checked on every write.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SplitTimesheetMethod".
 */
export interface SplitTimesheetMethod {
  params: SplitTimesheetParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "SplitTimesheetParams".
 */
export interface SplitTimesheetParams {
  end: IsoDateTime;
  job_id: number;
  line_id: number;
  service_id?: number | null;
  start: IsoDateTime;
}
/**
 * Move a confirmed job to Under Repair.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "StartRepairMethod".
 */
export interface StartRepairMethod {
  params: StartRepairParams;
  result: JobDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "StartRepairParams".
 */
export interface StartRepairParams {
  repair_id: number;
}
/**
 * Stop whatever timer the technician has running, from anywhere in
 * the app. The job it ran on, or ``None`` if nothing was running.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "StopRunningMethod".
 */
export interface StopRunningMethod {
  params: StopRunningParams;
  result: JobDetail | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "StopRunningParams".
 */
export interface StopRunningParams {}
/**
 * Start timing a service. A timer running anywhere else stops at the
 * same instant, and the first timer of the day clocks the technician in.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimerStartMethod".
 */
export interface TimerStartMethod {
  params: TimerStartParams;
  result: TimerStarted;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimerStartParams".
 */
export interface TimerStartParams {
  repair_id: number;
  service_id: number;
}
/**
 * A started timer, and what starting it did on the side.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimerStarted".
 */
export interface TimerStarted {
  /**
   * Starting the timer clocked the technician in for the day.
   */
  clocked_in: boolean;
  job: JobDetail;
  /**
   * The timer that was running elsewhere and stopped at the same instant.
   */
  stopped: RunningTimer | null;
}
/**
 * Stop timing a service. Stopping a timer that isn't running does
 * nothing.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimerStopMethod".
 */
export interface TimerStopMethod {
  params: TimerStopParams;
  result: JobDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimerStopParams".
 */
export interface TimerStopParams {
  repair_id: number;
  service_id: number;
}
/**
 * One entry, with the jobs it can be moved to.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetMethod".
 */
export interface TimesheetMethod {
  params: TimesheetParams;
  result: TimesheetDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetParams".
 */
export interface TimesheetParams {
  line_id: number;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetDetail".
 */
export interface TimesheetDetail {
  entry: TimesheetEntry;
  jobs: JobChoice[];
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetEntry".
 */
export interface TimesheetEntry {
  /**
   * The entry's day, ``YYYY-MM-DD``.
   */
  date: string;
  description: string;
  /**
   * ``None`` while the timer runs.
   */
  end: IsoDateTime | null;
  hours: number;
  id: number;
  /**
   * Named by its label (vehicle, else customer), as everywhere in the app.
   */
  job: Ref | null;
  /**
   * The order's reference: two jobs on one vehicle share a label.
   */
  job_ref: string;
  service: Ref | null;
  start: IsoDateTime | null;
}
/**
 * A job time can be moved to, with its services.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "JobChoice".
 */
export interface JobChoice {
  customer: string;
  id: number;
  name: string;
  ref: string;
  services: Ref[];
}
/**
 * The technician's repair-job time, newest first, 20 a page; with the
 * clocked time and the job time of each day on the page. ``search``
 * matches the job's reference or the description, or a day
 * (``YYYY-MM-DD``).
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetsMethod".
 */
export interface TimesheetsMethod {
  params: TimesheetsParams;
  result: TimesheetPage;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetsParams".
 */
export interface TimesheetsParams {
  page?: number;
  search?: string | null;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "TimesheetPage".
 */
export interface TimesheetPage {
  /**
   * Clocked time for the days this page shows.
   */
  attendance: AttendanceDay[];
  job_hours: DayHours[];
  page: number;
  page_size: number;
  records: TimesheetEntry[];
  total: number;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "AttendanceDay".
 */
export interface AttendanceDay {
  date: string;
  /**
   * Clocked time that day.
   */
  hours: number;
  records: Attendance[];
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "Attendance".
 */
export interface Attendance {
  check_in: IsoDateTime;
  check_out: IsoDateTime | null;
  id: number;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "DayHours".
 */
export interface DayHours {
  date: string;
  /**
   * Job time that day, across every entry, not only this page's.
   */
  hours: number;
}
/**
 * Correct one clocked period's start and end. Worked hours follow:
 * hr.attendance computes them from the two times.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateAttendanceMethod".
 */
export interface UpdateAttendanceMethod {
  params: UpdateAttendanceParams;
  result: AttendanceDay;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateAttendanceParams".
 */
export interface UpdateAttendanceParams {
  attendance_id: number;
  end: IsoDateTime;
  start: IsoDateTime;
}
/**
 * Move or resize the break after a clocked period: the end of that
 * period and the start of the next. The two job entries that met the
 * break's old edges ("Add break" split them there) follow it; any other
 * job time inside the new break is refused, not trimmed.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateBreakMethod".
 */
export interface UpdateBreakMethod {
  params: UpdateBreakParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateBreakParams".
 */
export interface UpdateBreakParams {
  attendance_id: number;
  end: IsoDateTime;
  start: IsoDateTime;
}
/**
 * Move or resize the gap between two parts of one job.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateJobBreakMethod".
 */
export interface UpdateJobBreakMethod {
  params: UpdateJobBreakParams;
  result: Notice;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateJobBreakParams".
 */
export interface UpdateJobBreakParams {
  after_id: number;
  end: IsoDateTime;
  line_id: number;
  start: IsoDateTime;
}
/**
 * Correct an entry's times, and with ``job_id`` its job and service.
 *
 * The duration is written as such rather than through ``date_time_end``,
 * whose inverse only works when the line's unit is hours and otherwise
 * leaves the old duration - read back later as "still running".
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateTimesheetMethod".
 */
export interface UpdateTimesheetMethod {
  params: UpdateTimesheetParams;
  result: TimesheetDetail;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UpdateTimesheetParams".
 */
export interface UpdateTimesheetParams {
  end: IsoDateTime;
  job_id?: number | null;
  line_id: number;
  service_id?: number | null;
  start: IsoDateTime;
}
/**
 * Mark the whole expected quantity as used. Not for tracked parts:
 * their lots or serials have to be scanned.
 *
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UseAllMethod".
 */
export interface UseAllMethod {
  params: UseAllParams;
  result: PartList;
}
/**
 * This interface was referenced by `RepairTechApp`'s JSON-Schema
 * via the `definition` "UseAllParams".
 */
export interface UseAllParams {
  move_id: number;
}

/** Every facade, by model and method: what client.ts types calls with. */
export type Api = RepairTechApp;

/** An ISO 8601 datetime with its offset, e.g. `2026-01-05T09:00:00Z`. */
export type IsoDateTime = string & {readonly __brand: "IsoDateTime"};
