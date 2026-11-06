---
title: "Avunu auto repair vertical"
description:
  "Odoo 18.0 modules for automotive repair shops: digital vehicle inspections and the
  customer's inspection report, estimates built from inspection findings, appointment
  scheduling, the service workflow on the repair order, and an iPad-first technician app
  on OCA Shopfloor."
---

Odoo 18.0 modules for automotive repair shops: digital vehicle inspections and the
customer's inspection report, estimates built from inspection findings, appointment
scheduling, the service workflow on the repair order, and an iPad-first technician app
on OCA Shopfloor. They are built and maintained by [Avunu LLC](https://avunu.net) and
published for anyone to use. Together they form an industry vertical in the spirit of
OCA's `vertical-*` repositories (such as
[OCA/vertical-hotel](https://github.com/OCA/vertical-hotel)), built on Avunu's
[repair](https://github.com/Avunu/repair-addons),
[fleet](https://github.com/Avunu/fleet-addons),
[EDI](https://github.com/Avunu/edi-addons) and
[Shopfloor](https://github.com/Avunu/shopfloor-app-addons) addons and on OCA modules.

## Modules

### Inspections and estimates

A repair order's inspections feed both the customer's report and the estimate.

| Module                                                | What it does                                                                                                                                                                                                                                                | Licence           |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| [`shop_inspection`](shop_inspection.md)               | Digital vehicle inspections (DVI) on repair orders, built on OCA `fleet_vehicle_inspection`: severity grades, condition and recommended-action catalogues, measurements with out-of-spec flags, grading inline in the checklist, and four seeded checklists | AGPL-3.0-or-later |
| [`shop_inspection_report`](shop_inspection_report.md) | The customer's inspection report: one PDF per repair order covering all of the visit's inspections, with measurements and photos, sent by email and shown on the customer portal                                                                            | AGPL-3.0-or-later |
| [`shop_estimate`](shop_estimate.md)                   | Turns inspection findings into a quotation of canned service jobs: must-do jobs become order lines and the rest optional products the customer can accept on the portal; approved jobs add their parts and labour to the repair order                       | AGPL-3.0-or-later |

### Scheduling and service workflow

| Module                                                          | What it does                                                                                                                                                                                                                                                                           | Licence           |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| [`shop_scheduling`](shop_scheduling.md)                         | Books repair orders into OCA `resource_booking` appointments: a slot is offered when any qualified technician is free, the job goes to one of them, and the appointment and the repair order's date, duration and technician stay in sync                                              | AGPL-3.0-or-later |
| [`repair_service_workflow`](repair_service_workflow.md)         | Customer acceptance and estimated/actual time for each service on the repair order's Services tab, with review wizards at Confirm Repair and End Repair; unaccepted services are archived, not billed, once a quotation is created                                                     | AGPL-3.0-or-later |
| `repair_service_productivity`                                   | Computes the Timesheets app's Billable Time and Non-billable Time for repair work: each technician gets their share of a service's invoiced time once the repair order has been invoiced, and clocked attendance beyond that is non-billable; adds an Estimated vs Actual Time measure | AGPL-3.0-or-later |
| [`repair_purchase_order_match`](repair_purchase_order_match.md) | Links a purchase order imported from an emailed or EDI document to its repair order: automatically when its PO number is a repair order number, otherwise through a TypeSafe AI suggestion that a user confirms from the chatter. Both steps are also available as `muk_mcp` tools     | AGPL-3.0-or-later |

### Technician app

`shopfloor_repair` holds the REST services and `shopfloor_repair_mobile` the app, so the
API stays usable without the frontend.

| Module                                                  | What it does                                                                                                                                                                                                                                | Licence           |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| [`shopfloor_repair`](shopfloor_repair.md)               | REST services for the technician app, as an OCA Shopfloor scenario: assigned jobs, a work timer, parts consumption, a parts catalogue and digital vehicle inspections                                                                       | AGPL-3.0-or-later |
| [`shopfloor_repair_mobile`](shopfloor_repair_mobile.md) | The iPad-first technician app on OCA `shopfloor_mobile_base`, served at `/shopfloor/app/repair_shop`, with camera scanning and photo capture; each technician has their own API key and signs in with Google or Apple rather than typing it | AGPL-3.0-or-later |

### Fleet app and demo data

| Module                      | What it does                                                                                                                                                                                                                                                                                          | Licence           |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| `fleet_vehicle_simplify`    | Strips the Fleet app down to what a repair shop needs: no tax fields, driver assignment or lease workflow, fewer menus (its inspection menus included), the VIN under the vehicle's title, decoded VIN data correctable by hand, and a default search that also matches VIN, owner and decoded fields | AGPL-3.0-or-later |
| [`shop_demo`](shop_demo.md) | Seeds USA Demo Company with a worked repair-shop scenario (customers, vehicles whose synthetic VINs decode on NHTSA vPIC, parts, canned jobs, technicians, and repair orders at every stage) by driving the real workflow; uninstalling removes it                                                    | AGPL-3.0-or-later |

## Branches

`develop` is the default branch and where pull requests go. Its code targets Odoo 18.0,
the series in `.odoo-series`. `18.0` follows `develop` automatically (a workflow
fast-forwards it after every push) and is the branch to install or pin. When a newer
Odoo series is maintained, it gets its own branch (`19.0`, …) and changes flow up from
`develop`.

## Install

Requires Odoo 18.0 and a PostgreSQL database. Pick the module or modules you want; each
pulls in the modules it depends on (see below), and those must be on your `addons_path`
first. Here that includes other Avunu repositories as well as OCA ones.

With a plain Odoo checkout, clone this repository on its `18.0` branch and add it to the
addons path:

```sh
git clone --branch 18.0 https://github.com/Avunu/vertical-auto-repair-addons.git
odoo-bin --addons-path=odoo/addons,/path/to/vertical-auto-repair-addons,<your other addons paths> \
  -d <database> -i <module> --stop-after-init
```

With [odoo-nix](https://github.com/Avunu/odoo-nix), add the repository from the dev
shell. `odoo module add` accepts an `owner/repo` and a branch, adds it as a submodule,
and the addons path is regenerated from the folders present (run `direnv reload`
afterwards):

```sh
odoo module add Avunu/vertical-auto-repair-addons 18.0
```

Add the repositories listed under Dependencies the same way.

Some modules need setting up after install: appointment types and bookable technicians
for `shop_scheduling`, a TypeSafe API key for `repair_purchase_order_match`, and
technician groups, API keys and a server restart for the technician app. Their READMEs
give the steps.

## Dependencies

Each module's `__manifest__.py` is the source of truth. Besides Odoo core modules
(`repair`, `fleet`, `hr_fleet`, `portal`, `sale_management`, `sale_timesheet`,
`hr_timesheet`, `hr_attendance`, `purchase_stock`), the modules depend on the following.
Use the 18.0 branch of each repository listed and clone the ones your chosen modules
need; each Avunu repository's README lists what its own modules need in turn.

| Module                        | Needs from OCA or others                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Python packages |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `shop_inspection`             | `fleet_vehicle_inspection` and `fleet_vehicle_inspection_template` ([OCA/fleet](https://github.com/OCA/fleet)), `repair_fleet_vehicle` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons))                                                                                                                                                                                                                                                                                                                             | none            |
| `shop_inspection_report`      | `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | none            |
| `shop_estimate`               | `repair_service_so_sync` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                                                                                                      | none            |
| `shop_scheduling`             | `repair_service` and `repair_scheduled_date_calendar_view` ([OCA/repair](https://github.com/OCA/repair)), `resource_booking` ([OCA/calendar](https://github.com/OCA/calendar)), `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                | none            |
| `repair_service_workflow`     | `repair_service_so_sync`, `repair_timesheet_time_control` and `repair_purchase_order_parts` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_scheduling` (this repository)                                                                                                                                                                                                                                                                                                                                   | none            |
| `repair_service_productivity` | `hr_timesheet_sheet` ([OCA/timesheet](https://github.com/OCA/timesheet)), `repair_service_workflow` (this repository)                                                                                                                                                                                                                                                                                                                                                                                                              | none            |
| `repair_purchase_order_match` | `edi_purchase_oca` ([OCA/edi-framework](https://github.com/OCA/edi-framework)), `queue_job` ([OCA/queue](https://github.com/OCA/queue)), `muk_mcp` ([muk-it/odoo-modules](https://github.com/muk-it/odoo-modules)), `repair_purchase_order_parts` and `repair_fleet_vehicle` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `edi_purchase_order_import` ([Avunu/edi-addons](https://github.com/Avunu/edi-addons))                                                                                                | `typesafe_sdk`  |
| `shopfloor_repair`            | `shopfloor_base` ([OCA/shopfloor-app](https://github.com/OCA/shopfloor-app)), `base_rest` ([OCA/rest-framework](https://github.com/OCA/rest-framework)), `jsonifier` ([OCA/server-tools](https://github.com/OCA/server-tools)), `repair_timesheet` ([OCA/repair](https://github.com/OCA/repair)), `repair_timesheet_time_control`, `repair_fleet_vehicle` and `repair_stage` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `repair_service_workflow`, `shop_inspection` and `shop_scheduling` (this repository) | none            |
| `shopfloor_repair_mobile`     | `shopfloor_mobile_base` and `shopfloor_mobile_base_auth_api_key` ([OCA/shopfloor-app](https://github.com/OCA/shopfloor-app)), `shopfloor_mobile_base_auth_oauth` and `shopfloor_mobile_camera_scan` ([Avunu/shopfloor-app-addons](https://github.com/Avunu/shopfloor-app-addons)), `shopfloor_repair` (this repository)                                                                                                                                                                                                            | none            |
| `fleet_vehicle_simplify`      | `shop_vehicle_vin` ([Avunu/fleet-addons](https://github.com/Avunu/fleet-addons)), `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                                                                                                              | none            |
| `shop_demo`                   | `l10n_us_gaap` ([OCA/l10n-usa](https://github.com/OCA/l10n-usa)), `repair_fleet_vehicle`, `repair_order_template_service`, `repair_service_so_sync` and `repair_timesheet_time_control` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_vehicle_catalog` and `shop_vehicle_vin` ([Avunu/fleet-addons](https://github.com/Avunu/fleet-addons)), `shop_inspection`, `shop_inspection_report`, `shop_estimate` and `shop_scheduling` (this repository)                                                         | none            |

`shop_demo` seeds a company named USA Demo Company, which `l10n_us_gaap`'s demo data
creates, and stops with an error if there is none: install it into a database with demo
data.

`shop_inspection` and OCA `repair_quality_control`
([OCA/repair](https://github.com/OCA/repair)) both define `repair.order.inspection_ids`,
for different models; `shop_demo`'s README describes how cancelling a repair order fails
when both are installed.

`shopfloor_repair_mobile` has no build step: its Vue components are plain ES modules.
The npm setup in its `static/` directory is a development check only, and production
needs no Node; see its README.

## Development

The repository carries its own development environment, built by
[odoo-nix](https://github.com/Avunu/odoo-nix) in addons mode. OCB and the repositories
these modules depend on are flake inputs pinned in `flake.lock`, and the Python
environment is locked in `nix/`. You need Nix with flakes, and optionally direnv.

```sh
git clone https://github.com/Avunu/vertical-auto-repair-addons.git && cd vertical-auto-repair-addons
direnv allow                  # or: nix develop --no-pure-eval
devenv up                     # PostgreSQL, Odoo and Mailpit
odoo db provision             # a database with every module here installed
odoo test fleet_vehicle_simplify
```

After `nix flake update`, or when a module gains a `depends` or a Python requirement,
run `odoo project relock` and commit `flake.lock` and `nix/`. A new dependency on
another repository also needs its input and an `externalSources` entry in `flake.nix`.
See odoo-nix's
[A repository of addons](https://github.com/Avunu/odoo-nix/blob/main/docs/scaffolding/addons-repository.md).

## Tests

Odoo runs a module's tests when you install or update it with `--test-enable`. Select a
module's tests with a `--test-tags` filter and use a throwaway database:

```sh
odoo-bin -c odoo.conf -d <testdb> -i <module> \
  --test-enable --test-tags /<module> --stop-after-init
```

Notes:

- `shopfloor_repair`'s README adds `--http-port 8098 --gevent-port 8097` to the command,
  which keeps the test run clear of a server on the default ports. Its test products use
  `SFR-TEST-*` barcodes, because `product.barcode` is unique across the database.
- `repair_purchase_order_match` needs `typesafe_sdk` installed even to run its tests;
  they replace the TypeSafe client with a mock, so no API key is needed.
- `shop_demo`, `fleet_vehicle_simplify`, `repair_service_productivity` and
  `shopfloor_repair_mobile` have no automated tests. `shopfloor_repair_mobile`'s README
  describes a development check instead: `npm install && npm run typecheck` in its
  `static/` directory type-checks the app's JSDoc types and compiles every component
  template with the Vue version the browser runs.

## Licence

Every module is licensed under the
[GNU Affero General Public License v3.0 or later](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/LICENSE).
The licence of each module is also stated in its `__manifest__.py` (`AGPL-3`, Odoo's
identifier for version 3) and in its source file headers. No module vendors third-party
code.

## Provenance

These modules were first developed in a private Avunu project, as part of Avunu's client
work, and imported here.
