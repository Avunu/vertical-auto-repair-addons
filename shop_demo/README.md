# Shop Demo Data

Seeds **USA Demo Company** with a worked repair-shop scenario — enough realistic data to
click through the whole job lifecycle from intake to invoice without typing anything
first.

## What you get

|                         |                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| 12 customers            | 8 retail, 4 commercial (landscaping, freight, plumbing, city parks)                           |
| 21 vehicles             | Synthetic VINs with valid check digits that decode on NHTSA vPIC — light-duty through Class 8 |
| 30 parts                | Costed, with vendors and lead times; some on the shelf, some deliberately not                 |
| 7 labor products        | Auto, heavy truck, diagnostic, sublet, shop supplies, disposal                                |
| 15 canned jobs          | Wired to inspection recommended actions, so findings price themselves                         |
| 3 technicians + advisor | Bookable resources with combinations, across 4 appointment types                              |
| 18 repair orders        | Spread across every stage of the lifecycle                                                    |

The 18 jobs sit where a real shop's work sits on a Tuesday morning:

- **6 finished and invoiced** over the past seven weeks (5 paid, 1 still open)
- **2 in the bay** with hours logged against Shop Labor
- **1 approved, waiting on a special-order axle**
- **4 quoted**, estimates sent, waiting on the customer
- **5 written up and booked** on the schedule for the next few days

## Design notes

**Python, not XML data files.** Nearly everything that makes the scenario useful is
_state_ — orders that were confirmed, quotes that were accepted, invoices posted and
paid, appointments relative to today. A static record cannot express any of it, so the
seeder drives the real buttons: `action_create_sale_order`, `action_confirm`,
`action_repair_start`, `_create_invoices`, `action_create_payments`. What lands in the
database is therefore internally consistent — stock moves exist, odometer history is
written, chatter reads the way it would after a real job.

**Everything gets an XML ID.** `_make()` registers each record under `shop_demo.<key>`,
which buys two things: re-running the seed is a no-op instead of a second copy, and
uninstalling the module removes the whole scenario. Records that already existed are
_adopted_ rather than duplicated (`_find_or_make`), so seeding a half-configured company
does not leave two "Diagnostic Fee" products behind.

**One scenario failing never costs the others.** Each job is built inside its own
savepoint; a failure logs which scenario and why, and the seed carries on.

**Appointments use real openings.** Slots come from OCA's own `_get_available_slots`
rather than a hard-coded clock time — a booking outside every technician's working
calendar is rejected, and a fixed hour would break the moment the shop's hours or the
run date changed. Finished jobs get no appointment: the API only searches forward, and
last month's work on the schedule board would be noise.

**Parts carry `repair_line_type='add'`.** That flag is what makes a move billable —
`stock.move` only raises a sale order line for moves of that type — and it drives the
source and destination locations too.

**Unstocked parts are on MTO + Buy**, so a job needing an alternator raises a per-job
RFQ. That is the "parts order themselves" behaviour, and it needs the MTO route
un-archived (the seeder does that).

## Running it

The seed runs once on install:

```sh
python odoo/odoo-bin -c odoo.conf -d <db> -i shop_demo --stop-after-init
```

To top it up after deleting things by hand, run **Settings ▸ Technical ▸ Server Actions
▸ "Shop Demo: seed / top up demo data"**, or:

```python
env["shop.demo.seed"].seed()
```

To remove the whole scenario, uninstall the module.

The scenario is defined in [models/demo_data.py](models/demo_data.py) — plain tables, no
Odoo API — and loaded by [models/shop_demo_seed.py](models/shop_demo_seed.py). Add a
customer, a part or a whole job by editing the tables.

## Known gaps

- **The "customer declined" path is not seeded**, because it does not work.
  `repair.order.action_repair_cancel` is overridden by OCA `repair_quality_control`,
  which reads `inspection_ids` expecting `qc.inspection` records — but `shop_inspection`
  redefines that same field as `fleet.vehicle.inspection` and wins the override.
  Cancelling any repair order raises `AttributeError` (the method does not exist on the
  model, so even an empty recordset fails), and any _draft_ DVI attached to the job is
  unlinked on the way past. The `intl_declined` scenario is parked at "quoted" with a
  note; the seeder already supports the `declined` stage, so flip it back once the field
  collision is resolved.
- **One booking may land unscheduled** if no opening exists in the two-week window after
  its target date. That is a real state (requested, not yet placed), not a failure.
