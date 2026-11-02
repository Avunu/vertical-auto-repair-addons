# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shop Demo Data",
    "summary": "Seeds USA Demo Company with a worked repair-shop scenario: "
    "customers, vehicles, parts, canned jobs, and repair orders at every "
    "stage of the job lifecycle.",
    # 1.1.0 logs the seeded hours against the repair order itself and points
    # the repair timer at the Shop Labor project.
    "version": "18.0.1.1.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://avu.nu",
    "license": "AGPL-3",
    "installable": True,
    # Everything created gets an XML ID, so uninstalling this module removes
    # the demo scenario and leaves the real configuration alone.
    "depends": [
        "repair_fleet_vehicle",
        "repair_order_template_service",
        "repair_service_so_sync",
        "shop_inspection",
        "shop_inspection_report",
        "shop_estimate",
        "shop_scheduling",
        "shop_vehicle_catalog",
        "shop_vehicle_vin",
        "hr_timesheet",
        # Carries account.analytic.line.repair_order_id and the company-level
        # labor project the seeded timesheets and the timer both need.
        "repair_timesheet_time_control",
        "purchase_stock",
    ],
    "data": [
        "data/ir_actions_server.xml",
    ],
    "post_init_hook": "post_init_hook",
}
