/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";

const RETIRED_GROUP_FIELDS = new Set([
    "brand_platform_id",
    "scene_ids",
    "substrate_tag_ids",
    "structure_tag_ids",
    "environment_tag_ids",
    "process_tag_ids",
]);

patch(SearchBarMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.fields = (this.fields || []).filter((field) => !RETIRED_GROUP_FIELDS.has(field.name));
    },

    validateField(fieldName, field) {
        if (RETIRED_GROUP_FIELDS.has(fieldName)) {
            return false;
        }
        return super.validateField(fieldName, field);
    },
});
