# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Shopfloor Repair Technician (Mobile)",
    "summary": "iPad-first technician app for the repair shop: assigned jobs, "
    "work timer, parts consumption and digital vehicle inspections",
    "version": "18.0.1.0.28",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://github.com/Avunu/vertical-auto-repair-addons",
    "license": "AGPL-3",
    "depends": [
        "shopfloor_repair",
        "shopfloor_mobile_base",
        # The only auth flavour migrated to 18.0. Each technician needs their
        # OWN api key in the group below: auth.api.key.user_id is the identity
        # every request runs as, so a shared key would collapse every
        # technician into one and make "my jobs" and every timesheet wrong.
        "shopfloor_mobile_base_auth_api_key",
        # Lets technicians sign in with their own Google/Apple account
        # instead of typing that key by hand - see data/shopfloor_app.xml,
        # which is what this app's Auth Type actually defaults to.
        "shopfloor_mobile_base_auth_oauth",
        # Camera barcode scanning. It overrides the *global* searchbar
        # component, so every state of this scenario gets a camera button
        # without a line of code here.
        "shopfloor_mobile_camera_scan",
    ],
    "data": [
        "data/auth_api_key_group.xml",
        "data/shopfloor_app.xml",
        "templates/assets.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
