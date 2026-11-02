# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Repair Service Productivity Reporting",
    "summary": "Attribute Services-tab Invoiced/Estimated/Actual time to "
    "employees in the Timesheets app's Billable Time report, and compare "
    "attendance against invoiced time",
    "version": "18.0.1.0.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://avu.nu",
    "license": "AGPL-3",
    "depends": [
        "repair_service_workflow",
        "sale_timesheet",
        "hr_attendance",
    ],
    "data": [
        "views/timesheets_analysis_views.xml",
    ],
    "installable": True,
}
