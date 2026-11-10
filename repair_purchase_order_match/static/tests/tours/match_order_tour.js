/* Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html). */
import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("repair_match_order_tour", {
    steps: () => [
        {
            content: "Open the Match Order dialog from the repair order header",
            trigger:
                ".o_form_view .o_statusbar_buttons button[name='action_match_order']",
            run: "click",
        },
        {
            content: "The card lists the purchase order's parts",
            trigger:
                ".modal .o_kanban_record:contains('Tour Vendor'):contains('TOUR-PART-1')",
        },
        {
            content: "Match the purchase order",
            trigger:
                ".modal .o_kanban_record:contains('Tour Vendor') button[name='action_match_to_repair']",
            run: "click",
        },
        {
            content: "The dialog is gone and the repair order was reloaded",
            trigger:
                "body:not(:has(.modal)) .o-mail-Message:contains('Linked to purchase order')",
        },
        {
            content: "Open the Parts tab",
            trigger: ".o_form_view .o_notebook .nav-link:contains('Parts')",
            run: "click",
        },
        {
            content: "The part is on the repair order",
            trigger:
                ".o_form_view .o_field_widget[name='move_ids']:contains('Tour Part')",
        },
    ],
});

registry.category("web_tour.tours").add("repair_match_repair_tour", {
    steps: () => [
        {
            content: "Open the Match Repair dialog from the purchase order header",
            trigger:
                ".o_form_view .o_statusbar_buttons button[name='action_match_repair']",
            run: "click",
        },
        {
            content: "Pick the repair order",
            trigger:
                ".modal .o_list_view .o_data_row .o_data_cell:contains('Tour Customer')",
            run: "click",
        },
        {
            content: "The dialog is gone and the purchase order was reloaded",
            trigger:
                "body:not(:has(.modal)) .o-mail-Message:contains('Linked to repair order')",
        },
    ],
});
