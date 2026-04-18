/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";

const INLINE_QUOTE_BUTTONS = new Set([
    "action_check_all_lines",
    "action_uncheck_all_lines",
    "action_copy_checked_lines",
    "action_delete_checked_lines",
    "action_sync_slitting_width",
    "action_sync_pitch",
    "action_sync_cavity",
    "action_sync_yield_rate",
]);

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        const record = this.model.root;
        const isInlineQuoteButton =
            record?.resModel === "diecut.quote" &&
            clickParams?.type === "object" &&
            INLINE_QUOTE_BUTTONS.has(clickParams.name);

        if (!isInlineQuoteButton) {
            return super.beforeExecuteActionButton(...arguments);
        }

        const saved = await record.save({ reload: false });
        if (saved === false) {
            return false;
        }
        if (this.props.onSave) {
            this.props.onSave(record, clickParams);
        }

        await this.orm.call(record.resModel, clickParams.name, [[record.resId]]);
        await this.model.load({
            resId: record.resId,
            resIds: record.resIds,
        });

        return false;
    },
});
