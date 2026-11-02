# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shopfloor Repair Technician",
    "summary": "REST services for the technician-facing repair shop app: "
    "assigned jobs, work timer, parts consumption and vehicle inspections",
    "version": "18.0.1.0.9",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://avu.nu",
    "license": "AGPL-3",
    # This module carries no frontend. The Vue app lives in
    # shopfloor_repair_mobile, which is also where the shopfloor.app record
    # and its API key group are defined (they need the api_key auth type that
    # shopfloor_mobile_base_auth_api_key adds).
    "depends": [
        "shopfloor_base",
        "jsonifier",
        "base_rest",
        "repair",
        # account.analytic.line.repair_order_id -- the back-link the timer needs
        "repair_timesheet",
        # company default timesheet project + the time control mixin on repair
        "repair_timesheet_time_control",
        # repair.service.accepted/estimated_time/actual_time and
        # account.analytic.line.repair_service_id -- what the per-service
        # timer endpoints and the Services screen read and write
        "repair_service_workflow",
        # severity grading, measurements, repair.order.inspection_ids
        "shop_inspection",
        # vehicle_id / odometer_in / customer_concern on repair.order
        "repair_fleet_vehicle",
        # employee.attendance_state / .last_check_in for the shift timer
        "hr_attendance",
        # repair.order.stage_id -- shown on the job card next to the status
        "repair_stage",
        # repair.order.booking_type_user_ids -- techs who share a job through
        # its appointment type
        "shop_scheduling",
    ],
    "data": [
        "security/shopfloor_repair_security.xml",
        "security/ir.model.access.csv",
        "views/res_users.xml",
        "data/mail_message_subtype.xml",
        "data/shopfloor_scenario.xml",
        "data/shopfloor_profile.xml",
        "data/shopfloor_menu.xml",
    ],
    "installable": True,
}
