# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shop Digital Vehicle Inspection",
    "summary": "Severity grades, condition/action catalogs and measurements "
    "on vehicle inspections, linked to repair orders",
    # 1.1.0 gives the seeded checklist lines their own XML IDs; see
    # migrations/18.0.1.1.0 for the cleanup of installs that drifted.
    # 1.2.0 moves line grading and measurement entry inline.
    # 1.3.0 opens the line form in a dialog instead of a full page.
    "version": "18.0.1.3.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "depends": [
        "fleet_vehicle_inspection",
        "fleet_vehicle_inspection_template",
        "repair_fleet_vehicle",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/shop_inspection_catalog_views.xml",
        "views/fleet_vehicle_inspection_item_views.xml",
        "views/fleet_vehicle_inspection_views.xml",
        "views/repair_order_views.xml",
        "data/shop_inspection_catalog_data.xml",
        "data/shop_inspection_item_data.xml",
        "data/shop_inspection_template_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "shop_inspection/static/src/dialog_edit_x2many/dialog_edit_x2many.js",
            "shop_inspection/static/src/dialog_edit_x2many/dialog_edit_x2many.xml",
        ],
    },
    "installable": True,
}
