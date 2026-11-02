// Copyright 2026 Avunu LLC (avu.nu)
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * Same list as usual, except the `open_form_view` cell always calls
 * `onOpenFormView` -- core refuses to for a record that has no id yet.
 */
export class DialogEditListRenderer extends ListRenderer {
    static recordRowTemplate = "shop_inspection.DialogEditListRenderer.RecordRow";
}

export class DialogEditX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: DialogEditListRenderer,
    };

    /**
     * Core saves the parent record and pushes a full page form. Open the row
     * in the regular x2many dialog instead: nothing has to be saved first, so
     * a line that only lives in memory can be opened too, and the technician
     * comes back to the list where they left it.
     *
     * @override
     */
    async switchToForm(record) {
        const list = this.list;
        const editedRecord = list.editedRecord;
        if (editedRecord) {
            // Push what is being typed in the row into the record before the
            // dialog reads it, and wait for any onchange it triggered.
            const proms = [];
            list.model.bus.trigger("NEED_LOCAL_CHANGES", { proms });
            await Promise.all([...proms, editedRecord._updatePromise]);
            // canAbandon: a row added and opened right away must survive.
            await list.leaveEditMode({ canAbandon: false });
        }
        return this._openRecord({
            record,
            context: this.props.context,
            mode: this.props.readonly ? "readonly" : "edit",
        });
    }
}

export const dialogEditX2ManyField = {
    ...x2ManyField,
    component: DialogEditX2ManyField,
    displayName: _t("Relational table (row opens a dialog)"),
};

registry.category("fields").add("x2many_dialog_edit", dialogEditX2ManyField);
