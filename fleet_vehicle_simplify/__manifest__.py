# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Fleet Vehicle Simplify",
    "summary": "Strip the Fleet app down to what an auto repair shop needs: no "
    "European tax/fiscality fields, no employee driver assignment, no "
    "lease-vehicle workflow.",
    "version": "18.0.1.0.1",
    "category": "Human Resources/Fleet",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "installable": True,
    "depends": [
        "fleet",
        "shop_vehicle_vin",
        "hr_fleet",
        # Transitively pulls in fleet_vehicle_inspection,
        # fleet_vehicle_inspection_template, and repair_fleet_vehicle, whose
        # menus/buttons this module also hides.
        "shop_inspection",
    ],
    "data": [
        "views/fleet_vehicle_views.xml",
        "data/fleet_menus.xml",
    ],
}
