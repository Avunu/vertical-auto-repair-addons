// Copyright 2026 Avunu LLC (avu.nu)
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import { registry } from "@web/core/registry";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { calendarView } from "@web/views/calendar/calendar_view";

/**
 * The repair calendar draws each job as vehicle + customer instead of the
 * order reference, the way the shop floor app names a job. Only the event
 * template changes; colour and the sidebar filter come from the view arch.
 * Scoped to js_class="repair_calendar" so no other calendar is touched.
 */
export class RepairCalendarCommonRenderer extends CalendarCommonRenderer {
    static eventTemplate = "shop_scheduling.RepairCalendarEvent";
}

export class RepairCalendarRenderer extends CalendarRenderer {
    static components = {
        ...CalendarRenderer.components,
        day: RepairCalendarCommonRenderer,
        week: RepairCalendarCommonRenderer,
        month: RepairCalendarCommonRenderer,
    };
}

registry.category("views").add("repair_calendar", {
    ...calendarView,
    Renderer: RepairCalendarRenderer,
});
