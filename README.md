# Avunu auto repair vertical

Odoo 18.0 modules for automotive repair shops: digital vehicle inspections and the
customer's inspection report, estimates built from inspection findings, appointment
scheduling, the service workflow on the repair order, an iPad-first technician app, and
the shop's job board. They are built and maintained by [Avunu LLC](https://avunu.net)
and published for anyone to use. Together they form an industry vertical in the spirit
of OCA's `vertical-*` repositories (such as
[OCA/vertical-hotel](https://github.com/OCA/vertical-hotel)), built on Avunu's
[repair](https://github.com/Avunu/repair-addons),
[fleet](https://github.com/Avunu/fleet-addons), and
[EDI](https://github.com/Avunu/edi-addons) addons and on OCA modules.

## Modules

### Inspections and estimates

A repair order's inspections feed both the customer's report and the estimate.

| Module                                                       | What it does                                                                                                                                                                                                                                                | Licence           |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| [`shop_inspection`](shop_inspection/README.md)               | Digital vehicle inspections (DVI) on repair orders, built on OCA `fleet_vehicle_inspection`: severity grades, condition and recommended-action catalogues, measurements with out-of-spec flags, grading inline in the checklist, and four seeded checklists | AGPL-3.0-or-later |
| [`shop_inspection_report`](shop_inspection_report/README.md) | The customer's inspection report: one PDF per repair order covering all of the visit's inspections, with measurements and photos, sent by email and shown on the customer portal                                                                            | AGPL-3.0-or-later |
| [`shop_estimate`](shop_estimate/README.md)                   | Turns inspection findings into a quotation of canned service jobs: must-do jobs become order lines and the rest optional products the customer can accept on the portal; approved jobs add their parts and labour to the repair order                       | AGPL-3.0-or-later |

### Scheduling and service workflow

| Module                                                                 | What it does                                                                                                                                                                                                                                                                           | Licence           |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| [`shop_scheduling`](shop_scheduling/README.md)                         | Books repair orders into OCA `resource_booking` appointments: a slot is offered when any qualified technician is free, the job goes to one of them, and the appointment and the repair order's date, duration and technician stay in sync                                              | AGPL-3.0-or-later |
| [`repair_service_workflow`](repair_service_workflow/README.md)         | Customer acceptance and estimated/actual time for each service on the repair order's Services tab, with review wizards at Confirm Repair and End Repair; unaccepted services are archived, not billed, once a quotation is created                                                     | AGPL-3.0-or-later |
| `repair_service_productivity`                                          | Computes the Timesheets app's Billable Time and Non-billable Time for repair work: each technician gets their share of a service's invoiced time once the repair order has been invoiced, and clocked attendance beyond that is non-billable; adds an Estimated vs Actual Time measure | AGPL-3.0-or-later |
| [`repair_purchase_order_match`](repair_purchase_order_match/README.md) | Links a purchase order imported from an emailed or EDI document to its repair order: automatically when its PO number is a repair order number, otherwise through a TypeSafe AI suggestion that a user confirms from the chatter. Both steps are also available as `muk_mcp` tools     | AGPL-3.0-or-later |

### Technician app and job board

Installable web apps in React and TypeScript, over typed model methods ("facades") that
`repair_tech_api` defines and generates the TypeScript from.

| Module                                             | What it does                                                                                                                                                                                                                                                                                                                          | Licence           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| [`repair_tech_app`](repair_tech_app/README.md)     | The technician's iPad app at `/repair-tech/app/`: jobs, a work timer per service, parts and the parts catalogue, inspections with measurements and photos, timesheets and the time clock; camera and hardware scanning, opens offline. Replaces `shopfloor_repair` and `shopfloor_repair_mobile` and takes their data over on install | AGPL-3.0-or-later |
| [`repair_tech_board`](repair_tech_board/README.md) | The shop's TV board at `/repair-tech/board/`: open jobs as colour-coded cards, one column per technician                                                                                                                                                                                                                              | AGPL-3.0-or-later |
| [`repair_tech_api`](repair_tech_api/README.md)     | Typed facades (Pydantic) callable over call_kw and JSON-2, the TypeScript and client generated from them, the plumbing for installable apps, and the board's data                                                                                                                                                                     | AGPL-3.0-or-later |

### Fleet app and demo data

| Module                             | What it does                                                                                                                                                                                                                                                                                          | Licence           |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| `fleet_vehicle_simplify`           | Strips the Fleet app down to what a repair shop needs: no tax fields, driver assignment or lease workflow, fewer menus (its inspection menus included), the VIN under the vehicle's title, decoded VIN data correctable by hand, and a default search that also matches VIN, owner and decoded fields | AGPL-3.0-or-later |
| [`shop_demo`](shop_demo/README.md) | Seeds USA Demo Company with a worked repair-shop scenario (customers, vehicles whose synthetic VINs decode on NHTSA vPIC, parts, canned jobs, technicians, and repair orders at every stage) by driving the real workflow; uninstalling removes it                                                    | AGPL-3.0-or-later |

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
for `shop_scheduling`, a TypeSafe API key for `repair_purchase_order_match`, and the
Technician group, employees and a timesheet project for the technician app. Their
READMEs give the steps.

## Dependencies

Each module's `__manifest__.py` is the source of truth. Besides Odoo core modules
(`repair`, `fleet`, `hr_fleet`, `portal`, `sale_management`, `sale_timesheet`,
`hr_timesheet`, `hr_attendance`, `purchase_stock`), the modules depend on the following.
Use the 18.0 branch of each repository listed and clone the ones your chosen modules
need; each Avunu repository's README lists what its own modules need in turn.

| Module                        | Needs from OCA or others                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Python packages |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `shop_inspection`             | `fleet_vehicle_inspection` and `fleet_vehicle_inspection_template` ([OCA/fleet](https://github.com/OCA/fleet)), `repair_fleet_vehicle` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons))                                                                                                                                                                                                                                                                     | none            |
| `shop_inspection_report`      | `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                                                                                                                                        | none            |
| `shop_estimate`               | `repair_service_so_sync` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                                              | none            |
| `shop_scheduling`             | `repair_service` and `repair_scheduled_date_calendar_view` ([OCA/repair](https://github.com/OCA/repair)), `resource_booking` ([OCA/calendar](https://github.com/OCA/calendar)), `shop_inspection` (this repository)                                                                                                                                                                                                                                                        | none            |
| `repair_service_workflow`     | `repair_service_so_sync`, `repair_timesheet_time_control` and `repair_purchase_order_parts` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_scheduling` (this repository)                                                                                                                                                                                                                                                                           | none            |
| `repair_service_productivity` | `hr_timesheet_sheet` ([OCA/timesheet](https://github.com/OCA/timesheet)), `repair_service_workflow` (this repository)                                                                                                                                                                                                                                                                                                                                                      | none            |
| `repair_purchase_order_match` | `edi_purchase_oca` ([OCA/edi-framework](https://github.com/OCA/edi-framework)), `queue_job` ([OCA/queue](https://github.com/OCA/queue)), `muk_mcp` ([muk-it/odoo-modules](https://github.com/muk-it/odoo-modules)), `repair_purchase_order_parts` and `repair_fleet_vehicle` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `edi_purchase_order_import` ([Avunu/edi-addons](https://github.com/Avunu/edi-addons))                                        | `typesafe_sdk`  |
| `repair_tech_api`             | `repair_stage` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_inspection` and `shop_scheduling` (this repository)                                                                                                                                                                                                                                                                                                                                  | `pydantic`      |
| `repair_tech_board`           | `repair_tech_api` (this repository)                                                                                                                                                                                                                                                                                                                                                                                                                                        | none            |
| `repair_tech_app`             | `repair_timesheet_time_control` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `repair_tech_api`, `repair_service_workflow`, `shop_inspection` and `shop_scheduling` (this repository)                                                                                                                                                                                                                                                                   | `pydantic`      |
| `fleet_vehicle_simplify`      | `shop_vehicle_vin` ([Avunu/fleet-addons](https://github.com/Avunu/fleet-addons)), `shop_inspection` (this repository)                                                                                                                                                                                                                                                                                                                                                      | none            |
| `shop_demo`                   | `l10n_us_gaap` ([OCA/l10n-usa](https://github.com/OCA/l10n-usa)), `repair_fleet_vehicle`, `repair_order_template_service`, `repair_service_so_sync` and `repair_timesheet_time_control` ([Avunu/repair-addons](https://github.com/Avunu/repair-addons)), `shop_vehicle_catalog` and `shop_vehicle_vin` ([Avunu/fleet-addons](https://github.com/Avunu/fleet-addons)), `shop_inspection`, `shop_inspection_report`, `shop_estimate` and `shop_scheduling` (this repository) | none            |

`shop_demo` seeds a company named USA Demo Company, which `l10n_us_gaap`'s demo data
creates, and stops with an error if there is none: install it into a database with demo
data.

`shop_inspection` and OCA `repair_quality_control`
([OCA/repair](https://github.com/OCA/repair)) both define `repair.order.inspection_ids`,
for different models; `shop_demo`'s README describes how cancelling a repair order fails
when both are installed.

`repair_tech_app` and `repair_tech_board` are compiled frontends: each has a
`package.json` and a pnpm lockfile, and its `build` script writes `static/dist/`, which
is not committed. odoo-nix builds them into the deployed tree; elsewhere, run
`pnpm install && pnpm run build` in each before installing it.

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

- `repair_tech_app` and `repair_tech_board` have browser tests that run the built
  frontend in Chrome; they are skipped until it is built (`odoo module build`).
  `repair_tech_app`'s frontend also has its own unit tests: `pnpm test` in the addon.
  Its test products use `RTA-TEST-*` barcodes, because `product.barcode` is unique
  across the database.
- `repair_purchase_order_match` needs `typesafe_sdk` installed even to run its tests;
  they replace the TypeSafe client with a mock, so no API key is needed.
- `shop_demo`, `fleet_vehicle_simplify` and `repair_service_productivity` have no
  automated tests.

## Licence

Every module is licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE). The licence of each module
is also stated in its `__manifest__.py` (`AGPL-3`, Odoo's identifier for version 3) and
in its source file headers. No module vendors third-party code.

## Provenance

These modules were first developed in a private Avunu project, as part of Avunu's client
work, and imported here.
