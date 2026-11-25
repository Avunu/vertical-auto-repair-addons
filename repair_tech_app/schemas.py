# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The technician app's data shapes: the contract between the facades in
``models/`` and the React app, whose ``frontend/api/api.d.ts`` is generated
from these classes (field docstrings become its JSDoc).

Only Pydantic here, no Odoo. Datetimes are ``AwareDatetime`` both ways: the
browser sends and receives them with their offset, never as local time.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from odoo.addons.repair_tech_api.schemas import Ref, Schema

RepairState = Literal["draft", "confirmed", "under_repair", "done", "cancel"]
Tracking = Literal["none", "lot", "serial"]
Severity = Literal["today", "good", "future", "attention", "fail_state", "na"]
InspectionState = Literal["draft", "confirmed", "cancel"]
InspectionResult = Literal["todo", "success", "failure"]
MoveState = Literal[
    "draft", "waiting", "confirmed", "partially_available", "assigned", "done", "cancel"
]

Quantity = Annotated[float, Field(ge=0)]
PositiveQuantity = Annotated[float, Field(gt=0)]
Page = Annotated[int, Field(ge=1)]
Note = Annotated[str, Field(max_length=10_000)]
Code = Annotated[str, Field(min_length=1, max_length=200)]


# -- who and what -------------------------------------------------------------


class AppOptions(Schema):
    """Shop settings the app needs to hide what it must not offer (Settings >
    Inventory > Technician App)."""

    allow_finish: bool
    """Technicians may close a job from the app."""
    require_photo_on_fail: bool
    """A problem grade needs a photo on the item first."""


class TechSession(Schema):
    """Who is using the app; fetched once at startup."""

    uid: int
    name: str
    lang: str
    tz: str | None
    company: Ref
    employee: Ref | None
    """``None`` means timers and clocking in are refused: time is logged per
    employee."""
    options: AppOptions


class RunningTimer(Schema):
    """The one work timer the technician has running, wherever it is."""

    repair_id: int
    service_id: int
    job_label: str
    service_name: str
    started_at: AwareDatetime


class Shift(Schema):
    """The technician's day: clocked in or not, and the job timer running."""

    clocked_in: bool
    since: AwareDatetime | None
    """When the current clock-in started."""
    hours_today: float
    """Everything clocked today, the open period up to now included."""
    running: RunningTimer | None


# -- jobs ---------------------------------------------------------------------


class Vehicle(Schema):
    id: int
    description: str
    """Colour/Year/Brand/Model/Plate/Unit: what a technician sees walking up
    to the car."""
    license_plate: str | None
    vin: str | None
    model_year: str | None
    unit_number: str | None


class JobSummary(Schema):
    """One row of "My Jobs"."""

    id: int
    name: str
    """The order's reference, e.g. ``RO/00123``."""
    label: str
    """Vehicle description, else customer, else the order's reference."""
    state: RepairState
    state_label: str
    stage: Ref | None
    priority: bool
    schedule_date: AwareDatetime | None
    partner: Ref | None
    vehicle: Vehicle | None
    technician: Ref | None
    is_mine: bool
    """Assigned to the current user (others' jobs show through a shared
    appointment type, or because nobody has them yet)."""
    customer_concern: str
    """Plain text, never markup."""
    timer_running: bool
    """The current user's timer is running on this job."""
    parts_done: int
    parts_total: int
    inspection_graded: int
    inspection_total: int


class Timer(Schema):
    """The current user's timer on one service."""

    running: bool
    started_at: AwareDatetime | None


class Service(Schema):
    """An accepted service line the technician logs time against."""

    id: int
    name: str
    estimated_hours: float
    actual_hours: float
    """Everyone's logged time."""
    my_hours: float
    """The current user's share of ``actual_hours``, stopped timers only."""
    timer: Timer


class JobDetail(JobSummary):
    """The job hub: everything one screen shows about a job."""

    internal_notes: str
    """The order's Repair Notes as plain text; technicians' notes land here."""
    repair_request: str
    odometer_in: float
    odometer_unit: str
    under_warranty: bool
    sale_order: Ref | None
    services: list[Service]
    inspection_count: int
    can_start: bool
    """Confirmed and not started: the Start Repair button."""
    can_finish: bool
    """Under repair, and the shop lets technicians close jobs."""
    can_edit_parts: bool


class TimerStarted(Schema):
    """A started timer, and what starting it did on the side."""

    job: JobDetail
    clocked_in: bool
    """Starting the timer clocked the technician in for the day."""
    stopped: RunningTimer | None
    """The timer that was running elsewhere and stopped at the same instant."""


# -- parts and catalog ----------------------------------------------------------


class Product(Schema):
    id: int
    name: str
    default_code: str | None
    barcode: str | None
    tracking: Tracking
    uom: Ref


class CatalogProduct(Product):
    qty_available: float


class Part(Schema):
    """A part to install: an ``add`` move on the repair."""

    id: int
    product: Product
    quantity_demand: float
    quantity_done: float
    picked: bool
    state: MoveState
    state_label: str
    available: bool
    """Reserved in stock, so it can be picked now."""
    added_by_technician: bool
    """Added from the app, on top of the estimate the customer approved."""
    lots: list[Ref]


class PartList(Schema):
    job: JobSummary
    parts: list[Part]
    can_edit: bool


class PartScan(Schema):
    """What a scanned code is: a part on the job, or a product to add."""

    move_id: int | None
    """The job's part with that product, when it has one."""
    product: CatalogProduct | None
    """The product, when the code names one but the job doesn't have it."""


class CatalogPage(Schema):
    records: list[CatalogProduct]
    total: int
    page: int
    page_size: int


# -- inspections ----------------------------------------------------------------


class SeverityCounts(Schema):
    today: int
    good: int
    future: int
    attention: int
    fail_state: int


class InspectionSummary(Schema):
    id: int
    name: str
    state: InspectionState
    state_label: str
    result: InspectionResult
    odometer: float
    odometer_unit: str
    date_inspected: AwareDatetime | None
    template: Ref | None
    graded_count: int
    line_count: int
    counts: SeverityCounts


class InspectionList(Schema):
    job: JobSummary
    records: list[InspectionSummary]
    templates: list[Ref]
    has_vehicle: bool
    default_odometer: float
    odometer_unit: str


class Measurement(Schema):
    id: int
    name: str
    position: str
    position_label: str
    uom_label: str
    value: float
    """0 means not measured yet."""
    spec_min: float
    spec_max: float
    out_of_spec: bool


class Photo(Schema):
    id: int
    name: str
    url: str
    """A 512px rendition, for the thumbnail strip."""
    full_url: str


class InspectionLine(Schema):
    """One checklist item."""

    id: int
    name: str
    category: Ref | None
    severity: Severity | None
    note: str
    instruction: str
    measurement_summary: str
    measurement_alert: bool
    conditions: list[Ref]
    actions: list[Ref]
    measurements: list[Measurement]
    photo_count: int


class InspectionDetail(Schema):
    """The checklist."""

    inspection: InspectionSummary
    job: JobSummary
    lines: list[InspectionLine]
    editable: bool


class SeverityChoice(Schema):
    value: Severity
    label: str


class InspectionLineDetail(Schema):
    """One item, with everything its grading form needs."""

    line: InspectionLine
    inspection: InspectionSummary
    photos: list[Photo]
    severities: list[SeverityChoice]
    conditions: list[Ref]
    """The item's usual conditions first, then the rest."""
    actions: list[Ref]
    """The item's usual recommended actions first, then the rest."""
    editable: bool


# -- timesheets -----------------------------------------------------------------


class TimesheetEntry(Schema):
    id: int
    description: str
    date: str
    """The entry's day, ``YYYY-MM-DD``."""
    start: AwareDatetime | None
    end: AwareDatetime | None
    """``None`` while the timer runs."""
    hours: float
    job: Ref | None
    """Named by its label (vehicle, else customer), as everywhere in the app."""
    job_ref: str
    """The order's reference: two jobs on one vehicle share a label."""
    service: Ref | None


class Attendance(Schema):
    id: int
    check_in: AwareDatetime
    check_out: AwareDatetime | None


class AttendanceDay(Schema):
    date: str
    hours: float
    """Clocked time that day."""
    records: list[Attendance]


class DayHours(Schema):
    date: str
    hours: float
    """Job time that day, across every entry, not only this page's."""


class TimesheetPage(Schema):
    records: list[TimesheetEntry]
    total: int
    page: int
    page_size: int
    attendance: list[AttendanceDay]
    """Clocked time for the days this page shows."""
    job_hours: list[DayHours]


class JobChoice(Schema):
    """A job time can be moved to, with its services."""

    id: int
    name: str
    ref: str
    customer: str
    services: list[Ref]


class TimesheetDetail(Schema):
    entry: TimesheetEntry
    jobs: list[JobChoice]


class Notice(Schema):
    """A change done; what to tell the technician."""

    message: str
