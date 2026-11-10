// Copyright 2026 Avunu LLC (avu.nu)
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import {CalendarCommonRenderer} from "@web/views/calendar/calendar_common/calendar_common_renderer";
import {CalendarController} from "@web/views/calendar/calendar_controller";
import {CalendarRenderer} from "@web/views/calendar/calendar_renderer";
import {_t} from "@web/core/l10n/translation";
import {browser} from "@web/core/browser/browser";
import {calendarView} from "@web/views/calendar/calendar_view";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

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

/**
 * Adds a Print button that opens the jobs on screen as a PDF in a new tab.
 * It sends the ids the calendar is drawing, so its search, sidebar filters,
 * scale and date all carry through without asking again. The browser's own
 * print of this page can only ever print the grid as drawn, app sidebar and
 * all.
 */
export class RepairCalendarController extends CalendarController {
    setup() {
        super.setup();
        this.notification = useService("notification");
    }

    /** The heading the calendar shows above the grid. */
    get printTitle() {
        switch (this.model.scale) {
            case "day":
                return this.dayHeader;
            case "week":
                return `${this.weekHeader} · ${_t("Week")} ${this.currentWeek}`;
            case "month":
                return this.currentMonth;
            default:
                return this.currentYear;
        }
    }

    onClickPrint() {
        const ids = Object.values(this.model.records).map(
            (record) => record.rawRecord.id
        );
        if (!ids.length) {
            this.notification.add(_t("Nothing on the calendar to print."), {
                type: "warning",
            });
            return;
        }
        // Opened by the browser's own PDF viewer: the report route serves the
        // file inline, where the report action would download it.
        const params = new URLSearchParams({
            title: this.printTitle,
            // The calendar draws in the browser's timezone, so the days on
            // paper have to be cut there too.
            context: JSON.stringify({
                tz: luxon.Settings.defaultZone.name,
                lang: user.context.lang,
            }),
        });
        browser.open(
            `/report/pdf/shop_scheduling.report_shop_schedule/${ids.join(",")}?${params}`,
            "_blank"
        );
    }
}

registry.category("views").add("repair_calendar", {
    ...calendarView,
    Controller: RepairCalendarController,
    Renderer: RepairCalendarRenderer,
    buttonTemplate: "shop_scheduling.RepairCalendarController.controlButtons",
});
