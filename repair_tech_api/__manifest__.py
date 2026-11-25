# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Repair Technician API",
    "summary": "Typed call_kw/JSON-2 facades (Pydantic) for the shop's "
    "frontends, TypeScript generated from them, PWA plumbing, and the job "
    "board's data",
    "version": "18.0.1.1.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "depends": [
        # repair.order.technician_id (and, through repair_fleet_vehicle,
        # vehicle_id): a board card's column and vehicle
        "shop_inspection",
        # repair.order.booking_type_id: the type marks the job board's cards
        "shop_scheduling",
        # repair.order.stage: the board's status lives on the stage
        "repair_stage",
    ],
    "external_dependencies": {"python": ["pydantic"]},
    "data": [
        "data/repair_order_stage_data.xml",
        "views/repair_order_stage_views.xml",
        "views/resource_booking_type_views.xml",
        "views/pwa_templates.xml",
    ],
    "installable": True,
}
