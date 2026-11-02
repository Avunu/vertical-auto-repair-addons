// Copyright 2026 Avunu LLC (avu.nu)
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

/**
 * A service can have an active shop-floor timer running against it while
 * the office unchecks its Accepted box on the repair order. Confirming per
 * checkbox click doesn't work reliably here: list_renderer.js's single-click
 * "toggle this boolean cell" shortcut (`onCellClicked`) only fires for a
 * field left on the default "boolean" widget, so a custom widget swapped in
 * to intercept the click just silently opts the field out of that shortcut
 * instead of ever getting a chance to confirm anything. Save time (and,
 * separately, End Repair time below) is the one place that reliably runs
 * regardless of how the checkbox got toggled.
 *
 * `has_running_timer` is re-read from the server at the moment of each
 * check rather than trusted from whatever was loaded when the form was
 * opened, or kept "fresh" via a background poll: a technician can start or
 * stop a shop-floor timer at any moment while this form sits open, and a
 * stale client-side value was producing confirmations for timers that had
 * already been stopped. A poll would only narrow that window; reading at
 * the instant of the actual check removes it entirely, for less code and
 * no background timer to manage/leak. The field isn't shown anywhere on
 * this form, so there's no other reason to keep it live in between.
 */
patch(FormController.prototype, {
    async onWillSaveRecord(record, changes) {
        if (
            this.props.resModel === "repair.order" &&
            !(await this._repairServiceWorkflowConfirmUnacceptedRunningTimers(record))
        ) {
            return false;
        }
        return super.onWillSaveRecord(record, changes);
    },

    async _repairServiceWorkflowConfirmUnacceptedRunningTimers(record) {
        const services = record.data.repair_service_ids;
        if (!services) {
            return true;
        }
        const candidates = services.records.filter((line) => line.dirty && !line.data.accepted);
        const flagged = await this._repairServiceWorkflowFilterRunning(candidates);
        return this._repairServiceWorkflowConfirmRunningTimers(
            flagged,
            _t("Timer Running on an Unaccepted Service"),
            "A technician currently has a timer running in the shop floor app on: %(names)s. Saving will NOT stop that timer, and the technician will not be notified. Save anyway?"
        );
    },

    // "End Repair" is a `type="object"` button (`action_repair_end`), not a
    // plain save - it has its own gate here rather than relying on
    // `onWillSaveRecord` (which only fires for the auto-save this button
    // would otherwise trigger, and only checks *unaccepted* lines). Any
    // service still showing a running timer, accepted or not, is worth
    // flagging before the job gets marked done - not just ones the office
    // just unchecked in this edit session.
    async beforeExecuteActionButton(clickParams) {
        if (
            this.props.resModel === "repair.order" &&
            clickParams.name === "action_repair_end" &&
            !(await this._repairServiceWorkflowConfirmRunningTimersBeforeEnd())
        ) {
            return false;
        }
        return super.beforeExecuteActionButton(clickParams);
    },

    async _repairServiceWorkflowConfirmRunningTimersBeforeEnd() {
        const services = this.model.root.data.repair_service_ids;
        if (!services) {
            return true;
        }
        const flagged = await this._repairServiceWorkflowFilterRunning(services.records);
        return this._repairServiceWorkflowConfirmRunningTimers(
            flagged,
            _t("Timer Running"),
            "A technician currently has a timer running in the shop floor app on: %(names)s. Ending the repair will NOT stop that timer, and the technician will not be notified. Continue anyway?"
        );
    },

    /** Re-check `has_running_timer` against the server for these lines, right now. */
    async _repairServiceWorkflowFilterRunning(candidates) {
        const saved = candidates.filter((line) => line.resId);
        if (!saved.length) {
            return [];
        }
        const fresh = await this.orm.read(
            "repair.service",
            saved.map((line) => line.resId),
            ["has_running_timer"]
        );
        const runningIds = new Set(
            fresh.filter((rec) => rec.has_running_timer).map((rec) => rec.id)
        );
        return saved.filter((line) => runningIds.has(line.resId));
    },

    _repairServiceWorkflowConfirmRunningTimers(flagged, title, bodyTemplate) {
        if (!flagged.length) {
            return true;
        }
        const names = flagged
            .map((line) => line.data.display_name)
            .filter(Boolean)
            .join(", ");
        return new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                title,
                body: _t(bodyTemplate, { names }),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
    },
});
