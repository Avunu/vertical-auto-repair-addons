# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Demo data for trying the technician app: a technician (login and
password "tina"), three confirmed jobs with services and parts, and a
checklist to inspect with. For a throwaway database only::

    odoo shell -c odoo.conf -d repair_tech_demo \
        < modules/vertical-auto-repair-addons/repair_tech_app/tools/seed_demo.py

Then sign in as tina and open /repair-tech/app/.
"""

# ruff: noqa: F821  (`env` comes from odoo shell)
from odoo import fields

env = env(context=dict(env.context, tracking_disable=True))
company = env.company
tech = env["res.users"].search([("login", "=", "tina")]) or env[
    "res.users"
].with_context(no_reset_password=True).create(
    {
        "name": "Tina Technician",
        "login": "tina",
        "password": "tina",
        "groups_id": [
            (
                6,
                0,
                [
                    env.ref(x).id
                    for x in (
                        "base.group_user",
                        "repair_tech_app.group_shop_technician",
                    )
                ],
            )
        ],
    }
)
if not tech.employee_id:
    env["hr.employee"].create({"name": tech.name, "user_id": tech.id})
company.repair_timesheet_project_id = env["project.project"].create(
    {"name": "Shop Labor", "allow_timesheets": True}
)


def product(name, kind="consu", code=None):
    vals = {"name": name, "type": kind, "default_code": code}
    if kind == "consu":
        vals["is_storable"] = True
    return env["product.product"].create(vals)


def vehicle(brand, model, plate, vin, year, color):
    b = env["fleet.vehicle.model.brand"].search([("name", "=", brand)], limit=1) or env[
        "fleet.vehicle.model.brand"
    ].create({"name": brand})
    m = env["fleet.vehicle.model"].create({"name": model, "brand_id": b.id})
    return env["fleet.vehicle"].create(
        {
            "model_id": m.id,
            "license_plate": plate,
            "vin_sn": vin,
            "model_year": year,
            "color": color,
        }
    )


pads, rotor, filt, oil = (
    product("Brake Pad Set", code="BP-100"),
    product("Brake Rotor", code="BR-220"),
    product("Oil Filter", code="OF-200"),
    product("5W-30 Oil (qt)", code="OIL-530"),
)
brake_job, diag, oil_change = (
    product("Front Brake Service", "service"),
    product("Diagnostics", "service"),
    product("Oil Change", "service"),
)

jobs = [
    (
        "Silver",
        "Toyota",
        "Corolla Matrix",
        "MXW4783",
        "2T1KR32E05C123456",
        "2005",
        "Grinding noise from the front when braking.\nWorse in the morning.",
        "1",
        [(brake_job, 1.5), (diag, 0.5)],
        [(pads, 1), (rotor, 2)],
    ),
    (
        "Blue",
        "Ford",
        "F-150",
        "TRK-0042",
        "1FTFW1ET5DFC10312",
        "2019",
        "Due for oil change. Check engine light came on yesterday.",
        "0",
        [(oil_change, 0.5), (diag, 0.5)],
        [(filt, 1), (oil, 6)],
    ),
    (
        "Red",
        "Honda",
        "Civic",
        "CVC-9001",
        "2HGFC2F59KH512345",
        "2019",
        "Customer reports a rattle over bumps.",
        "0",
        [(diag, 1.0)],
        [],
    ),
]
for color, brand, model, plate, vin, year, concern, prio, services, parts in jobs:
    partner = env["res.partner"].create({"name": f"{plate} Owner"})
    v = vehicle(brand, model, plate, vin, year, color)
    ro = env["repair.order"].create(
        {
            "partner_id": partner.id,
            "vehicle_id": v.id,
            "technician_id": tech.id,
            "customer_concern": concern.replace("\n", "<br/>"),
            "priority": prio,
            "schedule_date": fields.Datetime.now(),
        }
    )
    for p, qty in parts:
        env["stock.move"].create(
            {
                "repair_id": ro.id,
                "repair_line_type": "add",
                "product_id": p.id,
                "product_uom_qty": qty,
                "product_uom": p.uom_id.id,
            }
        )
    for p, est in services:
        env["repair.service"].create(
            {
                "repair_id": ro.id,
                "product_id": p.id,
                "accepted": True,
                "estimated_time": est,
            }
        )
    ro._action_repair_confirm()
# A checklist to start an inspection from.
Item = env["fleet.vehicle.inspection.item"]
brakes = env["shop.inspection.category"].create({"name": "Brakes", "sequence": 10})
tires = env["shop.inspection.category"].create({"name": "Tires", "sequence": 20})
worn = env["shop.inspection.condition"].create({"name": "Worn"})
replace = env["shop.inspection.action"].create({"name": "Replace"})
items = [
    Item.create(
        {
            "name": "Front brake pads",
            "category_id": brakes.id,
            "condition_ids": [(4, worn.id)],
            "recommended_action_ids": [(4, replace.id)],
            "measurement_spec_ids": [
                (0, 0, {"name": "Pad", "position": pos, "uom": "mm", "spec_min": 3})
                for pos in ("lf", "rf")
            ],
        }
    ),
    Item.create({"name": "Rear brake pads", "category_id": brakes.id}),
    Item.create(
        {
            "name": "Tread depth",
            "category_id": tires.id,
            "measurement_spec_ids": [
                (0, 0, {"name": "Tread", "position": pos, "uom": "in32", "spec_min": 4})
                for pos in ("lf", "rf", "lr", "rr")
            ],
        }
    ),
]
env["fleet.vehicle.inspection.template"].create(
    {
        "name": "Courtesy Check",
        "inspection_template_line_ids": [
            (0, 0, {"inspection_template_item_id": item.id, "sequence": n})
            for n, item in enumerate(items)
        ],
    }
)
env.cr.commit()
print("seeded", env["repair.order"].search_count([]), "repairs")  # pylint: disable=print-used
