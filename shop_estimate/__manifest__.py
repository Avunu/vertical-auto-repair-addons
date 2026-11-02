# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shop Estimate Builder",
    "summary": "Turn inspection findings into a quote with customer-selectable "
    "jobs; approved jobs populate the repair order",
    "version": "18.0.1.0.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "depends": [
        "shop_inspection",
        "sale_management",
        "repair_service_so_sync",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/shop_service_job_views.xml",
        "wizards/shop_estimate_builder_views.xml",
        "views/repair_order_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
}
