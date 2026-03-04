/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { View } from "@web/views/view";
import { useState, onMounted, onWillUnmount } from "@odoo/owl";

const SPLIT_STORAGE_PREFIX = "diecut_split_layout";

export class DiecutSplitListController extends ListController {
    static template = "diecut.SplitListView";

    setup() {
        super.setup();
        const persisted = this._loadLayoutPreference();
        this.splitState = useState({
            layoutMode: this._normalizeLayoutMode(persisted.layoutMode),
            splitRatio: persisted.splitRatio || 45,
        });
    }

    setSplitLayoutMode(mode) {
        this.splitState.layoutMode = this._normalizeLayoutMode(mode);
        this._saveLayoutPreference();
    }

    onSplitRatioChanged(ratio) {
        this.splitState.splitRatio = ratio;
        this._saveLayoutPreference();
    }

    _saveLayoutPreference() {
        const payload = {
            layoutMode: this.splitState.layoutMode,
            splitRatio: this.splitState.splitRatio,
        };
        window.localStorage.setItem(this._storageKey, JSON.stringify(payload));
    }

    _loadLayoutPreference() {
        const raw = window.localStorage.getItem(this._storageKey);
        if (!raw) {
            return {};
        }
        try {
            const parsed = JSON.parse(raw);
            return {
                layoutMode: parsed.layoutMode,
                splitRatio: Number(parsed.splitRatio) || 45,
            };
        } catch {
            return {};
        }
    }

    _normalizeLayoutMode(mode) {
        if (mode === "list") {
            return "list";
        }
        if (mode === "horizontal") {
            return "horizontal";
        }
        return "vertical";
    }

    get _storageKey() {
        const explicitKey = this.props.context?.split_storage_key;
        if (explicitKey) {
            return `${SPLIT_STORAGE_PREFIX}:${explicitKey}`;
        }
        const actionId = this.env.config?.actionId;
        if (actionId) {
            return `${SPLIT_STORAGE_PREFIX}:action:${actionId}`;
        }
        const model = this.props.resModel || "unknown";
        return `${SPLIT_STORAGE_PREFIX}:model:${model}:variant`;
    }
}

export class DiecutSplitListRenderer extends ListRenderer {
    static template = "diecut.SplitListRenderer";
    static props = [...ListRenderer.props, "splitLayoutMode", "splitRatio", "onSplitRatioChanged"];
    static components = {
        ...ListRenderer.components,
        View,
    };

    setup() {
        super.setup();
        this.state = useState({
            viewportWidth: window.innerWidth,
            resizing: false,
            selectedResId: null,
        });
        this._liveSplitRatio = this.props.splitRatio || 45;
        this._rafResizeTick = null;
        this._lastPointerEvent = null;

        onMounted(() => {
            this._onWindowResize = this.onWindowResize.bind(this);
            this._onPointerMove = this.onPointerMove.bind(this);
            this._onPointerUp = this.stopResize.bind(this);
            window.addEventListener("resize", this._onWindowResize);
            window.addEventListener("mousemove", this._onPointerMove);
            window.addEventListener("mouseup", this._onPointerUp);
            this._setSplitCssVar(this.props.splitRatio || 45);
        });

        onWillUnmount(() => {
            window.removeEventListener("resize", this._onWindowResize);
            window.removeEventListener("mousemove", this._onPointerMove);
            window.removeEventListener("mouseup", this._onPointerUp);
            if (this._rafResizeTick) {
                window.cancelAnimationFrame(this._rafResizeTick);
                this._rafResizeTick = null;
            }
        });
    }

    get isVertical() {
        if (this.isListMode) {
            return true;
        }
        return this.props.splitLayoutMode !== "horizontal";
    }

    get splitLayoutStyle() {
        if (this.isListMode) {
            return "";
        }
        if (this.isVertical) {
            return `--diecut-split-left: ${this.props.splitRatio}%;`;
        }
        return `--diecut-split-top: ${this.props.splitRatio}%;`;
    }

    get isListMode() {
        return this.props.splitLayoutMode === "list";
    }

    get splitRecords() {
        return this._collectRecords(this.props.list);
    }

    get selectedRecord() {
        if (!this.state.selectedResId) {
            return null;
        }
        const selected = this.splitRecords.find((record) => this._getRecordResId(record) === this.state.selectedResId);
        return selected || null;
    }

    get effectiveSelectedResId() {
        return this.selectedRecord ? this._getRecordResId(this.selectedRecord) : null;
    }

    getRowClass(record) {
        const className = super.getRowClass(record);
        const recordResId = this._getRecordResId(record);
        if (recordResId && recordResId === this.effectiveSelectedResId) {
            return `${className} o_diecut_split_row_active`;
        }
        return className;
    }

    async onCellClicked(record, column, ev, newWindow) {
        if (ev.target.special_click) {
            return;
        }
        if (newWindow || ev.ctrlKey || ev.metaKey || ev.shiftKey) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        if (this.props.list.selection.length || this.props.list.model.multiEdit || this.isInlineEditable(record)) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        this.state.selectedResId = this._getRecordResId(record);
    }

    startResize(ev) {
        ev.preventDefault();
        this.state.resizing = true;
    }

    onPointerMove(ev) {
        if (!this.state.resizing || !this.rootRef?.el || this.isListMode) {
            return;
        }
        this._lastPointerEvent = ev;
        if (this._rafResizeTick) {
            return;
        }
        this._rafResizeTick = window.requestAnimationFrame(() => {
            this._rafResizeTick = null;
            const pointerEv = this._lastPointerEvent;
            if (!pointerEv || !this.rootRef?.el) {
                return;
            }
            const rect = this.rootRef.el.getBoundingClientRect();
            if (!rect.width || !rect.height) {
                return;
            }
            let ratio;
            if (this.isVertical) {
                ratio = ((pointerEv.clientX - rect.left) / rect.width) * 100;
            } else {
                ratio = ((pointerEv.clientY - rect.top) / rect.height) * 100;
            }
            const clamped = Math.max(30, Math.min(68, ratio));
            this._liveSplitRatio = clamped;
            this._setSplitCssVar(clamped);
        });
    }

    stopResize() {
        if (!this.state.resizing || this.isListMode) {
            return;
        }
        if (this._rafResizeTick) {
            window.cancelAnimationFrame(this._rafResizeTick);
            this._rafResizeTick = null;
        }
        this.props.onSplitRatioChanged(this._liveSplitRatio);
        this.state.resizing = false;
        this._setSplitCssVar(this._liveSplitRatio);
    }

    onWindowResize() {
        this.state.viewportWidth = window.innerWidth;
        if (!this.isListMode) {
            this._setSplitCssVar(this.props.splitRatio || 45);
        }
    }

    get formViewProps() {
        const resId = this.effectiveSelectedResId;
        if (!resId) {
            return null;
        }
        const formViewId = this.splitFormViewId;
        return {
            type: "form",
            resModel: this.props.list.resModel || this.props.resModel,
            resId,
            viewId: formViewId,
            views: [[formViewId || false, "form"]],
            context: {
                ...(this.props.context || this.props.list.context || {}),
                edit: true,
                create: false,
                form_view_initial_mode: "edit",
                form_view_ref: "diecut.view_material_catalog_variant_split_form",
            },
            display: { controlPanel: {} },
            className: "o_diecut_split_embedded_form",
            readonly: false,
            preventEdit: false,
            preventCreate: true,
            onSave: this.onFormSaved.bind(this),
        };
    }

    get splitFormViewId() {
        const fromContext = this.props.context?.split_form_view_id || this.props.list.context?.split_form_view_id;
        if (!fromContext) {
            return false;
        }
        const viewId = Number(fromContext);
        return Number.isFinite(viewId) ? viewId : false;
    }

    async onFormSaved(record) {
        this.state.selectedResId = record.resId;
        await this.props.list.model.root.load();
    }

    _collectRecords(list) {
        if (!list) {
            return [];
        }
        if (list.isGrouped) {
            return list.groups.flatMap((group) => this._collectRecords(group.list));
        }
        return list.records || [];
    }

    _getRecordResId(record) {
        return record?.resId || record?.id || null;
    }

    _setSplitCssVar(ratio) {
        if (!this.rootRef?.el) {
            return;
        }
        if (this.isListMode) {
            this.rootRef.el.style.removeProperty("--diecut-split-left");
            this.rootRef.el.style.removeProperty("--diecut-split-top");
            return;
        }
        if (this.isVertical) {
            this.rootRef.el.style.setProperty("--diecut-split-left", `${ratio}%`);
            this.rootRef.el.style.removeProperty("--diecut-split-top");
        } else {
            this.rootRef.el.style.setProperty("--diecut-split-top", `${ratio}%`);
            this.rootRef.el.style.removeProperty("--diecut-split-left");
        }
    }

}

export const diecutSplitListView = {
    ...listView,
    Controller: DiecutSplitListController,
    Renderer: DiecutSplitListRenderer,
};

registry.category("views").add("diecut_split_list", diecutSplitListView);
