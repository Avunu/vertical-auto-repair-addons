# Repair Technician App

The technician's app, for an iPad on a bay: their jobs, a work timer on each service,
parts and the parts catalogue, digital vehicle inspections with measurements and photos,
their timesheets, and the time clock. It is an installable web app at
**`/repair-tech/app/`**, signed in with the user's ordinary Odoo session.

It replaces `shopfloor_repair` and `shopfloor_repair_mobile`, the OCA Shopfloor version
of the same app. Installing it over them takes their data along and uninstalls them (see
[Replacing shopfloor_repair](#replacing-shopfloor_repair)).

## What a technician can do

| Screen          | What's on it                                                                                                                                                                                                                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| My Jobs         | Their own jobs, then those they can pick up: shared through an appointment type they are bookable for, or nobody's yet. Filter by plate, VIN, unit number, customer or work order; scan a work order, plate or VIN to open its job.                                                                     |
| Job             | The customer's concern, each accepted service with a Start/Stop timer and the hours logged (theirs, everyone's, the estimate), notes, the vehicle. Start Repair and Finish.                                                                                                                             |
| Parts           | What the estimate expects and what has gone in: one tap for "used all", a decimal quantity with its lot or serial for the rest, Undo. Scan a part to find it on the job.                                                                                                                                |
| Catalog         | Search by name, part number or barcode, filter by category, add a part to the job (and mark it used). It reaches the customer's quote, flagged as added by the technician, with a note on the order for the service advisor.                                                                            |
| Inspections     | The job's inspections; start one from a checklist at the odometer reading.                                                                                                                                                                                                                              |
| Checklist, item | Items by category with their grades. Grading an item: measurements (out-of-spec flagged), the grade in the colours of the customer's report, conditions and recommended actions (the item's usual ones first), a note, photos. Saving moves on to the next ungraded item; complete once all are graded. |
| Timesheets      | Their job time by day beside the clocked time. Correct an entry's times or job, move part of it to another job, cut a break out of it, move or remove a break, correct a clock-in.                                                                                                                      |

Always in the header: the running timer (with Stop, from any screen), Clock in/out with
today's hours, and Scan.

The rules are the shop's, not the app's: one running timer per technician (starting
another stops the first at the same instant), the first timer of the day clocks them in,
clocking out stops the timer, a draft job can be diagnosed but not started, no two
timesheet entries of one technician overlap.

## Setup

1. Give each technician the **Technician** group (Inventory). It implies Inventory /
   User, Timesheets / User and Fleet / User, which the app reads with, and widens
   inspections to every customer vehicle.
2. Link each technician to an employee.
3. Set the company's **Repair Labor Project** (Settings, Repair).
4. Settings, Inventory, **Technician App**: whether technicians may finish jobs, see
   unassigned jobs and jobs they are Responsible for, whether a problem grade needs a
   photo, and the catalogue's page size.

## On an iPad

Open `/repair-tech/app/` in Safari and sign in, then Share, Add to Home Screen. It opens
full screen, keeps the screen on while a timer runs, and badges its icon. A long press
on the icon offers My Jobs, Scan and Timesheets.

It needs HTTPS, as the camera and the service worker do. Once opened, it opens without a
network and shows what it last saw, with a banner saying so; changes need the network,
and are refused rather than queued (a timer started when the connection returns would
start at the wrong time). A new version waits until the technician taps Update.

Scanning reads 1D codes, QR, Data Matrix and PDF417 through the camera: the browser's
own `BarcodeDetector` where it has one, else ZXing compiled to WebAssembly (iPad
Safari), which is part of the build, not fetched from a CDN. A Bluetooth or USB scanner
that types the code works anywhere outside a text field. Photos are taken with the rear
camera and downscaled to 1600 px JPEG on the device before upload.

## Replacing shopfloor_repair

Install this module where `shopfloor_repair` is installed, and in the same update:

- its records are taken over under the same ids: the Shop Floor Technician group (so
  every technician keeps it), the inspection access rights and record rules, and the
  Technician Note subtype;
- who added which part from the floor is copied to the new field;
- `shopfloor_repair` and `shopfloor_repair_mobile` are uninstalled. Their API keys and
  `shopfloor.app` record go with them; technicians sign in with their Odoo user instead.

The OCA Shopfloor modules they depended on (`shopfloor_base`, `shopfloor_mobile_base`,
…) stay installed; uninstall them separately if nothing else uses them.

## How it is built

The facades in
[`models/`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/repair_tech_app/models/)
are `@facade` methods of the `repair.tech.app` model (from
[`repair_tech_api`](repair_tech_api.md)): typed with Pydantic in
[`schemas.py`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/repair_tech_app/schemas.py),
validated on the way in and out, and called over call_kw on 18.0 or JSON-2 on 19.0.
`frontend/api/` is generated from them: the JSON Schema, the TypeScript types and the
typed client. A facade's parameters or result that changes in Python is a type error in
the app.

The frontend is React 19 with the React Compiler, TypeScript 7, Astryx, TanStack Router
and TanStack Query, built by Vite 8 into `static/dist/`. The build is Rust throughout:
Rolldown and Oxc, the React Compiler as `oxc-transform-react`, StyleX as `@stylexswc`.
The query cache persists to IndexedDB for the offline start. `AGENTS.md` here is
Astryx's guidance for working on the UI.

```sh
cd repair_tech_app
pnpm install
pnpm run generate   # after changing a facade or a schema
pnpm run check      # tsc, oxlint, and generated files up to date
pnpm test           # Vitest
pnpm run build      # tsc, then vite build
```

`odoo module build` builds it in the dev shell, `devenv up` keeps it built, and Nix
builds it into the deployed tree.

## Tests

- Python, against the facades as a technician holding only the Technician group: jobs
  and their visibility, timers, parts and the catalogue, inspections, timesheets and
  breaks, notes, the takeover from `shopfloor_repair`.
- In Chrome (`tests/test_browser.py`), on the built app: open a job from My Jobs, start
  and stop a timer, use parts, add a note, grade and complete an inspection, delete a
  timesheet entry; each checked in the database. Skipped until the app is built.
- Vitest, in `frontend/`: time handling, the timesheet day model and its breaks, the
  scanner's keyboard-wedge timing, photo sizing, the job filter.

To try it by hand,
[`tools/seed_demo.py`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/repair_tech_app/tools/seed_demo.py)
seeds a technician (login and password `tina`), three jobs and a checklist into a
throwaway database.
