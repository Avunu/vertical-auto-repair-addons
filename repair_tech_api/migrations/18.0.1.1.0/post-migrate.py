# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The job board's icon now comes from the appointment type instead of the
vehicle's model category. Give the shop's two types their icon, so the
board looks the same after the upgrade. Types are matched by name; any
other database is left alone, to be set up under Appointment Types."""

from odoo import SUPERUSER_ID, api

BOARD_TYPES = {
    "Truck Repair": ("truck", "Heavy truck"),
    "Auto Repair": ("car", "Car"),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Type = env["resource.booking.type"].with_context(active_test=False)
    for name, (icon, label) in BOARD_TYPES.items():
        Type.search([("name", "=", name), ("board_icon", "=", False)]).write(
            {"board_icon": icon, "board_label": label}
        )
