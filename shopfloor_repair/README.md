# Shopfloor Repair Technician (REST services)

The technician-facing half of the repair shop, exposed as an OCA **shopfloor-app**
scenario: assigned jobs, a work timer, parts consumption, a parts catalog, and digital
vehicle inspections.

This module carries **no frontend**. The Vue app, the `shopfloor.app` record and its API
key group live in [`shopfloor_repair_mobile`](../shopfloor_repair_mobile/). Keeping them
apart means the REST API stays usable headlessly — by the tests, by a future native
client, or by anything else that speaks HTTP.

## One scenario, one hub

`repair_job` is a single scenario covering the whole job. Shopfloor navigates menu →
scenario → service, so four menu items (jobs / time / parts / inspections) would force
the technician to re-select the job for every action. Instead there is one menu item and
the `job_detail` state is a hub they come back to.

```
init ──► job_list ──scan or tap──► job_detail ◄──── (every sub-flow returns here)
                                      │
        ┌──────────────┬──────────────┼──────────────┬──────────────────┐
        ▼              ▼              ▼              ▼                  ▼
  (timer inline)  start/finish     parts      catalog_search    inspection_list
                                      │              │                  │
                                      ▼              ▼                  ▼
                                part_detail ◄─ catalog_detail    inspection_lines
                                                                        │
                                                                        ▼
                                                             inspection_line_detail
```

## Endpoints

```
GET  /jobs                                   list my assigned jobs
GET  /scan/<identifier>                      work order no., quote no., plate or VIN
GET  /job/<id>                               the job hub
POST /job/<id>/start_repair                  → Under Repair
POST /job/<id>/finish                        → Repaired (option-gated)
POST /job/<id>/timer_start | /timer_stop     work timer

GET  /job/<id>/parts                         planned parts + what was used
POST /job/<id>/scan_part                     {barcode}
POST /part/<move_id>/set_quantity            {quantity, lot_id? | lot_name?}
POST /part/<move_id>/consume_all | /reset

GET  /catalog/categories
GET  /job/<id>/catalog                       {search?, category_id?, page?}
POST /job/<id>/add_part                      {product_id, quantity, consume_now?}

GET  /job/<id>/inspections
POST /job/<id>/inspection_create             {template_id, odometer}
GET  /inspection/<id>                        the checklist
GET  /inspection_line/<id>                   one item, with its grading choices
POST /inspection_line/<id>/grade             {severity, condition_ids?, action_ids?, note?}
POST /inspection_line/<id>/photo             {image_b64, filename?}
POST /measurement/<id>/set_value             {value}
POST /inspection/<id>/confirm
```

Scenario options (JSON on `shopfloor.scenario`, editable in the backend):

| option                  | default | effect                                              |
| ----------------------- | ------- | --------------------------------------------------- |
| `allow_repair_end`      | `true`  | technician may close the job                        |
| `show_unassigned`       | `true`  | unassigned jobs appear in every list                |
| `include_responsible`   | `false` | also list jobs where the tech is core "Responsible" |
| `catalog_page_size`     | `30`    | rows per catalog page                               |
| `require_photo_on_fail` | `false` | block a problem grade until a photo exists          |

## Load-bearing mechanics

Things that will bite whoever touches this next.

**Consumed quantity goes in `stock.move.quantity`, never `product_uom_qty`.** Core
`repair/models/stock_move.py` calls `_update_repair_sale_order_line()` whenever demand
changes on a move with a `sale_line_id` — that rewrites the customer's approved quote.
Recording usage writes `quantity` + `picked` only.

**A technician adding a catalog part does reach the customer's quote — on purpose.**
Core creates the `sale.order.line` from inside `stock.move.create`; we do not suppress
it. Instead the move is stamped `shopfloor_added_uid` and a note is logged on the repair
order, so the service advisor sees the delta against what the customer approved and
decides what to bill. Because a technician has stock rights but not sales rights, that
core create would raise AccessError — `stock_move._create_repair_sale_order_line` is
overridden to elevate **only** moves this app stamped.

**The chatter note uses `_message_log`, not `message_post`.** The latter resolves an
author email address and raises "please configure the sender's email address" when it
cannot, so a technician whose user record has no email could not add a part at all.

**One running timer at a time; starting a second stops the first.**
`account.analytic.line._running_domain()` is user-global (start time set, duration still
zero). Starting a timer on job B while job A runs would leave two running lines and the
OCA time control, which counts them, would then render neither Start nor Stop.
`service_timer_start` therefore stops the running timer and starts the new one at a
single shared moment, the next whole second (`stop_dt` context). Whole, because
`button_end_work()` otherwise stops at `datetime.now()` with microseconds while the new
line starts without them, so the two would overlap by a fraction of a second and the
no-overlap constraint would reject the start. The _next_ second, so a timer started a
moment ago still stops with a non-zero duration (zero marks it as running). Note
`button_start_work()` is unusable from REST — it returns an `ir.actions.act_window` for
a wizard; `button_end_work()` is headless-safe.

**A timesheet needs a project and an employee.** hr_timesheet silently drops analytic
lines with no project, so `timer_start` checks `company_id.repair_timesheet_project_id`
and `env.user.employee_id` up front and returns a real message instead of a traceback.

**Creating an inspection needs a non-zero odometer.**
`fleet.vehicle.inspection._inverse_odometer` raises on a falsy value. The odometer is
collected on the inspection list screen before the record exists.

**`button_confirm` refuses while any line is `todo`.** `severity = 'na'` maps to
`success` — that is the deliberate "skip" grade. The service reports how many items are
left rather than letting OCA's wall of text through.

**Inspections need their own group and their own record rule.**
`fleet_vehicle_inspection` grants create/write to Fleet _Manager_ only, and
`fleet_rule_inspection_visibility_user` restricts Officers to inspections of vehicles
**they personally drive** — never true of customer vehicles, so a technician would
create an inspection successfully and then watch it vanish from
`repair.order.inspection_ids`. `group_shop_technician` carries both the ACLs and a
permissive rule. Record rules are OR'ed only across groups the user actually holds, so a
group with no rule cannot widen anything: the rule has to be attached explicitly. (This
is the same trap `repair_fleet_vehicle` already had to undo one model up, for
`fleet.vehicle` itself.)

## Setup

1. Give each technician the **Shop Floor Technician** group, plus
   `stock.group_stock_user`, `hr_timesheet.group_hr_timesheet_user`,
   `fleet.fleet_group_user` and `shopfloor_base.group_shopfloor_user`.
2. Each technician needs an `hr.employee` linked to their user.
3. Set **Repair Labor Project** on the company (Settings → Repair).
4. Install `shopfloor_repair_mobile` and follow its README for API keys.

## Tests

```sh
python odoo/odoo-bin -c odoo.conf -d <testdb> -u shopfloor_repair \
  --test-enable --test-tags /shopfloor_repair \
  --http-port 8098 --gevent-port 8097 --stop-after-init
```

66 tests covering the job list and scanning, the timer (including switching from one to
another), parts consumption, the catalog and its billing side effects, and the whole
inspection flow. Test product barcodes are namespaced `SFR-TEST-*` because
`product.barcode` is unique database-wide and would otherwise collide with real data.
