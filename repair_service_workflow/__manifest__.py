# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Repair Service Workflow",
    "summary": "Service acceptance, estimated/actual time, and Confirm/Finalize "
    "wizards for repair orders",
    "version": "18.0.1.0.1",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://avu.nu",
    "license": "AGPL-3",
    "depends": [
        "repair_service_so_sync",
        "repair_timesheet_time_control",
        "repair_purchase_order_parts",
        "shop_scheduling",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/repair_service_views.xml",
        "report/report_repair_order.xml",
        "wizards/repair_service_confirm_wizard_views.xml",
        "wizards/repair_service_finalize_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "repair_service_workflow/static/src/views/repair_order_form_controller_patch.js",
        ],
    },
    "installable": True,
}
