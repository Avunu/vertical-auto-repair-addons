// Copyright 2026 Avunu LLC (avu.nu)
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import {KanbanController} from "@web/views/kanban/kanban_controller";
import {KanbanRecord} from "@web/views/kanban/kanban_record";
import {KanbanRenderer} from "@web/views/kanban/kanban_renderer";
import {kanbanView} from "@web/views/kanban/kanban_view";
import {registry} from "@web/core/registry";

/**
 * The Match Order dialog of a repair order: one purchase order card per row,
 * a click selects a card (one at a time), and the dialog footer's Match
 * button matches the selected purchase order to the repair order, which is
 * `repair_id` in the context (`purchase.order.action_match_to_repair`).
 */
export class RepairMatchKanbanRecord extends KanbanRecord {
    getRecordClasses() {
        const classes = `${super.getRecordClasses()} cursor-pointer`;
        return this.props.record.selected
            ? `${classes} o_repair_match_selected`
            : classes;
    }
}

export class RepairMatchKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: RepairMatchKanbanRecord,
    };
}

export class RepairMatchKanbanController extends KanbanController {
    get selectedRecord() {
        return this.model.root.records.find((record) => record.selected);
    }

    /** A click on a card selects it instead of opening the purchase order. */
    async openRecord(record) {
        for (const other of this.model.root.records) {
            if (other !== record && other.selected) {
                other.toggleSelection(false);
            }
        }
        await record.toggleSelection(true);
    }

    async onMatchClicked() {
        const record = this.selectedRecord;
        if (!record || this.matching) {
            return;
        }
        this.matching = true;
        try {
            await this.actionService.doActionButton({
                type: "object",
                name: "action_match_to_repair",
                resModel: record.resModel,
                resId: record.resId,
                resIds: [record.resId],
                context: record.context,
            });
        } finally {
            this.matching = false;
        }
    }

    onDiscardClicked() {
        this.env.dialogData?.close();
    }
}

export const repairMatchKanbanView = {
    ...kanbanView,
    Controller: RepairMatchKanbanController,
    Renderer: RepairMatchKanbanRenderer,
    buttonTemplate: "repair_purchase_order_match.RepairMatchKanban.Buttons",
};

registry.category("views").add("repair_match_kanban", repairMatchKanbanView);
