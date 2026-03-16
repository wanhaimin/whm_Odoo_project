/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onWillStart, useEffect, useState } from "@odoo/owl";

const specOptionsCache = new Map();

export class DiecutSpecValueField extends Component {
    static template = "diecut.SpecValueField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            choices: [],
        });

        onWillStart(async () => {
            await this._ensureChoicesLoaded();
        });

        useEffect(
            () => {
                this._ensureChoicesLoaded();
            },
            () => [this.isSelectionType, this.specDefId]
        );
    }

    get isSelectionType() {
        return this.props.record.data.value_type === "selection";
    }

    get specDefId() {
        const raw = this.props.record.data.param_id;
        if (!raw) {
            return null;
        }
        if (typeof raw === "number") {
            return raw;
        }
        if (Array.isArray(raw)) {
            return raw[0] || null;
        }
        if (typeof raw === "object" && "id" in raw) {
            return raw.id || null;
        }
        return null;
    }

    get value() {
        const raw = this.props.record.data[this.props.name];
        return raw || "";
    }

    async _ensureChoicesLoaded() {
        if (!this.isSelectionType) {
            this.state.choices = [];
            return;
        }
        const specDefId = this.specDefId;
        if (!specDefId) {
            this.state.choices = [];
            return;
        }
        if (specOptionsCache.has(specDefId)) {
            this.state.choices = specOptionsCache.get(specDefId);
            return;
        }
        const rows = await this.orm.read(
            "diecut.catalog.param",
            [specDefId],
            ["selection_options"]
        );
        const optionsText = rows?.[0]?.selection_options || "";
        const values = this._parseSelectionOptions(optionsText);
        const choices = values.map((value) => ({ value, label: value }));
        specOptionsCache.set(specDefId, choices);
        this.state.choices = choices;
    }

    _parseSelectionOptions(optionsText) {
        const text = (optionsText || "").replace(/\r/g, "\n").replace(/,/g, "\n");
        const dedup = new Set();
        for (const part of text.split("\n")) {
            const value = (part || "").trim();
            if (value) {
                dedup.add(value);
            }
        }
        return [...dedup];
    }

    onInput(ev) {
        this.props.record.update({ [this.props.name]: ev.target.value || false });
    }

    onSelect(ev) {
        const value = ev.target.value;
        this.props.record.update({ [this.props.name]: value || false });
    }
}

export const diecutSpecValueField = {
    component: DiecutSpecValueField,
    displayName: _t("Spec Value"),
    supportedTypes: ["char", "text"],
    extractProps: ({ placeholder }) => ({
        placeholder,
    }),
};

registry.category("fields").add("diecut_spec_value_widget", diecutSpecValueField);
