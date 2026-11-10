# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shop Scheduling",
    "summary": "Book repair orders into technician appointment slots drawn "
    "from the whole shop's availability",
    "version": "18.0.1.1.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "depends": [
        "shop_inspection",
        "repair_service",
        "repair_scheduled_date_calendar_view",
        "resource_booking",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/resource_booking_type_views.xml",
        "views/resource_booking_views.xml",
        "views/repair_order_views.xml",
        "views/calendar_event_views.xml",
        "wizards/shop_appointment_wizard_views.xml",
        "report/shop_schedule_report.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "shop_scheduling/static/src/views/repair_calendar/*",
        ],
    },
    "installable": True,
}
