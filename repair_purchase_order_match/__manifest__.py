# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Repair Purchase Order Match",
    "summary": "Link an EDI/email-imported purchase order to its repair "
    "order automatically when its PO number is a repair order number, "
    "otherwise ask TypeSafe for the likeliest open repair order and let a "
    "user confirm it from the chatter; either way a user can pick a "
    "different repair order from a link in the chatter.",
    "version": "18.0.3.0.0",
    "category": "Inventory/Repair",
    "author": "Avunu LLC",
    "website": "https://avu.nu",
    "license": "AGPL-3",
    "installable": True,
    "external_dependencies": {
        "python": ["typesafe_sdk"],
    },
    "depends": [
        # purchase.order._prepare_repair_move_vals, the actual linking logic
        "repair_purchase_order_parts",
        # purchase.order._edi_confirm_and_notify (our trigger point) and
        # _edi_notify_partners (who gets notified of a suggested match)
        "edi_purchase_order_import",
        # purchase.order.exchange_record_ids - the original email, linked
        # from the suggestion
        "edi_purchase_oca",
        # repair.order.vehicle_id / customer_concern - the match criteria
        "repair_fleet_vehicle",
        # muk_mcp.mixin / @mcp_tool
        "muk_mcp",
        # with_delay()
        "queue_job",
    ],
    "data": [
        "views/repair_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
}
