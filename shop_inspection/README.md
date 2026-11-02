# Shop Digital Vehicle Inspection

Extends the OCA `fleet_vehicle_inspection` stack into a full digital vehicle inspection (DVI) tool for a repair shop, linked to repair orders.

## What it adds

-   **Repair order link**: inspections carry a `repair_id`; the repair order gets an Inspections smart button, a _New Inspection_ header button (pre-filled with vehicle, odometer and staff), and aggregated severity counters across all inspections of the visit.
-   **Severity grades** on inspection lines: _Today's Services / Concerns_, _Good_, _Will Need Attention in the Future_, _Currently Needs Attention_, _Failed State Inspection_, _N/A_. Setting a severity also sets the OCA pass/fail `result`, so the standard confirm gate and rollup keep working.
-   **Condition & recommended-action catalogs** (`shop.inspection.condition`, `shop.inspection.action`), linked per finding line and, as defaults, per inspection item.
-   **Checklist categories** (`shop.inspection.category`) on items — drives the section grouping on the customer report.
-   **Measurements**: items define measurement specs (name, wheel position, unit, min/discard and max limits); inspection lines get the grid pre-filled and each measured value computes an `out_of_spec` flag (a value of 0 is treated as "not measured"). The inspection also exposes every line's measurements in one flat _Measurements_ tab for value entry.
-   **Inline entry**: the inspection line list is editable in place — severity, conditions, recommended actions and notes are graded in the row, with a read-only summary of the measured values (red when anything is out of spec). The full line form is still one tap away, in a dialog, through the expand button at the end of the row (photos, item instructions, per-line measurements). The dialog opens the line as it stands, so a brand new inspection does not have to be saved first.
-   **Staff fields**: technician and service advisor on inspections and repair orders.
-   **Seed data** (noupdate): four typical DVI checklist templates — Check In, Pre-Inspection / Test Drive, Courtesy Inspection, State Safety Inspection — with ~30 items, conditions, actions and measurement specs (tread depth, tire pressure, brake pads, rotor thickness, battery CCA, coolant freeze point).

## Usage

On a repair order, hit **New Inspection**, pick one of the checklist templates, then grade each line on the tablet directly in the list: severity, conditions, recommended actions and notes. Measurements are typed in the _Measurements_ tab, which lists every line's readings in checklist order. Photos are added from the line form, opened as a dialog with the expand button at the end of the row (photo capture comes from the OCA image model on lines; add `web_widget_o2m_attachment_image_gallery` for gallery UX).

Conditions/actions on lines are deliberately not domain-restricted to the item's catalogs — the item catalogs are defaults/reference, technicians can pick anything.
