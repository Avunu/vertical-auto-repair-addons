# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Repair Technician App",
    "summary": "The technician's iPad app: jobs, per-service work timers, parts "
    "and catalog, vehicle inspections with photos, timesheets and the time "
    "clock. React and TypeScript over typed facades; installable, works offline",
    "version": "18.0.1.0.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "depends": [
        # @facade, PwaApp and the generated client
        "repair_tech_api",
        # repair.service.accepted/estimated_time/actual_time and
        # account.analytic.line.repair_service_id: the per-service timers
        "repair_service_workflow",
        # the company's repair timesheet project and the time control
        "repair_timesheet_time_control",
        # inspections: severity, measurements, conditions, actions, photos;
        # repair.order.technician_id/service_advisor_id; through
        # repair_fleet_vehicle, the job's vehicle, odometer and concern
        "shop_inspection",
        # repair.order.booking_type_user_ids: technicians sharing a job by
        # its appointment type
        "shop_scheduling",
        # clocking in and out, and the day's clocked hours
        "hr_attendance",
    ],
    "external_dependencies": {"python": ["pydantic"]},
    "data": [
        "security/repair_tech_app_security.xml",
        "security/ir.model.access.csv",
        "data/mail_message_subtype.xml",
        "data/ir_config_parameter.xml",
        "views/res_config_settings_views.xml",
        "views/templates.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
}
