# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shop Inspection Report",
    "summary": "Customer-facing digital vehicle inspection report: "
    "branded PDF, email and portal page",
    "version": "18.0.1.0.1",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://avu.nu",
    "license": "AGPL-3",
    "depends": [
        "shop_inspection",
        "portal",
    ],
    "data": [
        "security/shop_inspection_report_security.xml",
        "report/shop_inspection_report_templates.xml",
        "report/shop_inspection_report_actions.xml",
        "data/mail_template_data.xml",
        "views/repair_order_views.xml",
        "views/portal_templates.xml",
    ],
    "installable": True,
}
